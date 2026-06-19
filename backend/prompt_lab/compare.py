from __future__ import annotations

from collections import Counter
from typing import Any, Literal

from prompt_lab.models.validators import (
    CompareCellDetail,
    CompareMatrixCell,
    CompareMatrixResponse,
    CompareMatrixRow,
    ValidationResultArtifact,
)


def build_compare_matrix(
    *,
    experiment_id: str,
    versions: list[str],
    validator_snapshots_by_version: dict[str, list[dict[str, Any]]],
    results_by_version: dict[str, list[ValidationResultArtifact]],
) -> CompareMatrixResponse:
    return CompareMatrixResponse(
        schema_version="prompt_lab.compare_matrix/v1",
        experiment_id=experiment_id,
        versions=versions,
        rows=[
            CompareMatrixRow(
                validator_id=validator_id,
                validator_title=validator_title,
                check_id=check_id,
                check_title=check_title,
                check_description=check_description,
                cells=[
                    _cell_for_version(
                        version=version,
                        validator_id=validator_id,
                        check_id=check_id,
                        results=results_by_version.get(version, []),
                    )
                    for version in versions
                ],
            )
            for (
                validator_id,
                validator_title,
                check_id,
                check_title,
                check_description,
            ) in _row_keys(versions, validator_snapshots_by_version)
        ],
    )


def _row_keys(
    versions: list[str],
    snapshots_by_version: dict[str, list[dict[str, Any]]],
) -> list[tuple[str, str, str, str, str]]:
    rows: dict[tuple[str, str], tuple[str, str, str, str, str]] = {}
    for version in versions:
        for validator in snapshots_by_version.get(version, []):
            validator_id = _non_empty_string(validator.get("validator_id"))
            if validator_id is None:
                continue
            validator_title = _non_empty_string(validator.get("title")) or validator_id
            checks = validator.get("checks")
            if not isinstance(checks, list):
                continue
            for check in checks:
                if not isinstance(check, dict):
                    continue
                check_id = _non_empty_string(check.get("check_id"))
                if check_id is None:
                    continue
                rows.setdefault(
                    (validator_id, check_id),
                    (
                        validator_id,
                        validator_title,
                        check_id,
                        _non_empty_string(check.get("title")) or check_id,
                        str(check.get("description") or ""),
                    ),
                )
    return [rows[key] for key in sorted(rows)]


def _cell_for_version(
    *,
    version: str,
    validator_id: str,
    check_id: str,
    results: list[ValidationResultArtifact],
) -> CompareMatrixCell:
    counts: Counter[str] = Counter()
    details: list[CompareCellDetail] = []
    for result in sorted(
        results,
        key=lambda item: (item.case_id, item.repeat_index, item.validation_result_id),
    ):
        if result.validator_id != validator_id or not result.included_in_judge:
            continue
        if result.status == "error":
            counts["error"] += 1
            details.append(
                CompareCellDetail(
                    case_id=result.case_id,
                    repeat_index=result.repeat_index,
                    validation_result_id=result.validation_result_id,
                    verdict="error",
                    comment=result.execution_error or "Validation result failed.",
                )
            )
            continue
        for check in result.check_results:
            if check.check_id != check_id or not check.included_in_judge:
                continue
            counts[check.verdict] += 1
            details.append(
                CompareCellDetail(
                    case_id=result.case_id,
                    repeat_index=result.repeat_index,
                    validation_result_id=result.validation_result_id,
                    verdict=check.verdict,
                    comment=check.comment,
                )
            )
    total = counts["yes"] + counts["no"] + counts["unknown"] + counts["error"]
    return CompareMatrixCell(
        version=version,
        status=_status(counts),
        yes=counts["yes"],
        no=counts["no"],
        unknown=counts["unknown"],
        missing=counts["missing"],
        error=counts["error"],
        total=total,
        details=details,
    )


def _status(counts: Counter[str]) -> Literal["pass", "fail", "mixed", "empty"]:
    total = counts["yes"] + counts["no"] + counts["unknown"] + counts["error"]
    if total == 0:
        return "empty"
    if counts["no"] > 0:
        return "fail"
    if counts["unknown"] > 0 or counts["error"] > 0:
        return "mixed"
    return "pass"


def _non_empty_string(value: object) -> str | None:
    if not isinstance(value, str) or value == "":
        return None
    return value
