from __future__ import annotations

import logging
from typing import Any

from shared.llm.cancellation import LlmRequestCancelled
from shared.llm.embeddings_client import default_embeddings_client
from shared.llm.embeddings_result import EmbeddingsResponse, EmbeddingsResult
from shared.llm.llm_cache import llm_cache_enabled


_LOGGER = logging.getLogger(__name__)


def request_embeddings_raw(
    inputs: str | list[str],
    *,
    preset: dict[str, Any],
    cache_enabled: bool | None = None,
) -> EmbeddingsResponse:
    """Execute one embeddings request from text input and preset."""

    with llm_cache_enabled(cache_enabled):
        return default_embeddings_client().embed(inputs, preset=preset)


def get_embeddings(
    inputs: str | list[str],
    preset: dict[str, Any],
    *,
    retry_count: int = 2,
    cache_enabled: bool | None = None,
) -> EmbeddingsResult:
    """Create embedding vectors for one or more text fragments.

    Args:
        inputs: A single text fragment or a list of text fragments. The result
            always contains a list of vectors, including for a single string.
        preset: Embeddings preset. ``model`` is required unless ``LLM_MODEL`` is set.
        retry_count: Retries on exception. Total attempts = retry_count + 1. Default 2.
        cache_enabled: Optional per-request cache override. ``None`` uses ``LLM_CACHE``.

    Returns:
        EmbeddingsResult with float vectors, usage stats, and optional raw response metadata.
    """

    if retry_count < 0:
        raise ValueError("retry_count cannot be negative.")

    for attempt in range(retry_count + 1):
        try:
            request_kwargs: dict[str, Any] = {"preset": preset}
            if cache_enabled is not None:
                request_kwargs["cache_enabled"] = cache_enabled
            response = request_embeddings_raw(inputs, **request_kwargs)
            return EmbeddingsResult(
                output=response.embeddings,
                usage=response.usage,
                model=response.model,
                raw_response=response.raw_response,
            )
        except LlmRequestCancelled:
            raise
        except Exception:
            if attempt >= retry_count:
                raise
            _LOGGER.info(
                "llm.embeddings.retry attempt=%s retry_count=%s",
                attempt + 1,
                retry_count,
            )

    raise RuntimeError("get_embeddings exceeded retry count without returning.")
