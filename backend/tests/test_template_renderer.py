from __future__ import annotations

from prompt_lab.models.artifacts import CaseArtifact
from prompt_lab.template_renderer import render_prompt


def test_render_prompt_uses_case_variables() -> None:
    case = CaseArtifact.model_validate(
        {
            "schema_version": "prompt_lab.case/v1",
            "id": "case-a",
            "title": "Case A",
            "variables": {"name": "Ada"},
        }
    )

    assert render_prompt("Hello {{ name }}.", case) == "Hello Ada."


def test_render_prompt_supports_lists() -> None:
    case = CaseArtifact.model_validate(
        {
            "schema_version": "prompt_lab.case/v1",
            "id": "case-a",
            "title": "Case A",
            "variables": {"items": ["a", "b"]},
        }
    )

    rendered = render_prompt("{% for item in items %}{{ item }}{% endfor %}", case)
    assert rendered == "ab"


def main() -> int:
    tests = [
        test_render_prompt_uses_case_variables,
        test_render_prompt_supports_lists,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
