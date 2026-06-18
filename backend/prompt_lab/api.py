from __future__ import annotations

import json
import logging
import re
import shutil
import time
from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path, PureWindowsPath

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from prompt_lab import llm_client
from prompt_lab.case_context import materialize_case_context
from prompt_lab.compare import build_comparison_prompt
from prompt_lab.config import PromptLabConfig
from prompt_lab.dry_run import (
    dry_comparison_response_json,
    dry_judgment_response_json,
    dry_proposal_response_json,
    dry_structured_response_json,
    dry_text_response,
)
from prompt_lab.experiment_seed import seed_experiments_from_examples
from prompt_lab.judge import build_judge_prompt
from prompt_lab.jobs import JobAlreadyRunningError, JobManager
from prompt_lab.models.artifacts import ExperimentArtifact, RunArtifact
from prompt_lab.models.judgments import (
    ComparisonArtifact,
    FindingDecisionSet,
    JudgmentArtifact,
)
from prompt_lab.proposal import ProposalDraft, ProposalSource, build_proposal_prompt
from prompt_lab.pydantic_loader import load_model_entrypoint
from prompt_lab.runner import iter_case_major, run_structured_case, run_text_case
from prompt_lab.storage import PromptLabStore
from prompt_lab.errors import NotFoundError


logger = logging.getLogger(__name__)


class HumanNotesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notes: str


class ComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline_version: str = Field(min_length=1)
    candidate_version: str = Field(min_length=1)
    dry_run: bool = False


class RunVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dry_run: bool = False


class DryRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dry_run: bool = False


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


def _validate_review_id_path_segment(review_id: str) -> None:
    windows_path = PureWindowsPath(review_id)
    if (
        not review_id
        or Path(review_id).is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or "/" in review_id
        or "\\" in review_id
        or review_id in {".", ".."}
    ):
        raise HTTPException(status_code=400, detail="Unsafe review id")


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_optional_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _error_detail_text(detail: object) -> str:
    return detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False)


def _validation_error_summary(error: ValidationError) -> str:
    messages = []
    for item in error.errors()[:5]:
        location = ".".join(str(part) for part in item.get("loc", ()))
        message = str(item.get("msg", "validation error"))
        messages.append(f"{location}: {message}" if location else message)
    remaining_count = len(error.errors()) - len(messages)
    if remaining_count > 0:
        messages.append(f"... and {remaining_count} more")
    return "; ".join(messages)


def _log_judge_rejection(
    *,
    experiment_id: str,
    version: str,
    selected_run_batch_id: str | None,
    run_batch_dir: Path | None,
    detail: object,
    exc_info: bool = False,
) -> None:
    logger.warning(
        "Judge request failed: experiment=%s version=%s run_batch=%s "
        "run_batch_dir=%s detail=%s",
        experiment_id,
        version,
        selected_run_batch_id or "<none>",
        str(run_batch_dir) if run_batch_dir is not None else "<none>",
        _error_detail_text(detail),
        exc_info=exc_info,
    )


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _markdown_text(value: str) -> str:
    return " ".join(value.split())


