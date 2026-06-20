from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from io import StringIO
from threading import Event, Thread
from tempfile import TemporaryDirectory
from typing import Any

from fastapi.testclient import TestClient
from pydantic import ValidationError

from prompt_lab import llm_client
from prompt_lab.api import create_app
from prompt_lab.config import PromptLabConfig
from prompt_lab.judge import build_judge_prompt
from prompt_lab.models.judgments import FindingDecisionSet, JudgmentArtifact
from prompt_lab.settings import PromptLabSettings, save_settings


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
        "schema_version": "prompt_lab.case/v2",
        "id": "case-a",
        "title": "Case A",
        "stores": {
            "case": {
                "kind": "flat_file_tree",
                "values": {
                    "value": {
                        "__carmilla_flat_file_node__": "file",
                        "value": "hello",
                    }
                },
            }
        },
        "bindings": {
            "value": {"kind": "store_scope", "store": "case", "path": "value"}
        },
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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_demo_experiment(
    root: Path, *, repeat_count: int = 2, case_ids: list[str] | None = None
) -> Path:
    save_settings(
        root / "config" / "settings.json",
        PromptLabSettings(
            default_generator_model="local/a",
            default_validator_model="openai/judge",
            default_judge_model="openai/judge",
            default_repeat_count=repeat_count,
        ),
    )
    case_ids = case_ids or ["case-a"]
    example = root / "examples" / "demo"
    version_dir = example / "versions" / "v001"
    cases_dir = example / "cases"
    cases_dir.mkdir(parents=True)
    version_dir.mkdir(parents=True)
    write_json(
        example / "experiment.json",
        {
            "schema_version": "prompt_lab.experiment/v1",
            "id": "demo",
            "title": "Demo",
            "description": "",
            "active_version": "v001",
            "output": {
                "type": "pydantic",
                "model_file": "model.py",
                "model_entrypoint": "model.DemoOutput",
            },
            "template": {"engine": "jinjax", "path": "prompt.md"},
            "models": {"generator_model": "local/a", "validator_model": "openai/judge", "judge_model": "openai/judge"},
            "run_defaults": {
                "repeat_count": repeat_count,
                "llm_cache": "disabled",
                "case_order": "case-major",
            },
        },
    )
    (example / "rubric.md").write_text(
        "Prefer complete answers and valid JSON.", encoding="utf-8"
    )
    (version_dir / "prompt.md").write_text("Say {{ value }}", encoding="utf-8")
    (version_dir / "model.py").write_text(
        "from pydantic import BaseModel\n\nclass DemoOutput(BaseModel):\n    answer: str\n",
        encoding="utf-8",
    )
    for case_id in case_ids:
        write_json(
            cases_dir / f"{case_id}.json",
            valid_case_payload(id=case_id, title=f"Case {case_id}"),
        )
    return version_dir


def runtime_version_dir(root: Path) -> Path:
    return root / "experiments" / "demo" / "versions" / "v001"


