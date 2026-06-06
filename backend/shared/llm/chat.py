from __future__ import annotations

from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator


ChatRole: TypeAlias = Literal["system", "developer", "user", "assistant"]


class ChatMessage(BaseModel):
    """Single typed chat message stored in a chat transcript."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    role: ChatRole
    content: str
    usage: dict[str, Any] | None = None
    reasoning_content: str | None = None

    @model_validator(mode="after")
    def validate_reasoning_role(self) -> "ChatMessage":
        if self.role != "assistant" and self.reasoning_content is not None:
            raise ValueError("reasoning_content is only valid for assistant messages.")
        return self


class Chat(BaseModel):
    """Mutable chat transcript used by the LLM helpers."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    messages: list[ChatMessage] = Field(default_factory=list)

    def _append(
        self,
        *,
        role: ChatRole,
        content: str,
        usage: dict[str, Any] | None = None,
        reasoning_content: str | None = None,
    ) -> Chat:
        self.messages.append(
            ChatMessage(
                role=role,
                content=content,
                usage=usage,
                reasoning_content=reasoning_content if role == "assistant" else None,
            )
        )
        return self

    def add_user(self, content: str) -> Chat:
        """Append a user message."""

        return self._append(role="user", content=content)

    def add_assistant(self, content: str, *, reasoning_content: str | None = None) -> Chat:
        """Append an assistant message."""

        return self._append(
            role="assistant",
            content=content,
            reasoning_content=reasoning_content,
        )

    def add_system(self, content: str) -> Chat:
        """Append a system message."""

        return self._append(role="system", content=content)

    def add_developer(self, content: str) -> Chat:
        """Append a developer message."""

        return self._append(role="developer", content=content)

    def clear(self) -> Chat:
        """Remove all messages."""

        self.messages = []
        return self

    def remove_last(self, count: int = 1) -> Chat:
        """Remove up to `count` messages from the end of the transcript."""

        if count <= 0:
            raise ValueError("count must be positive.")
        del self.messages[-count:]
        return self

    def to_llm_messages(self) -> list[dict[str, str]]:
        """Return the transport payload expected by the LLM layer."""

        return [{"role": message.role, "content": message.content} for message in self.messages]

    def clone(self) -> Chat:
        """Return a deep copy of the chat."""

        return self.model_copy(deep=True)

    @classmethod
    def empty(cls) -> Chat:
        """Create an empty chat."""

        return cls()

    @classmethod
    def with_system(cls, content: str) -> Chat:
        """Create a chat with an initial system message."""

        chat = cls()
        chat.add_system(content)
        return chat

    @property
    def is_empty(self) -> bool:
        return len(self.messages) == 0

    @property
    def length(self) -> int:
        return len(self.messages)
