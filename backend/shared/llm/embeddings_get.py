from __future__ import annotations

from typing import Any

from shared.llm.embeddings_client import default_embeddings_client
from shared.llm.embeddings_result import EmbeddingsResponse, EmbeddingsResult
from shared.llm.llm_cache import llm_cache_enabled


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
    cache_enabled: bool | None = None,
) -> EmbeddingsResult:
    """Create embedding vectors for one or more text fragments.

    Args:
        inputs: A single text fragment or a list of text fragments. The result
            always contains a list of vectors, including for a single string.
        preset: Embeddings preset. ``model`` is required unless ``LLM_MODEL`` is set.
        cache_enabled: Optional per-request cache override. ``None`` uses ``LLM_CACHE``.

    Returns:
        EmbeddingsResult with float vectors, usage stats, and optional raw response metadata.
    """

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