def write_run_batch(
    version_dir: Path,
    batch_id: str,
    *,
    repeat_count: int = 2,
    case_ids: list[str] | None = None,
    overrides_by_repeat: dict[tuple[str, int], dict[str, Any]] | None = None,
    write_validation: bool = True,
    validation_batch_id: str | None = None,
) -> None:
    case_ids = case_ids or ["case-a"]
    overrides_by_repeat = overrides_by_repeat or {}
    validation_batch_id = validation_batch_id or f"validation-{batch_id}"
    for case_id in case_ids:
        for repeat_index in range(1, repeat_count + 1):
            payload_overrides: dict[str, Any] = {
                "run_id": f"{batch_id}-{case_id}-repeat-{repeat_index:03d}",
                "run_batch_id": batch_id,
                "case_id": case_id,
                "repeat_index": repeat_index,
            }
            payload_overrides.update(
                overrides_by_repeat.get((case_id, repeat_index), {})
            )
            write_json(
                version_dir
                / "runs"
                / batch_id
                / case_id
                / f"repeat-{repeat_index:03d}.json",
                valid_run_payload(**payload_overrides),
            )
    if not write_validation:
        return
    write_json(
        version_dir / "validations" / validation_batch_id / "batch.json",
        {
            "schema_version": "prompt_lab.validation_batch/v1",
            "validation_batch_id": validation_batch_id,
            "run_batch_id": batch_id,
            "version": "v001",
            "status": "completed",
            "started_at": "2026-06-19T10:00:00Z",
            "finished_at": "2026-06-19T10:01:00Z",
            "total_results": len(case_ids) * repeat_count,
            "completed_results": len(case_ids) * repeat_count,
            "validator_model": "openai/judge",
            "validator_ids": ["quality"],
        },
    )
    write_json(
        version_dir
        / "validations"
        / validation_batch_id
        / "validators_snapshot"
        / "quality.json",
        {
            "schema_version": "prompt_lab.validator/v1",
            "validator_id": "quality",
            "type": "llm_questionnaire",
            "title": "Quality checks",
            "description": "",
            "enabled": True,
            "input_scope": "output_only",
            "checks": [
                {
                    "check_id": "complete",
                    "title": "Complete answer",
                    "question": "Is the answer complete?",
                    "description": "",
                }
            ],
        },
    )
    for case_id in case_ids:
        for repeat_index in range(1, repeat_count + 1):
            write_json(
                version_dir
                / "validations"
                / validation_batch_id
                / case_id
                / f"repeat-{repeat_index:03d}"
                / "quality.json",
                {
                    "schema_version": "prompt_lab.validation_result/v1",
                    "validation_result_id": (
                        f"{validation_batch_id}-{case_id}-"
                        f"repeat-{repeat_index:03d}-quality"
                    ),
                    "validation_batch_id": validation_batch_id,
                    "run_batch_id": batch_id,
                    "run_id": f"{batch_id}-{case_id}-repeat-{repeat_index:03d}",
                    "case_id": case_id,
                    "repeat_index": repeat_index,
                    "validator_id": "quality",
                    "validator_type": "llm_questionnaire",
                    "status": "ok",
                    "included_in_judge": True,
                    "check_results": [
                        {
                            "check_id": "complete",
                            "grade": 5,
                            "comment": (
                                f"Validation evidence for {case_id} "
                                f"repeat {repeat_index}"
                            ),
                            "included_in_judge": True,
                            "metrics": {},
                        }
                    ],
                    "usage": {},
                    "execution_error": None,
                },
            )


class FakeGeneratedStructured:
    def __init__(self, output: Any) -> None:
        self.output = output
        self.usage: dict[str, Any] = {}


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


def test_build_judge_prompt_uses_validation_evidence_without_raw_outputs_or_rubric() -> None:
    prompt = build_judge_prompt(
        experiment_id="demo",
        version="v001",
        run_batch_id="batch-001",
        validation_batch_id="validation-001",
        judge_model="openai/judge",
        output_declaration="pydantic model: model.DemoOutput",
        prompt_template="Say {{ value }}",
        model_source="class DemoOutput: ...\n    answer: str",
        validation_evidence=[
            {
                "validator_id": "quality",
                "validator_title": "Quality checks",
                "check_id": "complete",
                "check_title": "Complete answer",
                "case_id": "case-a",
                "repeat_index": 1,
                "grade": 1,
                "comment": "evidence comment",
            }
        ],
        run_errors=[
            {
                "case_id": "case-a",
                "repeat_index": 2,
                "status": "validation_error",
                "validation_error": "answer must be a string",
                "execution_error": None,
            }
        ],
    )

    assert "distinguish recurring problems from one-off deviations" in prompt
    assert "cite case/repeat evidence" in prompt
    assert "JSON matching JudgmentArtifact" in prompt
    assert prompt.count("<<MODEL>>") == 1
    assert "validation grades are evidence, not your final output format" in prompt
    assert "validation evidence as primary analysis of run outputs" in prompt
    assert "Do not ask for raw outputs" in prompt
    assert "Say {{ value }}" in prompt
    assert "pydantic model: model.DemoOutput" in prompt
    assert "class DemoOutput" in prompt
    assert "VALIDATION_EVIDENCE_JSON" in prompt
    assert "evidence comment" in prompt
    assert "validation-001" in prompt
    assert "RAW SECRET" not in prompt
    assert "RUBRIC" not in prompt
    assert "<<<PROMPT_TEMPLATE" in prompt
    assert "<<<OUTPUT_DECLARATION" in prompt
    assert "<<<VALIDATION_METADATA_JSON" in prompt
    assert "<<<VALIDATION_EVIDENCE_JSON" in prompt
    assert "<<<JUDGMENT_SCHEMA_JSON" not in prompt
    assert prompt.index("<<<VALIDATION_EVIDENCE_JSON") < prompt.index("<<MODEL>>")
    assert prompt.index("<<<RUN_ERRORS_JSON") < prompt.index("<<MODEL>>")
    assert "case-a" in prompt
    assert '"repeat_index": 1' in prompt
    assert '"grade": 1' in prompt
    assert '"verdict"' not in prompt
    assert "answer must be a string" in prompt
    assert '"version": "v001"' in prompt
    assert '"run_batch_ids": [' in prompt
    assert '"batch-001"' in prompt
    assert '"judge_model": "openai/judge"' in prompt


