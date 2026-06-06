from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class StreamCallbacks:
    on_text_delta: Callable[[str], None] | None = None
    on_reasoning_delta: Callable[[str], None] | None = None
    on_reasoning_segment_done: Callable[[], None] | None = None
    on_stream_phase: Callable[..., None] | None = None
    on_usage: Callable[..., None] | None = None
    on_prompt_messages: Callable[..., None] | None = None
    cancel_check: Callable[[], None] | None = None


def supports_reasoning_deltas(stream_callback: StreamCallbacks | None) -> bool:
    return stream_callback is not None and stream_callback.on_reasoning_delta is not None


def check_cancelled(callbacks: StreamCallbacks | None) -> None:
    if callbacks is None or callbacks.cancel_check is None:
        return
    callbacks.cancel_check()


def notify_text_delta(callbacks: StreamCallbacks | None, delta: str) -> None:
    if callbacks is None or not delta or callbacks.on_text_delta is None:
        return
    callbacks.on_text_delta(delta)


def notify_reasoning_delta(callbacks: StreamCallbacks | None, delta: str) -> None:
    if callbacks is None or not delta or callbacks.on_reasoning_delta is None:
        return
    callbacks.on_reasoning_delta(delta)


def notify_reasoning_segment_done(callbacks: StreamCallbacks | None) -> None:
    if callbacks is None or callbacks.on_reasoning_segment_done is None:
        return
    callbacks.on_reasoning_segment_done()


def notify_stream_phase(
    callbacks: StreamCallbacks | None,
    phase: str,
    *,
    reset: bool = False,
    meta: dict[str, Any] | None = None,
) -> None:
    if callbacks is None or callbacks.on_stream_phase is None:
        return
    callbacks.on_stream_phase(phase, reset=reset, meta=meta)


def notify_prompt_messages(
    callbacks: StreamCallbacks | None,
    messages: list[dict[str, Any]],
    *,
    attempt: int,
) -> None:
    if callbacks is None or callbacks.on_prompt_messages is None:
        return
    callbacks.on_prompt_messages(messages, attempt=attempt)


def notify_usage(
    callbacks: StreamCallbacks | None,
    usage: dict[str, Any] | None,
    *,
    attempt: int,
) -> None:
    if usage is None or callbacks is None or callbacks.on_usage is None:
        return
    callbacks.on_usage(usage, attempt=attempt)
