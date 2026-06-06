from __future__ import annotations

from typing import Any


_MODEL_PLACEHOLDER = "<<MODEL>>"
_ERROR_PLACEHOLDER = "<<ERROR>>"
_DEFAULT_FIX_PROMPT = """Your previous response was invalid for the required JSON schema.

Error:
<<ERROR>>

Return only corrected JSON that matches this schema:
<<MODEL>>"""


def _render_prompt(template: str, *, schema_text: str, require_model: bool) -> str:
    if require_model and _MODEL_PLACEHOLDER not in template:
        raise ValueError(f"Prompt must contain {_MODEL_PLACEHOLDER}.")
    return template.replace(_MODEL_PLACEHOLDER, schema_text)


def _render_fix_prompt_template(fix_prompt: str | None, *, schema_text: str) -> str:
    template = _DEFAULT_FIX_PROMPT if fix_prompt is None else fix_prompt
    if _ERROR_PLACEHOLDER not in template:
        raise ValueError(f"fix_prompt must contain {_ERROR_PLACEHOLDER}.")
    return _render_prompt(template, schema_text=schema_text, require_model=False)


def _visible_prompt_messages(
    base_messages: list[dict[str, Any]],
    prompt_text: str,
    *,
    prompt_role: str,
    include_system_messages: bool,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if include_system_messages:
        for msg in base_messages:
            if msg.get("role") in {"system", "developer"} and msg.get("content"):
                result.append({"role": msg["role"], "content": msg["content"]})
    result.append({"role": prompt_role, "content": prompt_text})
    return result