def _render_judgment_markdown(judgment: JudgmentArtifact) -> str:
    lines = [
        f"# Judgment {judgment.judgment_id}",
        "",
        _markdown_text(judgment.summary),
        "",
        "## What Looks Correct",
    ]
    for finding in judgment.what_looks_correct:
        evidence = "; ".join(_markdown_text(item) for item in finding.evidence)
        lines.extend(
            [
                (
                    f"- `{_markdown_text(finding.finding_id)}`: "
                    f"{_markdown_text(finding.description)}"
                ),
                f"  Evidence: {evidence}",
            ]
        )
    lines.extend(["", "## Findings"])
    for finding in judgment.findings:
        finding_header = (
            f"- `{_markdown_text(finding.finding_id)}` [{finding.severity}] "
            f"{_markdown_text(finding.area)}/{_markdown_text(finding.category)}: "
            f"{_markdown_text(finding.description)}"
        )
        evidence = "; ".join(_markdown_text(item) for item in finding.evidence)
        lines.extend(
            [
                finding_header,
                f"  Evidence: {evidence}",
                f"  Suggested change: {_markdown_text(finding.suggested_change)}",
            ]
        )
    lines.extend(["", "## Decision Points"])
    for decision in judgment.decision_points:
        options = "; ".join(_markdown_text(item) for item in decision.options)
        lines.extend(
            [
                (
                    f"- `{_markdown_text(decision.decision_id)}`: "
                    f"{_markdown_text(decision.description)}"
                ),
                f"  Options: {options}",
                f"  Recommended: {_markdown_text(decision.recommended_option)}",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _render_comparison_markdown(comparison: ComparisonArtifact) -> str:
    lines = [
        f"# Comparison {comparison.comparison_id}",
        "",
        f"Baseline: `{_markdown_text(comparison.baseline_version)}`",
        f"Candidate: `{_markdown_text(comparison.candidate_version)}`",
        f"Recommendation: `{comparison.recommendation}`",
        "",
        _markdown_text(comparison.summary),
    ]
    sections = [
        ("Improvements", comparison.improvements),
        ("Regressions", comparison.regressions),
        ("Unchanged Problems", comparison.unchanged_problems),
        ("New Problems", comparison.new_problems),
        ("Stability Changes", comparison.stability_changes),
    ]
    for title, items in sections:
        lines.extend(["", f"## {title}"])
        if items:
            lines.extend(f"- {_markdown_text(item)}" for item in items)
        else:
            lines.append("- None.")
    lines.extend(["", "## Decision Points"])
    if comparison.decision_points:
        for decision in comparison.decision_points:
            options = "; ".join(_markdown_text(item) for item in decision.options)
            lines.extend(
                [
                    (
                        f"- `{_markdown_text(decision.decision_id)}`: "
                        f"{_markdown_text(decision.description)}"
                    ),
                    f"  Options: {options}",
                    f"  Recommended: {_markdown_text(decision.recommended_option)}",
                ]
            )
    else:
        lines.append("- None.")
    return "\n".join(lines).rstrip() + "\n"


def _select_latest_run_batch_dir(runs_dir: Path) -> Path | None:
    run_batch_dirs = _run_batch_dirs_newest_first(runs_dir)
    if not run_batch_dirs:
        return None
    return run_batch_dirs[0]


def _run_batch_dirs_newest_first(runs_dir: Path) -> list[Path]:
    if not runs_dir.is_dir():
        return []
    run_batch_dirs = [path for path in runs_dir.iterdir() if path.is_dir()]
    return sorted(run_batch_dirs, key=lambda path: path.name, reverse=True)


def _load_run_artifacts_from_batch_dir(run_batch_dir: Path) -> list[RunArtifact]:
    return [
        RunArtifact.model_validate(json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(run_batch_dir.glob("*/*.json"))
    ]


def _validate_run_artifacts(
    *,
    run_artifacts: list[RunArtifact],
    selected_run_batch_id: str,
    version: str,
    case_ids: set[str],
    repeat_count: int,
) -> None:
    seen_pairs: set[tuple[str, int]] = set()
    for run in run_artifacts:
        if run.run_batch_id != selected_run_batch_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Run artifact {run.run_id} batch {run.run_batch_id} "
                    f"does not match selected batch {selected_run_batch_id}"
                ),
            )
        if run.version != version:
            raise HTTPException(
                status_code=400,
                detail=f"Run artifact {run.run_id} does not match version {version}",
            )
        if run.case_id not in case_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Run artifact {run.run_id} has unknown case_id {run.case_id}",
            )
        pair = (run.case_id, run.repeat_index)
        if pair in seen_pairs:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Duplicate run artifact for case {run.case_id} "
                    f"repeat {run.repeat_index}"
                ),
            )
        seen_pairs.add(pair)

    expected_pairs = {
        (case_id, repeat_index)
        for case_id in case_ids
        for repeat_index in range(1, repeat_count + 1)
    }
    unexpected_pairs = sorted(seen_pairs - expected_pairs)
    if unexpected_pairs:
        case_id, repeat_index = unexpected_pairs[0]
        raise HTTPException(
            status_code=400,
            detail=f"Unexpected run artifact for case {case_id} repeat {repeat_index}",
        )
    missing_pairs = sorted(expected_pairs - seen_pairs)
    if missing_pairs:
        missing = ", ".join(
            f"{case_id} repeat {repeat_index}"
            for case_id, repeat_index in missing_pairs
        )
        raise HTTPException(
            status_code=400,
            detail=f"Missing run artifacts for {missing}",
        )


def _validate_judgment_metadata(
    *,
    judgment: JudgmentArtifact,
    version: str,
    selected_run_batch_id: str,
    judge_model: str,
) -> None:
    if judgment.version != version:
        raise HTTPException(
            status_code=400,
            detail=f"Judgment version must be {version}",
        )
    if judgment.run_batch_ids != [selected_run_batch_id]:
        raise HTTPException(
            status_code=400,
            detail=f"Judgment run_batch_ids must be ['{selected_run_batch_id}']",
        )
    if judgment.judge_model != judge_model:
        raise HTTPException(
            status_code=400,
            detail=f"Judgment judge_model must be {judge_model}",
        )


def _validate_comparison_metadata(
    *,
    comparison: ComparisonArtifact,
    comparison_id: str,
    baseline_version: str,
    candidate_version: str,
    baseline_run_batch_id: str,
    candidate_run_batch_id: str,
    judge_model: str,
) -> None:
    if comparison.comparison_id != comparison_id:
        raise HTTPException(
            status_code=400,
            detail=f"Comparison comparison_id must be {comparison_id}",
        )
    if comparison.baseline_version != baseline_version:
        raise HTTPException(
            status_code=400,
            detail=f"Comparison baseline_version must be {baseline_version}",
        )
    if comparison.candidate_version != candidate_version:
        raise HTTPException(
            status_code=400,
            detail=f"Comparison candidate_version must be {candidate_version}",
        )
    if comparison.baseline_run_batch_ids != [baseline_run_batch_id]:
        raise HTTPException(
            status_code=400,
            detail=(
                "Comparison baseline_run_batch_ids must be "
                f"['{baseline_run_batch_id}']"
            ),
        )
    if comparison.candidate_run_batch_ids != [candidate_run_batch_id]:
        raise HTTPException(
            status_code=400,
            detail=(
                "Comparison candidate_run_batch_ids must be "
                f"['{candidate_run_batch_id}']"
            ),
        )
    if comparison.judge_model != judge_model:
        raise HTTPException(
            status_code=400,
            detail=f"Comparison judge_model must be {judge_model}",
        )


def _next_review_location(version_dir: Path) -> tuple[str, Path]:
    reviews_dir = version_dir / "reviews"
    index = 1
    while True:
        review_id = f"review-{index:03d}"
        review_dir = reviews_dir / review_id
        if not review_dir.exists():
            return review_id, review_dir
        index += 1


