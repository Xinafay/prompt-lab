from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from shared.llm.chat import Chat
from shared.llm.chat_result import LlmResponse, assistant_conversation_message
from shared.llm.chat_get_structured_lite import chat_get_structured_lite
from shared.llm.chat_get_text import chat_get_text
from shared.llm.clients.mock_client import MockChatClient
from shared.llm.structured_lite import StructuredLiteExhaustedError
from shared.llm.structured_lite import structured_lite


class PromptLabStructuredValidationError(Exception):
    """Raised when structured generation exhausts validation repair attempts."""


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


def generate_text(model: str, prompt: str) -> GeneratedText:
    """Generate text with Prompt Lab cache policy."""
    result = chat_get_text(
        Chat(),
        prompt,
        {"model": model},
        cache_enabled=False,
    )
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
) -> GeneratedStructured:
    """Generate structured output with Prompt Lab cache policy."""
    try:
        result = chat_get_structured_lite(
            Chat(),
            prompt,
            preset={"model": model},
            response_model=response_model,
            validation_context=validation_context,
            cache_enabled=False,
        )
    except StructuredLiteExhaustedError as exc:
        raise PromptLabStructuredValidationError(str(exc)) from exc
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
        raise PromptLabStructuredValidationError(str(exc)) from exc

    return GeneratedStructured(
        output=output,
        usage={"dry_run": True},
        raw_response=conversation,
    )
