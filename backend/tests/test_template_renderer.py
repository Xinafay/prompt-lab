from __future__ import annotations

from jinja2 import UndefinedError
from jinja2.exceptions import SecurityError

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


def test_render_prompt_missing_variables_raise_undefined_error() -> None:
    case = CaseArtifact.model_validate(
        {
            "schema_version": "prompt_lab.case/v1",
            "id": "case-a",
            "title": "Case A",
            "variables": {},
        }
    )

    try:
        render_prompt("Hello {{ name }}.", case)
    except UndefinedError:
        pass
    else:
        raise AssertionError("Expected UndefinedError")


def test_render_prompt_unsafe_attribute_access_raises_security_error() -> None:
    case = CaseArtifact.model_validate(
        {
            "schema_version": "prompt_lab.case/v1",
            "id": "case-a",
            "title": "Case A",
            "variables": {"name": "Ada"},
        }
    )

    try:
        render_prompt("{{ name.__class__ }}", case)
    except SecurityError:
        pass
    else:
        raise AssertionError("Expected SecurityError")


def test_render_prompt_does_not_expose_case_metadata() -> None:
    case = CaseArtifact.model_validate(
        {
            "schema_version": "prompt_lab.case/v1",
            "id": "case-a",
            "title": "Case A",
            "variables": {},
        }
    )

    try:
        render_prompt("{{ case.id }}", case)
    except UndefinedError:
        pass
    else:
        raise AssertionError("Expected UndefinedError")


def test_render_prompt_default_globals_are_not_visible() -> None:
    case = CaseArtifact.model_validate(
        {
            "schema_version": "prompt_lab.case/v1",
            "id": "case-a",
            "title": "Case A",
            "variables": {},
        }
    )

    try:
        render_prompt("{% for index in range(2) %}{{ index }}{% endfor %}", case)
    except UndefinedError:
        pass
    else:
        raise AssertionError("Expected UndefinedError")


def main() -> int:
    tests = [
        test_render_prompt_uses_case_variables,
        test_render_prompt_supports_lists,
        test_render_prompt_missing_variables_raise_undefined_error,
        test_render_prompt_unsafe_attribute_access_raises_security_error,
        test_render_prompt_does_not_expose_case_metadata,
        test_render_prompt_default_globals_are_not_visible,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
