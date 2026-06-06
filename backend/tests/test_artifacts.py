from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from prompt_lab.models.artifacts import (
    CaseArtifact,
    ExperimentArtifact,
    OutputConfig,
    RunArtifact,
    RunBatchArtifact,
    RunDefaults,
)


def assert_validation_error(
    model: type[Any], payload: dict[str, Any], message: str
) -> None:
    try:
        model.model_validate(payload)
    except ValidationError as error:
        assert message in str(error)
    else:
        raise AssertionError(f"Expected validation error containing {message!r}")


def valid_run_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "prompt_lab.run/v1",
        "run_id": "run-001",
        "run_batch_id": "batch-001",
        "version": "v001",
        "case_id": "case-a",
        "repeat_index": 1,
        "generator_model": "local/example-small-model",
        "status": "ok",
        "rendered_prompt": "Prompt",
        "raw_output": "Hello",
        "output_type": "text",
        "output_text": "Hello",
    }
    payload.update(overrides)
    return payload


def valid_run_batch_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "prompt_lab.run_batch/v1",
        "run_batch_id": "batch-001",
        "version": "v001",
        "status": "completed",
        "repeat_count": 3,
        "case_order": "case-major",
        "llm_cache": "disabled",
        "started_at": "2026-06-06T10:00:00Z",
        "finished_at": "2026-06-06T10:01:00Z",
        "total_runs": 3,
        "completed_runs": 3,
    }
    payload.update(overrides)
    return payload


def test_pydantic_experiment_artifact_validates() -> None:
    artifact = ExperimentArtifact.model_validate(
        {
            "schema_version": "prompt_lab.experiment/v1",
            "id": "split-scenes",
            "title": "Split scenes",
            "description": "Split scenes.",
            "active_version": "v001",
            "output": {
                "type": "pydantic",
                "model_file": "model.py",
                "model_entrypoint": "model.SceneList",
                "validation_context_from_case": "structured_validation_context",
            },
            "template": {"engine": "jinja2", "path": "prompt.md"},
            "models": {
                "generator_model": "local/example-small-model",
                "judge_model": "openai/example-large-model",
            },
            "run_defaults": {
                "repeat_count": 3,
                "llm_cache": "disabled",
                "case_order": "case-major",
            },
        }
    )

    assert artifact.id == "split-scenes"
    assert artifact.output.type == "pydantic"
    assert artifact.run_defaults.repeat_count == 3


def test_text_experiment_artifact_validates() -> None:
    output = OutputConfig.model_validate({"type": "text"})
    defaults = RunDefaults()

    assert output.type == "text"
    assert defaults.repeat_count == 3
    assert defaults.llm_cache == "disabled"
    assert defaults.case_order == "case-major"


def test_output_config_rejects_invalid_mode_fields() -> None:
    assert_validation_error(
        OutputConfig,
        {"type": "pydantic", "model_file": "model.py"},
        "pydantic output requires model_file and model_entrypoint",
    )
    assert_validation_error(
        OutputConfig,
        {"type": "text", "model_entrypoint": "model.SceneList"},
        "text output cannot include pydantic-only fields",
    )
    assert_validation_error(
        OutputConfig,
        {"type": "text", "validation_context_from_case": "context"},
        "text output cannot include pydantic-only fields",
    )
    assert_validation_error(
        OutputConfig,
        {
            "type": "pydantic",
            "model_file": "",
            "model_entrypoint": "model.SceneList",
        },
        "String should have at least 1 character",
    )
    assert_validation_error(
        OutputConfig,
        {"type": "pydantic", "model_file": "model.py", "model_entrypoint": ""},
        "String should have at least 1 character",
    )


def test_run_defaults_rejects_invalid_values_and_extras() -> None:
    assert_validation_error(RunDefaults, {"repeat_count": 0}, "greater than or equal to 1")
    assert_validation_error(RunDefaults, {"llm_cache": "enabled"}, "Input should be 'disabled'")
    assert_validation_error(RunDefaults, {"unknown": True}, "Extra inputs are not permitted")


def test_case_artifact_validates_variables() -> None:
    case = CaseArtifact.model_validate(
        {
            "schema_version": "prompt_lab.case/v1",
            "id": "case-a",
            "title": "Case A",
            "variables": {"chapter_text": "Hello"},
            "structured_validation_context": {"parts": []},
        }
    )

    assert case.variables["chapter_text"] == "Hello"
    assert case.structured_validation_context == {"parts": []}


