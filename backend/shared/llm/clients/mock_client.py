from __future__ import annotations

from typing import Any

from shared.llm.chat_result import LlmResponse
from shared.llm.stream_callbacks import StreamCallbacks, notify_text_delta


class MockChatClient:
    """Simple client returning pre-configured responses, useful in tests."""

    def __init__(self, responses: list[str | LlmResponse]) -> None:
        self._responses = list(responses)
        self._index = 0

    @property
    def calls(self) -> int:
        return self._index

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        preset: dict[str, Any],
        stream_callback: StreamCallbacks | None = None,
    ) -> LlmResponse:
        if self._index >= len(self._responses):
            raise RuntimeError(f"MockChatClient: no more responses (used {self._index})")
        resp = self._responses[self._index]
        self._index += 1
        response = resp if isinstance(resp, LlmResponse) else LlmResponse(content=resp)
        notify_text_delta(stream_callback, response.content)
        return response

    def complete_prepared(
        self,
        prepared: Any,
        *,
        stream_callback: StreamCallbacks | None = None,
    ) -> LlmResponse:
        return self.complete([], preset={}, stream_callback=stream_callback)
