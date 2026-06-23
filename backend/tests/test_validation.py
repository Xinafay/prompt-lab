from __future__ import annotations

from typing import Any

from prompt_lab.models.artifacts import CaseArtifact, RunArtifact
from prompt_lab.models.validators import LlmQuestionnaireResponse
from prompt_lab.models.validators import LlmQuestionnaireValidatorDefinition
from prompt_lab.models.validators import (
    ValidationInclusionUpdate,
    ValidationResultArtifact,
)
from prompt_lab.validation import (
    apply_inclusion_update,
    build_llm_validation_result,
    build_llm_validator_prompt,
    build_skipped_validation_result,
    validate_llm_check_ids,
)


def _validator(**overrides: object) -> LlmQuestionnaireValidatorDefinition:
    payload: dict[str, object] = {
        "schema_version": "prompt_lab.validator/v1",
        "validator_id": "quality",
        "type": "llm_questionnaire",
        "title": "Quality",
        "input_scope": "output_only",
        "checks": [
            {
                "check_id": "has-answer",
                "title": "Has answer",
                "question": "Does the output answer the request?",
            }
        ],
    }
    payload.update(overrides)
    return LlmQuestionnaireValidatorDefinition.model_validate(payload)


def _run_artifact(**overrides: object) -> RunArtifact:
    payload: dict[str, object] = {
        "schema_version": "prompt_lab.run/v1",
        "run_id": "run-001-case-a-repeat-001",
        "run_batch_id": "run-001",
        "version": "v001",
        "case_id": "case-a",
        "repeat_index": 1,
        "generator_model": "local/generator",
        "status": "ok",
        "rendered_prompt": "Rendered prompt should stay hidden",
        "raw_output": '{"answer":"Visible output"}',
        "output_type": "pydantic",
        "output_json": {"answer": "Visible output"},
        "usage": {},
    }
    payload.update(overrides)
    return RunArtifact.model_validate(payload)


def _case_artifact() -> CaseArtifact:
    return CaseArtifact.model_validate(
        {
            "id": "case-a",
            "payload": {},
        }
    )


def _validation_result(**overrides: object) -> ValidationResultArtifact:
    payload: dict[str, object] = {
        "schema_version": "prompt_lab.validation_result/v1",
        "validation_result_id": "validation-001-case-a-repeat-001-quality",
        "validation_batch_id": "validation-001",
        "run_batch_id": "run-001",
        "run_id": "run-001-case-a-repeat-001",
        "case_id": "case-a",
        "repeat_index": 1,
        "validator_id": "quality",
        "validator_type": "llm_questionnaire",
        "status": "ok",
        "included_in_judge": True,
        "check_results": [
            {
                "check_id": "has-answer",
                "grade": 5,
                "comment": "ok",
                "included_in_judge": True,
                "metrics": {},
            }
        ],
        "usage": {},
        "execution_error": None,
    }
    payload.update(overrides)
    return ValidationResultArtifact.model_validate(payload)


def test_build_llm_validator_prompt_respects_output_only_input_scope() -> None:
    prompt = build_llm_validator_prompt(
        experiment_id="demo",
        version="v001",
        validation_batch_id="validation-001",
        validator=_validator(),
        run=_run_artifact(),
        case=_case_artifact(),
        case_context={"secret_context": "Case context should stay hidden"},
    )

    assert "Visible output" in prompt
    assert "has-answer" in prompt
    assert prompt.count("<<MODEL>>") == 1
    assert "Return only JSON matching <<MODEL>>" not in prompt
    assert prompt.index("<<<OUTPUT_JSON") < prompt.index("<<MODEL>>")
    assert prompt.index("<<<QUESTIONNAIRE_JSON") < prompt.index("<<MODEL>>")
    assert "<<<VALIDATOR_JSON" not in prompt
    assert "<<<RUN_METADATA_JSON" not in prompt
    assert "<<<RUN_STATUS_JSON" not in prompt
    assert "Rendered prompt should stay hidden" not in prompt
    assert "secret_context" not in prompt


def test_build_llm_validator_prompt_defines_global_grade_scale() -> None:
    prompt = build_llm_validator_prompt(
        experiment_id="demo",
        version="v001",
        validation_batch_id="validation-001",
        validator=_validator(),
        run=_run_artifact(),
        case=_case_artifact(),
        case_context={},
    )

    assert "Use `5` for very good" in prompt
    assert "Use `4` for good" in prompt
    assert "Use `3` for acceptable but improvable" in prompt
    assert "Use `2` for weak" in prompt
    assert "Use `1` for bad" in prompt
    assert "Use `null` only when" in prompt
    assert "do not switch output language" in prompt
    assert "write validation comments in English" in prompt
    assert "Use `yes`" not in prompt
    assert "Use `no`" not in prompt
    assert "Use `unknown`" not in prompt


