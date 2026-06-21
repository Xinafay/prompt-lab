from __future__ import annotations

from prompt_lab.prompt_sections import fenced_section, json_block
from prompt_lab.prompt_templates import render_system_prompt


_MODEL_PLACEHOLDER = "<<MODEL>>"
_EMBEDDED_MODEL_PLACEHOLDER = "[MODEL_MARKER_LITERAL]"
_OUTPUT_MODEL_PLACEHOLDER = "[OUTPUT_MODEL_SCHEMA: see CURRENT_MODEL_PY]"


def _display_prompt_template(prompt_template: str) -> str:
    return prompt_template.replace(_MODEL_PLACEHOLDER, _OUTPUT_MODEL_PLACEHOLDER)


def _display_embedded_content(content: str) -> str:
    # structured_lite replaces every literal marker in the complete prompt.
    return content.replace(_MODEL_PLACEHOLDER, _EMBEDDED_MODEL_PLACEHOLDER)


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
    model_source_section = (
        fenced_section(
            "CURRENT_MODEL_PY",
            _display_embedded_content(model_source),
            fence="python",
        )
        if model_source is not None
        else None
    )
    return render_system_prompt(
        "judge.md.jinja",
        {
            "experiment_id": _display_embedded_content(experiment_id),
            "version": _display_embedded_content(version),
            "judgment_metadata_section": fenced_section(
                "JUDGMENT_METADATA_JSON",
                _display_embedded_content(
                    json_block(
                        {
                            "version": version,
                            "run_batch_ids": [run_batch_id],
                            "judge_model": judge_model,
                        }
                    )
                ),
                fence="json",
            ),
            "validation_metadata_section": fenced_section(
                "VALIDATION_METADATA_JSON",
                _display_embedded_content(
                    json_block(
                        {
                            "version": version,
                            "run_batch_id": run_batch_id,
                            "validation_batch_id": validation_batch_id,
                        }
                    )
                ),
                fence="json",
            ),
            "output_declaration_section": fenced_section(
                "OUTPUT_DECLARATION", _display_embedded_content(output_declaration)
            ),
            "prompt_template_section": fenced_section(
                "PROMPT_TEMPLATE", _display_prompt_template(prompt_template)
            ),
            "model_source_section": model_source_section,
            "validation_evidence_section": fenced_section(
                "VALIDATION_EVIDENCE_JSON",
                _display_embedded_content(json_block(validation_evidence)),
                fence="json",
            ),
            "run_errors_section": fenced_section(
                "RUN_ERRORS_JSON",
                _display_embedded_content(json_block(run_errors)),
                fence="json",
            ),
        },
    )
