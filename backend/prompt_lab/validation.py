from __future__ import annotations

from typing import Any

from prompt_lab.models.artifacts import CaseArtifact, RunArtifact
from prompt_lab.models.validators import (
    LlmQuestionnaireResponse,
    LlmQuestionnaireValidatorDefinition,
    ValidationCheckResult,
    ValidationInclusionUpdate,
    ValidationResultArtifact,
    ValidatorDefinition,
)
from prompt_lab.prompt_sections import fenced_section, json_block
from prompt_lab.prompt_templates import render_system_prompt


def enabled_validators(validators: list[ValidatorDefinition]) -> list[ValidatorDefinition]:
    return [validator for validator in validators if validator.enabled]


def build_llm_validator_prompt(
    *,
    experiment_id: str,
    version: str,
    validation_batch_id: str,
    validator: LlmQuestionnaireValidatorDefinition,
    run: RunArtifact,
    case: CaseArtifact,
    case_context: dict[str, Any],
) -> str:
    output_payload = {
        "raw_output": run.raw_output,
        "output_type": run.output_type,
        "output_text": run.output_text,
        "output_json": run.output_json,
    }
    status_payload = {
        "status": run.status,
        "validation_error": run.validation_error,
        "execution_error": run.execution_error,
    }
    rendered_prompt_section = ""
    if validator.input_scope in {"output_and_prompt", "output_prompt_and_case"}:
        rendered_prompt_section = fenced_section(
            "RENDERED_PROMPT",
            run.rendered_prompt,
        )
    case_context_section = ""
    if validator.input_scope in {"output_and_case", "output_prompt_and_case"}:
        case_context_section = fenced_section(
            "CASE_CONTEXT_JSON",
            json_block(
                {
                    "case": case.model_dump(mode="json"),
                    "materialized_context": case_context,
                }
            ),
            fence="json",
        )
    return render_system_prompt(
        "validator.md.jinja",
        {
            "validator_section": fenced_section(
                "VALIDATOR_JSON",
                json_block(validator.model_dump(mode="json")),
                fence="json",
            ),
            "run_metadata_section": fenced_section(
                "RUN_METADATA_JSON",
                json_block(
                    {
                        "experiment_id": experiment_id,
                        "version": version,
                        "validation_batch_id": validation_batch_id,
                        "run_batch_id": run.run_batch_id,
                        "run_id": run.run_id,
                        "case_id": run.case_id,
                        "repeat_index": run.repeat_index,
                    }
                ),
                fence="json",
            ),
            "run_status_section": fenced_section(
                "RUN_STATUS_JSON",
                json_block(status_payload),
                fence="json",
            ),
            "output_section": fenced_section(
                "OUTPUT_JSON",
                json_block(output_payload),
                fence="json",
            ),
            "rendered_prompt_section": rendered_prompt_section,
            "case_context_section": case_context_section,
            "response_schema_section": fenced_section(
                "RESPONSE_SCHEMA_JSON",
                "<<MODEL>>",
                fence="json",
            ),
        },
    )


def validate_llm_check_ids(
    validator: LlmQuestionnaireValidatorDefinition,
    response_check_ids: list[str],
) -> None:
    expected_ids = [check.check_id for check in validator.checks]
    expected = set(expected_ids)
    seen: set[str] = set()
    duplicates: list[str] = []
    for check_id in response_check_ids:
        if check_id in seen and check_id not in duplicates:
            duplicates.append(check_id)
        seen.add(check_id)

    submitted = set(response_check_ids)
    missing = sorted(expected - submitted)
    unknown = sorted(submitted - expected)
    if not missing and not unknown and not duplicates:
        return

    detail_parts = ["LLM validator check ids must exactly match validator checks"]
    if missing:
        detail_parts.append(f"missing: {', '.join(missing)}")
    if unknown:
        detail_parts.append(f"unknown: {', '.join(unknown)}")
    if duplicates:
        detail_parts.append(f"duplicates: {', '.join(sorted(duplicates))}")
    raise ValueError("; ".join(detail_parts))