def test_build_judge_prompt_keeps_validation_batch_out_of_judgment_metadata() -> None:
    prompt = build_judge_prompt(
        experiment_id="demo",
        version="v001",
        run_batch_id="batch-001",
        validation_batch_id="validation-001",
        judge_model="openai/judge",
        output_declaration="text output",
        prompt_template="Say {{ value }}",
        model_source=None,
        validation_evidence=[],
        run_errors=[],
    )

    judgment_metadata = prompt.split("<<<JUDGMENT_METADATA_JSON", 1)[1].split(
        "JUDGMENT_METADATA_JSON>>>", 1
    )[0]
    validation_metadata = prompt.split("<<<VALIDATION_METADATA_JSON", 1)[1].split(
        "VALIDATION_METADATA_JSON>>>", 1
    )[0]

    assert '"validation_batch_id"' not in judgment_metadata
    assert '"validation_batch_id": "validation-001"' in validation_metadata


def test_judge_prompt_template_file_is_used() -> None:
    template_path = (
        Path(__file__).parents[1]
        / "prompt_lab"
        / "system_prompts"
        / "judge.md.jinja"
    )
    assert template_path.is_file()
    assert "You are judging one Prompt Lab experiment version." in template_path.read_text(
        encoding="utf-8"
    )


def test_api_creates_judgment_and_default_accepted_decisions() -> None:
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
            JudgmentArtifact.model_validate(
                valid_judgment_payload(
                    run_batch_ids=["batch-001"], judge_model="openai/judge"
                )
            )
        )

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fake_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            version_dir = write_demo_experiment(root)
            write_run_batch(
                version_dir,
                "batch-001",
                overrides_by_repeat={
                    ("case-a", 2): {
                        "run_id": "batch-001-case-a-repeat-002",
                        "status": "validation_error",
                        "raw_output": "RAW SECRET",
                        "output_json": None,
                        "validation_error": "answer must be a string",
                    }
                },
            )
            write_json(
                version_dir
                / "validations"
                / "validation-batch-001"
                / "case-a"
                / "repeat-001"
                / "quality-excluded-check.json",
                {
                    "schema_version": "prompt_lab.validation_result/v1",
                    "validation_result_id": "excluded-check-result",
                    "validation_batch_id": "validation-batch-001",
                    "run_batch_id": "batch-001",
                    "run_id": "batch-001-case-a-repeat-001",
                    "case_id": "case-a",
                    "repeat_index": 1,
                    "validator_id": "quality",
                    "validator_type": "llm_questionnaire",
                    "status": "ok",
                    "included_in_judge": True,
                    "check_results": [
                        {
                            "check_id": "complete",
                            "grade": 1,
                            "comment": "EXCLUDED CHECK",
                            "included_in_judge": False,
                            "metrics": {},
                        }
                    ],
                    "usage": {},
                    "execution_error": None,
                },
            )
            write_json(
                version_dir
                / "validations"
                / "validation-batch-001"
                / "case-a"
                / "repeat-001"
                / "quality-excluded-result.json",
                {
                    "schema_version": "prompt_lab.validation_result/v1",
                    "validation_result_id": "excluded-result",
                    "validation_batch_id": "validation-batch-001",
                    "run_batch_id": "batch-001",
                    "run_id": "batch-001-case-a-repeat-001",
                    "case_id": "case-a",
                    "repeat_index": 1,
                    "validator_id": "quality",
                    "validator_type": "llm_questionnaire",
                    "status": "ok",
                    "included_in_judge": False,
                    "check_results": [
                        {
                            "check_id": "complete",
                            "grade": 1,
                            "comment": "EXCLUDED RESULT",
                            "included_in_judge": True,
                            "metrics": {},
                        }
                    ],
                    "usage": {},
                    "execution_error": None,
                },
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
            assert "VALIDATION_EVIDENCE_JSON" in captured["prompt"]
            assert "Validation evidence for case-a repeat 1" in captured["prompt"]
            assert "answer must be a string" in captured["prompt"]
            assert "RAW SECRET" not in captured["prompt"]
            assert "EXCLUDED CHECK" not in captured["prompt"]
            assert "EXCLUDED RESULT" not in captured["prompt"]
            assert "RUBRIC" not in captured["prompt"]
            review_dir = runtime_version_dir(root) / "reviews" / "review-001"
            assert (review_dir / "judgment.json").is_file()
            assert (review_dir / "judgment.md").is_file()
            assert not (review_dir / "rubric_snapshot.md").exists()
            validation_context = json.loads(
                (review_dir / "validation_context.json").read_text(encoding="utf-8")
            )
            assert validation_context["validation_batch_id"] == "validation-batch-001"
            assert validation_context["run_batch_id"] == "batch-001"
            assert validation_context["validation_evidence"][0]["comment"] == (
                "Validation evidence for case-a repeat 1"
            )
            assert "EXCLUDED CHECK" not in json.dumps(validation_context)
            assert "EXCLUDED RESULT" not in json.dumps(validation_context)
            decisions = json.loads(
                (review_dir / "decisions.json").read_text(encoding="utf-8")
            )
            assert decisions["finding_decisions"]["f001"]["decision"] == "accepted"
    finally:
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


def test_api_includes_validation_result_execution_errors_in_judge_evidence() -> None:
    captured: dict[str, Any] = {}

    def fake_generate_structured(
        model: str,
        prompt: str,
        response_model: Any,
        validation_context: dict[str, Any] | None,
    ) -> FakeGeneratedStructured:
        captured["prompt"] = prompt
        return FakeGeneratedStructured(
            JudgmentArtifact.model_validate(
                valid_judgment_payload(
                    run_batch_ids=["batch-001"], judge_model="openai/judge"
                )
            )
        )

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fake_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            version_dir = write_demo_experiment(root)
            write_run_batch(version_dir, "batch-001")
            write_json(
                version_dir
                / "validations"
                / "validation-batch-001"
                / "case-a"
                / "repeat-001"
                / "quality-error.json",
                {
                    "schema_version": "prompt_lab.validation_result/v1",
                    "validation_result_id": "quality-error-result",
                    "validation_batch_id": "validation-batch-001",
                    "run_batch_id": "batch-001",
                    "run_id": "batch-001-case-a-repeat-001",
                    "case_id": "case-a",
                    "repeat_index": 1,
                    "validator_id": "quality",
                    "validator_type": "llm_questionnaire",
                    "status": "error",
                    "included_in_judge": True,
                    "check_results": [],
                    "usage": {},
                    "execution_error": "validator crashed",
                },
            )
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app, raise_server_exceptions=False).post(
                "/api/experiments/demo/versions/v001/judgments"
            )

            assert response.status_code == 200
            assert "validator crashed" in captured["prompt"]
            review_dir = runtime_version_dir(root) / "reviews" / "review-001"
            validation_context = json.loads(
                (review_dir / "validation_context.json").read_text(encoding="utf-8")
            )
            error_evidence = [
                item
                for item in validation_context["validation_evidence"]
                if item.get("execution_error") == "validator crashed"
            ]
            assert error_evidence == [
                {
                    "validator_id": "quality",
                    "validator_title": "Quality checks",
                    "case_id": "case-a",
                    "repeat_index": 1,
                    "status": "error",
                    "execution_error": "validator crashed",
                }
            ]
    finally:
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


