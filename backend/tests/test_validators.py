from __future__ import annotations

from pydantic import ValidationError

from prompt_lab.models.validators import (
    AutomaticValidatorDefinition,
    CountComparison,
    LlmQuestionnaireValidatorDefinition,
    ValidationBatchArtifact,
    ValidationResultArtifact,
    ValidationState,
)


def test_llm_questionnaire_validator_definition_accepts_expected_fields() -> None:
    validator = LlmQuestionnaireValidatorDefinition.model_validate(
        {
            "schema_version": "prompt_lab.validator/v1",
            "validator_id": "clarity",
            "type": "llm_questionnaire",
            "title": "Clarity",
            "description": "Checks whether the answer is clear.",
            "enabled": True,
            "input_scope": "output_and_prompt",
            "checks": [
                {
                    "check_id": "direct",
                    "title": "Direct answer",
                    "question": "Does the output answer directly?",
                    "description": "Avoids evasive responses.",
                }
            ],
        }
    )

    assert validator.schema_version == "prompt_lab.validator/v1"
    assert validator.validator_id == "clarity"
    assert validator.type == "llm_questionnaire"
    assert validator.checks[0].description == "Avoids evasive responses."


def test_llm_questionnaire_validator_definition_rejects_duplicate_check_ids() -> None:
    try:
        LlmQuestionnaireValidatorDefinition.model_validate(
            {
                "schema_version": "prompt_lab.validator/v1",
                "validator_id": "clarity",
                "type": "llm_questionnaire",
                "title": "Clarity",
                "checks": [
                    {
                        "check_id": "direct",
                        "title": "Direct",
                        "question": "Is it direct?",
                    },
                    {
                        "check_id": "direct",
                        "title": "Still direct",
                        "question": "Is it still direct?",
                    },
                ],
            }
        )
    except ValidationError as exc:
        assert "duplicate check ids" in str(exc)
    else:
        raise AssertionError("Expected duplicate check IDs to be rejected")


def test_automatic_validator_definition_accepts_word_count_rule() -> None:
    validator = AutomaticValidatorDefinition.model_validate(
        {
            "schema_version": "prompt_lab.validator/v1",
            "validator_id": "length",
            "type": "automatic",
            "title": "Length",
            "checks": [
                {
                    "check_id": "under_100",
                    "title": "Under 100 words",
                    "rule": {
                        "kind": "word_count",
                        "source": "output_text",
                        "comparison": {"op": "lte", "value": 100},
                    },
                }
            ],
        }
    )

    assert validator.type == "automatic"
    assert validator.checks[0].rule.kind == "word_count"
    assert validator.checks[0].rule.comparison is not None
    assert validator.checks[0].rule.comparison.value == 100


def test_count_comparison_rejects_inverted_between_range() -> None:
    try:
        CountComparison.model_validate(
            {"op": "between", "min_value": 10, "max_value": 5}
        )
    except ValidationError as exc:
        assert "min_value cannot exceed max_value" in str(exc)
    else:
        raise AssertionError("Expected inverted between range to be rejected")


def test_validation_batch_and_result_artifacts_accept_expected_fields() -> None:
    batch = ValidationBatchArtifact.model_validate(
        {
            "schema_version": "prompt_lab.validation_batch/v1",
            "validation_batch_id": "validation-001",
            "run_batch_id": "run-001",
            "version": "v001",
            "status": "completed",
            "started_at": "2026-06-19T10:00:00Z",
            "finished_at": "2026-06-19T10:01:00Z",
            "total_results": 1,
            "completed_results": 1,
            "validator_model": "openai/validator",
            "validator_ids": ["clarity"],
        }
    )
    result = ValidationResultArtifact.model_validate(
        {
            "schema_version": "prompt_lab.validation_result/v1",
            "validation_result_id": "result-001",
            "validation_batch_id": "validation-001",
            "run_batch_id": "run-001",
            "run_id": "run-001-case-a-1",
            "case_id": "case-a",
            "repeat_index": 1,
            "validator_id": "clarity",
            "validator_type": "llm_questionnaire",
            "status": "ok",
            "included_in_judge": True,
            "check_results": [
                {
                    "check_id": "direct",
                    "verdict": "yes",
                    "comment": "The answer is direct.",
                    "included_in_judge": True,
                    "metrics": {"word_count": 42},
                }
            ],
            "usage": {"total_tokens": 12},
        }
    )

    assert batch.schema_version == "prompt_lab.validation_batch/v1"
    assert batch.status == "completed"
    assert batch.validator_model == "openai/validator"
    assert batch.validator_ids == ["clarity"]
    assert result.schema_version == "prompt_lab.validation_result/v1"
    assert result.status == "ok"
    assert result.check_results[0].verdict == "yes"
    assert result.check_results[0].comment == "The answer is direct."
    assert result.check_results[0].included_in_judge is True
    assert result.check_results[0].metrics == {"word_count": 42}


