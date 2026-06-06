from __future__ import annotations

from typing import Any, TypeVar, cast

from shared.llm.chat import Chat, ChatMessage
from shared.llm.chat_get_text import request_chat_raw_text
from shared.llm.chat_result import ChatResult, LlmResponse
from shared.llm.stream_callbacks import StreamCallbacks
from shared.llm.structured_lite import structured_lite

StructuredOutputT = TypeVar("StructuredOutputT")


def chat_get_structured_lite(
    chat: Chat,
    prompt: str,
    preset: dict[str, Any],
    *,
    response_model: type[StructuredOutputT] | Any,
    validation_context: dict[str, Any] | None = None,
    stream_callback: StreamCallbacks | None = None,
    fix_prompt: str | None = None,
    fix_retry: int = 1,
    cache_enabled: bool | None = None,
) -> ChatResult[StructuredOutputT]:
    """Send a structured prompt and parse the LLM response into ``response_model``.

    The prompt must contain ``<<MODEL>>``, which is replaced with the JSON schema.
    On validation failure, sends up to ``fix_retry`` repair requests with the error
    and schema. Transport retry logic is the responsibility of the underlying
    ``request_chat_raw_text`` caller.
    Updates ``chat.messages`` with the rendered prompt and serialised output on success.

    Args:
        chat: Conversation history. Updated in place on success. Created fresh if ``None``.
        prompt: User message template. Must contain ``<<MODEL>>``.
        preset: LLM preset (model, temperature, etc.).
        response_model: Pydantic model class or type annotation for the expected output.
        validation_context: Optional context dict forwarded to pydantic validation.
        stream_callback: Optional callbacks for streaming progress.
        fix_prompt: Repair request template (must contain ``<<ERROR>>``). Uses built-in if ``None``.
        fix_retry: How many repair requests to attempt after a validation failure. Default 1.
        cache_enabled: Optional per-request cache override. ``None`` uses ``LLM_CACHE``.

    Returns:
        ChatResult with the parsed output, usage stats, and the full repair conversation.

    Raises:
        StructuredLiteExhaustedError: If all repair attempts are exhausted.
    """

    if chat is None:
        chat = Chat()

    def _llm_caller(messages: list[dict[str, Any]]) -> LlmResponse:
        request_kwargs: dict[str, Any] = {
            "preset": preset,
            "stream_callback": stream_callback,
        }
        if cache_enabled is not None:
            request_kwargs["cache_enabled"] = cache_enabled
        return request_chat_raw_text(messages, **request_kwargs)

    output, usage, new_messages, conversation = structured_lite(
        chat.to_llm_messages(),
        prompt,
        llm_caller=_llm_caller,
        response_model=response_model,
        validation_context=validation_context,
        stream_callback=stream_callback,
        fix_prompt=fix_prompt,
        fix_retry=fix_retry,
    )
    chat.messages = [ChatMessage(**m) for m in new_messages]
    return ChatResult(output=cast(StructuredOutputT, output), usage=usage, conversation=conversation)