def build_llm_validation_result(
    validation_batch_id: str,
    run: RunArtifact,
    validator: LlmQuestionnaireValidatorDefinition,
    response: LlmQuestionnaireResponse,
    usage: dict[str, Any],
) -> ValidationResultArtifact:
    validate_llm_check_ids(
        validator,
        [check_result.check_id for check_result in response.check_results],
    )
    return ValidationResultArtifact.model_validate(
        {
            "schema_version": "prompt_lab.validation_result/v1",
            "validation_result_id": (
                f"{validation_batch_id}-{run.case_id}-"
                f"repeat-{run.repeat_index:03d}-{validator.validator_id}"
            ),
            "validation_batch_id": validation_batch_id,
            "run_batch_id": run.run_batch_id,
            "run_id": run.run_id,
            "case_id": run.case_id,
            "repeat_index": run.repeat_index,
            "validator_id": validator.validator_id,
            "validator_type": "llm_questionnaire",
            "status": "ok",
            "included_in_judge": True,
            "check_results": [
                ValidationCheckResult(
                    check_id=check_result.check_id,
                    verdict=check_result.verdict,
                    comment=check_result.comment,
                    included_in_judge=True,
                ).model_dump(mode="json")
                for check_result in response.check_results
            ],
            "usage": usage,
            "execution_error": None,
        }
    )


def apply_inclusion_update(
    results: list[ValidationResultArtifact],
    update: ValidationInclusionUpdate,
) -> list[ValidationResultArtifact]:
    results_by_id = {result.validation_result_id: result for result in results}
    seen_result_ids: set[str] = set()
    duplicate_result_ids: list[str] = []
    unknown_result_ids: list[str] = []
    for item in update.results:
        if item.validation_result_id in seen_result_ids:
            duplicate_result_ids.append(item.validation_result_id)
        seen_result_ids.add(item.validation_result_id)
        if item.validation_result_id not in results_by_id:
            unknown_result_ids.append(item.validation_result_id)

    if duplicate_result_ids or unknown_result_ids:
        detail_parts = ["Validation inclusion update contains invalid result ids"]
        if unknown_result_ids:
            detail_parts.append(
                f"unknown validation_result_id: {', '.join(sorted(unknown_result_ids))}"
            )
        if duplicate_result_ids:
            detail_parts.append(
                f"duplicate validation_result_id: "
                f"{', '.join(sorted(set(duplicate_result_ids)))}"
            )
        raise ValueError("; ".join(detail_parts))

    for item in update.results:
        result = results_by_id[item.validation_result_id]
        expected_check_ids = {check.check_id for check in result.check_results}
        seen_check_ids: set[str] = set()
        duplicate_check_ids: list[str] = []
        unknown_check_ids: list[str] = []
        for check in item.check_results:
            if check.check_id in seen_check_ids:
                duplicate_check_ids.append(check.check_id)
            seen_check_ids.add(check.check_id)
            if check.check_id not in expected_check_ids:
                unknown_check_ids.append(check.check_id)

        if duplicate_check_ids or unknown_check_ids:
            detail_parts = [
                f"Validation inclusion update contains invalid check ids for "
                f"{item.validation_result_id}"
            ]
            if unknown_check_ids:
                detail_parts.append(
                    f"unknown check_id: {', '.join(sorted(unknown_check_ids))}"
                )
            if duplicate_check_ids:
                detail_parts.append(
                    f"duplicate check_id: "
                    f"{', '.join(sorted(set(duplicate_check_ids)))}"
                )
            raise ValueError("; ".join(detail_parts))

    updates_by_result_id = {item.validation_result_id: item for item in update.results}
    updated_results: list[ValidationResultArtifact] = []
    for result in results:
        result_update = updates_by_result_id.get(result.validation_result_id)
        if result_update is None:
            updated_results.append(result)
            continue
        check_updates = {
            item.check_id: item.included_in_judge
            for item in result_update.check_results
        }
        updated_checks = [
            check.model_copy(
                update={
                    "included_in_judge": check_updates.get(
                        check.check_id,
                        check.included_in_judge,
                    )
                }
            )
            for check in result.check_results
        ]
        updated_results.append(
            result.model_copy(
                update={
                    "included_in_judge": result_update.included_in_judge,
                    "check_results": updated_checks,
                }
            )
        )
    return updated_results
