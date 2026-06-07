from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

_PROMPTS_DIR = Path(__file__).with_name("system_prompts")
_ENV = SandboxedEnvironment(
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
    undefined=StrictUndefined,
)


def render_system_prompt(template_name: str, context: dict[str, Any]) -> str:
    template_path = (_PROMPTS_DIR / template_name).resolve()
    prompts_root = _PROMPTS_DIR.resolve()
    if (
        template_path == prompts_root
        or not template_path.is_relative_to(prompts_root)
        or not template_path.is_file()
    ):
        raise FileNotFoundError(f"Prompt template not found: {template_name}")
    template = _ENV.from_string(template_path.read_text(encoding="utf-8"))
    return template.render(context).strip()
