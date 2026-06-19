from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, cast

from shared.llm.chat_request import _sanitize_cache_request_value
from shared.llm.server_registry import ModelSpec, ServerRegistry, default_server_registry


_OPENAI_ALLOWED_PARAMS = {"dimensions", "encoding_format", "user"}
_OPENAI_CLIENT_OPTION_PARAMS = {"extra_headers", "extra_query", "timeout"}
_IGNORED_PARAMS = {"drop_params"}
_CACHE_IGNORED_PARAMS = {"extra_headers", "extra_query", "timeout"}


@dataclass(frozen=True)
class PreparedEmbeddingsRequest:
    """Normalized embeddings request payload ready for OpenAI-compatible transports."""

    model_ref: str
    spec: ModelSpec
    inputs: list[str]
    request_kwargs: dict[str, Any]
    extra_body: dict[str, Any] | None


def _normalize_inputs(inputs: str | list[str]) -> list[str]:
    if isinstance(inputs, str):
        normalized = [inputs]
    elif isinstance(inputs, list):
        normalized = list(inputs)
    else:
        raise TypeError("inputs must be a string or list of strings.")
    if not normalized:
        raise ValueError("inputs cannot be empty.")
    for index, value in enumerate(normalized):
        if not isinstance(value, str):
            raise TypeError(f"Embedding input at index {index} must be a string.")
        if value == "":
            raise ValueError(f"Embedding input at index {index} cannot be empty.")
    return normalized


def _merge_extra_body(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError("extra_body must be a dict or None.")
    return dict(value)


def _filter_supported_params(params: Dict[str, Any]) -> dict[str, Any]:
    allowed = _OPENAI_ALLOWED_PARAMS | _OPENAI_CLIENT_OPTION_PARAMS
    return {key: value for key, value in params.items() if key in allowed}


def _merge_accept_encoding_header(
    headers: Any,
    *,
    accept_encoding: str | None,
) -> dict[str, Any] | None:
    if headers is None:
        merged: dict[str, Any] = {}
    elif isinstance(headers, dict):
        merged = dict(headers)
    else:
        raise TypeError("extra_headers must be a dict or None.")

    if accept_encoding is None:
        return merged or None

    if accept_encoding != "gzip":
        raise ValueError("accept_encoding must be 'gzip' when provided.")
    merged["Accept-Encoding"] = "gzip"
    return merged


def prepare_embeddings_request(
    inputs: str | list[str],
    *,
    model: Optional[str] = None,
    registry: ServerRegistry | None = None,
    **kwargs: Any,
) -> PreparedEmbeddingsRequest:
    """Normalize an embeddings request for hosted or local OpenAI endpoints."""

    if model is None:
        model = os.getenv("LLM_MODEL", None)
    reg = registry if registry is not None else default_server_registry()
    spec = reg.resolve(model)
    if spec.capabilities.embeddings_protocol is None:
        raise ValueError(
            f"Engine '{spec.engine}' does not support embeddings."
        )

    normalized_inputs = _normalize_inputs(inputs)
    body = dict(kwargs)
    for ignored_key in _IGNORED_PARAMS:
        body.pop(ignored_key, None)

    raw_content_encoding = body.pop("content_encoding", None)
    if raw_content_encoding is not None:
        raise ValueError(
            "content_encoding describes the request body and is not supported here; "
            "use accept_encoding='gzip' for compressed responses."
        )
    raw_accept_encoding = body.pop("accept_encoding", None)
    if raw_accept_encoding is not None and not isinstance(raw_accept_encoding, str):
        raise TypeError("accept_encoding must be a string or None.")

    encoding_format = body.get("encoding_format")
    if encoding_format is None:
        body["encoding_format"] = "float"
    elif encoding_format not in {"float", "base64"}:
        raise ValueError("encoding_format must be 'float' or 'base64'.")

    provided_extra_body = body.pop("extra_body", None)
    supported = _filter_supported_params(body)
    extra_headers = _merge_accept_encoding_header(
        supported.get("extra_headers"),
        accept_encoding=raw_accept_encoding,
    )
    if extra_headers is None:
        supported.pop("extra_headers", None)
    else:
        supported["extra_headers"] = extra_headers

    extra_body_payload = _merge_extra_body(provided_extra_body)
    extra_body: dict[str, Any] | None = extra_body_payload or None
    if spec.capabilities.openai_compatible_extras:
        unsupported = {
            key: value
            for key, value in body.items()
            if key not in supported
        }
        if unsupported:
            extra_body_payload.update(unsupported)
        if extra_body_payload:
            extra_body = extra_body_payload

    return PreparedEmbeddingsRequest(
        model_ref=cast(str, model),
        spec=spec,
        inputs=normalized_inputs,
        request_kwargs=supported,
        extra_body=extra_body,
    )


def build_embeddings_request(prepared: PreparedEmbeddingsRequest) -> dict[str, Any]:
    """Build the OpenAI SDK embeddings request payload."""

    request: dict[str, Any] = {
        **prepared.request_kwargs,
        "model": prepared.spec.model_name,
        "input": prepared.inputs,
    }
    if prepared.extra_body is not None:
        request["extra_body"] = prepared.extra_body
    return request


def build_embeddings_cache_request(prepared: PreparedEmbeddingsRequest) -> dict[str, Any]:
    """Build the canonical raw-request cache payload for an embeddings request."""

    request = build_embeddings_request(prepared)
    sanitized_request = {
        key: value
        for key, value in request.items()
        if key not in _CACHE_IGNORED_PARAMS
    }
    return {
        "transport": "embeddings",
        "server_name": prepared.spec.server_name,
        "engine": prepared.spec.engine,
        "model_ref": prepared.model_ref,
        "base_url": prepared.spec.base_url,
        "request": _sanitize_cache_request_value(sanitized_request),
    }