def test_run_artifact_accepts_valid_text_and_pydantic_outputs() -> None:
    text_run = RunArtifact.model_validate(valid_run_payload())
    pydantic_run = RunArtifact.model_validate(
        valid_run_payload(
            output_type="pydantic", output_text=None, output_json={"parts": []}
        )
    )

    assert text_run.output_text == "Hello"
    assert pydantic_run.output_json == {"parts": []}


def test_run_artifact_enforces_status_error_fields() -> None:
    assert_validation_error(
        RunArtifact,
        valid_run_payload(status="validation_error", output_text=None),
        "validation_error status requires validation_error",
    )
    assert_validation_error(
        RunArtifact,
        valid_run_payload(
            status="validation_error",
            validation_error="bad json",
            execution_error="timeout",
            output_text=None,
        ),
        "validation_error status cannot include execution_error",
    )
    assert_validation_error(
        RunArtifact,
        valid_run_payload(status="execution_error", output_text=None),
        "execution_error status requires execution_error",
    )
    assert_validation_error(
        RunArtifact,
        valid_run_payload(
            status="execution_error",
            execution_error="timeout",
            validation_error="bad json",
            output_text=None,
        ),
        "execution_error status cannot include validation_error",
    )
    assert_validation_error(
        RunArtifact,
        valid_run_payload(validation_error="bad json"),
        "ok status cannot include validation_error or execution_error",
    )


def test_run_artifact_enforces_output_type_fields() -> None:
    assert_validation_error(
        RunArtifact,
        valid_run_payload(output_text=None),
        "ok text output requires output_text",
    )
    assert_validation_error(
        RunArtifact,
        valid_run_payload(output_json={"parts": []}),
        "text output cannot include output_json",
    )
    assert_validation_error(
        RunArtifact,
        valid_run_payload(output_type="pydantic", output_text=None),
        "ok pydantic output requires output_json",
    )
    assert_validation_error(
        RunArtifact,
        valid_run_payload(output_type="pydantic", output_json={"parts": []}),
        "pydantic output cannot include output_text",
    )
    assert_validation_error(
        RunArtifact,
        valid_run_payload(
            status="validation_error",
            validation_error="bad json",
            output_text=None,
            output_json={"parts": []},
        ),
        "text output cannot include output_json",
    )


def test_run_artifact_rejects_empty_filesystem_keys() -> None:
    for field_name in ("run_id", "run_batch_id", "version", "case_id"):
        assert_validation_error(
            RunArtifact,
            valid_run_payload(**{field_name: ""}),
            "String should have at least 1 character",
        )


def test_run_batch_artifact_enforces_counts_and_keys() -> None:
    empty_batch = RunBatchArtifact.model_validate(
        valid_run_batch_payload(total_runs=0, completed_runs=0)
    )

    assert empty_batch.total_runs == 0
    assert empty_batch.completed_runs == 0

    assert_validation_error(
        RunBatchArtifact,
        valid_run_batch_payload(run_batch_id=""),
        "String should have at least 1 character",
    )
    assert_validation_error(
        RunBatchArtifact,
        valid_run_batch_payload(version=""),
        "String should have at least 1 character",
    )
    assert_validation_error(
        RunBatchArtifact,
        valid_run_batch_payload(completed_runs=-1),
        "greater than or equal to 0",
    )
    assert_validation_error(
        RunBatchArtifact,
        valid_run_batch_payload(total_runs=2, completed_runs=3),
        "completed_runs cannot exceed total_runs",
    )


def main() -> int:
    tests = [
        test_pydantic_experiment_artifact_validates,
        test_text_experiment_artifact_validates,
        test_output_config_rejects_invalid_mode_fields,
        test_run_defaults_rejects_invalid_values_and_extras,
        test_case_artifact_validates_variables,
        test_run_artifact_accepts_valid_text_and_pydantic_outputs,
        test_run_artifact_enforces_status_error_fields,
        test_run_artifact_enforces_output_type_fields,
        test_run_artifact_rejects_empty_filesystem_keys,
        test_run_batch_artifact_enforces_counts_and_keys,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