def test_api_rejects_contaminated_validation_result_before_judging() -> None:
    calls: list[str] = []

    def fake_generate_structured(
        model: str,
        prompt: str,
        response_model: Any,
        validation_context: dict[str, Any] | None,
    ) -> FakeGeneratedStructured:
        del model, response_model, validation_context
        calls.append(prompt)
        return FakeGeneratedStructured(
            JudgmentArtifact.model_validate(
                valid_judgment_payload(
                    run_batch_ids=["batch-001"], judge_model="openai/judge"
                )
            )
        )

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fake_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            version_dir = write_demo_experiment(root)
            write_run_batch(version_dir, "batch-001")
            write_json(
                version_dir
                / "validations"
                / "validation-batch-001"
                / "case-a"
                / "repeat-001"
                / "contaminated.json",
                {
                    "schema_version": "prompt_lab.validation_result/v1",
                    "validation_result_id": "contaminated-result",
                    "validation_batch_id": "other-validation",
                    "run_batch_id": "batch-001",
                    "run_id": "batch-001-case-a-repeat-001",
                    "case_id": "case-a",
                    "repeat_index": 1,
                    "validator_id": "quality",
                    "validator_type": "llm_questionnaire",
                    "status": "ok",
                    "included_in_judge": True,
                    "check_results": [
                        {
                            "check_id": "complete",
                            "grade": 1,
                            "comment": "CONTAMINATED EVIDENCE",
                            "included_in_judge": True,
                            "metrics": {},
                        }
                    ],
                    "usage": {},
                    "execution_error": None,
                },
            )
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app, raise_server_exceptions=False).post(
                "/api/experiments/demo/versions/v001/judgments"
            )

            assert response.status_code == 400
            assert "Validation result contaminated-result" in response.json()["detail"]
            assert "validation_batch_id" in response.json()["detail"]
            assert calls == []
            assert not (runtime_version_dir(root) / "reviews").exists()
    finally:
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


