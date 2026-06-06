from __future__ import annotations

import logging
import os
import time
from dataclasses import replace
from typing import Any

from shared.llm.chat_result import LlmResponse
from shared.llm.stream_callbacks import StreamCallbacks
from shared.llm.transports.usage import _count_chars_words, _flatten_usage_details, _usage_tokens

_LOGGER = logging.getLogger("shared.llm_client")
_FALSE_ENV = {"0", "false", "no", "off"}


def _progress_enabled() -> bool:
    value = os.getenv("LLM_LOG_PROGRESS", "1").strip().lower()
    return value not in _FALSE_ENV


class LoggingChatClient:
    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        preset: dict[str, Any],
        stream_callback: StreamCallbacks | None = None,
    ) -> LlmResponse:
        model = str(preset.get("model", "?"))
        stream_enabled = stream_callback is not None

        _LOGGER.info(
            "llm.request.start model=%s messages=%d stream=%s",
            model,
            len(messages),
            stream_enabled,
        )
        start_time = time.monotonic()

        actual_callback: StreamCallbacks | None = stream_callback
        if stream_enabled and _progress_enabled():
            assert stream_callback is not None
            actual_callback = _wrap_with_progress(stream_callback, model, start_time)

        try:
            response = self._inner.complete(
                messages,
                preset=preset,
                stream_callback=actual_callback,
            )
        except Exception:
            duration_s = time.monotonic() - start_time
            _LOGGER.exception(
                "llm.request.error model=%s duration_s=%.1f",
                model,
                duration_s,
            )
            raise

        duration_s = time.monotonic() - start_time
        content = response.content
        usage = response.usage
        chars, words = _count_chars_words(content)
        prompt_tokens, completion_tokens, total_tokens = _usage_tokens(usage)
        if any(t is not None for t in (prompt_tokens, completion_tokens, total_tokens)):
            usage_details = _flatten_usage_details(usage)
            extra_fields = ""
            if usage_details:
                extra_fields = " " + " ".join(f"{k}={v}" for k, v in sorted(usage_details.items()))
            _LOGGER.info(
                "llm.request.end model=%s duration_s=%.1f chars=%s words=%s"
                " prompt_tokens=%s completion_tokens=%s total_tokens=%s%s",
                model,
                duration_s,
                chars,
                words,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                extra_fields,
            )
        else:
            _LOGGER.info(
                "llm.request.end model=%s duration_s=%.1f chars=%s words=%s",
                model,
                duration_s,
                chars,
                words,
            )

        return response


def _wrap_with_progress(
    stream_callback: StreamCallbacks,
    model: str,
    start_time: float,
) -> StreamCallbacks:
    text_parts: list[str] = []
    next_at = [time.monotonic() + 5.0]

    def _emit_if_due(now: float) -> None:
        if now >= next_at[0]:
            chars, words = _count_chars_words("".join(text_parts))
            _LOGGER.info(
                "llm.request.progress model=%s duration_s=%.1f chars=%s words=%s",
                model,
                now - start_time,
                chars,
                words,
            )
            next_at[0] = now + 5.0

    original = stream_callback.on_text_delta

    def wrapped_delta(delta: str) -> None:
        if original is not None:
            original(delta)
        text_parts.append(delta)
        _emit_if_due(time.monotonic())

    return replace(stream_callback, on_text_delta=wrapped_delta)
