from __future__ import annotations

import os
from typing import Callable, Dict, Optional

from shared.llm.server_registry import ModelSpec, ServerRegistry, default_server_registry
from shared.llm.transports.tokenize import (
    TokenizeError,
    count_tokens_llama_swap,
    count_tokens_llamacpp,
    count_tokens_openai_input_tokens,
    count_tokens_vllm,
)

__all__ = ["count_tokens", "TokenizeError"]


# Maps the engine capability matrix's ``tokenize_protocol`` to its handler.
_TOKENIZE_DISPATCH: Dict[str, Callable[[ModelSpec, str], int]] = {
    "openai-input-tokens": count_tokens_openai_input_tokens,
    "llamacpp-tokenize": count_tokens_llamacpp,
    "llama-swap-tokenize": count_tokens_llama_swap,
    "vllm-tokenize": count_tokens_vllm,
}


def count_tokens(
    model: Optional[str],
    content: str,
    *,
    registry: ServerRegistry | None = None,
) -> int:
    """Count the number of tokens in ``content`` for ``model``.

    Args:
        model: Model reference ``"<server>/<model>"`` resolved via
            ``.servers.jsonc``. Falls back to the ``LLM_MODEL`` environment
            variable when ``None``.
        content: The text to tokenize.
        registry: Optional server registry override (mainly for tests).

    Returns:
        The token count, obtained over the network using the engine's tokenize
        protocol (see the engine capability matrix). Text only.

    Raises:
        TokenizeError: when the engine has no tokenize protocol, the protocol is
            not yet implemented, or the network request fails.
    """
    if not isinstance(content, str):
        raise TypeError("content must be a string.")
    if model is None:
        model = os.getenv("LLM_MODEL", None)
    reg = registry if registry is not None else default_server_registry()
    spec = reg.resolve(model)

    protocol = spec.capabilities.tokenize_protocol
    if protocol == "anthropic-count-tokens":
        raise TokenizeError(
            f"Engine '{spec.engine}' tokenization is not yet implemented."
        )
    handler = _TOKENIZE_DISPATCH.get(protocol) if protocol else None
    if handler is None:
        raise TokenizeError(
            f"Engine '{spec.engine}' does not support token counting."
        )
    return handler(spec, content)
