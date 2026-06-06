from __future__ import annotations

from typing import Any, cast

from pydantic import TypeAdapter


_JSON_SCHEMA_METADATA_KEYS = frozenset(
    {
        "$anchor",
        "$defs",
        "$dynamicAnchor",
        "$dynamicRef",
        "$id",
        "$ref",
        "$schema",
        "additionalProperties",
        "allOf",
        "anyOf",
        "const",
        "contains",
        "contentEncoding",
        "contentMediaType",
        "default",
        "definitions",
        "dependentRequired",
        "dependentSchemas",
        "deprecated",
        "description",
        "else",
        "enum",
        "examples",
        "exclusiveMaximum",
        "exclusiveMinimum",
        "format",
        "if",
        "maxContains",
        "maxItems",
        "maxLength",
        "maxProperties",
        "maximum",
        "minContains",
        "minItems",
        "minLength",
        "minProperties",
        "minimum",
        "multipleOf",
        "not",
        "oneOf",
        "pattern",
        "patternProperties",
        "prefixItems",
        "properties",
        "propertyNames",
        "readOnly",
        "required",
        "then",
        "title",
        "type",
        "unevaluatedItems",
        "unevaluatedProperties",
        "uniqueItems",
        "writeOnly",
    }
)

_SCHEMA_PRIMITIVE_TYPES: frozenset[str] = frozenset(
    {"string", "integer", "number", "boolean", "array", "object", "null"}
)

_UNAMBIGUOUS_SCHEMA_KEYS: frozenset[str] = frozenset(
    {"anyOf", "allOf", "oneOf", "$ref", "additionalProperties", "prefixItems", "unevaluatedProperties"}
)


def _resolve_schema_ref(node: dict[str, Any], *, root_schema: dict[str, Any]) -> dict[str, Any]:
    ref = node.get("$ref")
    if not isinstance(ref, str):
        return node
    if ref.startswith("#/$defs/"):
        ref_name = ref.removeprefix("#/$defs/")
        defs = root_schema.get("$defs")
        if isinstance(defs, dict):
            target = defs.get(ref_name)
            if isinstance(target, dict):
                resolved = dict(target)
                for key, value in node.items():
                    if key != "$ref":
                        resolved[key] = value
                return resolved
    if ref.startswith("#/definitions/"):
        ref_name = ref.removeprefix("#/definitions/")
        defs = root_schema.get("definitions")
        if isinstance(defs, dict):
            target = defs.get(ref_name)
            if isinstance(target, dict):
                resolved = dict(target)
                for key, value in node.items():
                    if key != "$ref":
                        resolved[key] = value
                return resolved
    return node


def _sanitize_payload_with_schema(payload: Any, *, schema: Any, root_schema: dict[str, Any]) -> Any:
    if not isinstance(schema, dict):
        return payload

    resolved_schema = _resolve_schema_ref(schema, root_schema=root_schema)
    if isinstance(payload, dict):
        properties = resolved_schema.get("properties")
        if isinstance(properties, dict):
            cleaned: dict[str, Any] = {}
            for key, value in payload.items():
                child_schema = properties.get(key)
                if child_schema is not None:
                    cleaned[key] = _sanitize_payload_with_schema(
                        value,
                        schema=child_schema,
                        root_schema=root_schema,
                    )
                    continue
                if key in _JSON_SCHEMA_METADATA_KEYS:
                    continue
                cleaned[key] = value
            return cleaned

        schema_type = resolved_schema.get("type")
        if schema_type == "array" and "items" in payload:
            other_keys = [
                key
                for key in payload
                if key != "items" and key not in _JSON_SCHEMA_METADATA_KEYS
            ]
            if not other_keys:
                return _sanitize_payload_with_schema(
                    payload["items"],
                    schema=resolved_schema.get("items"),
                    root_schema=root_schema,
                )
        return payload

    if isinstance(payload, list):
        item_schema = resolved_schema.get("items")
        if item_schema is None:
            return payload
        return [
            _sanitize_payload_with_schema(item, schema=item_schema, root_schema=root_schema)
            for item in payload
        ]

    return payload


def _sanitize_structured_payload(payload: Any, *, response_model: Any) -> Any:
    schema = _schema_dict(response_model)
    return _sanitize_payload_with_schema(payload, schema=schema, root_schema=schema)


def _schema_dict(response_model: Any) -> dict[str, Any]:
    if hasattr(response_model, "model_json_schema"):
        return cast(dict[str, Any], response_model.model_json_schema())
    return cast(dict[str, Any], TypeAdapter(response_model).json_schema())


def _looks_like_schema_echo(payload: Any) -> bool:
    if not isinstance(payload, dict) or not payload:
        return False
    if all(k in _JSON_SCHEMA_METADATA_KEYS for k in payload):
        return True
    for v in payload.values():
        if not isinstance(v, dict):
            continue
        if _UNAMBIGUOUS_SCHEMA_KEYS & v.keys():
            return True
        v_type = v.get("type")
        if isinstance(v_type, str) and v_type in _SCHEMA_PRIMITIVE_TYPES:
            return True
    return False


def _generate_skeleton_payload(schema: Any, *, root_schema: dict[str, Any]) -> Any:
    """Generate a structurally-typed empty payload from a JSON schema.

    Used to replace a model's schema-echo response with a blank skeleton in the
    repair conversation, so the model sees its "previous" output as obviously
    empty rather than as the schema text.
    """
    if not isinstance(schema, dict):
        return None

    resolved = _resolve_schema_ref(schema, root_schema=root_schema)

    if "const" in resolved:
        return resolved["const"]

    enum = resolved.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]

    for variants_key in ("anyOf", "oneOf"):
        variants = resolved.get(variants_key)
        if isinstance(variants, list) and variants:
            non_null = [v for v in variants if isinstance(v, dict) and v.get("type") != "null"]
            chosen = non_null[0] if non_null else variants[0]
            return _generate_skeleton_payload(chosen, root_schema=root_schema)

    schema_type = resolved.get("type")
    if isinstance(schema_type, list):
        non_null_types = [t for t in schema_type if t != "null"]
        schema_type = non_null_types[0] if non_null_types else "null"

    if schema_type == "string":
        return ""
    if schema_type == "integer":
        return 0
    if schema_type == "number":
        return 0
    if schema_type == "boolean":
        return False
    if schema_type == "null":
        return None
    if schema_type == "array":
        return []
    if schema_type == "object":
        properties = resolved.get("properties")
        if not isinstance(properties, dict):
            return {}
        return {
            key: _generate_skeleton_payload(prop_schema, root_schema=root_schema)
            for key, prop_schema in properties.items()
        }

    return None


def _try_unwrap_schema_shaped_payload(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    inner = payload.get("properties")
    if not isinstance(inner, dict):
        return None
    other_keys = {k for k in payload if k != "properties"}
    if not other_keys.issubset(_JSON_SCHEMA_METADATA_KEYS):
        return None
    return inner
