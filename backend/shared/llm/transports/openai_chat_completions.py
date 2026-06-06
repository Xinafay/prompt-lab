from __future__ import annotations

from typing import Any, Callable, Optional, cast

from shared.llm.chat_request import PreparedChatRequest, _build_chat_completion_request
from shared.llm.chat_result import LlmResponse
from shared.llm.stream_callbacks import StreamCallbacks, check_cancelled, notify_reasoning_delta
from shared.llm.transports.openai_client import _get_openai_client
from shared.llm.transports.usage import normalize_usage


def _to_plain_payload(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(mode="json")
        except TypeError:
            return value.model_dump()
    if isinstance(value, dict):
        return {key: _to_plain_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_plain_payload(item) for item in value]
    if hasattr(value, "__dict__") and not isinstance(value, type):
        return {
            key: _to_plain_payload(item)
            for key, item in value.__dict__.items()
            if not key.startswith("_")
        }
    return value


def _get_delta_field(chunk: Any, *field_names: str) -> Optional[str]:
    try:
        choices = getattr(chunk, "choices", None)
        if choices is None and isinstance(chunk, dict):
            choices = chunk.get("choices")
        if not choices:
            return None
        first = choices[0]
        delta = getattr(first, "delta", None)
        if delta is None and isinstance(first, dict):
            delta = first.get("delta")
        if delta is None:
            return None
        for name in field_names:
            value = delta.get(name) if isinstance(delta, dict) else getattr(delta, name, None)
            if isinstance(value, str):
                return value
    except Exception:
        pass
    return None


def _extract_delta_content(chunk: Any) -> Optional[str]:
    return _get_delta_field(chunk, "content")


def _extract_delta_reasoning(chunk: Any) -> Optional[str]:
    return _get_delta_field(chunk, "reasoning_content", "reasoning")


def _extract_message_field(resp: Any, *field_names: str) -> Optional[str]:
    try:
        choices = getattr(resp, "choices", None)
        if choices is None and isinstance(resp, dict):
            choices = resp.get("choices")
        if not choices:
            return None
        first = choices[0]
        message = getattr(first, "message", None)
        if message is None and isinstance(first, dict):
            message = first.get("message")
        if message is None:
            return None
        for name in field_names:
            value = message.get(name) if isinstance(message, dict) else getattr(message, name, None)
            if isinstance(value, str):
                return value
    except Exception:
        pass
    return None


def _extract_usage(chunk: Any) -> dict[str, Any] | None:
    usage = chunk.get("usage") if isinstance(chunk, dict) else getattr(chunk, "usage", None)
    return normalize_usage(usage)


def execute_chat_completions(
    prepared: Any,
    *,
    stream_enabled: bool,
    call_fn: Callable[..., Any],
    stream_handler: Callable[[str], None] | None,
    callbacks: StreamCallbacks | None,
) -> LlmResponse:
    check_cancelled(callbacks)
    resp = cast(Any, call_fn(prepared, stream_enabled=stream_enabled))
    usage: dict[str, Any] | None = None
    if stream_enabled:
        parts: list[str] = []
        reasoning_parts: list[str] = []
        raw_chunks: list[Any] = []
        for chunk in resp:
            check_cancelled(callbacks)
            raw_chunks.append(_to_plain_payload(chunk))
            delta = _extract_delta_content(chunk)
            if delta:
                parts.append(delta)
                if stream_handler is not None:
                    stream_handler(delta)
            reasoning_delta = _extract_delta_reasoning(chunk)
            if reasoning_delta:
                reasoning_parts.append(reasoning_delta)
                notify_reasoning_delta(callbacks, reasoning_delta)
            chunk_usage = _extract_usage(chunk)
            if chunk_usage:
                usage = chunk_usage
        check_cancelled(callbacks)
        return LlmResponse(
            content="".join(parts),
            usage=usage,
            reasoning_content="".join(reasoning_parts),
            raw_response=raw_chunks,
        )

    content = _extract_message_field(resp, "content")
    if content is None:
        content = resp.choices[0].message.content
    reasoning_content = _extract_message_field(resp, "reasoning_content", "reasoning")
    usage = normalize_usage(getattr(resp, "usage", None))
    if usage is None and isinstance(resp, dict):
        usage = normalize_usage(resp.get("usage"))
    check_cancelled(callbacks)
    return LlmResponse(
        content=content,
        usage=usage,
        reasoning_content=reasoning_content,
        raw_response=_to_plain_payload(resp),
    )


def _call_chat_completion(prepared: PreparedChatRequest, *, stream_enabled: bool) -> Any:
    client = _get_openai_client(prepared)
    request = _build_chat_completion_request(prepared, stream_enabled=stream_enabled)
    return client.chat.completions.create(**request)
