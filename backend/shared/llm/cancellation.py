from __future__ import annotations

import threading


class LlmRequestCancelled(Exception):
    """Raised when an in-flight LLM request is cancelled by the workflow host."""


class CancellationToken:
    """Thread-safe cooperative cancellation token for active workflow requests."""

    def __init__(self) -> None:
        self._event = threading.Event()

    @property
    def is_cancelled(self) -> bool:
        """Return whether cancellation has been requested."""
        return self._event.is_set()

    def cancel(self) -> None:
        """Request cancellation for consumers that check this token."""
        self._event.set()

    def raise_if_cancelled(self) -> None:
        """Raise ``LlmRequestCancelled`` when cancellation was requested."""
        if self.is_cancelled:
            raise LlmRequestCancelled("LLM request cancelled.")
