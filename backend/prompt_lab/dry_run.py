from __future__ import annotations

import json
from types import NoneType, UnionType
from typing import Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel


def dry_text_response(case_id: str, repeat_index: int) -> str:
    return f"Dry run response for case {case_id} repeat {repeat_index}."


def dry_structured_response_json(
    response_model: type[BaseModel],
    validation_context: dict[str, Any] | None = None,
) -> str:
    return json.dumps(
        sample_model_payload(response_model, validation_context=validation_context),
        ensure_ascii=False,
    )


def dry_judgment_response_json(
    *,
    version: str,
    run_batch_id: str,
    judge_model: str,
) -> str:
    return json.dumps(
        {
            "schema_version": "prompt_lab.judgment/v1",
            "judgment_id": "dry-run-judgment",
            "version": version,
            "run_batch_ids": [run_batch_id],
            "judge_model": judge_model,
            "summary": "Dry-run judgment generated from deterministic fake LLM JSON.",
            "what_looks_correct": [
                {
                    "finding_id": "dry-run-correct",
                    "description": "The review workflow produced parseable run evidence.",
                    "evidence": [f"{run_batch_id} dry-run evidence"],
                }
            ],
            "findings": [
                {
                    "finding_id": "dry-run-finding",
                    "severity": "optional",
                    "area": "prompt",
                    "category": "dry_run",
                    "description": "Dry-run placeholder finding for artifact workflow validation.",
                    "evidence": [f"{run_batch_id} dry-run evidence"],
                    "suggested_change": "Replace dry-run output with a live judge review.",
                }
            ],
            "decision_points": [],
        },
        ensure_ascii=False,
    )


def dry_validator_response_json(check_ids: list[str]) -> str:
    return json.dumps(
        {
            "check_results": [
                {
                    "check_id": check_id,
                    "verdict": "yes",
                    "comment": f"dry-run validator response for {check_id}",
                }
                for check_id in check_ids
            ]
        },
        ensure_ascii=False,
    )


def dry_proposal_response_json(
    *,
    prompt_template: str,
    model_source: str | None,
    output_type: str,
) -> str:
    payload = {
        "prompt_md": prompt_template
        or "Dry-run prompt proposal placeholder.",
        "model_py": model_source if output_type == "pydantic" else None,
        "rationale_md": (
            "Dry-run proposal generated from deterministic fake LLM JSON. "
            "No live model was called."
        ),
    }
    return json.dumps(payload, ensure_ascii=False)


def sample_model_payload(
    annotation: Any,
    *,
    field_name: str | None = None,
    validation_context: dict[str, Any] | None = None,
) -> Any:
    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin in {list, tuple, set, frozenset}:
        item_annotation = args[0] if args else str
        return [
            sample_model_payload(
                item_annotation,
                validation_context=validation_context,
            )
        ]

    if origin in {UnionType, Union}:
        for arg in args:
            if arg is NoneType:
                continue
            return sample_model_payload(
                arg,
                field_name=field_name,
                validation_context=validation_context,
            )
        return None

    if origin is Literal:
        return args[0] if args else "dry-run"

    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        if getattr(annotation, "__pydantic_root_model__", False):
            root_field = annotation.model_fields["root"]
            return sample_model_payload(
                root_field.annotation,
                field_name="root",
                validation_context=validation_context,
            )
        return {
            name: sample_model_payload(
                field.annotation,
                field_name=name,
                validation_context=validation_context,
            )
            for name, field in annotation.model_fields.items()
            if field.is_required()
        }

    if annotation is str:
        return "dry-run"
    if annotation is int:
        return _sample_int(field_name, validation_context)
    if annotation is float:
        return 1.0
    if annotation is bool:
        return True
    if annotation is dict or origin is dict:
        return {}
    if annotation is Any:
        return "dry-run"
    return "dry-run"


def _sample_int(
    field_name: str | None,
    validation_context: dict[str, Any] | None,
) -> int:
    if field_name == "paragraph_number" and validation_context is not None:
        parts = validation_context.get("parts")
        if isinstance(parts, list) and parts:
            last_part = parts[-1]
            if isinstance(last_part, dict):
                first = last_part.get("first_paragraph_number")
                paragraphs = last_part.get("paragraphs")
                if isinstance(first, int) and isinstance(paragraphs, list):
                    return first + len(paragraphs) - 1
    if field_name == "identifier":
        return 1
    return 1
