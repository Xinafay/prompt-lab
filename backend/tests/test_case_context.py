from __future__ import annotations

from prompt_lab.case_context import materialize_case_context
from prompt_lab.models.artifacts import CaseArtifact


def test_materialize_case_context_returns_plain_payload_copy() -> None:
    case = CaseArtifact.model_validate(
        {
            "id": "case-a",
            "payload": {
                "chapter": {
                    "data": {"title": "Intro", "parts": ["open"]},
                    "summary": "Hello",
                },
                "computed": {"name": "Ada"},
            },
        }
    )

    context = materialize_case_context(case)

    assert context == {
        "chapter": {
            "data": {"title": "Intro", "parts": ["open"]},
            "summary": "Hello",
        },
        "computed": {"name": "Ada"},
    }
    context["chapter"]["data"]["parts"].append("changed")
    assert materialize_case_context(case)["chapter"]["data"]["parts"] == ["open"]


def main() -> int:
    test_materialize_case_context_returns_plain_payload_copy()
    print("OK: test_materialize_case_context_returns_plain_payload_copy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
