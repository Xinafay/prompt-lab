from __future__ import annotations

from jinja2 import UndefinedError

from prompt_lab.template_renderer import render_prompt


def test_render_prompt_uses_materialized_context() -> None:
    context = {"chapter": {"name": "Ada"}}

    assert render_prompt("Hello {{ chapter.name }}.", context) == "Hello Ada."


def test_render_prompt_supports_lists() -> None:
    context = {"items": ["a", "b"]}

    rendered = render_prompt("{% for item in items %}{{ item }}{% endfor %}", context)
    assert rendered == "ab"


def test_render_prompt_supports_carmilla_tojson_filter() -> None:
    context = {"value": "a\u2028b"}

    assert render_prompt("{{ value | tojson }}", context) == '"a\\u2028b"'
    assert render_prompt("{{ value | tojson(None, False) }}", context) == '"a\u2028b"'


def test_render_prompt_missing_name_raises_undefined_error() -> None:
    try:
        render_prompt("Hello {{ missing.name }}.", {})
    except UndefinedError:
        pass
    else:
        raise AssertionError("Expected UndefinedError")


def main() -> int:
    tests = [
        test_render_prompt_uses_materialized_context,
        test_render_prompt_supports_lists,
        test_render_prompt_supports_carmilla_tojson_filter,
        test_render_prompt_missing_name_raises_undefined_error,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
