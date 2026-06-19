from __future__ import annotations

import time
from typing import Any, Callable

from shared.llm.chat_request import PreparedChatRequest
from shared.llm.chat_result import LlmResponse
from shared.llm.stream_callbacks import (
    StreamCallbacks,
    check_cancelled,
    notify_reasoning_delta,
    notify_reasoning_segment_done,
    notify_text_delta,
    supports_reasoning_deltas,
)
from shared.llm.transports.usage import normalize_usage
import shared.llm.transports.openai_client as _client_impl
import shared.llm.transports.openai_chat_completions as _cc_impl
import shared.llm.transports.openai_responses as _resp_impl
from shared.llm.transports.openai_client import _get_openai_client
from shared.llm.transports.openai_chat_completions import _call_chat_completion
from shared.llm.transports.openai_responses import _call_openai_responses

# Re-export cache so tests can call transport_utils._OPENAI_CLIENT_CACHE.clear()
_OPENAI_CLIENT_CACHE = _client_impl._OPENAI_CLIENT_CACHE

# Re-export for backward compat with tests and utils/chat.py façade.
_supports_reasoning_deltas = supports_reasoning_deltas
_notify_reasoning_delta = notify_reasoning_delta
_notify_reasoning_segment_done = notify_reasoning_segment_done


def replay_cached_response(
    text: str,
    stream_callback: StreamCallbacks | None,
    *,
    reasoning_content: str | None = None,
) -> None:
    """Replay a cached raw response through the provided callback."""
    check_cancelled(stream_callback)
    if reasoning_content:
        notify_reasoning_delta(stream_callback, reasoning_content)
        notify_reasoning_segment_done(stream_callback)
    if text:
        notify_text_delta(stream_callback, text)
    check_cancelled(stream_callback)


def _execute_prepared_chat_request_uncached(
    prepared: PreparedChatRequest,
    *,
    stream_callback: StreamCallbacks | None = None,
    stream_enabled: bool,
    reasoning_summary_enabled: bool,
) -> LlmResponse:
    """Execute a prepared chat request through the direct OpenAI SDK."""
    check_cancelled(stream_callback)
    stream_handler: Callable[[str], None] | None = (
        stream_callback.on_text_delta if (stream_enabled and stream_callback is not None) else None
    )

    chat_protocol = prepared.spec.capabilities.chat_protocol
    if chat_protocol == "openai-responses":
        response = _resp_impl.execute_openai_responses(
            prepared,
            stream_enabled=stream_enabled,
            reasoning_summary_enabled=reasoning_summary_enabled,
            call_fn=_call_openai_responses,
            stream_handler=stream_handler,
            callbacks=stream_callback,
        )
    elif chat_protocol == "openai-chat-completions":
        response = _cc_impl.execute_chat_completions(
            prepared,
            stream_enabled=stream_enabled,
            call_fn=_call_chat_completion,
            stream_handler=stream_handler,
            callbacks=stream_callback,
        )
    else:
        raise NotImplementedError(
            f"Chat protocol '{chat_protocol}' (engine '{prepared.spec.engine}') "
            f"is not yet supported."
        )

    content = response.content
    if content is None:
        raise ValueError("Model response content is empty.")
    if not isinstance(content, str):
        content = str(content)
    if not content:
        raise ValueError("Model response content is empty.")

    check_cancelled(stream_callback)
    return LlmResponse(
        content=content,
        usage=response.usage,
        reasoning_content=response.reasoning_content,
        raw_response=response.raw_response,
    )


def execute_prepared_chat_request(
    prepared: PreparedChatRequest,
    *,
    stream_callback: StreamCallbacks | None = None,
) -> LlmResponse:
    """Execute a prepared chat request (no caching — use CachedChatClient for that)."""
    return _execute_prepared_chat_request_uncached(
        prepared,
        stream_callback=stream_callback,
        stream_enabled=stream_callback is not None,
        reasoning_summary_enabled=supports_reasoning_deltas(stream_callback),
    )
