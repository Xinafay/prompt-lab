from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast


def _normalize_embeddings(value: Any) -> list[list[float]]:
    if not isinstance(value, list):
        raise ValueError("Embeddings payload must be a list.")
    embeddings: list[list[float]] = []
    for vector_index, raw_vector in enumerate(value):
        if not isinstance(raw_vector, list):
            raise ValueError(f"Embedding at index {vector_index} must be a list.")
        vector: list[float] = []
        for item_index, item in enumerate(raw_vector):
            if isinstance(item, bool) or not isinstance(item, (int, float)):
                raise ValueError(
                    f"Embedding value at index {vector_index}.{item_index} must be numeric."
                )
            vector.append(float(item))
        embeddings.append(vector)
    return embeddings


@dataclass(frozen=True)
class EmbeddingsResponse:
    """Raw embeddings response with projected vectors and optional usage metadata."""

    embeddings: list[list[float]]
    usage: dict[str, Any] | None = None
    model: str | None = None
    raw_response: Any | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "embeddings", _normalize_embeddings(self.embeddings))

    def to_json(self) -> dict[str, Any]:
        """Serialize the cacheable embeddings response payload."""

        payload: dict[str, Any] = {"embeddings": self.embeddings}
        if self.usage is not None:
            payload["usage"] = self.usage
        if self.model is not None:
            payload["model"] = self.model
        if self.raw_response is not None:
            payload["raw_response"] = self.raw_response
        return payload

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "EmbeddingsResponse":
        """Restore a cached embeddings response payload."""

        usage = payload.get("usage")
        if usage is not None and not isinstance(usage, dict):
            usage = {"value": usage}
        model = payload.get("model")
        return cls(
            embeddings=_normalize_embeddings(payload.get("embeddings")),
            usage=cast(dict[str, Any] | None, usage),
            model=model if isinstance(model, str) else None,
            raw_response=payload.get("raw_response"),
        )


@dataclass(frozen=True)
class EmbeddingsResult:
    """Public embeddings result returned by ``get_embeddings``."""

    output: list[list[float]]
    usage: dict[str, Any] | None
    model: str | None = None
    raw_response: Any | None = None