def _next_comparison_location(version_dir: Path) -> tuple[str, Path]:
    comparisons_dir = version_dir / "comparisons"
    index = 1
    while True:
        comparison_id = f"comparison-{index:03d}"
        comparison_dir = comparisons_dir / comparison_id
        try:
            comparison_dir.mkdir(parents=True)
            return comparison_id, comparison_dir
        except FileExistsError:
            pass
        index += 1


def _cleanup_reserved_comparison_dir(comparison_dir: Path) -> None:
    if comparison_dir.exists():
        shutil.rmtree(comparison_dir)
    comparisons_dir = comparison_dir.parent
    try:
        comparisons_dir.rmdir()
    except OSError:
        pass


def _remove_runtime_children(version_dir: Path, names: list[str]) -> None:
    for name in names:
        child = version_dir / name
        if child.is_dir():
            shutil.rmtree(child)


def _resolve_existing_review_dir(version_dir: Path, review_id: str) -> Path:
    _validate_review_id_path_segment(review_id)
    reviews_dir = (version_dir / "reviews").resolve()
    review_dir = (reviews_dir / review_id).resolve()
    if (
        review_dir == reviews_dir
        or not review_dir.is_relative_to(reviews_dir)
        or not review_dir.is_dir()
    ):
        raise HTTPException(status_code=404, detail="Review not found")
    if not (review_dir / "judgment.json").is_file():
        raise HTTPException(status_code=404, detail="Review not found")
    return review_dir


def _select_latest_review_dir(version_dir: Path) -> Path | None:
    reviews_dir = version_dir / "reviews"
    if not reviews_dir.is_dir():
        return None
    review_dirs = [
        path
        for path in reviews_dir.iterdir()
        if path.is_dir() and (path / "judgment.json").is_file()
    ]
    if not review_dirs:
        return None
    return max(review_dirs, key=lambda path: path.name)


def _read_review_state(review_dir: Path, review_id: str) -> dict[str, object]:
    judgment = JudgmentArtifact.model_validate(_read_json(review_dir / "judgment.json"))
    decisions_path = review_dir / "decisions.json"
    if not decisions_path.is_file():
        raise HTTPException(status_code=404, detail="Review not found")
    decisions = FindingDecisionSet.model_validate(_read_json(decisions_path))
    human_notes_path = review_dir / "human_notes.md"
    judgment_markdown_path = review_dir / "judgment.md"
    rubric_snapshot_path = review_dir / "rubric_snapshot.md"
    return {
        "review_id": review_id,
        "judgment": judgment.model_dump(mode="json"),
        "decisions": decisions.model_dump(mode="json"),
        "human_notes": (
            human_notes_path.read_text(encoding="utf-8")
            if human_notes_path.is_file()
            else ""
        ),
        "judgment_markdown": (
            judgment_markdown_path.read_text(encoding="utf-8")
            if judgment_markdown_path.is_file()
            else ""
        ),
        "rubric_snapshot": (
            rubric_snapshot_path.read_text(encoding="utf-8")
            if rubric_snapshot_path.is_file()
            else ""
        ),
    }


def _validate_decision_keys_match_judgment(
    *, judgment: JudgmentArtifact, decisions: FindingDecisionSet
) -> None:
    expected_ids = {finding.finding_id for finding in judgment.findings}
    submitted_ids = set(decisions.finding_decisions)
    if submitted_ids != expected_ids:
        missing_ids = sorted(expected_ids - submitted_ids)
        unknown_ids = sorted(submitted_ids - expected_ids)
        detail_parts = [
            "finding_decisions keys must exactly match judgment finding ids"
        ]
        if missing_ids:
            detail_parts.append(f"missing: {', '.join(missing_ids)}")
        if unknown_ids:
            detail_parts.append(f"unknown: {', '.join(unknown_ids)}")
        raise HTTPException(status_code=400, detail="; ".join(detail_parts))


def _decision_summary(decisions: FindingDecisionSet) -> dict[str, list[str]]:
    summary = {"accepted": [], "rejected": [], "deferred": []}
    for finding_id, decision in sorted(decisions.finding_decisions.items()):
        summary[decision.decision].append(finding_id)
    return summary


def _resolve_version_local_write_path(version_dir: Path, relative_path: str) -> Path:
    root = version_dir.resolve()
    candidate = (root / relative_path).resolve()
    if candidate == root or not candidate.is_relative_to(root):
        raise HTTPException(status_code=400, detail="Unsafe version path")
    return candidate


def _next_numeric_version_dir(versions_root: Path) -> tuple[str, Path]:
    highest = 0
    for path in versions_root.iterdir() if versions_root.is_dir() else []:
        if not path.is_dir():
            continue
        match = re.fullmatch(r"v(\d{3})", path.name)
        if match is not None:
            highest = max(highest, int(match.group(1)))
    index = highest + 1
    while True:
        version = f"v{index:03d}"
        version_dir = versions_root / version
        if not version_dir.exists():
            return version, version_dir
        index += 1


def _remove_generated_version_dirs(version_dir: Path) -> None:
    for name in ["runs", "reviews", "comparisons"]:
        path = version_dir / name
        if path.exists():
            shutil.rmtree(path)


