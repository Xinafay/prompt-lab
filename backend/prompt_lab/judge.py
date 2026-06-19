from __future__ import annotations

from prompt_lab.models.judgments import JudgmentArtifact
from prompt_lab.prompt_sections import fenced_section, json_block
from prompt_lab.prompt_templates import render_system_prompt


def build_judge_prompt(
    *,
    experiment_id: str,
    version: str,
    run_batch_id: str,
    validation_batch_id: str,
    judge_model: str,
    output_declaration: str,
    prompt_template: str,
    model_source: str | None,
    validation_evidence: list[dict[str, object]],
    run_errors: list[dict[str, object]],
) -> str:
    schema = json_block(JudgmentArtifact.model_json_schema())
    model_source_section = (
        fenced_section("CURRENT_MODEL_PY", model_source, fence="python")
        if model_source is not None
        else None
    )
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
                        "validation_batch_id": validation_batch_id,
                        "judge_model": judge_model,
                    }
                ),
                fence="json",
            ),
            "validation_metadata_section": fenced_section(
                "VALIDATION_METADATA_JSON",
                json_block(
                    {
                        "version": version,
                        "run_batch_id": run_batch_id,
                        "validation_batch_id": validation_batch_id,
                    }
                ),
                fence="json",
            ),
            "output_declaration_section": fenced_section(
                "OUTPUT_DECLARATION", output_declaration
            ),
            "prompt_template_section": fenced_section("PROMPT_TEMPLATE", prompt_template),
            "model_source_section": model_source_section,
            "validation_evidence_section": fenced_section(
                "VALIDATION_EVIDENCE_JSON",
                json_block(validation_evidence),
                fence="json",
            ),
            "run_errors_section": fenced_section(
                "RUN_ERRORS_JSON", json_block(run_errors), fence="json"
            ),
            "judgment_schema_section": fenced_section(
                "JUDGMENT_SCHEMA_JSON", schema, fence="json"
            ),
        },
    )
