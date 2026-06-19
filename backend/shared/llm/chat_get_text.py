from __future__ import annotations

from typing import Any

from shared.llm.chat import Chat
from shared.llm.chat_client import default_chat_client
from shared.llm.chat_result import (
    ChatResult,
    LlmResponse,
    assistant_conversation_message,
)
from shared.llm.llm_cache import llm_cache_enabled
from shared.llm.stream_callbacks import StreamCallbacks


def request_chat_raw_text(
    messages: list[dict[str, Any]],
    *,
    preset: dict[str, Any],
    stream_callback: StreamCallbacks | None = None,
    cache_enabled: bool | None = None,
) -> LlmResponse:
    """Execute one LLM request from a message list and preset."""

    with llm_cache_enabled(cache_enabled):
        return default_chat_client().complete(
            messages,
            preset=preset,
            stream_callback=stream_callback,
        )


def chat_get_text(
    chat: Chat | None,
    prompt: str,
    preset: dict[str, Any],
    *,
    stream_callback: StreamCallbacks | None = None,
    cache_enabled: bool | None = None,
) -> ChatResult[str]:
    """Send a prompt to the LLM and return the raw text response.

    Updates ``chat.messages`` with the user prompt and assistant reply on success.

    Args:
        chat: Conversation history. Updated in place on success. Created fresh if ``None``.
        prompt: User message to send.
        preset: LLM preset (model, temperature, etc.).
        stream_callback: Optional callbacks for streaming progress.
        cache_enabled: Optional per-request cache override. ``None`` uses ``LLM_CACHE``.

    Returns:
        ChatResult with the raw text output, usage stats, and the exchange.
    """

    if chat is None:
        chat = Chat()

    base_chat = chat.clone()
    working_chat = base_chat.clone()
    working_chat.add_user(prompt)
    request_kwargs: dict[str, Any] = {
        "preset": preset,
        "stream_callback": stream_callback,
    }
    if cache_enabled is not None:
        request_kwargs["cache_enabled"] = cache_enabled
    response = request_chat_raw_text(working_chat.to_llm_messages(), **request_kwargs)
    raw_response = response.content
    final_chat = working_chat.clone()
    final_chat.add_assistant(raw_response, reasoning_content=response.reasoning_content)
    chat.messages = final_chat.messages
    conversation = [
        {"role": "user", "content": prompt},
        assistant_conversation_message(raw_response, response.reasoning_content),
    ]
    return ChatResult(output=raw_response, usage=response.usage, conversation=conversation)
