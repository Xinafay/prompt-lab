from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from prompt_lab.models.judgments import FindingDecisionSet, JudgmentArtifact


def assert_validation_error(
    model: type[Any], payload: dict[str, Any], message: str
) -> None:
    try:
        model.model_validate(payload)
    except ValidationError as error:
        assert message in str(error)
    else:
        raise AssertionError(f"Expected validation error containing {message!r}")


def assert_raises_value_error(call: Any, message: str) -> None:
    try:
        call()
    except ValueError as error:
        assert message in str(error)
    else:
        raise AssertionError(f"Expected value error containing {message!r}")


def valid_judgment_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "prompt_lab.judgment/v1",
        "judgment_id": "j001",
        "version": "v001",
        "run_batch_ids": ["batch-001"],
        "judge_model": "openai/example-large-model",
        "summary": "The prompt is mostly reliable but needs clearer boundaries.",
        "what_looks_correct": [],
        "findings": [
            {
                "finding_id": "f001",
                "severity": "recommended",
                "area": "prompt",
                "category": "recurring_problem",
                "description": "The model skips one required section.",
                "evidence": ["case after-hours repeat 1"],
                "suggested_change": "Make the required sections explicit.",
            }
        ],
        "decision_points": [],
    }
    payload.update(overrides)
    return payload


def test_judgment_artifact_validates() -> None:
    judgment = JudgmentArtifact.model_validate(valid_judgment_payload())

    assert judgment.findings[0].finding_id == "f001"


def test_judgment_artifact_rejects_invalid_severity() -> None:
    assert_validation_error(
        JudgmentArtifact,
        valid_judgment_payload(
            findings=[
                {
                    "finding_id": "f001",
                    "severity": "critical",
                    "area": "prompt",
                    "category": "recurring_problem",
                    "description": "The model skips one required section.",
                    "evidence": ["case after-hours repeat 1"],
                    "suggested_change": "Make the required sections explicit.",
                }
            ]
        ),
        "Input should be 'recommended', 'optional', 'do_not_change_yet' or 'regression_risk'",
    )


def test_judgment_artifact_rejects_empty_list_items() -> None:
    assert_validation_error(
        JudgmentArtifact,
        valid_judgment_payload(run_batch_ids=[""]),
        "String should have at least 1 character",
    )
    assert_validation_error(
        JudgmentArtifact,
        valid_judgment_payload(
            what_looks_correct=[
                {
                    "finding_id": "correct-001",
                    "description": "The prompt preserves the requested tone.",
                    "evidence": [""],
                }
            ]
        ),
        "String should have at least 1 character",
    )
    assert_validation_error(
        JudgmentArtifact,
        valid_judgment_payload(
            findings=[
                {
                    "finding_id": "f001",
                    "severity": "recommended",
                    "area": "prompt",
                    "category": "recurring_problem",
                    "description": "The model skips one required section.",
                    "evidence": [""],
                    "suggested_change": "Make the required sections explicit.",
                }
            ]
        ),
        "String should have at least 1 character",
    )
    assert_validation_error(
        JudgmentArtifact,
        valid_judgment_payload(
            decision_points=[
                {
                    "decision_id": "d001",
                    "description": "Choose how strict the prompt should be.",
                    "options": [""],
                    "recommended_option": "strict",
                }
            ]
        ),
        "String should have at least 1 character",
    )


def test_evidence_finding_rejects_empty_evidence() -> None:
    assert_validation_error(
        JudgmentArtifact,
        valid_judgment_payload(
            what_looks_correct=[
                {
                    "finding_id": "correct-001",
                    "description": "The prompt preserves the requested tone.",
                    "evidence": [],
                }
            ]
        ),
        "List should have at least 1 item",
    )


def test_decision_point_recommended_option_must_be_listed() -> None:
    assert_validation_error(
        JudgmentArtifact,
        valid_judgment_payload(
            decision_points=[
                {
                    "decision_id": "d001",
                    "description": "Choose how strict the prompt should be.",
                    "options": ["strict", "loose"],
                    "recommended_option": "balanced",
                }
            ]
        ),
        "recommended_option must be one of options",
    )


def test_nested_artifacts_reject_extra_fields() -> None:
    assert_validation_error(
        JudgmentArtifact,
        valid_judgment_payload(
            findings=[
                {
                    "finding_id": "f001",
                    "severity": "recommended",
                    "area": "prompt",
                    "category": "recurring_problem",
                    "description": "The model skips one required section.",
                    "evidence": ["case after-hours repeat 1"],
                    "suggested_change": "Make the required sections explicit.",
                    "confidence": "high",
                }
            ]
        ),
        "Extra inputs are not permitted",
    )


def test_decisions_default_to_accepted() -> None:
    decisions = FindingDecisionSet.from_finding_ids(["f001", "f002"])

    assert decisions.schema_version == "prompt_lab.decisions/v1"
    assert decisions.finding_decisions["f001"].decision == "accepted"
    assert decisions.finding_decisions["f002"].decision == "accepted"


def test_decisions_reject_invalid_decision() -> None:
    assert_validation_error(
        FindingDecisionSet,
        {
            "schema_version": "prompt_lab.decisions/v1",
            "finding_decisions": {"f001": {"decision": "ignored"}},
        },
        "Input should be 'accepted', 'rejected' or 'deferred'",
    )


def test_decisions_reject_empty_finding_ids() -> None:
    assert_validation_error(
        FindingDecisionSet,
        {
            "schema_version": "prompt_lab.decisions/v1",
            "finding_decisions": {"": {"decision": "accepted"}},
        },
        "finding_decisions cannot contain empty finding ids",
    )
    assert_raises_value_error(
        lambda: FindingDecisionSet.from_finding_ids([""]),
        "finding_ids cannot contain empty ids",
    )


def test_decisions_reject_duplicate_finding_ids() -> None:
    assert_raises_value_error(
        lambda: FindingDecisionSet.from_finding_ids(["f001", "f001"]),
        "finding_ids cannot contain duplicate ids",
    )


def main() -> int:
    tests = [
        test_judgment_artifact_validates,
        test_judgment_artifact_rejects_invalid_severity,
        test_judgment_artifact_rejects_empty_list_items,
        test_evidence_finding_rejects_empty_evidence,
        test_decision_point_recommended_option_must_be_listed,
        test_nested_artifacts_reject_extra_fields,
        test_decisions_default_to_accepted,
        test_decisions_reject_invalid_decision,
        test_decisions_reject_empty_finding_ids,
        test_decisions_reject_duplicate_finding_ids,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
