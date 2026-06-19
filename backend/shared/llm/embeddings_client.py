from __future__ import annotations

import logging
import time
from typing import Any, Protocol, runtime_checkable

from shared.llm.cancellation import LlmRequestCancelled
from shared.llm.embeddings_request import (
    PreparedEmbeddingsRequest,
    build_embeddings_cache_request,
    prepare_embeddings_request,
)
from shared.llm.embeddings_result import EmbeddingsResponse
from shared.llm.embeddings_transport import execute_prepared_embeddings_request
from shared.llm.llm_cache import SqliteLlmCache, get_llm_cache
from shared.llm.transports.usage import _flatten_usage_details, _usage_tokens
from shared.llm.transport_retry import run_with_transport_retry, transport_retries_from_env


_LOGGER = logging.getLogger("shared.llm_client")
_DEFAULT_MAX_RETRIES = 1


@runtime_checkable
class EmbeddingsClient(Protocol):
    def embed(
        self,
        inputs: str | list[str],
        *,
        preset: dict[str, Any],
    ) -> EmbeddingsResponse: ...


class PreparedEmbeddingsClient(Protocol):
    def embed_prepared(self, prepared: PreparedEmbeddingsRequest) -> EmbeddingsResponse: ...


class DefaultEmbeddingsClient:
    """Thin wrapper over prepare_embeddings_request + execute_prepared_embeddings_request."""

    def embed(
        self,
        inputs: str | list[str],
        *,
        preset: dict[str, Any],
    ) -> EmbeddingsResponse:
        request_preset = dict(preset)
        model = request_preset.pop("model", None)
        prepared = prepare_embeddings_request(inputs, model=model, **request_preset)
        return self.embed_prepared(prepared)

    def embed_prepared(self, prepared: PreparedEmbeddingsRequest) -> EmbeddingsResponse:
        return execute_prepared_embeddings_request(prepared)


class CachedEmbeddingsClient:
    """Cache decorator: checks cache before delegating to inner PreparedEmbeddingsClient."""

    def __init__(self, inner: PreparedEmbeddingsClient, cache: SqliteLlmCache) -> None:
        self._inner = inner
        self._cache = cache

    def embed(
        self,
        inputs: str | list[str],
        *,
        preset: dict[str, Any],
    ) -> EmbeddingsResponse:
        request_preset = dict(preset)
        model = request_preset.pop("model", None)
        prepared = prepare_embeddings_request(inputs, model=model, **request_preset)
        cache_key = build_embeddings_cache_request(prepared)

        cached = self._cache.get_payload(cache_key)
        if cached is not None:
            _LOGGER.info(
                "llm.embeddings.cache_hit model=%s server=%s inputs=%d",
                prepared.model_ref,
                prepared.spec.server_name,
                len(prepared.inputs),
            )
            return EmbeddingsResponse.from_json(cached.response)

        response = self._inner.embed_prepared(prepared)
        self._cache.put_payload(cache_key, response=response.to_json())
        return response

    def embed_prepared(self, prepared: PreparedEmbeddingsRequest) -> EmbeddingsResponse:
        return self._inner.embed_prepared(prepared)


class RetryingEmbeddingsClient:
    def __init__(self, inner: Any, *, max_retries: int = _DEFAULT_MAX_RETRIES) -> None:
        self._inner = inner
        self._max_retries = max_retries

    def _run_with_retry(self, fn: Any) -> EmbeddingsResponse:
        return run_with_transport_retry(
            fn,
            max_retries=self._max_retries,
            cancellation_error=LlmRequestCancelled,
        )

    def embed(
        self,
        inputs: str | list[str],
        *,
        preset: dict[str, Any],
    ) -> EmbeddingsResponse:
        return self._run_with_retry(lambda: self._inner.embed(inputs, preset=preset))

    def embed_prepared(self, prepared: PreparedEmbeddingsRequest) -> EmbeddingsResponse:
        return self._run_with_retry(lambda: self._inner.embed_prepared(prepared))


class LoggingEmbeddingsClient:
    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def embed(
        self,
        inputs: str | list[str],
        *,
        preset: dict[str, Any],
    ) -> EmbeddingsResponse:
        normalized_input_count = 1 if isinstance(inputs, str) else len(inputs)
        model = str(preset.get("model", "?"))
        _LOGGER.info(
            "llm.embeddings.start model=%s inputs=%d",
            model,
            normalized_input_count,
        )
        start_time = time.monotonic()
        try:
            response = self._inner.embed(inputs, preset=preset)
        except Exception:
            duration_s = time.monotonic() - start_time
            _LOGGER.exception(
                "llm.embeddings.error model=%s duration_s=%.1f",
                model,
                duration_s,
            )
            raise

        duration_s = time.monotonic() - start_time
        prompt_tokens, _completion_tokens, total_tokens = _usage_tokens(response.usage)
        usage_details = _flatten_usage_details(response.usage)
        extra_fields = ""
        if usage_details:
            extra_fields = " " + " ".join(f"{key}={value}" for key, value in sorted(usage_details.items()))
        _LOGGER.info(
            "llm.embeddings.end model=%s duration_s=%.1f inputs=%d vectors=%d"
            " prompt_tokens=%s total_tokens=%s%s",
            model,
            duration_s,
            normalized_input_count,
            len(response.embeddings),
            prompt_tokens,
            total_tokens,
            extra_fields,
        )
        return response


def default_embeddings_client() -> EmbeddingsClient:
    """Build the default embeddings client stack: Logging(Cached(Retrying(Default())))."""

    transport_retries = transport_retries_from_env()
    cache = get_llm_cache()
    client: Any = DefaultEmbeddingsClient()
    client = RetryingEmbeddingsClient(client, max_retries=transport_retries)
    if cache is not None:
        client = CachedEmbeddingsClient(client, cache)
    return LoggingEmbeddingsClient(client)
