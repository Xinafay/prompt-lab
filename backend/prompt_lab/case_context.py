from __future__ import annotations

from copy import deepcopy
from typing import Any

from prompt_lab.models.artifacts import CaseArtifact, StoreScopeBinding, ValueBinding


FILE_NODE_MARKER = "__carmilla_flat_file_node__"
FILE_NODE_KEYS = frozenset({FILE_NODE_MARKER, "value"})


def materialize_case_context(case: CaseArtifact) -> dict[str, Any]:
    """Resolve case bindings into the plain context object used by prompt templates."""

    context: dict[str, Any] = {}
    for name, binding in case.bindings.items():
        if isinstance(binding, ValueBinding):
            context[name] = deepcopy(binding.value)
            continue

        context[name] = _materialize_store_scope(case, binding)
    return context


def _materialize_store_scope(case: CaseArtifact, binding: StoreScopeBinding) -> Any:
    store = case.stores.get(binding.store)
    if store is None:
        raise ValueError(f"missing store {binding.store!r}")

    selected = _resolve_scope_path(store.values, binding.path)
    return _unwrap_tree(selected, _display_path(binding.path))


def _resolve_scope_path(root: dict[str, Any], path: str) -> Any:
    current: Any = root
    normalized_path = path.strip("/")
    if normalized_path == "":
        return current

    for segment in normalized_path.split("/"):
        if not isinstance(current, dict) or _is_file_node(current):
            raise ValueError(f"missing scope path {path!r}")
        if segment not in current:
            raise ValueError(f"missing scope path {path!r}")
        current = current[segment]
    return current


def _unwrap_tree(node: Any, path: str) -> Any:
    if not isinstance(node, dict):
        raise ValueError(f"directory entry {path!r} is not an object")

    if _is_file_node(node):
        return _unwrap_file_node(node, path)
    if _is_malformed_exact_file_node(node):
        raise ValueError(f"malformed file node at {path!r}")

    materialized: dict[str, Any] = {}
    for name, child in node.items():
        child_path = _join_path(path, name)
        if not isinstance(child, dict):
            raise ValueError(f"directory entry {child_path!r} is not an object")
        materialized[name] = _unwrap_tree(child, child_path)
    return materialized


def _unwrap_file_node(node: dict[str, Any], path: str) -> Any:
    if not _is_file_node(node):
        raise ValueError(f"malformed file node at {path!r}")
    return deepcopy(node["value"])


def _is_file_node(node: dict[str, Any]) -> bool:
    return set(node.keys()) == FILE_NODE_KEYS and node[FILE_NODE_MARKER] == "file"


def _is_malformed_exact_file_node(node: dict[str, Any]) -> bool:
    if set(node.keys()) != FILE_NODE_KEYS:
        return False
    marker_value = node[FILE_NODE_MARKER]
    return marker_value != "file" and not isinstance(marker_value, dict)


def _display_path(path: str) -> str:
    normalized = path.strip("/")
    return normalized if normalized else "."


def _join_path(parent: str, child: str) -> str:
    if parent == ".":
        return child
    return f"{parent}/{child}"
