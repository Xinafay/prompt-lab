from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from shared.llm.chat import Chat
from shared.llm.chat_result import LlmResponse, assistant_conversation_message
from shared.llm.chat_get_structured_lite import chat_get_structured_lite
from shared.llm.chat_get_text import chat_get_text
from shared.llm.cancellation import LlmRequestCancelled
from shared.llm.clients.mock_client import MockChatClient
from shared.llm.stream_callbacks import StreamCallbacks
from shared.llm.structured_lite import StructuredLiteExhaustedError
from shared.llm.structured_lite import structured_lite


class PromptLabStructuredValidationError(Exception):
    """Raised when structured generation exhausts validation repair attempts."""

    def __init__(
        self,
        message: str,
        *,
        raw_output: str | None = None,
        conversation: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.raw_output = raw_output
        self.conversation = conversation or []


class PromptLabLlmCancelled(Exception):
    """Raised when a Prompt Lab workflow cancels an active LLM request."""


@dataclass(frozen=True)
class GeneratedText:
    output: str
    usage: dict[str, Any]
    raw_response: Any


@dataclass(frozen=True)
class GeneratedStructured:
    output: BaseModel
    usage: dict[str, Any]
    raw_response: Any


def _raw_response(result: Any) -> Any:
    if hasattr(result, "response"):
        response = result.response
        if response is not None:
            return response
    if hasattr(result, "conversation"):
        return result.conversation
    raise AttributeError("LLM result has neither non-None response nor conversation.")


def _last_assistant_content(conversation: list[dict[str, Any]]) -> str | None:
    for message in reversed(conversation):
        if message.get("role") != "assistant":
            continue
        content = message.get("content")
        if isinstance(content, str):
            return content
    return None


def cancellation_callbacks(is_cancelled: Callable[[], bool]) -> StreamCallbacks:
    """Build stream callbacks that bridge Prompt Lab job cancellation into LLM transport."""

    def raise_if_cancelled() -> None:
        if is_cancelled():
            raise LlmRequestCancelled("Workflow job was cancelled.")

    return StreamCallbacks(cancel_check=raise_if_cancelled)


def generate_text(
    model: str,
    prompt: str,
    *,
    stream_callback: StreamCallbacks | None = None,
) -> GeneratedText:
    """Generate text with Prompt Lab cache policy."""
    try:
        result = chat_get_text(
            Chat(),
            prompt,
            {"model": model},
            stream_callback=stream_callback,
            cache_enabled=False,
        )
    except LlmRequestCancelled as exc:
        raise PromptLabLlmCancelled(str(exc)) from exc
    return GeneratedText(
        output=result.output,
        usage=result.usage or {},
        raw_response=_raw_response(result),
    )


def generate_structured(
    model: str,
    prompt: str,
    response_model: type[BaseModel],
    validation_context: dict[str, Any] | None,
    *,
    stream_callback: StreamCallbacks | None = None,
) -> GeneratedStructured:
    """Generate structured output with Prompt Lab cache policy."""
    try:
        result = chat_get_structured_lite(
            Chat(),
            prompt,
            preset={"model": model},
            response_model=response_model,
            validation_context=validation_context,
            stream_callback=stream_callback,
            cache_enabled=False,
        )
    except LlmRequestCancelled as exc:
        raise PromptLabLlmCancelled(str(exc)) from exc
    except StructuredLiteExhaustedError as exc:
        raise PromptLabStructuredValidationError(
            str(exc),
            raw_output=_last_assistant_content(exc.conversation),
            conversation=exc.conversation,
        ) from exc
    return GeneratedStructured(
        output=result.output,
        usage=result.usage or {},
        raw_response=_raw_response(result),
    )


def generate_text_from_fake_response(
    model: str,
    prompt: str,
    response_text: str,
) -> GeneratedText:
    """Generate text from a deterministic fake response without provider transport."""
    client = MockChatClient(
        [LlmResponse(content=response_text, usage={"dry_run": True})]
    )
    chat = Chat()
    chat.add_user(prompt)
    response = client.complete(chat.to_llm_messages(), preset={"model": model})
    conversation = [
        {"role": "user", "content": prompt},
        assistant_conversation_message(response.content, response.reasoning_content),
    ]
    return GeneratedText(
        output=response.content,
        usage=response.usage or {},
        raw_response=conversation,
    )


def generate_structured_from_fake_response(
    model: str,
    prompt: str,
    response_model: type[BaseModel],
    validation_context: dict[str, Any] | None,
    response_text: str,
) -> GeneratedStructured:
    """Validate deterministic fake JSON with structured_lite and no provider transport."""
    client = MockChatClient(
        [LlmResponse(content=response_text, usage={"dry_run": True})]
    )

    def llm_caller(messages: list[dict[str, Any]]) -> LlmResponse:
        return client.complete(messages, preset={"model": model})

    try:
        output, _usage, _new_messages, conversation = structured_lite(
            Chat().to_llm_messages(),
            prompt,
            llm_caller=llm_caller,
            response_model=response_model,
            validation_context=validation_context,
            fix_retry=0,
        )
    except StructuredLiteExhaustedError as exc:
        raise PromptLabStructuredValidationError(
            str(exc),
            raw_output=_last_assistant_content(exc.conversation),
            conversation=exc.conversation,
        ) from exc

    return GeneratedStructured(
        output=output,
        usage={"dry_run": True},
        raw_response=conversation,
    )