def test_api_creates_dry_run_judgment_without_live_llm() -> None:
    def fake_generate_structured(
        model: str,
        prompt: str,
        response_model: Any,
        validation_context: dict[str, Any] | None,
    ) -> FakeGeneratedStructured:
        raise AssertionError("dry-run judgment must not call live structured LLM")

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fake_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            version_dir = write_demo_experiment(root)
            write_run_batch(version_dir, "batch-001")
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app, raise_server_exceptions=False).post(
                "/api/experiments/demo/versions/v001/judgments",
                json={"dry_run": True},
            )

            assert response.status_code == 200
            body = response.json()
            assert body["review_id"] == "review-001"
            assert body["run_batch_id"] == "batch-001"
            assert body["judgment"]["version"] == "v001"
            assert body["judgment"]["run_batch_ids"] == ["batch-001"]
            assert body["judgment"]["judge_model"] == "openai/judge"
            review_dir = runtime_version_dir(root) / "reviews" / "review-001"
            assert (review_dir / "judgment.json").is_file()
            assert (review_dir / "judgment.md").is_file()
            decisions = json.loads(
                (review_dir / "decisions.json").read_text(encoding="utf-8")
            )
            assert sorted(decisions["finding_decisions"]) == [
                finding["finding_id"] for finding in body["judgment"]["findings"]
            ]
    finally:
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


def test_api_rejects_judgment_without_completed_validation_batch() -> None:
    calls: list[str] = []

    def fake_generate_structured(
        model: str,
        prompt: str,
        response_model: Any,
        validation_context: dict[str, Any] | None,
    ) -> FakeGeneratedStructured:
        del model, response_model, validation_context
        calls.append(prompt)
        return FakeGeneratedStructured({})

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fake_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            version_dir = write_demo_experiment(root)
            write_run_batch(version_dir, "batch-001", write_validation=False)
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app, raise_server_exceptions=False).post(
                "/api/experiments/demo/versions/v001/judgments"
            )

            assert response.status_code == 400
            assert "requires a completed validation batch" in response.json()["detail"]
            assert calls == []
            assert not (runtime_version_dir(root) / "reviews").exists()
    finally:
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


