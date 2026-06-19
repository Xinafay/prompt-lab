from __future__ import annotations

from shared.jinjax import Template


def test_copied_jinjax_template_renders_dict_context() -> None:
    rendered = Template("Hello {{ chapter.name }}").render(
        {"chapter": {"name": "Ada"}}
    )

    assert rendered == "Hello Ada"


def test_copied_jinjax_tojson_filter_uses_carmilla_output() -> None:
    rendered = Template("{{ value | tojson }}").render({"value": "a\u2028b"})

    assert rendered == '"a\\u2028b"'


def main() -> int:
    tests = [
        test_copied_jinjax_template_renders_dict_context,
        test_copied_jinjax_tojson_filter_uses_carmilla_output,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
