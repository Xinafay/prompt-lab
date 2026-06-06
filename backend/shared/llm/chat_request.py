from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, cast

from shared.llm.server_registry import ModelSpec, ServerRegistry, default_server_registry


# Supported chat-completions parameters from the OpenAI Python SDK.
_OPENAI_ALLOWED_PARAMS = {
    "audio",
    "frequency_penalty",
    "function_call",
    "functions",
    "logit_bias",
    "logprobs",
    "max_completion_tokens",
    "max_tokens",
    "metadata",
    "modalities",
    "n",
    "parallel_tool_calls",
    "prediction",
    "presence_penalty",
    "prompt_cache_key",
    "prompt_cache_retention",
    "reasoning_effort",
    "response_format",
    "safety_identifier",
    "seed",
    "service_tier",
    "stop",
    "store",
    "stream",
    "stream_options",
    "temperature",
    "tool_choice",
    "tools",
    "top_logprobs",
    "top_p",
    "user",
    "verbosity",
    "web_search_options",
}
_OPENAI_CLIENT_OPTION_PARAMS = {"extra_headers", "extra_query", "timeout"}
_IGNORED_PARAMS = {"drop_params"}
_CACHE_IGNORED_PARAMS = {"stream", "stream_options", "extra_headers", "extra_query", "timeout"}


@dataclass(frozen=True)
class PreparedChatRequest:
    """Normalized request payload ready for the supported OpenAI transports."""

    model_ref: str
    spec: ModelSpec
    messages: list[dict[str, Any]]
    request_kwargs: dict[str, Any]
    extra_body: dict[str, Any] | None


def _default_transport_name(prepared: PreparedChatRequest) -> str:
    if prepared.spec.server_type == "openai":
        return "responses"
    return "chat_completions"


def resolve_model_spec(model: Optional[str]) -> ModelSpec:
    """Resolve a model reference like 'openai/gpt-5-mini' using .servers.jsonc."""
    return default_server_registry().resolve(model)


def is_local_model(model: Optional[str] = None) -> bool:
    """Return True if the model resolves to a local server."""

    if model is None:
        model = os.getenv("LLM_MODEL", None)
    return resolve_model_spec(model).server_type == "local"