def test_build_llm_validator_prompt_rejects_structured_prompt_placeholder() -> None:
    try:
        build_llm_validator_prompt(
            experiment_id="demo",
            version="v001",
            validation_batch_id="validation-001",
            validator=_validator(input_scope="output_and_prompt"),
            run=_run_artifact(
                rendered_prompt="Return JSON matching this schema:\n<<MODEL>>"
            ),
            case=_case_artifact(),
            case_context={},
        )
    except ValueError as exc:
        assert "rendered_prompt contains unresolved <<MODEL>>" in str(exc)
    else:
        raise AssertionError("Expected unresolved structured prompt marker to fail")


def test_build_llm_validator_prompt_renders_text_output_as_text() -> None:
    prompt = build_llm_validator_prompt(
        experiment_id="demo",
        version="v001",
        validation_batch_id="validation-001",
        validator=_validator(),
        run=_run_artifact(
            output_type="text",
            output_text="Visible text output",
            output_json=None,
            raw_output="Visible text output",
        ),
        case=_case_artifact(),
        case_context={},
    )

    assert "<<<OUTPUT_TEXT" in prompt
    assert "Visible text output" in prompt
    assert "<<<OUTPUT_JSON" not in prompt
    assert '"output_text"' not in prompt
    assert '"raw_output"' not in prompt


def test_build_llm_validator_prompt_renders_validation_error_with_raw_output() -> None:
    prompt = build_llm_validator_prompt(
        experiment_id="demo",
        version="v001",
        validation_batch_id="validation-001",
        validator=_validator(),
        run=_run_artifact(
            status="validation_error",
            output_type="pydantic",
            output_json=None,
            raw_output='{"answer": 123}',
            validation_error="answer must be a string",
        ),
        case=_case_artifact(),
        case_context={},
    )

    assert "<<<INVALID_OUTPUT_TEXT" in prompt
    assert '{"answer": 123}' in prompt
    assert "<<<VALIDATION_ERROR" in prompt
    assert "answer must be a string" in prompt
    assert "<<<RUN_STATUS_JSON" not in prompt
    assert "<<<OUTPUT_JSON" not in prompt


def test_build_llm_validator_prompt_includes_only_materialized_case_context() -> None:
    case = CaseArtifact.model_validate(
        {
            "id": "case-a",
            "payload": {
                "state": {
                    "visible": "Visible case context",
                },
            },
        }
    )

    prompt = build_llm_validator_prompt(
        experiment_id="demo",
        version="v001",
        validation_batch_id="validation-001",
        validator=_validator(input_scope="output_and_case"),
        run=_run_artifact(),
        case=case,
        case_context={"chapter": {"text": "Visible source context"}},
    )

    assert "Visible output" in prompt
    assert "Visible source context" in prompt
    assert "Full store should stay hidden" not in prompt
    assert '"stores"' not in prompt
    assert '"bindings"' not in prompt
    assert "Rendered prompt should stay hidden" not in prompt


def test_build_llm_validation_result_records_grades() -> None:
    result = build_llm_validation_result(
        "validation-001",
        _run_artifact(),
        _validator(),
        LlmQuestionnaireResponse.model_validate(
            {
                "check_results": [
                    {
                        "check_id": "has-answer",
                        "grade": 4,
                        "comment": "Good with minor omissions.",
                    }
                ]
            }
        ),
        usage={"total_tokens": 7},
    )

    assert result.status == "ok"
    assert result.check_results[0].grade == 4
    assert result.check_results[0].comment == "Good with minor omissions."
    assert result.check_results[0].included_in_judge is True
    assert result.usage == {"total_tokens": 7}


def test_build_skipped_validation_result_records_non_included_result() -> None:
    result = build_skipped_validation_result(
        "validation-001",
        _run_artifact(status="execution_error", execution_error="transport failed"),
        _validator(),
        reason="Generator execution_error; validator skipped.",
    )

    assert result.status == "skipped"
    assert result.included_in_judge is False
    assert result.check_results == []
    assert result.usage == {}
    assert result.execution_error == "Generator execution_error; validator skipped."


