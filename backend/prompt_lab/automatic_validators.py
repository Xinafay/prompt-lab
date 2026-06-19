from __future__ import annotations

import json
import re
from typing import Any

from prompt_lab.models.artifacts import RunArtifact
from prompt_lab.models.validators import (
    AutomaticRule,
    AutomaticValidatorDefinition,
    CountComparison,
    ValidationCheckResult,
    ValidationResultArtifact,
)


def execute_automatic_validator(
    validation_batch_id: str,
    run: RunArtifact,
    validator: AutomaticValidatorDefinition,
) -> ValidationResultArtifact:
    try:
        check_results = [
            _execute_check(run, check.check_id, check.rule) for check in validator.checks
        ]
        return _validation_result(
            validation_batch_id,
            run,
            validator,
            status="ok",
            included_in_judge=True,
            check_results=check_results,
            execution_error=None,
        )
    except ValueError as exc:
        return _validation_result(
            validation_batch_id,
            run,
            validator,
            status="error",
            included_in_judge=False,
            check_results=[],
            execution_error=str(exc),
        )


def _validation_result(
    validation_batch_id: str,
    run: RunArtifact,
    validator: AutomaticValidatorDefinition,
    *,
    status: str,
    included_in_judge: bool,
    check_results: list[ValidationCheckResult],
    execution_error: str | None,
) -> ValidationResultArtifact:
    return ValidationResultArtifact.model_validate(
        {
            "schema_version": "prompt_lab.validation_result/v1",
            "validation_result_id": (
                f"{validation_batch_id}-{run.case_id}-"
                f"repeat-{run.repeat_index:03d}-{validator.validator_id}"
            ),
            "validation_batch_id": validation_batch_id,
            "run_batch_id": run.run_batch_id,
            "run_id": run.run_id,
            "case_id": run.case_id,
            "repeat_index": run.repeat_index,
            "validator_id": validator.validator_id,
            "validator_type": "automatic",
            "status": status,
            "included_in_judge": included_in_judge,
            "check_results": [result.model_dump(mode="json") for result in check_results],
            "usage": {},
            "execution_error": execution_error,
        }
    )


def _execute_check(
    run: RunArtifact,
    check_id: str,
    rule: AutomaticRule,
) -> ValidationCheckResult:
    value = _measure(run, rule)
    if rule.kind == "json_path_exists":
        verdict = "yes" if value == 1 else "no"
    else:
        if rule.comparison is None:
            raise ValueError(f"{rule.kind} requires comparison")
        verdict = "yes" if _compare(value, rule.comparison) else "no"
    return ValidationCheckResult(
        check_id=check_id,
        verdict=verdict,
        included_in_judge=True,
        metrics={"value": value},
    )


def _measure(run: RunArtifact, rule: AutomaticRule) -> int:
    source = rule.source
    if rule.kind == "word_count":
        text = _text_source(run, source)
        return len(re.findall(r"\S+", text))
    if rule.kind == "sentence_count":
        text = _text_source(run, source).strip()
        if not text:
            return 0
        sentences = [part for part in re.split(r"[.!?]+", text) if part.strip()]
        return len(sentences) if sentences else 1
    if rule.kind == "character_count":
        return len(_text_source(run, source))
    if rule.kind in {"json_path_count", "json_path_exists"}:
        target = _resolve_json_path(_json_source(run, source), rule.path)
        if rule.kind == "json_path_exists":
            return 1
        if target is None:
            return 0
        if isinstance(target, (list, dict, str)):
            return len(target)
        raise ValueError("json_path_count target is not countable")
    raise ValueError(f"Unsupported automatic validator rule: {rule.kind}")


def _text_source(run: RunArtifact, source: str) -> str:
    if source == "output_text" and run.output_text is not None:
        return run.output_text
    if source == "raw_output" and run.raw_output is not None:
        return run.raw_output
    if source == "output_json" and run.output_json is not None:
        return json.dumps(run.output_json, ensure_ascii=False)
    raise ValueError(f"Source {source} is unavailable")


def _json_source(run: RunArtifact, source: str) -> Any:
    if source == "output_json" and run.output_json is not None:
        return run.output_json
    raise ValueError(f"Source {source} is unavailable")


def _resolve_json_path(root: Any, path: str | None) -> Any:
    if path is None:
        raise ValueError("JSON path is required")
    current = root
    for segment in path.split("."):
        if not segment:
            raise ValueError("JSON path cannot contain empty segments")
        if isinstance(current, dict):
            if segment not in current:
                raise ValueError(f"JSON path not found: {path}")
            current = current[segment]
        elif isinstance(current, list):
            try:
                index = int(segment)
            except ValueError as exc:
                raise ValueError(f"JSON path segment is not a list index: {segment}") from exc
            if index < 0 or index >= len(current):
                raise ValueError(f"JSON path not found: {path}")
            current = current[index]
        else:
            raise ValueError(f"JSON path not found: {path}")
    return current


def _compare(value: int, comparison: CountComparison) -> bool:
    if comparison.op == "lt":
        return value < _comparison_value(comparison)
    if comparison.op == "lte":
        return value <= _comparison_value(comparison)
    if comparison.op == "gt":
        return value > _comparison_value(comparison)
    if comparison.op == "gte":
        return value >= _comparison_value(comparison)
    if comparison.op == "eq":
        return value == _comparison_value(comparison)
    if comparison.op == "between":
        if comparison.min_value is None or comparison.max_value is None:
            raise ValueError("between comparison requires min_value and max_value")
        return comparison.min_value <= value <= comparison.max_value
    raise ValueError(f"Unsupported comparison: {comparison.op}")


def _comparison_value(comparison: CountComparison) -> float:
    if comparison.value is None:
        raise ValueError(f"{comparison.op} comparison requires value")
    return comparison.value
