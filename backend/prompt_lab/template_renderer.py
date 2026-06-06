from __future__ import annotations

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from prompt_lab.models.artifacts import CaseArtifact


_ENV = SandboxedEnvironment(undefined=StrictUndefined, autoescape=False)


def render_prompt(template_text: str, case: CaseArtifact) -> str:
    """Render a prompt template with case variables."""
    template = _ENV.from_string(template_text)
    return template.render(case.variables)
