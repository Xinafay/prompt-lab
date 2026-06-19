from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, TypeAlias, TypeVar

from pydantic import BaseModel, TypeAdapter

from shared.llm.chat_result import LlmResponse


StructuredOutputT = TypeVar("StructuredOutputT")

LlmCaller: TypeAlias = Callable[[list[dict[str, Any]]], LlmResponse]


class StructuredLiteExhaustedError(Exception):
    """Raised when structured_lite exhausts all repair attempts.

    Attributes:
        error: The last validation error.
        conversation: Formatted prompt and raw model responses exchanged during repair,
            as ``{"role": ..., "content": ...}`` dicts (same format as the messages API).
    """

    def __init__(self, error: Exception, conversation: list[dict[str, Any]]) -> None:
        super().__init__(str(error))
        self.error = error
        self.conversation = conversation


@dataclass(frozen=True)
class _CandidateValidation:
    status: Literal["ok", "structural", "constraint", "exception"]
    structural_errors: int
    constraint_errors: int
    error: Exception | None

    @property
    def score(self) -> tuple[int, int]:
        return (self.structural_errors, self.constraint_errors)


@dataclass(frozen=True)
class _Candidate:
    payload: Any
    source_index: int
    source_kind: Literal["fenced", "brace", "raw_text"]
    transform: Literal[
        "raw", "sanitized", "unwrapped", "sanitized+unwrapped", "value_extracted"
    ]
    validation: _CandidateValidation | None = None


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, BaseException):
        return str(value)
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    return value


def _restore_structured_output(
    response_model: Any,
    payload: Any,
    *,
    validation_context: dict[str, Any] | None = None,
) -> Any:
    if hasattr(response_model, "model_validate"):
        return response_model.model_validate(payload, context=validation_context)
    return TypeAdapter(response_model).validate_python(payload, context=validation_context)


def _serialize_output(value: Any) -> str:
    return json.dumps(_to_jsonable(value), ensure_ascii=False)
