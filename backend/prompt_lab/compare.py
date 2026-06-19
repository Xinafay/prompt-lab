from __future__ import annotations

from collections import Counter
from typing import Any

from prompt_lab.models.artifacts import CaseArtifact, RunArtifact
from prompt_lab.models.judgments import ComparisonArtifact
from prompt_lab.prompt_sections import fenced_section, json_block
from prompt_lab.prompt_templates import render_system_prompt


def _run_summary(run_artifacts: list[RunArtifact]) -> dict[str, Any]:
    sorted_runs = sorted(
        run_artifacts, key=lambda item: (item.case_id, item.repeat_index, item.run_id)
    )
    statuses = Counter(run.status for run in sorted_runs)
    errors = [
        {
            "case_id": run.case_id,
            "repeat_index": run.repeat_index,
            "status": run.status,
            "validation_error": run.validation_error,
            "execution_error": run.execution_error,
        }
        for run in sorted_runs
        if run.validation_error is not None or run.execution_error is not None
    ]
    outputs = [
        {
            "case_repeat": f"{run.case_id} repeat {run.repeat_index}",
            "status": run.status,
            "rendered_prompt": run.rendered_prompt,
            "raw_output": run.raw_output,
            "output_json": run.output_json,
            "output_text": run.output_text,
            "validation_error": run.validation_error,
            "execution_error": run.execution_error,
        }
        for run in sorted_runs
    ]
    return {
        "run_count": len(sorted_runs),
        "status_counts": dict(sorted(statuses.items())),
        "errors": errors,
        "outputs": outputs,
    }


def _run_outputs_text(run_artifacts: list[RunArtifact]) -> str:
    output_lines = []
    for run in sorted(
        run_artifacts, key=lambda item: (item.case_id, item.repeat_index, item.run_id)
    ):
        output_lines.append(
            "\n".join(
                [
                    f"{run.case_id} repeat {run.repeat_index}",
                    f"status: {run.status}",
                    f"rendered_prompt: {run.rendered_prompt}",
                    f"raw_output: {run.raw_output}",
                    f"output_text: {run.output_text}",
                    f"validation_error: {run.validation_error}",
                    f"execution_error: {run.execution_error}",
                ]
            )
        )
    return "\n\n".join(output_lines)


def build_comparison_prompt(
    *,
    experiment_id: str,
    baseline_version: str,
    candidate_version: str,
    rubric: str,
    baseline_prompt_template: str,
    candidate_prompt_template: str,
    baseline_run_batch_ids: list[str],
    candidate_run_batch_ids: list[str],
    baseline_cases: list[CaseArtifact],
    candidate_cases: list[CaseArtifact],
    baseline_run_artifacts: list[RunArtifact],
    candidate_run_artifacts: list[RunArtifact],
    comparison_id: str | None = None,
) -> str:
    schema = json_block(ComparisonArtifact.model_json_schema())
    return render_system_prompt(
        "comparison.md.jinja",
        {
            "experiment_id": experiment_id,
            "baseline_version": baseline_version,
            "candidate_version": candidate_version,
            "baseline_run_batches": ", ".join(baseline_run_batch_ids),
            "candidate_run_batches": ", ".join(candidate_run_batch_ids),
            "comparison_id": comparison_id,
            "rubric_section": fenced_section("RUBRIC_SNAPSHOT", rubric),
            "baseline_prompt_section": fenced_section(
                "BASELINE_PROMPT_TEMPLATE", baseline_prompt_template
            ),
            "candidate_prompt_section": fenced_section(
                "CANDIDATE_PROMPT_TEMPLATE", candidate_prompt_template
            ),
            "baseline_cases_section": fenced_section(
                "BASELINE_CASES_JSON",
                json_block([case.model_dump(mode="json") for case in baseline_cases]),
                fence="json",
            ),
            "candidate_cases_section": fenced_section(
                "CANDIDATE_CASES_JSON",
                json_block([case.model_dump(mode="json") for case in candidate_cases]),
                fence="json",
            ),
            "baseline_run_summary_section": fenced_section(
                "BASELINE_RUN_SUMMARY",
                json_block(_run_summary(baseline_run_artifacts)),
                fence="json",
            ),
            "baseline_run_outputs_section": fenced_section(
                "BASELINE_RUN_OUTPUTS_AND_ERRORS",
                _run_outputs_text(baseline_run_artifacts),
            ),
            "candidate_run_summary_section": fenced_section(
                "CANDIDATE_RUN_SUMMARY",
                json_block(_run_summary(candidate_run_artifacts)),
                fence="json",
            ),
            "candidate_run_outputs_section": fenced_section(
                "CANDIDATE_RUN_OUTPUTS_AND_ERRORS",
                _run_outputs_text(candidate_run_artifacts),
            ),
            "comparison_schema_section": fenced_section(
                "COMPARISON_SCHEMA_JSON", schema, fence="json"
            ),
        },
    )
