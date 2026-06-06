from __future__ import annotations

from prompt_lab.models.artifacts import (
    CaseArtifact,
    ExperimentArtifact,
    OutputConfig,
    RunDefaults,
)


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


def main() -> int:
    tests = [
        test_pydantic_experiment_artifact_validates,
        test_text_experiment_artifact_validates,
        test_case_artifact_validates_variables,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
