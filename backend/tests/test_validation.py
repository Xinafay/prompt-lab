from __future__ import annotations

from typing import Any

from prompt_lab.models.artifacts import CaseArtifact, RunArtifact
from prompt_lab.models.validators import LlmQuestionnaireValidatorDefinition
from prompt_lab.validation import build_llm_validator_prompt, validate_llm_check_ids


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
            "schema_version": "prompt_lab.case/v2",
            "id": "case-a",
            "title": "Case A",
            "stores": {},
            "bindings": {},
        }
    )


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
    assert "<<MODEL>>" in prompt
    assert "Rendered prompt should stay hidden" not in prompt
    assert "secret_context" not in prompt


def test_validate_llm_check_ids_rejects_missing_check_ids() -> None:
    try:
        validate_llm_check_ids(_validator(), [])
    except ValueError as exc:
        assert "missing: has-answer" in str(exc)
    else:
        raise AssertionError("Expected missing check ids to be rejected")


def main() -> int:
    tests = [
        test_build_llm_validator_prompt_respects_output_only_input_scope,
        test_validate_llm_check_ids_rejects_missing_check_ids,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
