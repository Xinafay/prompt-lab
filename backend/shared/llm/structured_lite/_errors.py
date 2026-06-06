from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import ValidationError

from shared.llm.structured_lite._types import _CandidateValidation, _to_jsonable


_STRUCTURAL_ERROR_TYPES: frozenset[str] = frozenset(
    {
        "missing",
        "model_type",
        "model_attributes_type",
        "dict_type",
        "list_type",
        "tuple_type",
        "set_type",
        "frozen_set_type",
        "int_type",
        "int_parsing",
        "int_from_float",
        "string_type",
        "bool_type",
        "bool_parsing",
        "float_type",
        "float_parsing",
        "bytes_type",
        "none_required",
        "literal_error",
        "enum",
        "union_tag_invalid",
        "union_tag_not_found",
        "is_instance_of",
        "is_subclass_of",
        "callable_type",
        "extra_forbidden",
    }
)

_MESSAGE_PREFIXES_TO_STRIP = ("Value error, ", "Assertion failed, ")


def _classify_validation_error(error: Exception) -> _CandidateValidation:
    if not isinstance(error, ValidationError):
        return _CandidateValidation(
            status="exception",
            structural_errors=0,
            constraint_errors=0,
            error=error,
        )
    structural = 0
    constraint = 0
    for detail in error.errors(include_url=False):
        if detail.get("type") in _STRUCTURAL_ERROR_TYPES:
            structural += 1
        else:
            constraint += 1
    status: Literal["structural", "constraint"] = "structural" if structural > 0 else "constraint"
    return _CandidateValidation(
        status=status,
        structural_errors=structural,
        constraint_errors=constraint,
        error=error,
    )


def _format_structured_error(error: Exception) -> str:
    if not isinstance(error, ValidationError):
        return str(error)

    lines = [f"{error.error_count()} validation error(s) for {error.title}"]
    for index, detail in enumerate(error.errors(include_url=False, include_input=True), start=1):
        error_type = detail.get("type")
        location = _format_validation_location(detail.get("loc", ()))

        if error_type == "missing" and location is not None:
            lines.append(f"\n{index}. Field `{location}` is required.")
        elif error_type == "extra_forbidden" and location is not None:
            lines.append(f"\n{index}. Extra field `{location}` is not permitted.")
        else:
            message = _clean_validation_message(str(detail.get("msg", "")))
            if location is None:
                lines.append(f"\n{index}. {message}")
            else:
                lines.append(f"\n{index}. At `{location}`: {message}")
                if "input" in detail:
                    lines.append("   Received value:")
                    lines.append(_indent_json(detail["input"], spaces=6))
    return "\n".join(lines)


def _format_validation_location(location: Any) -> str | None:
    if not isinstance(location, tuple) or not location:
        return None
    return ".".join(str(part) for part in location)


def _clean_validation_message(message: str) -> str:
    for prefix in _MESSAGE_PREFIXES_TO_STRIP:
        if message.startswith(prefix):
            return message[len(prefix):].strip()
    return message.strip()


def _indent_json(value: Any, *, spaces: int) -> str:
    text = json.dumps(_to_jsonable(value), ensure_ascii=False, indent=2)
    prefix = " " * spaces
    return "\n".join(f"{prefix}{line}" for line in text.splitlines())
