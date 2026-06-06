from __future__ import annotations

from shared.llm.chat_get_text import chat_get_text, request_chat_raw_text
from shared.llm.chat_request import (
    ModelSpec,
    PreparedChatRequest,
    _build_chat_completion_request,
    _build_openai_responses_request,
    build_cache_request,
    is_local_model,
    prepare_chat_request,
    resolve_model_spec,
)
from shared.llm.chat_transport import (
    _call_chat_completion,
    _call_openai_responses,
    _execute_prepared_chat_request_uncached,
    execute_prepared_chat_request,
    normalize_usage,
    replay_cached_response,
)
from shared.llm.transports.openai_responses import _to_plain_payload


__all__ = [
    "ModelSpec",
    "PreparedChatRequest",
    "prepare_chat_request",
    "resolve_model_spec",
    "is_local_model",
    "build_cache_request",
    "normalize_usage",
    "execute_prepared_chat_request",
    "replay_cached_response",
    "request_chat_raw_text",
    "chat_get_text",
    "_build_chat_completion_request",
    "_build_openai_responses_request",
    "_call_chat_completion",
    "_call_openai_responses",
    "_execute_prepared_chat_request_uncached",
    "_to_plain_payload",
]
