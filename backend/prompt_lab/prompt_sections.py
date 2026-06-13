from __future__ import annotations

import json


def json_block(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def fenced_section(name: str, body: str, *, fence: str = "text") -> str:
    return f"<<<{name}\n```{fence}\n{body}\n```\n{name}>>>"