def test_api_judgment_replaces_existing_reviews_and_proposals() -> None:
    def fake_generate_structured(
        model: str,
        prompt: str,
        response_model: Any,
        validation_context: dict[str, Any] | None,
    ) -> FakeGeneratedStructured:
        return FakeGeneratedStructured(
            JudgmentArtifact.model_validate(
                valid_judgment_payload(
                    run_batch_ids=["batch-001"], judge_model="openai/judge"
                )
            )
        )

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fake_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            version_dir = write_demo_experiment(root)
            write_run_batch(version_dir, "batch-001")
            app = create_app(PromptLabConfig.from_env(project_root=root))
            client = TestClient(app, raise_server_exceptions=False)

            first = client.post("/api/experiments/demo/versions/v001/judgments")
            assert first.status_code == 200
            assert first.json()["review_id"] == "review-001"
            runtime_dir = runtime_version_dir(root)
            first_decisions_path = (
                runtime_dir / "reviews" / "review-001" / "decisions.json"
            )
            first_decisions_path.write_text(
                '{"schema_version":"prompt_lab.decisions/v1","finding_decisions":{"sentinel":{"decision":"accepted","reason":"keep me"}}}\n',
                encoding="utf-8",
            )
            proposal_dir = runtime_dir / "reviews" / "review-001" / "proposal"
            proposal_dir.mkdir()
            (proposal_dir / "prompt.md").write_text("old proposal", encoding="utf-8")

            second = client.post("/api/experiments/demo/versions/v001/judgments")

            assert second.status_code == 200
            assert second.json()["review_id"] == "review-001"
            assert not (runtime_dir / "reviews" / "review-002").exists()
            assert not proposal_dir.exists()
            assert "keep me" not in first_decisions_path.read_text(encoding="utf-8")
    finally:
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


def test_api_selects_latest_run_batch_by_name_not_mtime() -> None:
    captured: dict[str, Any] = {}

    def fake_generate_structured(
        model: str,
        prompt: str,
        response_model: Any,
        validation_context: dict[str, Any] | None,
    ) -> FakeGeneratedStructured:
        captured["prompt"] = prompt
        return FakeGeneratedStructured(
            JudgmentArtifact.model_validate(
                valid_judgment_payload(
                    run_batch_ids=["run_version-000002"], judge_model="openai/judge"
                )
            )
        )

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fake_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            version_dir = write_demo_experiment(root)
            write_run_batch(version_dir, "run_version-000001")
            write_run_batch(version_dir, "run_version-000002")
            old_dir = version_dir / "runs" / "run_version-000001"
            new_dir = version_dir / "runs" / "run_version-000002"
            old_time = 1_700_000_000
            new_time = old_time + 60
            old_dir.touch()
            new_dir.touch()

            os.utime(old_dir, ns=(new_time * 1_000_000_000, new_time * 1_000_000_000))
            os.utime(new_dir, ns=(old_time * 1_000_000_000, old_time * 1_000_000_000))
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app, raise_server_exceptions=False).post(
                "/api/experiments/demo/versions/v001/judgments"
            )

            assert response.status_code == 200
            assert response.json()["run_batch_id"] == "run_version-000002"
            assert "run_version-000002" in captured["prompt"]
    finally:
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


def test_api_reports_active_judge_job_and_rejects_second_judgment() -> None:
    started = Event()
    release = Event()

    def slow_generate_structured(
        model: str,
        prompt: str,
        response_model: Any,
        validation_context: dict[str, Any] | None,
    ) -> FakeGeneratedStructured:
        del model, prompt, response_model, validation_context
        started.set()
        if not release.wait(timeout=5):
            raise TimeoutError("test timed out waiting to release fake judge")
        return FakeGeneratedStructured(
            JudgmentArtifact.model_validate(
                valid_judgment_payload(
                    run_batch_ids=["batch-001"], judge_model="openai/judge"
                )
            )
        )

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = slow_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            version_dir = write_demo_experiment(root)
            write_run_batch(version_dir, "batch-001")
            app = create_app(PromptLabConfig.from_env(project_root=root))
            client = TestClient(app, raise_server_exceptions=False)
            responses: list[Any] = []

            def start_judge() -> None:
                responses.append(
                    client.post("/api/experiments/demo/versions/v001/judgments")
                )

            thread = Thread(target=start_judge)
            thread.start()
            try:
                assert started.wait(timeout=5)

                active_response = client.get("/api/jobs/active")
                assert active_response.status_code == 200
                active_job = active_response.json()["job"]
                assert active_job["kind"] == "judge"
                assert active_job["status"] == "running"

                duplicate_response = client.post(
                    "/api/experiments/demo/versions/v001/judgments"
                )
                assert duplicate_response.status_code == 409
                assert active_job["job_id"] in duplicate_response.json()["detail"]
            finally:
                release.set()
                thread.join(timeout=5)

            assert responses
            assert responses[0].status_code == 200
    finally:
        release.set()
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


