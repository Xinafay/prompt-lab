from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeAlias, TypeVar


JsonValue: TypeAlias = (
    dict[str, "JsonValue"]
    | list["JsonValue"]
    | str
    | int
    | float
    | bool
    | None
)

T = TypeVar("T")


def _clean_reasoning_content(reasoning_content: str | None) -> str | None:
    if not isinstance(reasoning_content, str):
        return None
    reasoning_content = reasoning_content.strip()
    return reasoning_content or None


@dataclass(frozen=True)
class LlmResponse:
    """Raw LLM response with projected text, usage, and exposed reasoning text."""

    content: str
    usage: dict[str, Any] | None = None
    reasoning_content: str | None = None
    raw_response: Any | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "reasoning_content",
            _clean_reasoning_content(self.reasoning_content),
        )

    def to_json(self) -> dict[str, Any]:
        """Serialize the full cacheable response payload."""

        payload: dict[str, Any] = {"content": self.content}
        if self.usage is not None:
            payload["usage"] = self.usage
        if self.reasoning_content is not None:
            payload["reasoning_content"] = self.reasoning_content
        if self.raw_response is not None:
            payload["raw_response"] = self.raw_response
        return payload

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "LlmResponse":
        """Restore a cached response payload."""

        content = payload.get("content")
        if not isinstance(content, str):
            raise ValueError("Cached LLM response is missing string content.")
        usage = payload.get("usage")
        if usage is not None and not isinstance(usage, dict):
            usage = {"value": usage}
        reasoning_content = payload.get("reasoning_content")
        return cls(
            content=content,
            usage=usage,
            reasoning_content=reasoning_content if isinstance(reasoning_content, str) else None,
            raw_response=payload.get("raw_response"),
        )


def assistant_conversation_message(content: str, reasoning_content: str | None = None) -> dict[str, Any]:
    """Build an assistant transcript entry, omitting empty reasoning content."""

    message: dict[str, Any] = {"role": "assistant", "content": content}
    cleaned_reasoning = _clean_reasoning_content(reasoning_content)
    if cleaned_reasoning is not None:
        message["reasoning_content"] = cleaned_reasoning
    return message


@dataclass(frozen=True)
class ChatResult(Generic[T]):
    """LLM response payload with optional usage metadata."""

    output: T
    usage: dict[str, Any] | None
    conversation: list[dict[str, Any]]
