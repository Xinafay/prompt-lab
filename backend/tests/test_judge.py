from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from fastapi.testclient import TestClient
from pydantic import ValidationError

from prompt_lab import llm_client
from prompt_lab.api import create_app
from prompt_lab.config import PromptLabConfig
from prompt_lab.judge import build_judge_prompt
from prompt_lab.models.artifacts import CaseArtifact, RunArtifact
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


def valid_case_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "prompt_lab.case/v1",
        "id": "case-a",
        "title": "Case A",
        "variables": {"value": "hello"},
    }
    payload.update(overrides)
    return payload


def valid_run_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "prompt_lab.run/v1",
        "run_id": "batch-001-case-a-repeat-001",
        "run_batch_id": "batch-001",
        "version": "v001",
        "case_id": "case-a",
        "repeat_index": 1,
        "generator_model": "local/generator",
        "status": "ok",
        "rendered_prompt": "Say hello",
        "raw_output": '{"answer":"hello"}',
        "output_type": "pydantic",
        "output_json": {"answer": "hello"},
        "usage": {},
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


def test_build_judge_prompt_includes_validation_errors_and_repeats() -> None:
    prompt = build_judge_prompt(
        experiment_id="demo",
        version="v001",
        output_declaration="pydantic model: model.DemoOutput",
        rubric="Prefer complete answers and valid JSON.",
        prompt_template="Say {{ value }}",
        cases=[
            CaseArtifact.model_validate(
                valid_case_payload(id="case-a", title="Case A")
            )
        ],
        run_artifacts=[
            RunArtifact.model_validate(
                valid_run_payload(
                    run_id="batch-001-case-a-repeat-001",
                    repeat_index=1,
                    status="ok",
                    raw_output='{"answer":"hello"}',
                    output_json={"answer": "hello"},
                )
            ),
            RunArtifact.model_validate(
                valid_run_payload(
                    run_id="batch-001-case-a-repeat-002",
                    repeat_index=2,
                    status="validation_error",
                    raw_output='{"answer": 7}',
                    output_json=None,
                    validation_error="answer must be a string",
                )
            ),
        ],
    )

    assert "distinguish recurring problems from one-off deviations" in prompt
    assert "cite case/repeat evidence" in prompt
    assert "JSON matching JudgmentArtifact" in prompt
    assert "avoid numeric scorecards as primary output" in prompt
    assert "case-a repeat 1" in prompt
    assert "case-a repeat 2" in prompt
    assert '{"answer":"hello"}' in prompt
    assert "answer must be a string" in prompt


def test_api_creates_judgment_and_default_accepted_decisions() -> None:
    class FakeGeneratedStructured:
        def __init__(self, output: Any) -> None:
            self.output = output
            self.usage: dict[str, Any] = {}

    captured: dict[str, Any] = {}

    def fake_generate_structured(
        model: str,
        prompt: str,
        response_model: Any,
        validation_context: dict[str, Any] | None,
    ) -> FakeGeneratedStructured:
        captured["model"] = model
        captured["prompt"] = prompt
        captured["response_model"] = response_model
        captured["validation_context"] = validation_context
        return FakeGeneratedStructured(
            JudgmentArtifact.model_validate(valid_judgment_payload())
        )

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fake_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            example = root / "examples" / "demo"
            version_dir = example / "versions" / "v001"
            run_dir = version_dir / "runs" / "batch-001" / "case-a"
            (version_dir / "cases").mkdir(parents=True)
            run_dir.mkdir(parents=True)
            (example / "experiment.json").write_text(
                '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"pydantic","model_file":"model.py","model_entrypoint":"model.DemoOutput"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/judge"},"run_defaults":{"repeat_count":2,"llm_cache":"disabled","case_order":"case-major"}}',
                encoding="utf-8",
            )
            (example / "rubric.md").write_text(
                "Prefer complete answers and valid JSON.", encoding="utf-8"
            )
            (version_dir / "prompt.md").write_text("Say {{ value }}", encoding="utf-8")
            (version_dir / "model.py").write_text(
                "from pydantic import BaseModel\n\nclass DemoOutput(BaseModel):\n    answer: str\n",
                encoding="utf-8",
            )
            (version_dir / "cases" / "case-a.json").write_text(
                json.dumps(valid_case_payload(), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (run_dir / "repeat-001.json").write_text(
                json.dumps(valid_run_payload(), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (run_dir / "repeat-002.json").write_text(
                json.dumps(
                    valid_run_payload(
                        run_id="batch-001-case-a-repeat-002",
                        repeat_index=2,
                        status="validation_error",
                        raw_output='{"answer": 7}',
                        output_json=None,
                        validation_error="answer must be a string",
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app, raise_server_exceptions=False).post(
                "/api/experiments/demo/versions/v001/judgments"
            )

            assert response.status_code == 200
            body = response.json()
            assert body["review_id"] == "review-001"
            assert body["judgment"]["findings"][0]["finding_id"] == "f001"
            assert captured["model"] == "openai/judge"
            assert captured["response_model"] is JudgmentArtifact
            assert captured["validation_context"] is None
            assert "answer must be a string" in captured["prompt"]
            review_dir = version_dir / "reviews" / "review-001"
            assert (review_dir / "judgment.json").is_file()
            assert (review_dir / "judgment.md").is_file()
            assert (review_dir / "rubric_snapshot.md").read_text(
                encoding="utf-8"
            ) == "Prefer complete answers and valid JSON."
            decisions = json.loads(
                (review_dir / "decisions.json").read_text(encoding="utf-8")
            )
            assert decisions["finding_decisions"]["f001"]["decision"] == "accepted"
    finally:
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


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
        test_build_judge_prompt_includes_validation_errors_and_repeats,
        test_api_creates_judgment_and_default_accepted_decisions,
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
