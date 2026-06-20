from __future__ import annotations

from prompt_lab.automatic_validators import execute_automatic_validator
from prompt_lab.models.artifacts import RunArtifact
from prompt_lab.models.validators import AutomaticValidatorDefinition


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
        "rendered_prompt": "Prompt",
        "raw_output": "one two three",
        "output_type": "text",
        "output_text": "one two three",
        "usage": {},
    }
    payload.update(overrides)
    return RunArtifact.model_validate(payload)


def _automatic_validator(rule: dict[str, object]) -> AutomaticValidatorDefinition:
    return AutomaticValidatorDefinition.model_validate(
        {
            "schema_version": "prompt_lab.validator/v1",
            "validator_id": "auto-length",
            "type": "automatic",
            "title": "Automatic length",
            "checks": [
                {
                    "check_id": "check-001",
                    "title": "Check 001",
                    "rule": rule,
                }
            ],
        }
    )


def test_word_count_rule_passes_lte_limit() -> None:
    result = execute_automatic_validator(
        "validation-001",
        _run_artifact(output_text="one two three", raw_output="one two three"),
        _automatic_validator(
            {
                "kind": "word_count",
                "source": "output_text",
                "comparison": {"op": "lte", "value": 3},
            }
        ),
    )

    assert result.schema_version == "prompt_lab.validation_result/v1"
    assert result.validation_result_id == (
        "validation-001-case-a-repeat-001-auto-length"
    )
    assert result.status == "ok"
    assert result.included_in_judge is True
    assert result.execution_error is None
    assert result.check_results[0].grade == 5
    assert result.check_results[0].metrics == {"value": 3}


def test_word_count_rule_failure_maps_to_min_grade() -> None:
    result = execute_automatic_validator(
        "validation-001",
        _run_artifact(output_text="one two three four", raw_output="one two three four"),
        _automatic_validator(
            {
                "kind": "word_count",
                "source": "output_text",
                "comparison": {"op": "lte", "value": 3},
            }
        ),
    )

    assert result.status == "ok"
    assert result.check_results[0].grade == 1
    assert result.check_results[0].metrics == {"value": 4}


def test_json_path_count_counts_list_items_at_path() -> None:
    result = execute_automatic_validator(
        "validation-001",
        _run_artifact(
            output_type="pydantic",
            output_text=None,
            output_json={"scenes": [{"title": "One"}, {"title": "Two"}]},
        ),
        _automatic_validator(
            {
                "kind": "json_path_count",
                "source": "output_json",
                "path": "scenes",
                "comparison": {"op": "gte", "value": 2},
            }
        ),
    )

    assert result.status == "ok"
    assert result.check_results[0].grade == 5
    assert result.check_results[0].metrics == {"value": 2}


def test_unavailable_output_json_source_records_error_result() -> None:
    result = execute_automatic_validator(
        "validation-001",
        _run_artifact(
            status="validation_error",
            output_type="pydantic",
            output_text=None,
            output_json=None,
            validation_error="invalid json",
        ),
        _automatic_validator(
            {
                "kind": "json_path_count",
                "source": "output_json",
                "path": "scenes",
                "comparison": {"op": "gte", "value": 2},
            }
        ),
    )

    assert result.status == "error"
    assert result.included_in_judge is False
    assert result.check_results == []
    assert result.execution_error is not None


def main() -> int:
    tests = [
        test_word_count_rule_passes_lte_limit,
        test_word_count_rule_failure_maps_to_min_grade,
        test_json_path_count_counts_list_items_at_path,
        test_unavailable_output_json_source_records_error_result,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
