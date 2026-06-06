from __future__ import annotations

from typing import Any, Callable, cast

from shared.llm.chat_request import PreparedChatRequest, _build_openai_responses_request
from shared.llm.chat_result import LlmResponse
from shared.llm.stream_callbacks import (
    StreamCallbacks,
    check_cancelled,
    notify_reasoning_delta,
    notify_reasoning_segment_done,
)
from shared.llm.transports.openai_client import _get_openai_client
from shared.llm.transports.usage import normalize_usage


def _to_plain_payload(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _to_plain_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_plain_payload(item) for item in value]
    return value


def _extract_response_message_text(output_items: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for item in output_items:
        if item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for content_part in content:
            if not isinstance(content_part, dict):
                continue
            if content_part.get("type") != "output_text":
                continue
            text = content_part.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


def _extract_reasoning_summary_text(output_items: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for item in output_items:
        if item.get("type") != "reasoning":
            continue
        summary = item.get("summary")
        if not isinstance(summary, list):
            continue
        for summary_part in summary:
            if not isinstance(summary_part, dict):
                continue
            text = summary_part.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


def _extract_response_text(payload: dict[str, Any]) -> str:
    output = payload.get("output")
    if isinstance(output, list):
        text = _extract_response_message_text(cast(list[dict[str, Any]], output))
        if text:
            return text
    output_text = payload.get("output_text")
    if isinstance(output_text, str):
        return output_text
    return ""


def _extract_response_reasoning(payload: dict[str, Any]) -> str:
    output = payload.get("output")
    if isinstance(output, list):
        return _extract_reasoning_summary_text(cast(list[dict[str, Any]], output))
    return ""


def _extract_response_usage(payload: dict[str, Any]) -> dict[str, Any] | None:
    return normalize_usage(payload.get("usage"))


def execute_openai_responses(
    prepared: Any,
    *,
    stream_enabled: bool,
    reasoning_summary_enabled: bool,
    call_fn: Callable[..., Any],
    stream_handler: Callable[[str], None] | None,
    callbacks: StreamCallbacks | None,
) -> LlmResponse:
    check_cancelled(callbacks)
    resp = cast(
        Any,
        call_fn(
            prepared,
            stream_enabled=stream_enabled,
            reasoning_summary_enabled=reasoning_summary_enabled,
        ),
    )

    if not stream_enabled:
        payload = cast(dict[str, Any], _to_plain_payload(resp))
        check_cancelled(callbacks)
        return LlmResponse(
            content=_extract_response_text(payload),
            usage=_extract_response_usage(payload),
            reasoning_content=_extract_response_reasoning(payload),
            raw_response=payload,
        )

    output_delta_parts: list[str] = []
    output_done_parts: list[str] = []
    reasoning_delta_parts: list[str] = []
    reasoning_done_parts: list[str] = []
    summary_delta_keys: set[tuple[str, int]] = set()
    text_delta_keys: set[tuple[str, int]] = set()
    output_items_by_index: dict[int, dict[str, Any]] = {}
    usage: dict[str, Any] | None = None
    final_response: dict[str, Any] | None = None
    raw_events: list[Any] = []

    for raw_event in resp:
        check_cancelled(callbacks)
        payload = cast(dict[str, Any], _to_plain_payload(raw_event))
        raw_events.append(payload)
        event_type = payload.get("type")
        if not isinstance(event_type, str):
            continue

        if event_type == "response.output_text.delta":
            delta = payload.get("delta")
            if isinstance(delta, str) and delta:
                output_delta_parts.append(delta)
                item_id = payload.get("item_id")
                content_index = payload.get("content_index")
                if isinstance(item_id, str) and isinstance(content_index, int):
                    text_delta_keys.add((item_id, content_index))
                if stream_handler is not None:
                    stream_handler(delta)
        elif event_type == "response.output_text.done":
            text = payload.get("text")
            item_id = payload.get("item_id")
            content_index = payload.get("content_index")
            key = (item_id, content_index) if isinstance(item_id, str) and isinstance(content_index, int) else None
            if isinstance(text, str) and text and (key is None or key not in text_delta_keys):
                output_done_parts.append(text)
                if stream_handler is not None:
                    stream_handler(text)
        elif event_type == "response.reasoning_summary_text.delta":
            delta = payload.get("delta")
            item_id = payload.get("item_id")
            summary_index = payload.get("summary_index")
            if (
                isinstance(delta, str)
                and delta
                and isinstance(item_id, str)
                and isinstance(summary_index, int)
            ):
                summary_delta_keys.add((item_id, summary_index))
                reasoning_delta_parts.append(delta)
                notify_reasoning_delta(callbacks, delta)
        elif event_type == "response.reasoning_summary_text.done":
            text = payload.get("text")
            item_id = payload.get("item_id")
            summary_index = payload.get("summary_index")
            key = (item_id, summary_index) if isinstance(item_id, str) and isinstance(summary_index, int) else None
            if isinstance(text, str) and text and (key is None or key not in summary_delta_keys):
                reasoning_done_parts.append(text)
                notify_reasoning_delta(callbacks, text)
            notify_reasoning_segment_done(callbacks)
        elif event_type in {"response.output_item.added", "response.output_item.done"}:
            item = payload.get("item")
            output_index = payload.get("output_index")
            if isinstance(item, dict) and isinstance(output_index, int):
                output_items_by_index[output_index] = item
        elif event_type in {"response.completed", "response.incomplete"}:
            response = payload.get("response")
            if isinstance(response, dict):
                final_response = response
                response_usage = _extract_response_usage(response)
                if response_usage is not None:
                    usage = response_usage

    content = "".join(output_delta_parts).strip()
    if not content:
        content = "".join(output_done_parts).strip()

    if not content and final_response is not None:
        content = _extract_response_text(final_response).strip()
        if content and stream_handler is not None:
            stream_handler(content)

    if not content and output_items_by_index:
        ordered_items = [item for _, item in sorted(output_items_by_index.items())]
        content = _extract_response_message_text(ordered_items).strip()
        if content and stream_handler is not None:
            stream_handler(content)

    reasoning_content = "".join(reasoning_delta_parts).strip()
    if not reasoning_content:
        reasoning_content = "".join(reasoning_done_parts).strip()

    if not reasoning_content and final_response is not None:
        reasoning_content = _extract_response_reasoning(final_response).strip()

    if not reasoning_content and output_items_by_index:
        ordered_items = [item for _, item in sorted(output_items_by_index.items())]
        reasoning_content = _extract_reasoning_summary_text(ordered_items).strip()

    check_cancelled(callbacks)
    return LlmResponse(
        content=content,
        usage=usage,
        reasoning_content=reasoning_content,
        raw_response=raw_events,
    )


def _call_openai_responses(
    prepared: PreparedChatRequest,
    *,
    stream_enabled: bool,
    reasoning_summary_enabled: bool,
) -> Any:
    client = _get_openai_client(prepared)
    request = _build_openai_responses_request(
        prepared,
        stream_enabled=stream_enabled,
        reasoning_summary_enabled=reasoning_summary_enabled,
    )
    return client.responses.create(**request)
