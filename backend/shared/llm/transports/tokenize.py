from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Any

import httpx

from shared.llm.server_registry import ModelSpec
from shared.llm.transports.openai_client import _get_openai_client


class TokenizeError(Exception):
    """Raised when token counting fails or is unsupported for an engine."""


_DEFAULT_TIMEOUT = 30.0


def _host_root(spec: ModelSpec) -> str:
    """Return the server base URL without the trailing OpenAI-compatible ``/v1``.

    Self-hosted tokenize endpoints (llama.cpp ``/tokenize``, vLLM ``/tokenize``,
    llama-swap ``/upstream/{model}/tokenize``) live outside the ``/v1`` namespace.
    """
    base = spec.base_url or ""
    if not base:
        raise TokenizeError(f"Server '{spec.server_name}' has no host configured.")
    return re.sub(r"/v1/?$", "", base).rstrip("/")


def _post_json(spec: ModelSpec, path: str, payload: dict[str, Any]) -> Any:
    url = f"{_host_root(spec)}{path}"
    headers = {"Content-Type": "application/json"}
    if spec.api_key:
        headers["Authorization"] = f"Bearer {spec.api_key}"
    try:
        response = httpx.post(
            url,
            json=payload,
            headers=headers,
            timeout=_DEFAULT_TIMEOUT,
            verify=not spec.no_verify_tls,
        )
    except httpx.HTTPError as exc:
        raise TokenizeError(f"Tokenize request to {url} failed: {exc}") from exc
    if response.status_code != 200:
        raise TokenizeError(
            f"Tokenize request to {url} returned status {response.status_code}: {response.text}"
        )
    try:
        return response.json()
    except ValueError as exc:
        raise TokenizeError(f"Tokenize response from {url} was not valid JSON.") from exc


def _tokens_len(payload: Any, *, endpoint: str) -> int:
    if not isinstance(payload, dict) or not isinstance(payload.get("tokens"), list):
        raise TokenizeError(f"Unexpected tokenize response from {endpoint}: {payload!r}")
    return len(payload["tokens"])


def count_tokens_llamacpp(spec: ModelSpec, content: str) -> int:
    """llama.cpp native ``POST /tokenize`` → ``{"tokens": [...]}``."""
    payload = _post_json(spec, "/tokenize", {"content": content})
    return _tokens_len(payload, endpoint="/tokenize")


def count_tokens_llama_swap(spec: ModelSpec, content: str) -> int:
    """llama-swap ``POST /upstream/{model}/tokenize`` forwarded to llama.cpp.

    The ``{model}`` segment is the same identifier used for chat requests, so
    llama-swap routes (and loads) the right upstream before tokenizing.
    """
    path = f"/upstream/{spec.model_name}/tokenize"
    payload = _post_json(spec, path, {"content": content})
    return _tokens_len(payload, endpoint=path)


def count_tokens_vllm(spec: ModelSpec, content: str) -> int:
    """vLLM ``POST /tokenize`` → ``{"count": N, "tokens": [...]}``."""
    payload = _post_json(spec, "/tokenize", {"model": spec.model_name, "prompt": content})
    if isinstance(payload, dict):
        count = payload.get("count")
        if isinstance(count, int) and not isinstance(count, bool):
            return count
    return _tokens_len(payload, endpoint="/tokenize")


def count_tokens_openai_input_tokens(spec: ModelSpec, content: str) -> int:
    """Hosted OpenAI ``POST /v1/responses/input_tokens`` via the SDK.

    Counts exactly what the model would receive for the given text input.
    """
    client = _get_openai_client(SimpleNamespace(spec=spec))
    try:
        result = client.responses.input_tokens.count(model=spec.model_name, input=content)
    except Exception as exc:  # surface SDK/transport errors as TokenizeError
        raise TokenizeError(f"OpenAI input-token count failed: {exc}") from exc

    value = getattr(result, "input_tokens", None)
    if value is None and isinstance(result, dict):
        value = result.get("input_tokens")
    if not isinstance(value, int) or isinstance(value, bool):
        raise TokenizeError(f"Unexpected input-token count response: {result!r}")
    return value