def test_validation_result_artifact_accepts_skipped_status() -> None:
    result = ValidationResultArtifact.model_validate(
        {
            "schema_version": "prompt_lab.validation_result/v1",
            "validation_result_id": "result-skipped",
            "validation_batch_id": "validation-001",
            "run_batch_id": "run-001",
            "run_id": "run-001-case-a-1",
            "case_id": "case-a",
            "repeat_index": 1,
            "validator_id": "clarity",
            "validator_type": "llm_questionnaire",
            "status": "skipped",
            "included_in_judge": False,
            "check_results": [],
            "usage": {},
            "execution_error": "Generator execution_error; validator skipped.",
        }
    )

    assert result.status == "skipped"
    assert result.included_in_judge is False
    assert result.check_results == []


def test_validation_result_artifact_rejects_included_skipped_status() -> None:
    try:
        ValidationResultArtifact.model_validate(
            {
                "schema_version": "prompt_lab.validation_result/v1",
                "validation_result_id": "result-skipped",
                "validation_batch_id": "validation-001",
                "run_batch_id": "run-001",
                "run_id": "run-001-case-a-1",
                "case_id": "case-a",
                "repeat_index": 1,
                "validator_id": "clarity",
                "validator_type": "llm_questionnaire",
                "status": "skipped",
                "included_in_judge": True,
                "check_results": [],
                "usage": {},
                "execution_error": "Generator execution_error; validator skipped.",
            }
        )
    except ValidationError as exc:
        assert "skipped status cannot be included in judge" in str(exc)
    else:
        raise AssertionError("Expected included skipped result to be rejected")


def test_validation_state_rejects_malformed_validator_definitions() -> None:
    batch = {
        "schema_version": "prompt_lab.validation_batch/v1",
        "validation_batch_id": "validation-001",
        "run_batch_id": "run-001",
        "version": "v001",
        "status": "completed",
        "started_at": "2026-06-19T10:00:00Z",
        "finished_at": "2026-06-19T10:01:00Z",
        "total_results": 0,
        "completed_results": 0,
        "validator_model": "openai/validator",
        "validator_ids": ["clarity"],
    }

    try:
        ValidationState.model_validate(
            {
                "validation_batch": batch,
                "validators": [
                    {
                        "schema_version": "prompt_lab.validator/v1",
                        "validator_id": "clarity",
                        "type": "llm_questionnaire",
                        "title": "Clarity",
                    }
                ],
                "results": [],
            }
        )
    except ValidationError as exc:
        assert "checks" in str(exc)
    else:
        raise AssertionError("Expected malformed validator definition to be rejected")


def main() -> int:
    tests = [
        test_llm_questionnaire_validator_definition_accepts_expected_fields,
        test_llm_questionnaire_validator_definition_rejects_duplicate_check_ids,
        test_automatic_validator_definition_accepts_word_count_rule,
        test_count_comparison_rejects_inverted_between_range,
        test_validation_batch_and_result_artifacts_accept_expected_fields,
        test_validation_result_artifact_accepts_skipped_status,
        test_validation_result_artifact_rejects_included_skipped_status,
        test_validation_state_rejects_malformed_validator_definitions,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
