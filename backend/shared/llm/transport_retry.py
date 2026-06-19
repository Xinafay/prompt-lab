from __future__ import annotations

import email.utils
import os
import random
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

T = TypeVar("T")

_DEFAULT_MAX_RETRIES = 1
_MAX_HEADER_DELAY_SECONDS = 60.0


def transport_retries_from_env() -> int:
    """Return the configured transport retry count."""
    return int(os.getenv("LLM_TRANSPORT_RETRIES", str(_DEFAULT_MAX_RETRIES)))


def is_retryable_transport_error(exc: Exception) -> bool:
    """Return whether an exception represents a transient provider/transport failure."""
    try:
        import openai
    except ImportError:
        return False

    if isinstance(exc, (openai.RateLimitError, openai.APIConnectionError, openai.APITimeoutError)):
        return True
    if isinstance(exc, openai.APIStatusError):
        return exc.status_code in {408, 409, 429} or exc.status_code >= 500
    return False


def _parse_retry_after(value: str) -> float | None:
    value = value.strip()
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            parsed = email.utils.parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        seconds = (parsed - datetime.now(timezone.utc)).total_seconds()
    return max(0.0, seconds)


def _parse_reset_duration(value: str) -> float | None:
    value = value.strip().lower()
    if not value:
        return None
    total = 0.0
    position = 0
    for match in re.finditer(r"(\d+(?:\.\d+)?)(ms|s|m|h)", value):
        if match.start() != position:
            return None
        amount = float(match.group(1))
        unit = match.group(2)
        if unit == "ms":
            total += amount / 1000.0
        elif unit == "s":
            total += amount
        elif unit == "m":
            total += amount * 60.0
        elif unit == "h":
            total += amount * 3600.0
        position = match.end()
    if position != len(value) or position == 0:
        return None
    return total


def _header_delay_seconds(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers is None:
        return None

    retry_after = headers.get("retry-after")
    if retry_after:
        parsed_retry_after = _parse_retry_after(str(retry_after))
        if parsed_retry_after is not None:
            return min(parsed_retry_after, _MAX_HEADER_DELAY_SECONDS)

    reset_candidates: list[float] = []
    exhausted_candidates: list[float] = []
    for remaining_header, reset_header in (
        ("x-ratelimit-remaining-requests", "x-ratelimit-reset-requests"),
        ("x-ratelimit-remaining-tokens", "x-ratelimit-reset-tokens"),
    ):
        reset_value = headers.get(reset_header)
        if not reset_value:
            continue
        parsed_reset = _parse_reset_duration(str(reset_value))
        if parsed_reset is None:
            continue
        reset_candidates.append(parsed_reset)
        remaining_value = headers.get(remaining_header)
        try:
            remaining = float(str(remaining_value))
        except (TypeError, ValueError):
            remaining = None
        if remaining is not None and remaining <= 0:
            exhausted_candidates.append(parsed_reset)

    if exhausted_candidates:
        return min(max(exhausted_candidates), _MAX_HEADER_DELAY_SECONDS)
    if reset_candidates:
        return min(min(reset_candidates), _MAX_HEADER_DELAY_SECONDS)
    return None


def retry_delay_seconds(exc: Exception, fallback_delay: float) -> float:
    """Return a retry delay, preferring provider headers over local backoff."""
    header_delay = _header_delay_seconds(exc)
    if header_delay is not None:
        return header_delay
    return fallback_delay * random.uniform(0.8, 1.2)


def run_with_transport_retry(
    fn: Callable[[], T],
    *,
    max_retries: int | None = None,
    on_retry: Callable[[int], None] | None = None,
    cancellation_error: type[BaseException] | tuple[type[BaseException], ...] = (),
) -> T:
    """Run a provider call with bounded retry for transient transport failures."""
    retries = transport_retries_from_env() if max_retries is None else max_retries
    delay = 1.0
    for attempt in range(retries + 1):
        try:
            return fn()
        except BaseException as exc:
            if cancellation_error and isinstance(exc, cancellation_error):
                raise
            if not isinstance(exc, Exception):
                raise
            if not is_retryable_transport_error(exc) or attempt >= retries:
                raise
            if on_retry is not None:
                on_retry(attempt + 1)
            time.sleep(retry_delay_seconds(exc, delay))
            delay *= 2
    raise RuntimeError("unreachable")