def test_validate_llm_check_ids_rejects_missing_check_ids() -> None:
    try:
        validate_llm_check_ids(_validator(), [])
    except ValueError as exc:
        assert "missing: has-answer" in str(exc)
    else:
        raise AssertionError("Expected missing check ids to be rejected")


def test_apply_inclusion_update_rejects_unknown_result_id() -> None:
    update = ValidationInclusionUpdate.model_validate(
        {
            "results": [
                {
                    "validation_result_id": "missing-result",
                    "included_in_judge": False,
                    "check_results": [],
                }
            ]
        }
    )

    try:
        apply_inclusion_update([_validation_result()], update)
    except ValueError as exc:
        assert "unknown validation_result_id: missing-result" in str(exc)
    else:
        raise AssertionError("Expected unknown validation_result_id to be rejected")


def test_apply_inclusion_update_rejects_unknown_check_id() -> None:
    update = ValidationInclusionUpdate.model_validate(
        {
            "results": [
                {
                    "validation_result_id": "validation-001-case-a-repeat-001-quality",
                    "included_in_judge": True,
                    "check_results": [
                        {"check_id": "missing-check", "included_in_judge": False}
                    ],
                }
            ]
        }
    )

    try:
        apply_inclusion_update([_validation_result()], update)
    except ValueError as exc:
        assert "unknown check_id: missing-check" in str(exc)
    else:
        raise AssertionError("Expected unknown check_id to be rejected")


def test_apply_inclusion_update_rejects_duplicate_ids() -> None:
    update = ValidationInclusionUpdate.model_validate(
        {
            "results": [
                {
                    "validation_result_id": "validation-001-case-a-repeat-001-quality",
                    "included_in_judge": True,
                    "check_results": [],
                },
                {
                    "validation_result_id": "validation-001-case-a-repeat-001-quality",
                    "included_in_judge": False,
                    "check_results": [],
                },
            ]
        }
    )

    try:
        apply_inclusion_update([_validation_result()], update)
    except ValueError as exc:
        assert (
            "duplicate validation_result_id: validation-001-case-a-repeat-001-quality"
            in str(exc)
        )
    else:
        raise AssertionError("Expected duplicate validation_result_id to be rejected")

    check_update = ValidationInclusionUpdate.model_validate(
        {
            "results": [
                {
                    "validation_result_id": "validation-001-case-a-repeat-001-quality",
                    "included_in_judge": True,
                    "check_results": [
                        {"check_id": "has-answer", "included_in_judge": False},
                        {"check_id": "has-answer", "included_in_judge": True},
                    ],
                }
            ]
        }
    )

    try:
        apply_inclusion_update([_validation_result()], check_update)
    except ValueError as exc:
        assert "duplicate check_id: has-answer" in str(exc)
    else:
        raise AssertionError("Expected duplicate check_id to be rejected")


def test_apply_inclusion_update_rejects_included_skipped_result() -> None:
    skipped = _validation_result(
        status="skipped",
        included_in_judge=False,
        check_results=[],
        execution_error="Generator execution_error; validator skipped.",
    )
    update = ValidationInclusionUpdate.model_validate(
        {
            "results": [
                {
                    "validation_result_id": "validation-001-case-a-repeat-001-quality",
                    "included_in_judge": True,
                    "check_results": [],
                }
            ]
        }
    )

    try:
        apply_inclusion_update([skipped], update)
    except ValueError as exc:
        assert "skipped validation result cannot be included in judge" in str(exc)
    else:
        raise AssertionError("Expected skipped result inclusion to be rejected")


def main() -> int:
    tests = [
        test_build_llm_validator_prompt_respects_output_only_input_scope,
        test_build_llm_validator_prompt_defines_global_grade_scale,
        test_build_llm_validator_prompt_rejects_structured_prompt_placeholder,
        test_build_llm_validator_prompt_renders_text_output_as_text,
        test_build_llm_validator_prompt_renders_validation_error_with_raw_output,
        test_build_llm_validator_prompt_includes_only_materialized_case_context,
        test_build_llm_validation_result_records_grades,
        test_build_skipped_validation_result_records_non_included_result,
        test_validate_llm_check_ids_rejects_missing_check_ids,
        test_apply_inclusion_update_rejects_unknown_result_id,
        test_apply_inclusion_update_rejects_unknown_check_id,
        test_apply_inclusion_update_rejects_duplicate_ids,
        test_apply_inclusion_update_rejects_included_skipped_result,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
