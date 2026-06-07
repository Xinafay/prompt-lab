from __future__ import annotations

from pydantic import BaseModel

from prompt_lab.dry_run import dry_structured_response_json, dry_text_response
from prompt_lab.llm_client import PromptLabStructuredValidationError
from prompt_lab.models.artifacts import CaseArtifact
from prompt_lab.runner import iter_case_major, run_structured_case, run_text_case


class DemoOutput(BaseModel):
    name: str


def test_iter_case_major_groups_repeats_per_case() -> None:
    cases = [
        CaseArtifact.model_validate(
            {
                "schema_version": "prompt_lab.case/v1",
                "id": "a",
                "title": "A",
                "variables": {},
            }
        ),
        CaseArtifact.model_validate(
            {
                "schema_version": "prompt_lab.case/v1",
                "id": "b",
                "title": "B",
                "variables": {},
            }
        ),
    ]

    pairs = [(case.id, repeat) for case, repeat in iter_case_major(cases, repeat_count=3)]

    assert pairs == [("a", 1), ("a", 2), ("a", 3), ("b", 1), ("b", 2), ("b", 3)]


def test_run_text_case_saves_text_output() -> None:
    case = CaseArtifact.model_validate(
        {
            "schema_version": "prompt_lab.case/v1",
            "id": "a",
            "title": "A",
            "variables": {"name": "Ada"},
        }
    )

    def generate(model: str, prompt: str) -> object:
        class Result:
            output = f"out:{prompt}"
            usage = {"total_tokens": 2}

        return Result()

    run = run_text_case(
        version="v001",
        run_batch_id="batch-1",
        case=case,
        repeat_index=1,
        generator_model="local/model",
        template_text="Hello {{ name }}",
        generate_text=generate,
    )

    assert run.status == "ok"
    assert run.output_text == "out:Hello Ada"
    assert run.rendered_prompt == "Hello Ada"


def test_run_text_case_stores_execution_errors() -> None:
    case = CaseArtifact.model_validate(
        {
            "schema_version": "prompt_lab.case/v1",
            "id": "a",
            "title": "A",
            "variables": {"name": "Ada"},
        }
    )

    def generate(model: str, prompt: str) -> object:
        raise RuntimeError("transport failed")

    run = run_text_case(
        version="v001",
        run_batch_id="batch-1",
        case=case,
        repeat_index=1,
        generator_model="local/model",
        template_text="Hello {{ name }}",
        generate_text=generate,
    )

    assert run.status == "execution_error"
    assert run.execution_error is not None
    assert "transport failed" in run.execution_error


def test_run_structured_case_saves_json_output() -> None:
    case = CaseArtifact.model_validate(
        {
            "schema_version": "prompt_lab.case/v1",
            "id": "a",
            "title": "A",
            "variables": {"name": "Ada"},
            "structured_validation_context": {"allowed": ["Ada"]},
        }
    )

    def generate(
        model: str,
        prompt: str,
        response_model: type[BaseModel],
        validation_context: dict[str, object] | None,
    ) -> object:
        assert model == "local/model"
        assert prompt == "Hello Ada"
        assert response_model is DemoOutput
        assert validation_context == {"allowed": ["Ada"]}

        class Result:
            output = DemoOutput(name="Ada")
            usage = {"total_tokens": 5}

        return Result()

    run = run_structured_case(
        version="v001",
        run_batch_id="batch-1",
        case=case,
        repeat_index=1,
        generator_model="local/model",
        template_text="Hello {{ name }}",
        response_model=DemoOutput,
        generate_structured=generate,
    )

    assert run.status == "ok"
    assert run.output_json == {"name": "Ada"}
    assert run.output_type == "pydantic"


def test_run_structured_case_stores_validation_errors() -> None:
    case = CaseArtifact.model_validate(
        {
            "schema_version": "prompt_lab.case/v1",
            "id": "a",
            "title": "A",
            "variables": {"name": "Ada"},
        }
    )

    def generate(
        model: str,
        prompt: str,
        response_model: type[BaseModel],
        validation_context: dict[str, object] | None,
    ) -> object:
        raise PromptLabStructuredValidationError("invalid structured output")

    run = run_structured_case(
        version="v001",
        run_batch_id="batch-1",
        case=case,
        repeat_index=1,
        generator_model="local/model",
        template_text="Hello {{ name }}",
        response_model=DemoOutput,
        generate_structured=generate,
    )

    assert run.status == "validation_error"
    assert run.validation_error is not None
    assert "invalid structured output" in run.validation_error


def test_run_structured_case_stores_execution_errors() -> None:
    case = CaseArtifact.model_validate(
        {
            "schema_version": "prompt_lab.case/v1",
            "id": "a",
            "title": "A",
            "variables": {"name": "Ada"},
        }
    )

    def generate(
        model: str,
        prompt: str,
        response_model: type[BaseModel],
        validation_context: dict[str, object] | None,
    ) -> object:
        raise RuntimeError("transport failed")

    run = run_structured_case(
        version="v001",
        run_batch_id="batch-1",
        case=case,
        repeat_index=1,
        generator_model="local/model",
        template_text="Hello {{ name }}",
        response_model=DemoOutput,
        generate_structured=generate,
    )

    assert run.status == "execution_error"
    assert run.execution_error is not None
    assert "transport failed" in run.execution_error


def test_dry_run_text_response_is_deterministic() -> None:
    assert dry_text_response("case-a", 2) == "Dry run response for case case-a repeat 2."


def test_dry_run_structured_response_matches_model() -> None:
    response = dry_structured_response_json(DemoOutput)

    assert DemoOutput.model_validate_json(response).name == "dry-run"


def main() -> int:
    tests = [
        test_iter_case_major_groups_repeats_per_case,
        test_run_text_case_saves_text_output,
        test_run_text_case_stores_execution_errors,
        test_run_structured_case_saves_json_output,
        test_run_structured_case_stores_validation_errors,
        test_run_structured_case_stores_execution_errors,
        test_dry_run_text_response_is_deterministic,
        test_dry_run_structured_response_matches_model,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
