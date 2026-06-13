from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from prompt_lab.case_context import materialize_case_context
from prompt_lab.models.artifacts import CaseArtifact


def valid_case_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "prompt_lab.case/v2",
        "id": "case-a",
        "title": "Case A",
        "stores": {
            "case": {
                "kind": "flat_file_tree",
                "values": {
                    "chapter": {
                        "scene.md": {
                            "__carmilla_flat_file_node__": "file",
                            "value": "Hello",
                        },
                        "notes.json": {
                            "__carmilla_flat_file_node__": "file",
                            "value": {"beats": ["open", "close"]},
                        },
                    }
                },
            }
        },
        "bindings": {
            "chapter": {"kind": "store_scope", "store": "case", "path": "chapter"},
            "scene_text": {
                "kind": "store_scope",
                "store": "case",
                "path": "chapter/scene.md",
            },
            "literal": {"kind": "value", "value": {"draft": ["keep"]}},
        },
    }
    payload.update(overrides)
    return payload


def assert_value_error(case: CaseArtifact, message: str) -> None:
    try:
        materialize_case_context(case)
    except ValueError as error:
        assert message in str(error)
    else:
        raise AssertionError(f"Expected ValueError containing {message!r}")


def test_materialize_case_context_resolves_bindings() -> None:
    case = CaseArtifact.model_validate(valid_case_payload())

    context = materialize_case_context(case)

    assert context == {
        "chapter": {
            "scene.md": "Hello",
            "notes.json": {"beats": ["open", "close"]},
        },
        "scene_text": "Hello",
        "literal": {"draft": ["keep"]},
    }

    context["literal"]["draft"].append("changed")
    assert materialize_case_context(case)["literal"] == {"draft": ["keep"]}


def test_materialize_case_context_resolves_empty_path_to_root() -> None:
    case = CaseArtifact.model_validate(
        valid_case_payload(
            bindings={"root": {"kind": "store_scope", "store": "case"}}
        )
    )

    assert materialize_case_context(case) == {
        "root": {
            "chapter": {
                "scene.md": "Hello",
                "notes.json": {"beats": ["open", "close"]},
            }
        }
    }


def test_materialize_case_context_rejects_missing_store_and_scope_path() -> None:
    missing_store = CaseArtifact.model_validate(
        valid_case_payload(
            bindings={"bad": {"kind": "store_scope", "store": "missing"}}
        )
    )
    missing_path = CaseArtifact.model_validate(
        valid_case_payload(
            bindings={
                "bad": {
                    "kind": "store_scope",
                    "store": "case",
                    "path": "chapter/missing.md",
                }
            }
        )
    )

    assert_value_error(missing_store, "missing store 'missing'")
    assert_value_error(missing_path, "missing scope path 'chapter/missing.md'")


def test_materialize_case_context_rejects_malformed_file_node() -> None:
    case = CaseArtifact.model_validate(
        valid_case_payload(
            stores={
                "case": {
                    "kind": "flat_file_tree",
                    "values": {
                        "bad.md": {
                            "__carmilla_flat_file_node__": "folder",
                            "value": "Hello",
                        }
                    },
                }
            },
            bindings={"bad": {"kind": "store_scope", "store": "case"}},
        )
    )

    assert_value_error(case, "malformed file node")


def test_materialize_case_context_rejects_non_object_directory_entry() -> None:
    case = CaseArtifact.model_validate(
        valid_case_payload(
            stores={
                "case": {
                    "kind": "flat_file_tree",
                    "values": {"chapter": {"scene.md": "Hello"}},
                }
            },
            bindings={"bad": {"kind": "store_scope", "store": "case"}},
        )
    )

    assert_value_error(case, "directory entry 'chapter/scene.md' is not an object")


def test_case_artifact_rejects_old_v1_variables_shape() -> None:
    try:
        CaseArtifact.model_validate(
            {
                "schema_version": "prompt_lab.case/v1",
                "id": "case-a",
                "title": "Case A",
                "variables": {"chapter_text": "Hello"},
            }
        )
    except ValidationError as error:
        assert "prompt_lab.case/v2" in str(error)
    else:
        raise AssertionError("Expected old v1 case shape to be rejected")


def main() -> int:
    tests = [
        test_materialize_case_context_resolves_bindings,
        test_materialize_case_context_resolves_empty_path_to_root,
        test_materialize_case_context_rejects_missing_store_and_scope_path,
        test_materialize_case_context_rejects_malformed_file_node,
        test_materialize_case_context_rejects_non_object_directory_entry,
        test_case_artifact_rejects_old_v1_variables_shape,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
