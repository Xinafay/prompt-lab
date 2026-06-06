from __future__ import annotations

import logging
import os
from typing import Any, Protocol, runtime_checkable

from shared.llm.chat_request import PreparedChatRequest, build_cache_request, prepare_chat_request
from shared.llm.chat_result import LlmResponse
from shared.llm.chat_transport import execute_prepared_chat_request, replay_cached_response
from shared.llm.stream_callbacks import StreamCallbacks, supports_reasoning_deltas
from shared.llm.llm_cache import SqliteLlmCache, get_llm_cache

_LOGGER = logging.getLogger(__name__)


@runtime_checkable
class ChatClient(Protocol):
    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        preset: dict[str, Any],
        stream_callback: StreamCallbacks | None = None,
    ) -> LlmResponse: ...


class PreparedChatClient(Protocol):
    def complete_prepared(
        self,
        prepared: PreparedChatRequest,
        *,
        stream_callback: StreamCallbacks | None = None,
    ) -> LlmResponse: ...


class DefaultChatClient:
    """Thin wrapper over prepare_chat_request + execute_prepared_chat_request."""

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        preset: dict[str, Any],
        stream_callback: StreamCallbacks | None = None,
    ) -> LlmResponse:
        request_preset = dict(preset)
        model = request_preset.pop("model", None)
        prepared = prepare_chat_request(messages, model=model, **request_preset)
        return self.complete_prepared(prepared, stream_callback=stream_callback)

    def complete_prepared(
        self,
        prepared: PreparedChatRequest,
        *,
        stream_callback: StreamCallbacks | None = None,
    ) -> LlmResponse:
        return execute_prepared_chat_request(prepared, stream_callback=stream_callback)


class CachedChatClient:
    """Cache decorator: checks cache before delegating to inner PreparedChatClient."""

    def __init__(self, inner: PreparedChatClient, cache: SqliteLlmCache) -> None:
        self._inner = inner
        self._cache = cache

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        preset: dict[str, Any],
        stream_callback: StreamCallbacks | None = None,
    ) -> LlmResponse:
        reasoning_summary_enabled = supports_reasoning_deltas(stream_callback)
        request_preset = dict(preset)
        model = request_preset.pop("model", None)
        prepared = prepare_chat_request(messages, model=model, **request_preset)
        cache_key = build_cache_request(prepared, reasoning_summary_enabled=reasoning_summary_enabled)

        cached = self._cache.get(cache_key)
        if cached is not None:
            _LOGGER.info(
                "llm.request.cache_hit model=%s server=%s messages=%d",
                prepared.model_ref,
                prepared.spec.server_name,
                len(prepared.messages),
            )
            replay_cached_response(
                cached.response.content,
                stream_callback,
                reasoning_content=cached.response.reasoning_content,
            )
            return cached.response

        response = self._inner.complete_prepared(prepared, stream_callback=stream_callback)
        self._cache.put(
            cache_key,
            response=response,
        )
        return response


def default_chat_client() -> ChatClient:
    """Build the default client stack: Logging(Cached(Retrying(Default())))."""

    from shared.llm.clients.logging_client import LoggingChatClient
    from shared.llm.clients.retrying_client import RetryingChatClient

    transport_retries = int(os.getenv("LLM_TRANSPORT_RETRIES", "1"))
    cache = get_llm_cache()
    client: Any = DefaultChatClient()
    client = RetryingChatClient(client, max_retries=transport_retries)
    if cache is not None:
        client = CachedChatClient(client, cache)
    return LoggingChatClient(client)
