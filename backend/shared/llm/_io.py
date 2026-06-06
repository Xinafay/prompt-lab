from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyjson5

JsonData = dict[str, Any] | list[Any]

_ENCODINGS = ("utf-8", "utf-8-sig", "cp1250")


def _is_json5_path(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in {".jsonc", ".json5"}


def load_json(file_path: str, default: JsonData | None = None) -> JsonData:
    last_error: Exception | None = None
    for encoding in _ENCODINGS:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                content = f.read()
            if _is_json5_path(file_path):
                return pyjson5.decode(content)
            return json.loads(content)
        except FileNotFoundError:
            raise
        except Exception as exc:
            last_error = exc
    if default is not None:
        return default
    if last_error is not None:
        raise last_error
    raise ValueError("No JSON encodings configured.")
