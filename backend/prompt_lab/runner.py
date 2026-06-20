from __future__ import annotations

import traceback
from collections.abc import Callable, Iterable, Iterator
from typing import Any

from pydantic import BaseModel

from prompt_lab.case_context import materialize_case_context
from prompt_lab.llm_client import PromptLabStructuredValidationError
from prompt_lab.models.artifacts import CaseArtifact, RunArtifact
from prompt_lab.template_renderer import render_prompt


def iter_case_major(
    cases: Iterable[CaseArtifact], *, repeat_count: int
) -> Iterator[tuple[CaseArtifact, int]]:
    """Yield case/repeat pairs as A-A-A-B-B-B."""
    for case in cases:
        for repeat_index in range(1, repeat_count + 1):
            yield case, repeat_index


def run_text_case(
    *,
    version: str,
    run_batch_id: str,
    case: CaseArtifact,
    repeat_index: int,
    generator_model: str,
    template_text: str,
    generate_text: Callable[[str, str], Any],
) -> RunArtifact:
    context = materialize_case_context(case)
    rendered_prompt = render_prompt(template_text, context)
    run_id = f"{run_batch_id}-{case.id}-repeat-{repeat_index:03d}"
    try:
        result = generate_text(generator_model, rendered_prompt)
    except Exception:
        return RunArtifact(
            schema_version="prompt_lab.run/v1",
            run_id=run_id,
            run_batch_id=run_batch_id,
            version=version,
            case_id=case.id,
            repeat_index=repeat_index,
            generator_model=generator_model,
            status="execution_error",
            rendered_prompt=rendered_prompt,
            output_type="text",
            execution_error=traceback.format_exc(),
        )
    output = getattr(result, "output", None)
    return RunArtifact(
        schema_version="prompt_lab.run/v1",
        run_id=run_id,
        run_batch_id=run_batch_id,
        version=version,
        case_id=case.id,
        repeat_index=repeat_index,
        generator_model=generator_model,
        status="ok",
        rendered_prompt=rendered_prompt,
        raw_output=output,
        output_type="text",
        output_text=output,
        usage=getattr(result, "usage", {}) or {},
    )


def run_structured_case(
    *,
    version: str,
    run_batch_id: str,
    case: CaseArtifact,
    repeat_index: int,
    generator_model: str,
    template_text: str,
    response_model: type[BaseModel],
    generate_structured: Callable[
        [str, str, type[BaseModel], dict[str, Any] | None], Any
    ],
) -> RunArtifact:
    context = materialize_case_context(case)
    rendered_prompt = render_prompt(template_text, context)
    run_id = f"{run_batch_id}-{case.id}-repeat-{repeat_index:03d}"
    try:
        result = generate_structured(
            generator_model,
            rendered_prompt,
            response_model,
            context,
        )
        output = getattr(result, "output")
    except PromptLabStructuredValidationError as exc:
        return RunArtifact(
            schema_version="prompt_lab.run/v1",
            run_id=run_id,
            run_batch_id=run_batch_id,
            version=version,
            case_id=case.id,
            repeat_index=repeat_index,
            generator_model=generator_model,
            status="validation_error",
            rendered_prompt=rendered_prompt,
            output_type="pydantic",
            raw_output=exc.raw_output,
            validation_error=traceback.format_exc(),
        )
    except Exception:
        return RunArtifact(
            schema_version="prompt_lab.run/v1",
            run_id=run_id,
            run_batch_id=run_batch_id,
            version=version,
            case_id=case.id,
            repeat_index=repeat_index,
            generator_model=generator_model,
            status="execution_error",
            rendered_prompt=rendered_prompt,
            output_type="pydantic",
            execution_error=traceback.format_exc(),
        )
    return RunArtifact(
        schema_version="prompt_lab.run/v1",
        run_id=run_id,
        run_batch_id=run_batch_id,
        version=version,
        case_id=case.id,
        repeat_index=repeat_index,
        generator_model=generator_model,
        status="ok",
        rendered_prompt=rendered_prompt,
        raw_output=output.model_dump_json(),
        output_type="pydantic",
        output_json=output.model_dump(mode="json"),
        usage=getattr(result, "usage", {}) or {},
    )
