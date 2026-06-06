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


def main() -> int:
    tests = [
        test_judgment_artifact_validates,
        test_judgment_artifact_rejects_invalid_severity,
        test_decisions_default_to_accepted,
        test_decisions_reject_invalid_decision,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
