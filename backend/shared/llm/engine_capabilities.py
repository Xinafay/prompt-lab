from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class EngineCapabilities:
    """Per-engine wire protocol selection for each LLM operation.

    This matrix is the single source of truth for *which protocol* an engine
    speaks for chat, embeddings, and tokenization. Operation modules branch on
    these capability values instead of comparing engine names, so adding a new
    engine is one row here rather than scattered ``if engine == ...`` edits.

    Engines that are OpenAI-compatible (llama.cpp, llama-swap, vLLM, Ollama)
    share the same chat/embeddings protocols and differ only where the matrix
    says so (notably tokenization).
    """

    # "openai-responses" | "openai-chat-completions" | "anthropic-messages"
    chat_protocol: str
    # "openai-embeddings" | None (engine has no embeddings support)
    embeddings_protocol: Optional[str]
    # Consumed by the upcoming count_tokens helper. None = unsupported.
    # "openai-input-tokens" | "anthropic-count-tokens" | "llamacpp-tokenize"
    # | "llama-swap-tokenize" | "vllm-tokenize"
    tokenize_protocol: Optional[str]
    # Self-hosted servers require a base URL ("host") in .servers.jsonc.
    requires_host: bool
    # Hosted providers require a real API key; self-hosted servers do not.
    requires_api_key: bool
    # OpenAI-compatible self-hosted servers accept `start` assistant priming
    # and pass unsupported request params through `extra_body`.
    openai_compatible_extras: bool


# tokenize_protocol values are declared now but wired by the upcoming
# count_tokens helper; chat and embeddings already consume the other columns.
_ENGINE_CAPABILITIES: Dict[str, EngineCapabilities] = {
    "openai": EngineCapabilities(
        chat_protocol="openai-responses",
        embeddings_protocol="openai-embeddings",
        tokenize_protocol="openai-input-tokens",
        requires_host=False,
        requires_api_key=True,
        openai_compatible_extras=False,
    ),
    "anthropic": EngineCapabilities(
        chat_protocol="anthropic-messages",
        embeddings_protocol=None,
        tokenize_protocol="anthropic-count-tokens",
        requires_host=False,
        requires_api_key=True,
        openai_compatible_extras=False,
    ),
    "llamacpp": EngineCapabilities(
        chat_protocol="openai-chat-completions",
        embeddings_protocol="openai-embeddings",
        tokenize_protocol="llamacpp-tokenize",
        requires_host=True,
        requires_api_key=False,
        openai_compatible_extras=True,
    ),
    "llama-swap": EngineCapabilities(
        chat_protocol="openai-chat-completions",
        embeddings_protocol="openai-embeddings",
        tokenize_protocol="llama-swap-tokenize",
        requires_host=True,
        requires_api_key=False,
        openai_compatible_extras=True,
    ),
    "vllm": EngineCapabilities(
        chat_protocol="openai-chat-completions",
        embeddings_protocol="openai-embeddings",
        tokenize_protocol="vllm-tokenize",
        requires_host=True,
        requires_api_key=False,
        openai_compatible_extras=True,
    ),
    "ollama": EngineCapabilities(
        chat_protocol="openai-chat-completions",
        embeddings_protocol="openai-embeddings",
        # Ollama exposes no OpenAI-compatible tokenize endpoint.
        tokenize_protocol=None,
        requires_host=True,
        requires_api_key=False,
        openai_compatible_extras=True,
    ),
}


SUPPORTED_ENGINES: Tuple[str, ...] = tuple(_ENGINE_CAPABILITIES)


def engine_capabilities(engine: str) -> EngineCapabilities:
    """Return the capability row for an engine, or raise on unknown engines."""

    caps = _ENGINE_CAPABILITIES.get(engine)
    if caps is None:
        supported = ", ".join(sorted(_ENGINE_CAPABILITIES))
        raise ValueError(
            f"Unsupported engine '{engine}'. Supported engines: {supported}."
        )
    return caps
