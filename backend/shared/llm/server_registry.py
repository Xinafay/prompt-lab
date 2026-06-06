from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from shared.llm._io import load_json


@dataclass(frozen=True)
class ModelSpec:
    """Resolved model routing details from .servers.jsonc."""

    server_name: str
    server_type: str
    model_name: str
    api_key: Optional[str]
    base_url: Optional[str]
    no_verify_tls: bool = False


def _servers_config_path() -> str:
    return os.path.join(os.getcwd(), ".servers.jsonc")


def _split_model_ref(model: str) -> Tuple[str, str]:
    if "/" not in model:
        raise ValueError(
            "Model must be in the format '<server>/<model>', e.g. 'openai/gpt-5-mini'."
        )
    server_name, model_name = model.split("/", 1)
    if not server_name or not model_name:
        raise ValueError(
            "Model must be in the format '<server>/<model>', e.g. 'openai/gpt-5-mini'."
        )
    return server_name, model_name


def _resolve_env_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if value.startswith("env:"):
        env_key = value[4:]
        env_value = os.getenv(env_key)
        if not env_value:
            raise ValueError(f"Missing environment variable: {env_key}")
        return env_value
    return value


def _resolve_no_verify_tls(server_name: str, server: Dict[str, Any]) -> bool:
    raw_value = server.get("no_verify_tls", server.get("no-verify-tls", False))
    if isinstance(raw_value, bool):
        return raw_value
    raise ValueError(f"Server option 'no_verify_tls' for '{server_name}' must be a boolean.")


class ServerRegistry:
    """Server configuration loaded from .servers.jsonc."""

    def __init__(self, servers: Dict[str, Dict[str, Any]], source_path: str | None = None) -> None:
        self._servers = servers
        self._source_path = source_path or "<unknown>"

    @classmethod
    def from_jsonc(cls, path: str) -> "ServerRegistry":
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing servers config: {path}")
        data = load_json(path)
        if not isinstance(data, dict):
            raise ValueError("Servers config must be a JSON object at the top level.")
        return cls(data, source_path=path)

    def resolve(self, model: Optional[str]) -> ModelSpec:
        """Resolve a model reference like 'openai/gpt-5-mini' to a ModelSpec."""

        if not model:
            raise ValueError("Model is required. Set LLM_MODEL or pass `model` explicitly.")

        server_name, model_name = _split_model_ref(model)
        server = self._servers.get(server_name)
        if server is None:
            raise ValueError(f"Unknown server '{server_name}' in {self._source_path}")

        server_type = server.get("type")
        if server_type not in {"openai", "local"}:
            raise ValueError(f"Unsupported server type '{server_type}' for '{server_name}'.")

        raw_api_key = server.get("api_key")
        api_key = _resolve_env_value(raw_api_key)
        if server_type == "local" and not api_key:
            api_key = "api_key"
        if server_type == "openai" and not api_key:
            raise ValueError(f"Missing api_key for server '{server_name}'.")

        base_url = server.get("host") or server.get("api_base") or server.get("base_url")
        if server_type == "local" and not base_url:
            raise ValueError(f"Missing host for local server '{server_name}'.")
        if base_url and server_type in {"local", "openai"} and not base_url.rstrip("/").endswith("/v1"):
            base_url = f"{base_url.rstrip('/')}/v1"
        no_verify_tls = _resolve_no_verify_tls(server_name, server)

        return ModelSpec(
            server_name=server_name,
            server_type=server_type,
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
            no_verify_tls=no_verify_tls,
        )


_DEFAULT_REGISTRY: Optional[ServerRegistry] = None


def default_server_registry() -> ServerRegistry:
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = ServerRegistry.from_jsonc(_servers_config_path())
    return _DEFAULT_REGISTRY


def reset_default_server_registry() -> None:
    global _DEFAULT_REGISTRY
    _DEFAULT_REGISTRY = None
