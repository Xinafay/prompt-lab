import os
from typing import Any

from shared.llm._io import load_json


def _models_config_path() -> str:
    return os.path.join(os.getcwd(), ".models.jsonc")


def load_models_config() -> list[str]:
    """Load model names from .models.jsonc in the current working directory."""
    path = _models_config_path()
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing models config: {path}")

    data: Any = load_json(path)
    if not isinstance(data, list):
        raise ValueError("Models config must be a JSON array of model strings.")

    models: list[str] = []
    for item in data:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("Models config entries must be non-empty strings.")
        models.append(item)

    if not models:
        raise ValueError("Models config must list at least one model.")

    return models
