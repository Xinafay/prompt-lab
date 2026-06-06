from __future__ import annotations

import json
from typing import Any, cast

from pydantic import TypeAdapter


def schema_dict(response_model: Any) -> dict[str, Any]:
    """Return a JSON schema dictionary for a Pydantic model or supported type."""
    if hasattr(response_model, "model_json_schema"):
        return cast(dict[str, Any], response_model.model_json_schema())
    return cast(dict[str, Any], TypeAdapter(response_model).json_schema())


def schema_text(response_model: Any) -> str:
    """Return formatted JSON schema text for prompt/template inclusion."""
    return json.dumps(schema_dict(response_model), ensure_ascii=False, indent=2)