def _load_validated_proposal_source(
    *,
    proposal_dir: Path,
    experiment_id: str,
    version: str,
    review_id: str,
    judgment: JudgmentArtifact,
) -> ProposalSource:
    source_path = proposal_dir / "source.json"
    if not source_path.is_file():
        raise HTTPException(status_code=404, detail="Proposal source not found")
    try:
        source = ProposalSource.model_validate(_read_json(source_path))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid proposal source.json: {exc}",
        ) from exc

    expected = {
        "experiment_id": experiment_id,
        "source_version": version,
        "review_id": review_id,
        "judgment_id": judgment.judgment_id,
    }
    actual = source.model_dump(mode="json")
    mismatches = [
        field
        for field, expected_value in expected.items()
        if actual.get(field) != expected_value
    ]
    if mismatches:
        raise HTTPException(
            status_code=400,
            detail=f"Proposal source mismatch: {', '.join(mismatches)}",
        )
    return source


def _read_proposal_response(proposal_dir: Path) -> dict[str, object]:
    prompt_path = proposal_dir / "prompt.md"
    rationale_path = proposal_dir / "rationale.md"
    if not prompt_path.is_file() or not rationale_path.is_file():
        raise HTTPException(status_code=404, detail="Proposal not found")
    model_path = proposal_dir / "model.py"
    proposal = ProposalDraft.model_validate(
        {
            "prompt_md": prompt_path.read_text(encoding="utf-8"),
            "model_py": (
                model_path.read_text(encoding="utf-8")
                if model_path.is_file()
                else None
            ),
            "rationale_md": rationale_path.read_text(encoding="utf-8"),
        }
    )
    source_path = proposal_dir / "source.json"
    if not source_path.is_file():
        raise HTTPException(status_code=404, detail="Proposal source not found")
    return {
        "proposal_dir": str(proposal_dir),
        "proposal": proposal.model_dump(mode="json"),
        "source": _read_json(source_path),
    }


def _load_latest_validated_run_batch(
    *,
    version_dir: Path,
    version: str,
    cases: set[str],
    repeat_count: int,
) -> tuple[str, list[RunArtifact]]:
    runs_dir = version_dir / "runs"
    run_batch_dir = _select_latest_run_batch_dir(runs_dir)
    if run_batch_dir is None:
        raise HTTPException(status_code=400, detail="Version has no run batches")
    selected_run_batch_id = run_batch_dir.name
    run_artifacts = _load_run_artifacts_from_batch_dir(run_batch_dir)
    if not run_artifacts:
        raise HTTPException(status_code=400, detail="Run batch has no artifacts")
    _validate_run_artifacts(
        run_artifacts=run_artifacts,
        selected_run_batch_id=selected_run_batch_id,
        version=version,
        case_ids=cases,
        repeat_count=repeat_count,
    )
    return selected_run_batch_id, run_artifacts


