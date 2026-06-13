from __future__ import annotations

from prompt_lab.models.artifacts import CaseArtifact, RunArtifact
from prompt_lab.models.judgments import JudgmentArtifact
from prompt_lab.prompt_sections import fenced_section, json_block
from prompt_lab.prompt_templates import render_system_prompt


def build_judge_prompt(
    *,
    experiment_id: str,
    version: str,
    run_batch_id: str,
    judge_model: str,
    output_declaration: str,
    rubric: str,
    prompt_template: str,
    cases: list[CaseArtifact],
    run_artifacts: list[RunArtifact],
) -> str:
    case_payload = [case.model_dump(mode="json") for case in cases]
    run_payload = [
        {
            "case_repeat": f"{run.case_id} repeat {run.repeat_index}",
            "artifact": run.model_dump(mode="json"),
        }
        for run in sorted(run_artifacts, key=lambda item: (item.case_id, item.repeat_index))
    ]
    error_payload = [
        {
            "case_id": run.case_id,
            "repeat_index": run.repeat_index,
            "status": run.status,
            "validation_error": run.validation_error,
            "execution_error": run.execution_error,
        }
        for run in run_artifacts
        if run.validation_error is not None or run.execution_error is not None
    ]
    output_lines = []
    for run in sorted(run_artifacts, key=lambda item: (item.case_id, item.repeat_index)):
        output_lines.append(
            "\n".join(
                [
                    f"{run.case_id} repeat {run.repeat_index}",
                    f"raw_output: {run.raw_output}",
                    f"output_text: {run.output_text}",
                    f"validation_error: {run.validation_error}",
                    f"execution_error: {run.execution_error}",
                ]
            )
        )
    schema = json_block(JudgmentArtifact.model_json_schema())
    return render_system_prompt(
        "judge.md.jinja",
        {
            "experiment_id": experiment_id,
            "version": version,
            "judgment_metadata_section": fenced_section(
                "JUDGMENT_METADATA_JSON",
                json_block(
                    {
                        "version": version,
                        "run_batch_ids": [run_batch_id],
                        "judge_model": judge_model,
                    }
                ),
                fence="json",
            ),
            "output_declaration_section": fenced_section(
                "OUTPUT_DECLARATION", output_declaration
            ),
            "rubric_section": fenced_section("RUBRIC_SNAPSHOT", rubric),
            "prompt_template_section": fenced_section("PROMPT_TEMPLATE", prompt_template),
            "cases_section": fenced_section(
                "CASES_JSON", json_block(case_payload), fence="json"
            ),
            "run_artifacts_section": fenced_section(
                "RUN_ARTIFACTS_JSON", json_block(run_payload), fence="json"
            ),
            "run_outputs_section": fenced_section(
                "RUN_OUTPUTS_AND_ERRORS", "\n\n".join(output_lines)
            ),
            "run_errors_section": fenced_section(
                "RUN_ERRORS_JSON", json_block(error_payload), fence="json"
            ),
            "judgment_schema_section": fenced_section(
                "JUDGMENT_SCHEMA_JSON", schema, fence="json"
            ),
        },
    )