def test_api_uses_latest_named_run_batch_when_older_batch_mtime_is_newer() -> None:
    captured: dict[str, Any] = {}

    def fake_generate_structured(
        model: str,
        prompt: str,
        response_model: Any,
        validation_context: dict[str, Any] | None,
    ) -> FakeGeneratedStructured:
        captured["prompt"] = prompt
        return FakeGeneratedStructured(
            JudgmentArtifact.model_validate(
                valid_judgment_payload(
                    run_batch_ids=["run_version-000002"], judge_model="openai/judge"
                )
            )
        )

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fake_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            version_dir = write_demo_experiment(root, repeat_count=2)
            write_run_batch(version_dir, "run_version-000001", repeat_count=3)
            write_run_batch(version_dir, "run_version-000002", repeat_count=2)
            stale_dir = version_dir / "runs" / "run_version-000001"
            latest_dir = version_dir / "runs" / "run_version-000002"
            old_time = 1_700_000_000
            stale_dir.touch()
            latest_dir.touch()
            os.utime(
                stale_dir,
                ns=((old_time + 60) * 1_000_000_000, (old_time + 60) * 1_000_000_000),
            )
            os.utime(
                latest_dir,
                ns=(old_time * 1_000_000_000, old_time * 1_000_000_000),
            )
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app, raise_server_exceptions=False).post(
                "/api/experiments/demo/versions/v001/judgments"
            )

            assert response.status_code == 200
            assert response.json()["run_batch_id"] == "run_version-000002"
            assert "run_version-000002" in captured["prompt"]
    finally:
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


def test_api_rejects_run_artifact_version_mismatch_without_judging() -> None:
    calls: list[str] = []

    def fake_generate_structured(
        model: str,
        prompt: str,
        response_model: Any,
        validation_context: dict[str, Any] | None,
    ) -> FakeGeneratedStructured:
        calls.append(prompt)
        return FakeGeneratedStructured(
            JudgmentArtifact.model_validate(
                valid_judgment_payload(
                    run_batch_ids=["batch-001"], judge_model="openai/judge"
                )
            )
        )

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fake_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            version_dir = write_demo_experiment(root)
            write_run_batch(
                version_dir,
                "batch-001",
                overrides_by_repeat={("case-a", 1): {"version": "v999"}},
            )
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app, raise_server_exceptions=False).post(
                "/api/experiments/demo/versions/v001/judgments"
            )

            assert response.status_code == 400
            assert "does not match version v001" in response.json()["detail"]
            assert calls == []
    finally:
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


def test_api_rejects_missing_run_coverage_without_judging() -> None:
    calls: list[str] = []

    def fake_generate_structured(
        model: str,
        prompt: str,
        response_model: Any,
        validation_context: dict[str, Any] | None,
    ) -> FakeGeneratedStructured:
        calls.append(prompt)
        return FakeGeneratedStructured(
            JudgmentArtifact.model_validate(
                valid_judgment_payload(
                    run_batch_ids=["batch-001"], judge_model="openai/judge"
                )
            )
        )

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fake_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            version_dir = write_demo_experiment(root, repeat_count=2)
            write_run_batch(version_dir, "batch-001", repeat_count=1)
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app, raise_server_exceptions=False).post(
                "/api/experiments/demo/versions/v001/judgments"
            )

            assert response.status_code == 400
            assert "Missing run artifacts" in response.json()["detail"]
            assert calls == []
    finally:
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


