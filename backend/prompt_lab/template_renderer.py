from __future__ import annotations

from typing import Any

from shared.jinjax import Template


def render_prompt(template_text: str, context: dict[str, Any]) -> str:
    """Render a prompt template with a materialized case context."""
    return Template(template_text).render(context)
