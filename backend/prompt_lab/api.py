from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path, PureWindowsPath

from fastapi import FastAPI, HTTPException

from prompt_lab import llm_client
from prompt_lab.config import PromptLabConfig
from prompt_lab.judge import build_judge_prompt
from prompt_lab.jobs import JobManager
from prompt_lab.models.artifacts import RunArtifact
from prompt_lab.models.judgments import FindingDecisionSet, JudgmentArtifact
from prompt_lab.pydantic_loader import load_model_entrypoint
from prompt_lab.runner import iter_case_major, run_structured_case, run_text_case
from prompt_lab.storage import PromptLabStore


def _validate_case_id_path_segment(case_id: str) -> None:
    windows_path = PureWindowsPath(case_id)
    if (
        not case_id
        or Path(case_id).is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or "/" in case_id
        or "\\" in case_id
        or case_id in {".", ".."}
    ):
        raise HTTPException(status_code=400, detail="Unsafe case id")


def _validate_run_batch_id_path_segment(run_batch_id: str) -> None:
    windows_path = PureWindowsPath(run_batch_id)
    if (
        not run_batch_id
        or Path(run_batch_id).is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or "/" in run_batch_id
        or "\\" in run_batch_id
        or run_batch_id in {".", ".."}
    ):
        raise HTTPException(status_code=400, detail="Unsafe run batch id")


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _render_judgment_markdown(judgment: JudgmentArtifact) -> str:
    lines = [
        f"# Judgment {judgment.judgment_id}",
        "",
        judgment.summary,
        "",
        "## What Looks Correct",
    ]
    for finding in judgment.what_looks_correct:
        lines.extend(
            [
                f"- {finding.finding_id}: {finding.description}",
                f"  Evidence: {'; '.join(finding.evidence)}",
            ]
        )
    lines.extend(["", "## Findings"])
    for finding in judgment.findings:
        lines.extend(
            [
                f"- {finding.finding_id} [{finding.severity}] {finding.area}/{finding.category}: {finding.description}",
                f"  Evidence: {'; '.join(finding.evidence)}",
                f"  Suggested change: {finding.suggested_change}",
            ]
        )
    lines.extend(["", "## Decision Points"])
    for decision in judgment.decision_points:
        lines.extend(
            [
                f"- {decision.decision_id}: {decision.description}",
                f"  Options: {'; '.join(decision.options)}",
                f"  Recommended: {decision.recommended_option}",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def create_app(config: PromptLabConfig | None = None) -> FastAPI:
    resolved_config = config or PromptLabConfig.from_env()
    store = PromptLabStore(
        experiments_root=resolved_config.experiments_root,
        examples_root=resolved_config.examples_root,
    )
    job_manager = JobManager()
    app = FastAPI(title="Prompt Lab")

    @app.get("/api/experiments")
    def list_experiments() -> list[dict[str, object]]:
        return [item.model_dump(mode="json") for item in store.list_experiments()]

    @app.post("/api/experiments/{experiment_id}/versions/{version}/runs")
    def run_experiment_version(experiment_id: str, version: str) -> dict[str, object]:
        experiment = store.load_experiment(experiment_id)
        cases = store.load_cases(experiment_id, version)
        if not cases:
            raise HTTPException(status_code=400, detail="Version has no cases")
        for case in cases:
            _validate_case_id_path_segment(case.id)
        repeat_count = experiment.run_defaults.repeat_count
        template_text = store.read_text(experiment_id, version, experiment.template.path)
        response_model = None
        if experiment.output.type == "pydantic":
            model_file = experiment.output.model_file
            model_entrypoint = experiment.output.model_entrypoint
            assert model_file is not None
            assert model_entrypoint is not None
            version_dir = store.version_dir(experiment_id, version)
            response_model = load_model_entrypoint(
                version_dir, model_file, model_entrypoint
            )
        job = job_manager.start_job(
            kind="run_version",
            experiment_id=experiment_id,
            version=version,
            total_units=len(cases) * repeat_count,
        )

        completed_units = 0
        try:
            for case, repeat_index in iter_case_major(cases, repeat_count=repeat_count):
                if experiment.output.type == "pydantic":
                    assert response_model is not None
                    run = run_structured_case(
                        version=version,
                        run_batch_id=job.job_id,
                        case=case,
                        repeat_index=repeat_index,
                        generator_model=experiment.models.generator_model,
                        template_text=template_text,
                        response_model=response_model,
                        generate_structured=llm_client.generate_structured,
                    )
                else:
                    run = run_text_case(
                        version=version,
                        run_batch_id=job.job_id,
                        case=case,
                        repeat_index=repeat_index,
                        generator_model=experiment.models.generator_model,
                        template_text=template_text,
                        generate_text=llm_client.generate_text,
                    )
                store.write_run_artifact(
                    experiment_id,
                    version,
                    f"runs/{job.job_id}/{case.id}/repeat-{repeat_index:03d}.json",
                    run.model_dump(mode="json"),
                )
                completed_units += 1
                job = job_manager.update(
                    job.job_id,
                    completed_units=completed_units,
                    message=f"Completed {case.id} repeat {repeat_index}",
                )

            job = job_manager.complete(job.job_id, message="Run completed")
        except Exception as exc:
            current_job = job_manager.get(job.job_id)
            if current_job.status not in {"completed", "failed"}:
                job_manager.fail(job.job_id, message=str(exc) or type(exc).__name__)
            raise
        return asdict(job)

    @app.post("/api/experiments/{experiment_id}/versions/{version}/judgments")
    def judge_experiment_version(
        experiment_id: str, version: str, run_batch_id: str | None = None
    ) -> dict[str, object]:
        experiment = store.load_experiment(experiment_id)
        version_dir = store.version_dir(experiment_id, version)
        runs_dir = version_dir / "runs"
        if run_batch_id is None:
            run_batch_dirs = (
                sorted(path for path in runs_dir.iterdir() if path.is_dir())
                if runs_dir.is_dir()
                else []
            )
            if not run_batch_dirs:
                raise HTTPException(status_code=400, detail="Version has no run batches")
            run_batch_dir = run_batch_dirs[-1]
            selected_run_batch_id = run_batch_dir.name
        else:
            _validate_run_batch_id_path_segment(run_batch_id)
            selected_run_batch_id = run_batch_id
            run_batch_dir = (runs_dir / run_batch_id).resolve()
            resolved_runs_dir = runs_dir.resolve()
            if (
                run_batch_dir == resolved_runs_dir
                or not run_batch_dir.is_relative_to(resolved_runs_dir)
                or not run_batch_dir.is_dir()
            ):
                raise HTTPException(status_code=404, detail="Run batch not found")

        experiment_dir = store.experiment_dir(experiment_id)
        rubric_path = experiment_dir / "rubric.md"
        rubric = (
            rubric_path.read_text(encoding="utf-8")
            if rubric_path.is_file()
            else ""
        )
        prompt_template = store.read_text(
            experiment_id, version, experiment.template.path
        )
        cases = store.load_cases(experiment_id, version)
        run_artifacts = [
            RunArtifact.model_validate(json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(run_batch_dir.glob("*/*.json"))
        ]
        if not run_artifacts:
            raise HTTPException(status_code=400, detail="Run batch has no artifacts")

        if experiment.output.type == "pydantic":
            model_file = experiment.output.model_file
            model_entrypoint = experiment.output.model_entrypoint
            assert model_file is not None
            assert model_entrypoint is not None
            model_source = store.read_text(experiment_id, version, model_file)
            output_declaration = (
                f"pydantic model: {model_entrypoint}\n"
                f"model file: {model_file}\n\n{model_source}"
            )
        else:
            output_declaration = "text output"

        judge_prompt = build_judge_prompt(
            experiment_id=experiment_id,
            version=version,
            output_declaration=output_declaration,
            rubric=rubric,
            prompt_template=prompt_template,
            cases=cases,
            run_artifacts=run_artifacts,
        )
        generated = llm_client.generate_structured(
            experiment.models.judge_model,
            judge_prompt,
            JudgmentArtifact,
            None,
        )
        output = generated.output
        judgment = (
            output
            if isinstance(output, JudgmentArtifact)
            else JudgmentArtifact.model_validate(output)
        )
        decisions = FindingDecisionSet.from_finding_ids(
            [finding.finding_id for finding in judgment.findings]
        )

        review_id = "review-001"
        review_dir = version_dir / "reviews" / review_id
        _write_json(review_dir / "judgment.json", judgment.model_dump(mode="json"))
        (review_dir / "judgment.md").write_text(
            _render_judgment_markdown(judgment), encoding="utf-8"
        )
        (review_dir / "rubric_snapshot.md").write_text(rubric, encoding="utf-8")
        _write_json(review_dir / "decisions.json", decisions.model_dump(mode="json"))
        return {
            "review_id": review_id,
            "run_batch_id": selected_run_batch_id,
            "judgment": judgment.model_dump(mode="json"),
        }

    return app
