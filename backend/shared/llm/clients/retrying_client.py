from __future__ import annotations

import random
import time
from typing import Any, Callable

from shared.llm.chat_result import LlmResponse
from shared.llm.cancellation import LlmRequestCancelled
from shared.llm.stream_callbacks import StreamCallbacks, notify_stream_phase

_DEFAULT_MAX_RETRIES = 1


def _is_retryable(exc: Exception) -> bool:
    try:
        import openai
        return isinstance(exc, (openai.RateLimitError, openai.APIConnectionError, openai.APITimeoutError))
    except ImportError:
        return False


class RetryingChatClient:
    def __init__(self, inner: Any, *, max_retries: int = _DEFAULT_MAX_RETRIES) -> None:
        self._inner = inner
        self._max_retries = max_retries

    def _run_with_retry(
        self,
        fn: Callable[[], Any],
        stream_callback: StreamCallbacks | None,
    ) -> LlmResponse:
        delay = 1.0
        for attempt in range(self._max_retries + 1):
            try:
                return fn()
            except LlmRequestCancelled:
                raise
            except Exception as exc:
                if not _is_retryable(exc) or attempt >= self._max_retries:
                    raise
                notify_stream_phase(
                    stream_callback,
                    "transport_retry",
                    reset=True,
                    meta={"attempt": attempt + 1},
                )
                time.sleep(delay * random.uniform(0.8, 1.2))
                delay *= 2
        raise RuntimeError("unreachable")

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        preset: dict[str, Any],
        stream_callback: StreamCallbacks | None = None,
    ) -> LlmResponse:
        return self._run_with_retry(
            lambda: self._inner.complete(messages, preset=preset, stream_callback=stream_callback),
            stream_callback,
        )

    def complete_prepared(
        self,
        prepared: Any,
        *,
        stream_callback: StreamCallbacks | None = None,
    ) -> LlmResponse:
        return self._run_with_retry(
            lambda: self._inner.complete_prepared(prepared, stream_callback=stream_callback),
            stream_callback,
        )
