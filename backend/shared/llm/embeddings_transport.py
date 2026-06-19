from __future__ import annotations

import array
import base64
from typing import Any, cast

from shared.llm.embeddings_request import (
    PreparedEmbeddingsRequest,
    build_embeddings_request,
)
from shared.llm.embeddings_result import EmbeddingsResponse
from shared.llm.transports.usage import normalize_usage
import shared.llm.transports.openai_client as _client_impl
from shared.llm.transports.openai_client import _get_openai_client


_OPENAI_CLIENT_CACHE = _client_impl._OPENAI_CLIENT_CACHE


def _to_plain_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _to_plain_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_plain_payload(item) for item in value]
    if hasattr(value, "model_dump"):
        return _to_plain_payload(value.model_dump())
    if hasattr(value, "dict"):
        return _to_plain_payload(value.dict())
    return value


def _plain_embedding_item(item: Any, *, fallback_index: int) -> dict[str, Any]:
    if isinstance(item, dict):
        return dict(item)
    if hasattr(item, "embedding"):
        payload: dict[str, Any] = {
            "index": getattr(item, "index", fallback_index),
            "embedding": getattr(item, "embedding"),
        }
        object_value = getattr(item, "object", None)
        if object_value is not None:
            payload["object"] = object_value
        return payload
    return _to_plain_payload(item)


def _to_plain_embeddings_response(response: Any) -> Any:
    if isinstance(response, dict):
        return _to_plain_payload(response)
    data = getattr(response, "data", None)
    if isinstance(data, list):
        payload: dict[str, Any] = {
            "data": [
                _plain_embedding_item(item, fallback_index=index)
                for index, item in enumerate(data)
            ]
        }
        model = getattr(response, "model", None)
        if model is not None:
            payload["model"] = model
        object_value = getattr(response, "object", None)
        if object_value is not None:
            payload["object"] = object_value
        usage = getattr(response, "usage", None)
        if usage is not None:
            payload["usage"] = _to_plain_payload(usage)
        return payload
    return _to_plain_payload(response)


def _item_payload(item: Any, *, fallback_index: int) -> dict[str, Any]:
    if isinstance(item, dict):
        return dict(item)
    if hasattr(item, "embedding"):
        return _plain_embedding_item(item, fallback_index=fallback_index)
    if hasattr(item, "__dict__"):
        return dict(item.__dict__)
    if hasattr(item, "model_dump"):
        return cast(dict[str, Any], item.model_dump())
    if hasattr(item, "dict"):
        return cast(dict[str, Any], item.dict())
    raise ValueError(f"Unsupported embedding item payload: {item!r}")


def _extract_ordered_embeddings(response: Any) -> list[list[float]]:
    data = getattr(response, "data", None)
    if data is None and isinstance(response, dict):
        data = response.get("data")
    if not isinstance(data, list):
        raise ValueError("Embeddings response is missing data list.")

    indexed: list[tuple[int, list[float]]] = []
    for fallback_index, item in enumerate(data):
        payload = _item_payload(item, fallback_index=fallback_index)
        raw_index = payload.get("index", fallback_index)
        if isinstance(raw_index, bool) or not isinstance(raw_index, int):
            raise ValueError(f"Embedding index must be an integer, got {raw_index!r}.")
        raw_embedding = payload.get("embedding")
        if isinstance(raw_embedding, str):
            raw_embedding = _decode_base64_embedding(raw_embedding, index=raw_index)
        if not isinstance(raw_embedding, list):
            raise ValueError(f"Embedding at index {raw_index} must be a list.")
        vector: list[float] = []
        for value in raw_embedding:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"Embedding at index {raw_index} contains non-numeric value.")
            vector.append(float(value))
        indexed.append((raw_index, vector))

    return [vector for _index, vector in sorted(indexed, key=lambda item: item[0])]


def _decode_base64_embedding(value: str, *, index: int) -> list[float]:
    try:
        decoded = base64.b64decode(value, validate=True)
    except Exception as exc:
        raise ValueError(f"Embedding at index {index} is not valid base64.") from exc
    if len(decoded) % 4 != 0:
        raise ValueError(f"Embedding at index {index} has invalid float32 byte length.")
    vector = array.array("f")
    vector.frombytes(decoded)
    return [float(item) for item in vector]


def _call_embeddings(request: dict[str, Any], prepared: PreparedEmbeddingsRequest) -> Any:
    client = _get_openai_client(prepared)
    return client.embeddings.create(**request)


def execute_prepared_embeddings_request(
    prepared: PreparedEmbeddingsRequest,
) -> EmbeddingsResponse:
    """Execute a prepared embeddings request through the direct OpenAI SDK."""

    request = build_embeddings_request(prepared)
    response = _call_embeddings(request, prepared)
    usage = normalize_usage(getattr(response, "usage", None))
    if usage is None and isinstance(response, dict):
        usage = normalize_usage(response.get("usage"))
    model = getattr(response, "model", None)
    if model is None and isinstance(response, dict):
        model = response.get("model")
    return EmbeddingsResponse(
        embeddings=_extract_ordered_embeddings(response),
        usage=usage,
        model=model if isinstance(model, str) else None,
        raw_response=_to_plain_embeddings_response(response),
    )