def create_app(config: PromptLabConfig | None = None) -> FastAPI:
    resolved_config = config or PromptLabConfig.from_env()
    seed_experiments_from_examples(
        experiments_root=resolved_config.experiments_root,
        examples_root=resolved_config.examples_root,
    )
    store = PromptLabStore(
        experiments_root=resolved_config.experiments_root,
        examples_root=resolved_config.examples_root,
    )
    job_manager = JobManager()
    app = FastAPI(title="Prompt Lab")

    @app.exception_handler(NotFoundError)
    def handle_not_found_error(
        request: object, exc: NotFoundError
    ) -> JSONResponse:
        del request
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.get("/api/experiments")
    def list_experiments() -> list[dict[str, object]]:
        return [item.model_dump(mode="json") for item in store.list_experiments()]

    @app.put("/api/experiments/{experiment_id}")
    def update_experiment(
        experiment_id: str, experiment: ExperimentArtifact
    ) -> dict[str, object]:
        if experiment.id != experiment_id:
            raise HTTPException(status_code=400, detail="Experiment id mismatch")
        try:
            store.save_experiment(experiment_id, experiment)
        except NotFoundError as exc:
            if str(exc) == "Version not found":
                raise HTTPException(status_code=400, detail="Version not found") from exc
            raise
        return experiment.model_dump(mode="json")

    @app.get("/api/experiments/{experiment_id}/versions")
    def list_experiment_versions(experiment_id: str) -> dict[str, object]:
        experiment = store.load_experiment(experiment_id)
        versions = store.list_versions(experiment_id)
        return {
            "active_version": experiment.active_version,
            "versions": [
                {
                    "version": version,
                    "is_active": version == experiment.active_version,
                }
                for version in versions
            ],
        }

    @app.get("/api/experiments/{experiment_id}/versions/{version}")
    def get_experiment_version(
        experiment_id: str, version: str
    ) -> dict[str, object]:
        experiment = store.load_experiment(experiment_id)
        experiment_dir = store.experiment_dir(experiment_id)
        prompt_template = store.read_text(
            experiment_id, version, experiment.template.path
        )
        cases = store.load_cases(experiment_id)
        return {
            "experiment": experiment.model_dump(mode="json"),
            "version": version,
            "prompt": prompt_template,
            "rubric": _read_optional_text(experiment_dir / "rubric.md"),
            "cases": [case.model_dump(mode="json") for case in cases],
        }

    @app.get("/api/experiments/{experiment_id}/versions/{version}/runs")
    def list_version_runs(experiment_id: str, version: str) -> dict[str, object]:
        version_dir = store.version_dir(experiment_id, version)
        run_batch_dir = _select_latest_run_batch_dir(version_dir / "runs")
        if run_batch_dir is None:
            return {"run_batch_id": None, "runs": []}
        run_artifacts = _load_run_artifacts_from_batch_dir(run_batch_dir)
        return {
            "run_batch_id": run_batch_dir.name,
            "runs": [run.model_dump(mode="json") for run in run_artifacts],
        }

    @app.get("/api/jobs/active")
    def get_active_job() -> dict[str, object]:
        active_job = job_manager.active_job()
        return {"job": asdict(active_job) if active_job is not None else None}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, object]:
        try:
            return asdict(job_manager.get(job_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc

    @app.get("/api/jobs/{job_id}/events")
    def get_job_events(job_id: str) -> list[dict[str, object]]:
        try:
            return [asdict(event) for event in job_manager.events(job_id)]
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc

    @app.get("/api/jobs/{job_id}/events/stream")
    def stream_job_events(job_id: str) -> StreamingResponse:
        try:
            job_manager.get(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc

        def event_stream() -> Iterator[str]:
            last_event_id = 0
            while True:
                try:
                    events = job_manager.events(job_id)
                    job = job_manager.get(job_id)
                except KeyError:
                    yield 'event: error\ndata: {"detail":"Job not found"}\n\n'
                    return

                for event in events:
                    if event.event_id <= last_event_id:
                        continue
                    last_event_id = event.event_id
                    yield (
                        f"id: {event.event_id}\n"
                        "event: job\n"
                        f"data: {json.dumps(asdict(event), ensure_ascii=False)}\n\n"
                    )

                if job.status in {"completed", "failed", "cancelled"}:
                    return
                time.sleep(0.1)

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> dict[str, object]:
        try:
            job = job_manager.cancel(job_id, message="Cancelled by user")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return asdict(job)

    @app.post("/api/experiments/{experiment_id}/versions/{version}/runs")
    def run_experiment_version(
        experiment_id: str,
        version: str,
        background_tasks: BackgroundTasks,
        request: RunVersionRequest | None = None,
    ) -> dict[str, object]:
        dry_run = request.dry_run if request is not None else False
        experiment = store.load_experiment(experiment_id)
        version_dir = store.version_dir(experiment_id, version)
        cases = store.load_cases(experiment_id)
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
            response_model = load_model_entrypoint(
                version_dir, model_file, model_entrypoint
            )
        try:
            job = job_manager.start_job(
                kind="run_version",
                experiment_id=experiment_id,
                version=version,
                total_units=len(cases) * repeat_count,
            )
        except JobAlreadyRunningError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        job_id = job.job_id
        _remove_runtime_children(version_dir, ["runs", "reviews", "comparisons"])

        def execute_run_job() -> None:
            completed_units = 0
            try:
                for case, repeat_index in iter_case_major(
                    cases, repeat_count=repeat_count
                ):
                    if job_manager.get(job_id).status == "cancelled":
                        return
                    job_manager.update(
                        job_id,
                        completed_units=completed_units,
                        message=f"Running {case.id} repeat {repeat_index}",
                    )
                    if experiment.output.type == "pydantic":
                        assert response_model is not None
                        generate_structured = llm_client.generate_structured
                        if dry_run:
                            validation_context = materialize_case_context(case)
                            response_text = dry_structured_response_json(
                                response_model,
                                validation_context=validation_context,
                            )

                            def generate_structured(
                                model: str,
                                prompt: str,
                                response_model: type[BaseModel],
                                validation_context: dict[str, object] | None,
                            ) -> object:
                                return llm_client.generate_structured_from_fake_response(
                                    model,
                                    prompt,
                                    response_model,
                                    validation_context,
                                    response_text,
                                )

                        run = run_structured_case(
                            version=version,
                            run_batch_id=job_id,
                            case=case,
                            repeat_index=repeat_index,
                            generator_model=experiment.models.generator_model,
                            template_text=template_text,
                            response_model=response_model,
                            generate_structured=generate_structured,
                        )
                    else:
                        generate_text = llm_client.generate_text
                        if dry_run:
                            response_text = dry_text_response(case.id, repeat_index)

                            def generate_text(model: str, prompt: str) -> object:
                                return llm_client.generate_text_from_fake_response(
                                    model,
                                    prompt,
                                    response_text,
                                )

                        run = run_text_case(
                            version=version,
                            run_batch_id=job_id,
                            case=case,
                            repeat_index=repeat_index,
                            generator_model=experiment.models.generator_model,
                            template_text=template_text,
                            generate_text=generate_text,
                        )
                    if job_manager.get(job_id).status == "cancelled":
                        return
                    store.write_run_artifact(
                        experiment_id,
                        version,
                        f"runs/{job_id}/{case.id}/repeat-{repeat_index:03d}.json",
                        run.model_dump(mode="json"),
                    )
                    completed_units += 1
                    job_manager.update(
                        job_id,
                        completed_units=completed_units,
                        message=f"Completed {case.id} repeat {repeat_index}",
                    )

                job_manager.complete(job_id, message="Run completed")
            except Exception as exc:
                current_job = job_manager.get(job_id)
                if current_job.status not in {"completed", "failed", "cancelled"}:
                    job_manager.fail(job_id, message=str(exc) or type(exc).__name__)

        background_tasks.add_task(execute_run_job)
        return asdict(job)

    @app.post("/api/experiments/{experiment_id}/versions/{version}/judgments")
    def judge_experiment_version(
        experiment_id: str,
        version: str,
        request: DryRunRequest | None = None,
        run_batch_id: str | None = None,
    ) -> dict[str, object]:
        selected_run_batch_id: str | None = None
        run_batch_dir: Path | None = None
        try:
            dry_run = request.dry_run if request is not None else False
            experiment = store.load_experiment(experiment_id)
            version_dir = store.version_dir(experiment_id, version)
            runs_dir = version_dir / "runs"
            experiment_dir = store.experiment_dir(experiment_id)
            rubric_path = experiment_dir / "rubric.md"
            rubric = _read_optional_text(rubric_path)
            prompt_template = store.read_text(
                experiment_id, version, experiment.template.path
            )
            cases = store.load_cases(experiment_id)
            case_ids = {case.id for case in cases}
            if run_batch_id is None:
                selected_run_batch_id, run_artifacts = _load_latest_validated_run_batch(
                    version_dir=version_dir,
                    version=version,
                    cases=case_ids,
                    repeat_count=experiment.run_defaults.repeat_count,
                )
                run_batch_dir = runs_dir / selected_run_batch_id
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
                run_artifacts = _load_run_artifacts_from_batch_dir(run_batch_dir)
                if not run_artifacts:
                    raise HTTPException(
                        status_code=400, detail="Run batch has no artifacts"
                    )
                _validate_run_artifacts(
                    run_artifacts=run_artifacts,
                    selected_run_batch_id=selected_run_batch_id,
                    version=version,
                    case_ids=case_ids,
                    repeat_count=experiment.run_defaults.repeat_count,
                )

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
                run_batch_id=selected_run_batch_id,
                judge_model=experiment.models.judge_model,
                output_declaration=output_declaration,
                rubric=rubric,
                prompt_template=prompt_template,
                cases=cases,
                run_artifacts=run_artifacts,
            )
            if dry_run:
                generated = llm_client.generate_structured_from_fake_response(
                    experiment.models.judge_model,
                    judge_prompt,
                    JudgmentArtifact,
                    None,
                    dry_judgment_response_json(
                        version=version,
                        run_batch_id=selected_run_batch_id,
                        judge_model=experiment.models.judge_model,
                    ),
                )
            else:
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
            _validate_judgment_metadata(
                judgment=judgment,
                version=version,
                selected_run_batch_id=selected_run_batch_id,
                judge_model=experiment.models.judge_model,
            )
            decisions = FindingDecisionSet.from_finding_ids(
                [finding.finding_id for finding in judgment.findings]
            )

            _remove_runtime_children(version_dir, ["reviews"])
            review_id, review_dir = _next_review_location(version_dir)
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
        except ValidationError as exc:
            detail = f"Judge response failed validation: {_validation_error_summary(exc)}"
            _log_judge_rejection(
                experiment_id=experiment_id,
                version=version,
                selected_run_batch_id=selected_run_batch_id,
                run_batch_dir=run_batch_dir,
                detail=detail,
                exc_info=True,
            )
            raise HTTPException(status_code=400, detail=detail) from exc
        except HTTPException as exc:
            if exc.status_code == 400:
                _log_judge_rejection(
                    experiment_id=experiment_id,
                    version=version,
                    selected_run_batch_id=selected_run_batch_id,
                    run_batch_dir=run_batch_dir,
                    detail=exc.detail,
                )
            raise
        except Exception as exc:
            detail = f"Judge request failed: {type(exc).__name__}: {exc}"
            _log_judge_rejection(
                experiment_id=experiment_id,
                version=version,
                selected_run_batch_id=selected_run_batch_id,
                run_batch_dir=run_batch_dir,
                detail=detail,
                exc_info=True,
            )
            raise HTTPException(status_code=500, detail=detail) from exc

    @app.post("/api/experiments/{experiment_id}/comparisons")
    def compare_experiment_versions(
        experiment_id: str, request: ComparisonRequest
    ) -> dict[str, object]:
        experiment = store.load_experiment(experiment_id)
        baseline_version = request.baseline_version
        candidate_version = request.candidate_version
        dry_run = request.dry_run
        baseline_version_dir = store.version_dir(experiment_id, baseline_version)
        candidate_version_dir = store.version_dir(experiment_id, candidate_version)

        baseline_cases = store.load_cases(experiment_id)
        candidate_cases = baseline_cases
        if not baseline_cases:
            raise HTTPException(status_code=400, detail="Experiment has no cases")
        for case in baseline_cases:
            _validate_case_id_path_segment(case.id)
        shared_case_ids = {case.id for case in baseline_cases}

        repeat_count = experiment.run_defaults.repeat_count
        baseline_run_batch_id, baseline_run_artifacts = _load_latest_validated_run_batch(
            version_dir=baseline_version_dir,
            version=baseline_version,
            cases=shared_case_ids,
            repeat_count=repeat_count,
        )
        candidate_run_batch_id, candidate_run_artifacts = _load_latest_validated_run_batch(
            version_dir=candidate_version_dir,
            version=candidate_version,
            cases=shared_case_ids,
            repeat_count=repeat_count,
        )

        experiment_dir = store.experiment_dir(experiment_id)
        rubric_path = experiment_dir / "rubric.md"
        rubric = _read_optional_text(rubric_path)
        baseline_prompt_template = store.read_text(
            experiment_id, baseline_version, experiment.template.path
        )
        candidate_prompt_template = store.read_text(
            experiment_id, candidate_version, experiment.template.path
        )
        comparison_id, comparison_dir = _next_comparison_location(
            candidate_version_dir
        )
        try:
            comparison_prompt = build_comparison_prompt(
                experiment_id=experiment_id,
                baseline_version=baseline_version,
                candidate_version=candidate_version,
                rubric=rubric,
                baseline_prompt_template=baseline_prompt_template,
                candidate_prompt_template=candidate_prompt_template,
                baseline_run_batch_ids=[baseline_run_batch_id],
                candidate_run_batch_ids=[candidate_run_batch_id],
                baseline_cases=baseline_cases,
                candidate_cases=candidate_cases,
                baseline_run_artifacts=baseline_run_artifacts,
                candidate_run_artifacts=candidate_run_artifacts,
                comparison_id=comparison_id,
            )
            if dry_run:
                generated = llm_client.generate_structured_from_fake_response(
                    experiment.models.judge_model,
                    comparison_prompt,
                    ComparisonArtifact,
                    None,
                    dry_comparison_response_json(
                        comparison_id=comparison_id,
                        baseline_version=baseline_version,
                        candidate_version=candidate_version,
                        baseline_run_batch_id=baseline_run_batch_id,
                        candidate_run_batch_id=candidate_run_batch_id,
                        judge_model=experiment.models.judge_model,
                    ),
                )
            else:
                generated = llm_client.generate_structured(
                    experiment.models.judge_model,
                    comparison_prompt,
                    ComparisonArtifact,
                    None,
                )
            output = generated.output
            comparison = (
                output
                if isinstance(output, ComparisonArtifact)
                else ComparisonArtifact.model_validate(output)
            )
            _validate_comparison_metadata(
                comparison=comparison,
                comparison_id=comparison_id,
                baseline_version=baseline_version,
                candidate_version=candidate_version,
                baseline_run_batch_id=baseline_run_batch_id,
                candidate_run_batch_id=candidate_run_batch_id,
                judge_model=experiment.models.judge_model,
            )

            _write_json(
                comparison_dir / "comparison.json", comparison.model_dump(mode="json")
            )
            (comparison_dir / "comparison.md").write_text(
                _render_comparison_markdown(comparison), encoding="utf-8"
            )
            (comparison_dir / "rubric_snapshot.md").write_text(
                rubric, encoding="utf-8"
            )
        except Exception:
            _cleanup_reserved_comparison_dir(comparison_dir)
            raise
        return {
            "comparison_id": comparison_id,
            "baseline_run_batch_id": baseline_run_batch_id,
            "candidate_run_batch_id": candidate_run_batch_id,
            "comparison": comparison.model_dump(mode="json"),
        }

    @app.put(
        "/api/experiments/{experiment_id}/versions/{version}/reviews/{review_id}/decisions"
    )
    def update_review_decisions(
        experiment_id: str,
        version: str,
        review_id: str,
        decisions: FindingDecisionSet,
    ) -> dict[str, object]:
        version_dir = store.version_dir(experiment_id, version)
        review_dir = _resolve_existing_review_dir(version_dir, review_id)
        judgment = JudgmentArtifact.model_validate(_read_json(review_dir / "judgment.json"))
        _validate_decision_keys_match_judgment(
            judgment=judgment,
            decisions=decisions,
        )
        saved = decisions.model_dump(mode="json")
        _write_json(review_dir / "decisions.json", saved)
        return saved

    @app.put(
        "/api/experiments/{experiment_id}/versions/{version}/reviews/{review_id}/human-notes"
    )
    def update_review_human_notes(
        experiment_id: str,
        version: str,
        review_id: str,
        request: HumanNotesRequest,
    ) -> dict[str, str]:
        version_dir = store.version_dir(experiment_id, version)
        review_dir = _resolve_existing_review_dir(version_dir, review_id)
        (review_dir / "human_notes.md").write_text(request.notes, encoding="utf-8")
        return {"human_notes": request.notes}

    @app.get(
        "/api/experiments/{experiment_id}/versions/{version}/reviews/{review_id}/proposal"
    )
    def get_review_proposal(
        experiment_id: str,
        version: str,
        review_id: str,
    ) -> dict[str, object]:
        version_dir = store.version_dir(experiment_id, version)
        review_dir = _resolve_existing_review_dir(version_dir, review_id)
        return _read_proposal_response(review_dir / "proposal")

    @app.post(
        "/api/experiments/{experiment_id}/versions/{version}/reviews/{review_id}/proposal"
    )
    def generate_review_proposal(
        experiment_id: str,
        version: str,
        review_id: str,
        request: DryRunRequest | None = None,
    ) -> dict[str, object]:
        dry_run = request.dry_run if request is not None else False
        experiment = store.load_experiment(experiment_id)
        version_dir = store.version_dir(experiment_id, version)
        review_dir = _resolve_existing_review_dir(version_dir, review_id)
        judgment = JudgmentArtifact.model_validate(_read_json(review_dir / "judgment.json"))
        decisions_path = review_dir / "decisions.json"
        if not decisions_path.is_file():
            raise HTTPException(status_code=404, detail="Review decisions not found")
        decisions = FindingDecisionSet.model_validate(_read_json(decisions_path))
        _validate_decision_keys_match_judgment(
            judgment=judgment,
            decisions=decisions,
        )

        prompt_template = store.read_text(
            experiment_id, version, experiment.template.path
        )
        rubric_snapshot_path = review_dir / "rubric_snapshot.md"
        rubric_snapshot = (
            rubric_snapshot_path.read_text(encoding="utf-8")
            if rubric_snapshot_path.is_file()
            else ""
        )
        human_notes_path = review_dir / "human_notes.md"
        human_notes = (
            human_notes_path.read_text(encoding="utf-8")
            if human_notes_path.is_file()
            else ""
        )
        model_source = None
        if experiment.output.type == "pydantic":
            model_file = experiment.output.model_file
            assert model_file is not None
            model_source = store.read_text(experiment_id, version, model_file)

        proposal_prompt = build_proposal_prompt(
            experiment_id=experiment_id,
            version=version,
            current_model=experiment.models.generator_model,
            output_type=experiment.output.type,
            prompt_template=prompt_template,
            model_source=model_source,
            rubric_snapshot=rubric_snapshot,
            judgment=judgment,
            decisions=decisions,
            human_notes=human_notes,
        )
        if dry_run:
            generated = llm_client.generate_structured_from_fake_response(
                experiment.models.judge_model,
                proposal_prompt,
                ProposalDraft,
                None,
                dry_proposal_response_json(
                    prompt_template=prompt_template,
                    model_source=model_source,
                    output_type=experiment.output.type,
                ),
            )
        else:
            generated = llm_client.generate_structured(
                experiment.models.judge_model,
                proposal_prompt,
                ProposalDraft,
                None,
            )
        output = generated.output
        proposal = (
            output
            if isinstance(output, ProposalDraft)
            else ProposalDraft.model_validate(output)
        )
        if experiment.output.type == "text" and proposal.model_py is not None:
            raise HTTPException(
                status_code=400,
                detail="Text output proposals cannot include model_py",
            )

        proposal_dir = review_dir / "proposal"
        proposal_dir.mkdir(parents=True, exist_ok=True)
        (proposal_dir / "prompt.md").write_text(
            proposal.prompt_md, encoding="utf-8"
        )
        model_proposal_path = proposal_dir / "model.py"
        if proposal.model_py is not None:
            model_proposal_path.write_text(proposal.model_py, encoding="utf-8")
        elif model_proposal_path.exists():
            model_proposal_path.unlink()
        (proposal_dir / "rationale.md").write_text(
            proposal.rationale_md, encoding="utf-8"
        )
        source = {
            "experiment_id": experiment_id,
            "source_version": version,
            "review_id": review_id,
            "judgment_id": judgment.judgment_id,
            "decision_summary": _decision_summary(decisions),
            "decisions_path": "decisions.json",
            "human_notes_present": bool(human_notes.strip()),
            "generated_by_model": experiment.models.judge_model,
            "output_type": experiment.output.type,
        }
        _write_json(proposal_dir / "source.json", source)
        return {
            "proposal_dir": str(proposal_dir),
            "proposal": proposal.model_dump(mode="json"),
            "source": source,
        }

    @app.post(
        "/api/experiments/{experiment_id}/versions/{version}/reviews/{review_id}/proposal/create-version"
    )
    def create_version_from_review_proposal(
        experiment_id: str, version: str, review_id: str
    ) -> dict[str, object]:
        experiment = store.load_experiment(experiment_id)
        source_version_dir = store.version_dir(experiment_id, version)
        review_dir = _resolve_existing_review_dir(source_version_dir, review_id)
        proposal_dir = review_dir / "proposal"
        proposal_prompt_path = proposal_dir / "prompt.md"
        if not proposal_prompt_path.is_file():
            raise HTTPException(status_code=404, detail="Proposal not found")
        judgment = JudgmentArtifact.model_validate(_read_json(review_dir / "judgment.json"))
        _load_validated_proposal_source(
            proposal_dir=proposal_dir,
            experiment_id=experiment_id,
            version=version,
            review_id=review_id,
            judgment=judgment,
        )

        versions_root = source_version_dir.parent
        new_version, new_version_dir = _next_numeric_version_dir(versions_root)
        staging_dir = versions_root / f".{new_version}.tmp"
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        try:
            shutil.copytree(source_version_dir, staging_dir)
            _remove_generated_version_dirs(staging_dir)
            legacy_cases_dir = staging_dir / "cases"
            if legacy_cases_dir.exists():
                shutil.rmtree(legacy_cases_dir)

            prompt_target = _resolve_version_local_write_path(
                staging_dir, experiment.template.path
            )
            prompt_target.parent.mkdir(parents=True, exist_ok=True)
            prompt_target.write_text(
                proposal_prompt_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            proposal_model_path = proposal_dir / "model.py"
            if experiment.output.type == "pydantic" and proposal_model_path.is_file():
                model_file = experiment.output.model_file
                assert model_file is not None
                model_target = _resolve_version_local_write_path(
                    staging_dir, model_file
                )
                model_target.parent.mkdir(parents=True, exist_ok=True)
                model_target.write_text(
                    proposal_model_path.read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
            staging_dir.rename(new_version_dir)
        except Exception:
            if staging_dir.exists():
                shutil.rmtree(staging_dir)
            if new_version_dir.exists():
                shutil.rmtree(new_version_dir)
            raise

        return {
            "version": new_version,
            "source_version": version,
            "review_id": review_id,
            "version_dir": str(new_version_dir),
        }

    @app.get("/api/experiments/{experiment_id}/versions/{version}/reviews/latest")
    def get_latest_review_state(experiment_id: str, version: str) -> dict[str, object]:
        version_dir = store.version_dir(experiment_id, version)
        review_dir = _select_latest_review_dir(version_dir)
        if review_dir is None:
            raise HTTPException(status_code=404, detail="Review not found")
        return _read_review_state(review_dir, review_dir.name)

    @app.get("/api/experiments/{experiment_id}/versions/{version}/reviews/{review_id}")
    def get_review_state(
        experiment_id: str, version: str, review_id: str
    ) -> dict[str, object]:
        version_dir = store.version_dir(experiment_id, version)
        review_dir = _resolve_existing_review_dir(version_dir, review_id)
        return _read_review_state(review_dir, review_id)

    return app