def _merge_local_extra_body(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError("extra_body must be a dict or None.")
    return dict(value)


def _filter_supported_params(params: Dict[str, Any]) -> dict[str, Any]:
    allowed = _OPENAI_ALLOWED_PARAMS | _OPENAI_CLIENT_OPTION_PARAMS
    return {key: value for key, value in params.items() if key in allowed}


def prepare_chat_request(
    messages: list[dict[str, Any]],
    *,
    model: Optional[str] = None,
    registry: ServerRegistry | None = None,
    **kwargs: Any,
) -> PreparedChatRequest:
    """Normalize a chat completion request for hosted or local OpenAI endpoints."""

    if model is None:
        model = os.getenv("LLM_MODEL", None)
    reg = registry if registry is not None else default_server_registry()
    spec = reg.resolve(model)

    normalized_messages = [dict(message) for message in messages]
    body = dict(kwargs)
    for ignored_key in _IGNORED_PARAMS:
        body.pop(ignored_key, None)

    if spec.server_type == "local":
        start = body.pop("start", None)
        if start is not None:
            normalized_messages = normalized_messages + [{"role": "assistant", "content": start}]
    else:
        body.pop("start", None)

    provided_extra_body = body.pop("extra_body", None)
    supported = _filter_supported_params(body)

    extra_body: dict[str, Any] | None = None
    if spec.server_type == "local":
        extra_body_payload = _merge_local_extra_body(provided_extra_body)
        unsupported = {
            key: value
            for key, value in body.items()
            if key not in supported
        }
        if unsupported:
            extra_body_payload.update(unsupported)
        if extra_body_payload:
            extra_body = extra_body_payload

    return PreparedChatRequest(
        model_ref=cast(str, model),
        spec=spec,
        messages=normalized_messages,
        request_kwargs=supported,
        extra_body=extra_body,
    )


def _merge_stream_options(
    raw_stream_options: Any,
    *,
    include_usage: bool,
) -> dict[str, Any] | None:
    if raw_stream_options is None:
        return {"include_usage": True} if include_usage else None
    if not isinstance(raw_stream_options, dict):
        raise TypeError("stream_options must be a dict or None.")
    stream_options = dict(raw_stream_options)
    if include_usage:
        stream_options.setdefault("include_usage", True)
    return stream_options


def _build_local_stream_options(
    prepared: PreparedChatRequest,
    *,
    stream_enabled: bool,
) -> dict[str, Any] | None:
    raw_stream_options = prepared.request_kwargs.get("stream_options")
    return _merge_stream_options(raw_stream_options, include_usage=stream_enabled)


def _build_chat_completion_request(
    prepared: PreparedChatRequest,
    *,
    stream_enabled: bool,
) -> dict[str, Any]:
    stream_options = _build_local_stream_options(prepared, stream_enabled=stream_enabled)
    request: dict[str, Any] = {
        **prepared.request_kwargs,
        "model": prepared.spec.model_name,
        "messages": prepared.messages,
        "stream": stream_enabled,
    }
    if stream_options is not None:
        request["stream_options"] = stream_options
    if prepared.extra_body is not None:
        request["extra_body"] = prepared.extra_body
    return request


def _build_openai_responses_input(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for index, message in enumerate(messages):
        role = message.get("role")
        if not isinstance(role, str) or role not in {"user", "assistant", "system", "developer"}:
            raise ValueError(f"Unsupported message role at index {index}: {role!r}")
        content = message.get("content")
        if isinstance(content, (str, list)):
            normalized_content: str | list[Any] = content
        elif content is None:
            normalized_content = ""
        else:
            normalized_content = str(content)
        payload.append({"role": role, "content": normalized_content})
    return payload


def _build_openai_responses_request(
    prepared: PreparedChatRequest,
    *,
    stream_enabled: bool,
    reasoning_summary_enabled: bool,
) -> dict[str, Any]:
    request_kwargs = prepared.request_kwargs
    request: dict[str, Any] = {
        "model": prepared.spec.model_name,
        "input": _build_openai_responses_input(prepared.messages),
        "stream": stream_enabled,
    }

    for key in (
        "extra_headers",
        "extra_query",
        "metadata",
        "prompt_cache_key",
        "prompt_cache_retention",
        "safety_identifier",
        "service_tier",
        "store",
        "stream_options",
        "temperature",
        "timeout",
        "top_p",
        "user",
    ):
        value = request_kwargs.get(key)
        if value is not None:
            request[key] = value

    max_output_tokens = request_kwargs.get("max_completion_tokens")
    if max_output_tokens is None:
        max_output_tokens = request_kwargs.get("max_tokens")
    if isinstance(max_output_tokens, (int, float)) and not isinstance(max_output_tokens, bool):
        request["max_output_tokens"] = int(max_output_tokens)

    reasoning: dict[str, Any] = {}
    reasoning_effort = request_kwargs.get("reasoning_effort")
    if isinstance(reasoning_effort, str) and reasoning_effort:
        reasoning["effort"] = reasoning_effort
    if reasoning_summary_enabled:
        reasoning["summary"] = "auto"
    if reasoning:
        request["reasoning"] = reasoning

    verbosity = request_kwargs.get("verbosity")
    if isinstance(verbosity, str) and verbosity:
        request["text"] = {"verbosity": verbosity}

    return request


def _sanitize_cache_request_value(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if key in _CACHE_IGNORED_PARAMS or item is None:
                continue
            result[key] = _sanitize_cache_request_value(item)
        return result
    if isinstance(value, list):
        return [_sanitize_cache_request_value(item) for item in value]
    return value


def build_cache_request(
    prepared: PreparedChatRequest,
    *,
    reasoning_summary_enabled: bool,
) -> dict[str, Any]:
    """Build the canonical raw-request cache payload for a prepared request."""

    if prepared.spec.server_type == "openai":
        request = _build_openai_responses_request(
            prepared,
            stream_enabled=False,
            reasoning_summary_enabled=reasoning_summary_enabled,
        )
    else:
        request = _build_chat_completion_request(prepared, stream_enabled=False)

    return {
        "transport": _default_transport_name(prepared),
        "server_name": prepared.spec.server_name,
        "server_type": prepared.spec.server_type,
        "model_ref": prepared.model_ref,
        "base_url": prepared.spec.base_url,
        "request": _sanitize_cache_request_value(request),
    }
