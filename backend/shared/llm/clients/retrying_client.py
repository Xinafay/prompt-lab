from __future__ import annotations

from typing import Any, Callable

from shared.llm.chat_result import LlmResponse
from shared.llm.cancellation import LlmRequestCancelled
from shared.llm.stream_callbacks import StreamCallbacks, notify_stream_phase
from shared.llm.transport_retry import run_with_transport_retry

_DEFAULT_MAX_RETRIES = 1


class RetryingChatClient:
    def __init__(self, inner: Any, *, max_retries: int = _DEFAULT_MAX_RETRIES) -> None:
        self._inner = inner
        self._max_retries = max_retries

    def _run_with_retry(
        self,
        fn: Callable[[], Any],
        stream_callback: StreamCallbacks | None,
    ) -> LlmResponse:
        return run_with_transport_retry(
            fn,
            max_retries=self._max_retries,
            cancellation_error=LlmRequestCancelled,
            on_retry=lambda attempt: notify_stream_phase(
                stream_callback,
                "transport_retry",
                reset=True,
                meta={"attempt": attempt},
            ),
        )

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
