from __future__ import annotations

import json
from typing import Any, cast


def _count_chars_words(text: str) -> tuple[int, int]:
    if not text:
        return 0, 0
    return len(text), len(text.split())


def _usage_tokens(usage: dict[str, Any] | None) -> tuple[Any | None, Any | None, Any | None]:
    if not usage:
        return None, None, None
    return (
        usage.get("prompt_tokens"),
        usage.get("completion_tokens"),
        usage.get("total_tokens"),
    )


def _flatten_usage_details(
    usage: dict[str, Any] | None,
    *,
    prefix: str = "",
) -> dict[str, Any]:
    if not usage:
        return {}
    result: dict[str, Any] = {}
    for key, value in usage.items():
        if key in {"prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens"}:
            continue
        if value is None:
            continue
        name = f"{prefix}{key}" if prefix else key
        if isinstance(value, dict):
            result.update(_flatten_usage_details(value, prefix=f"{name}."))
        elif value != 0:
            result[name] = value
    return result


def _normalize_usage_numeric(usage: dict[str, Any] | None) -> dict[str, Any] | None:
    if not usage:
        return None
    result: dict[str, Any] = {}
    for key, value in usage.items():
        if isinstance(value, dict):
            nested = _normalize_usage_numeric(cast(dict[str, Any], value))
            if nested:
                result[key] = nested
            continue
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            result[key] = value
    return result or None


def _merge_usage_dicts(total: dict[str, Any], incoming: dict[str, Any]) -> None:
    for key, value in incoming.items():
        if isinstance(value, dict):
            current = total.get(key)
            if not isinstance(current, dict):
                total[key] = {}
                current = cast(dict[str, Any], total[key])
            _merge_usage_dicts(cast(dict[str, Any], current), cast(dict[str, Any], value))
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        current_value = total.get(key)
        if isinstance(current_value, bool) or not isinstance(current_value, (int, float)):
            total[key] = value
        else:
            total[key] = current_value + value


def _accumulate_usage(
    total: dict[str, Any] | None,
    usage: dict[str, Any] | None,
) -> dict[str, Any] | None:
    normalized = _normalize_usage_numeric(usage)
    if normalized is None:
        return total
    if total is None:
        return cast(dict[str, Any], json.loads(json.dumps(normalized)))
    _merge_usage_dicts(total, normalized)
    return total


def normalize_usage(usage: Any) -> dict[str, Any] | None:
    """Normalize SDK/model usage payloads into plain dicts."""

    if usage is None:
        return None
    result: dict[str, Any]
    if isinstance(usage, dict):
        result = dict(usage)
    elif hasattr(usage, "model_dump"):
        result = cast(dict[str, Any], usage.model_dump())
    elif hasattr(usage, "dict"):
        result = cast(dict[str, Any], usage.dict())
    elif hasattr(usage, "__dict__"):
        result = cast(dict[str, Any], dict(usage.__dict__))
    else:
        return {"value": str(usage)}

    input_tokens = result.get("input_tokens")
    output_tokens = result.get("output_tokens")
    input_tokens_details = result.get("input_tokens_details")
    output_tokens_details = result.get("output_tokens_details")
    prompt_tokens = result.get("prompt_tokens")
    completion_tokens = result.get("completion_tokens")
    prompt_tokens_details = result.get("prompt_tokens_details")
    completion_tokens_details = result.get("completion_tokens_details")
    total_tokens = result.get("total_tokens")
    if isinstance(input_tokens, (int, float)) and "prompt_tokens" not in result:
        result["prompt_tokens"] = input_tokens
    if isinstance(output_tokens, (int, float)) and "completion_tokens" not in result:
        result["completion_tokens"] = output_tokens
    if isinstance(prompt_tokens, (int, float)) and "input_tokens" not in result:
        result["input_tokens"] = prompt_tokens
    if isinstance(completion_tokens, (int, float)) and "output_tokens" not in result:
        result["output_tokens"] = completion_tokens
    if input_tokens_details is None and prompt_tokens_details is not None:
        result["input_tokens_details"] = prompt_tokens_details
    if output_tokens_details is None and completion_tokens_details is not None:
        result["output_tokens_details"] = completion_tokens_details

    normalized_input_tokens = result.get("input_tokens")
    normalized_output_tokens = result.get("output_tokens")
    if (
        "total_tokens" not in result
        and isinstance(normalized_input_tokens, (int, float))
        and isinstance(normalized_output_tokens, (int, float))
    ):
        result["total_tokens"] = normalized_input_tokens + normalized_output_tokens
    elif (
        total_tokens is None
        and isinstance(normalized_input_tokens, (int, float))
        and isinstance(normalized_output_tokens, (int, float))
    ):
        result["total_tokens"] = normalized_input_tokens + normalized_output_tokens
    return result