def test_api_rejects_judgment_metadata_mismatch_without_writing_review() -> None:
    def fake_generate_structured(
        model: str,
        prompt: str,
        response_model: Any,
        validation_context: dict[str, Any] | None,
    ) -> FakeGeneratedStructured:
        return FakeGeneratedStructured(
            JudgmentArtifact.model_validate(
                valid_judgment_payload(
                    run_batch_ids=["other-batch"], judge_model="openai/judge"
                )
            )
        )

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fake_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            version_dir = write_demo_experiment(root)
            write_run_batch(version_dir, "batch-001")
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app, raise_server_exceptions=False).post(
                "/api/experiments/demo/versions/v001/judgments"
            )

            assert response.status_code == 400
            assert "Judgment run_batch_ids must be ['batch-001']" in response.json()[
                "detail"
            ]
            assert not (runtime_version_dir(root) / "reviews").exists()
    finally:
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


def test_api_logs_invalid_judgment_response_context() -> None:
    def fake_generate_structured(
        model: str,
        prompt: str,
        response_model: Any,
        validation_context: dict[str, Any] | None,
    ) -> FakeGeneratedStructured:
        return FakeGeneratedStructured({"summary": "missing required metadata"})

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fake_generate_structured  # type: ignore[assignment]
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    logger = logging.getLogger("prompt_lab.api")
    original_level = logger.level
    logger.setLevel(logging.WARNING)
    logger.addHandler(handler)
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            version_dir = write_demo_experiment(root)
            write_run_batch(version_dir, "batch-001")
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app, raise_server_exceptions=False).post(
                "/api/experiments/demo/versions/v001/judgments"
            )

            assert response.status_code == 400
            assert response.json()["detail"].startswith(
                "Judge response failed validation:"
            )
            log_text = stream.getvalue()
            assert "Judge request failed" in log_text
            assert "experiment=demo" in log_text
            assert "version=v001" in log_text
            assert "run_batch=batch-001" in log_text
            assert "Judge response failed validation" in log_text
            assert not (runtime_version_dir(root) / "reviews").exists()
    finally:
        logger.removeHandler(handler)
        logger.setLevel(original_level)
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


def test_api_logs_unexpected_judgment_failure_context() -> None:
    def fake_generate_structured(
        model: str,
        prompt: str,
        response_model: Any,
        validation_context: dict[str, Any] | None,
    ) -> FakeGeneratedStructured:
        raise ValueError("missing judge configuration")

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fake_generate_structured  # type: ignore[assignment]
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    logger = logging.getLogger("prompt_lab.api")
    original_level = logger.level
    logger.setLevel(logging.WARNING)
    logger.addHandler(handler)
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            version_dir = write_demo_experiment(root)
            write_run_batch(version_dir, "batch-001")
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app, raise_server_exceptions=False).post(
                "/api/experiments/demo/versions/v001/judgments"
            )

            assert response.status_code == 500
            assert (
                response.json()["detail"]
                == "Judge request failed: ValueError: missing judge configuration"
            )
            log_text = stream.getvalue()
            assert "Judge request failed" in log_text
            assert "experiment=demo" in log_text
            assert "version=v001" in log_text
            assert "run_batch=batch-001" in log_text
            assert "missing judge configuration" in log_text
            assert not (runtime_version_dir(root) / "reviews").exists()
    finally:
        logger.removeHandler(handler)
        logger.setLevel(original_level)
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
        test_build_judge_prompt_uses_validation_evidence_without_raw_outputs_or_rubric,
        test_build_judge_prompt_keeps_validation_batch_out_of_judgment_metadata,
        test_judge_prompt_template_file_is_used,
        test_api_creates_judgment_and_default_accepted_decisions,
        test_api_includes_validation_result_execution_errors_in_judge_evidence,
        test_api_rejects_contaminated_validation_result_before_judging,
        test_api_creates_dry_run_judgment_without_live_llm,
        test_api_rejects_judgment_without_completed_validation_batch,
        test_api_judgment_replaces_existing_reviews_and_proposals,
        test_api_selects_latest_run_batch_by_name_not_mtime,
        test_api_reports_active_judge_job_and_rejects_second_judgment,
        test_api_uses_latest_named_run_batch_when_older_batch_mtime_is_newer,
        test_api_rejects_run_artifact_version_mismatch_without_judging,
        test_api_rejects_missing_run_coverage_without_judging,
        test_api_rejects_judgment_metadata_mismatch_without_writing_review,
        test_api_logs_invalid_judgment_response_context,
        test_api_logs_unexpected_judgment_failure_context,
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
