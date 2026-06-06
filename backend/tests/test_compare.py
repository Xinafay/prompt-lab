from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from fastapi.testclient import TestClient
from pydantic import ValidationError

from prompt_lab import llm_client
from prompt_lab.api import create_app
from prompt_lab.compare import build_comparison_prompt
from prompt_lab.config import PromptLabConfig
from prompt_lab.models.artifacts import RunArtifact
from prompt_lab.models.judgments import ComparisonArtifact


def assert_validation_error(
    model: type[Any], payload: dict[str, Any], message: str
) -> None:
    try:
        model.model_validate(payload)
    except ValidationError as error:
        assert message in str(error)
    else:
        raise AssertionError(f"Expected validation error containing {message!r}")


def valid_comparison_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "prompt_lab.comparison/v1",
        "comparison_id": "comparison-001",
        "baseline_version": "v001",
        "candidate_version": "v002",
        "baseline_run_batch_ids": ["baseline-batch"],
        "candidate_run_batch_ids": ["candidate-batch"],
        "judge_model": "openai/judge",
        "summary": "The candidate improves structure but adds one new edge-case issue.",
        "improvements": ["Answers include the required summary more consistently."],
        "regressions": ["One output omits the optional caveat."],
        "unchanged_problems": ["Both versions still over-explain short inputs."],
        "new_problems": ["Candidate sometimes adds unsupported confidence labels."],
        "stability_changes": ["Candidate is more consistent across repeats."],
        "recommendation": "revise_new_version",
        "decision_points": [
            {
                "decision_id": "d001",
                "description": "Decide whether the candidate's structure is worth revising.",
                "options": ["revise", "revert"],
                "recommended_option": "revise",
            }
        ],
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


def write_demo_experiment(root: Path, *, repeat_count: int = 2) -> tuple[Path, Path]:
    example = root / "examples" / "demo"
    baseline_dir = example / "versions" / "v001"
    candidate_dir = example / "versions" / "v002"
    for version_dir in [baseline_dir, candidate_dir]:
        (version_dir / "cases").mkdir(parents=True)
        write_json(
            version_dir / "cases" / "case-a.json",
            {
                "schema_version": "prompt_lab.case/v1",
                "id": "case-a",
                "title": "Case A",
                "variables": {"value": "hello"},
            },
        )
        (version_dir / "model.py").write_text(
            "from pydantic import BaseModel\n\nclass DemoOutput(BaseModel):\n    answer: str\n",
            encoding="utf-8",
        )
    write_json(
        example / "experiment.json",
        {
            "schema_version": "prompt_lab.experiment/v1",
            "id": "demo",
            "title": "Demo",
            "description": "",
            "active_version": "v002",
            "output": {
                "type": "pydantic",
                "model_file": "model.py",
                "model_entrypoint": "model.DemoOutput",
            },
            "template": {"engine": "jinja2", "path": "prompt.md"},
            "models": {"generator_model": "local/a", "judge_model": "openai/judge"},
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
    (baseline_dir / "prompt.md").write_text(
        "Baseline prompt: say {{ value }}.", encoding="utf-8"
    )
    (candidate_dir / "prompt.md").write_text(
        "Candidate prompt: say {{ value }} and include a summary.", encoding="utf-8"
    )
    return baseline_dir, candidate_dir


def write_run_batch(
    version_dir: Path,
    batch_id: str,
    *,
    version: str,
    answer_prefix: str,
    repeat_count: int = 2,
) -> None:
    for repeat_index in range(1, repeat_count + 1):
        write_json(
            version_dir
            / "runs"
            / batch_id
            / "case-a"
            / f"repeat-{repeat_index:03d}.json",
            valid_run_payload(
                run_id=f"{batch_id}-case-a-repeat-{repeat_index:03d}",
                run_batch_id=batch_id,
                version=version,
                repeat_index=repeat_index,
                raw_output=f'{{"answer":"{answer_prefix} {repeat_index}"}}',
                output_json={"answer": f"{answer_prefix} {repeat_index}"},
            ),
        )


class FakeGeneratedStructured:
    def __init__(self, output: Any) -> None:
        self.output = output
        self.usage: dict[str, Any] = {}


def test_comparison_artifact_validates_design_shape() -> None:
    comparison = ComparisonArtifact.model_validate(valid_comparison_payload())

    assert comparison.schema_version == "prompt_lab.comparison/v1"
    assert comparison.recommendation == "revise_new_version"
    assert comparison.decision_points[0].recommended_option == "revise"


def test_comparison_artifact_rejects_invalid_recommendation_and_empty_items() -> None:
    assert_validation_error(
        ComparisonArtifact,
        valid_comparison_payload(recommendation="ship_it"),
        (
            "Input should be 'keep_new_version', 'revise_new_version', "
            "'revert_to_baseline' or 'inconclusive'"
        ),
    )
    assert_validation_error(
        ComparisonArtifact,
        valid_comparison_payload(baseline_run_batch_ids=[""]),
        "String should have at least 1 character",
    )
    assert_validation_error(
        ComparisonArtifact,
        valid_comparison_payload(improvements=[""]),
        "String should have at least 1 character",
    )


def test_build_comparison_prompt_includes_versions_runs_rubric_and_id_guidance() -> None:
    baseline_runs = [
        RunArtifact.model_validate(
            valid_run_payload(
                run_batch_id="baseline-batch",
                version="v001",
                raw_output='{"id":"base-1","answer":"short"}',
                output_json={"id": "base-1", "answer": "short"},
            )
        )
    ]
    candidate_runs = [
        RunArtifact.model_validate(
            valid_run_payload(
                run_id="candidate-batch-case-a-repeat-001",
                run_batch_id="candidate-batch",
                version="v002",
                raw_output='{"id":"candidate-9","answer":"short with summary"}',
                output_json={"id": "candidate-9", "answer": "short with summary"},
            )
        )
    ]

    prompt = build_comparison_prompt(
        experiment_id="demo",
        baseline_version="v001",
        candidate_version="v002",
        rubric="Prefer complete answers and valid JSON.",
        baseline_prompt_template="Baseline prompt: say {{ value }}.",
        candidate_prompt_template="Candidate prompt: say {{ value }} and summarize.",
        baseline_run_batch_ids=["baseline-batch"],
        candidate_run_batch_ids=["candidate-batch"],
        baseline_run_artifacts=baseline_runs,
        candidate_run_artifacts=candidate_runs,
    )

    assert "compare semantic quality" in prompt
    assert "do not require identical generated IDs unless the rubric requires it" in prompt
    assert "Prefer complete answers and valid JSON." in prompt
    assert "Baseline prompt: say {{ value }}." in prompt
    assert "Candidate prompt: say {{ value }} and summarize." in prompt
    assert "baseline-batch" in prompt
    assert "candidate-batch" in prompt
    assert "v001" in prompt
    assert "v002" in prompt
    assert '{"id":"base-1","answer":"short"}' in prompt
    assert '{"id":"candidate-9","answer":"short with summary"}' in prompt
    assert "BASELINE_RUN_SUMMARY" in prompt
    assert "CANDIDATE_RUN_SUMMARY" in prompt
    assert "COMPARISON_SCHEMA_JSON" in prompt


def test_api_creates_comparison_under_candidate_version() -> None:
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
            ComparisonArtifact.model_validate(valid_comparison_payload())
        )

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fake_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline_dir, candidate_dir = write_demo_experiment(root)
            write_run_batch(
                baseline_dir,
                "baseline-batch",
                version="v001",
                answer_prefix="baseline",
            )
            write_run_batch(
                candidate_dir,
                "candidate-batch",
                version="v002",
                answer_prefix="candidate",
            )
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app, raise_server_exceptions=False).post(
                "/api/experiments/demo/comparisons",
                json={"baseline_version": "v001", "candidate_version": "v002"},
            )

            assert response.status_code == 200
            body = response.json()
            assert body["comparison_id"] == "comparison-001"
            assert body["baseline_run_batch_id"] == "baseline-batch"
            assert body["candidate_run_batch_id"] == "candidate-batch"
            assert body["comparison"]["recommendation"] == "revise_new_version"
            assert captured["model"] == "openai/judge"
            assert captured["response_model"] is ComparisonArtifact
            assert captured["validation_context"] is None
            assert "Baseline prompt: say {{ value }}." in captured["prompt"]
            assert "Candidate prompt: say {{ value }} and include a summary." in captured[
                "prompt"
            ]
            comparison_dir = candidate_dir / "comparisons" / "comparison-001"
            assert (comparison_dir / "comparison.json").is_file()
            assert (comparison_dir / "comparison.md").is_file()
            assert (comparison_dir / "rubric_snapshot.md").read_text(
                encoding="utf-8"
            ) == "Prefer complete answers and valid JSON."
    finally:
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


def test_api_allocates_next_comparison_without_overwriting() -> None:
    def fake_generate_structured(
        model: str,
        prompt: str,
        response_model: Any,
        validation_context: dict[str, Any] | None,
    ) -> FakeGeneratedStructured:
        return FakeGeneratedStructured(
            ComparisonArtifact.model_validate(
                valid_comparison_payload(comparison_id="comparison-002")
            )
        )

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fake_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline_dir, candidate_dir = write_demo_experiment(root)
            write_run_batch(
                baseline_dir,
                "baseline-batch",
                version="v001",
                answer_prefix="baseline",
            )
            write_run_batch(
                candidate_dir,
                "candidate-batch",
                version="v002",
                answer_prefix="candidate",
            )
            first_dir = candidate_dir / "comparisons" / "comparison-001"
            first_dir.mkdir(parents=True)
            (first_dir / "comparison.json").write_text(
                '{"sentinel":"keep me"}\n', encoding="utf-8"
            )
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app, raise_server_exceptions=False).post(
                "/api/experiments/demo/comparisons",
                json={"baseline_version": "v001", "candidate_version": "v002"},
            )

            assert response.status_code == 200
            assert response.json()["comparison_id"] == "comparison-002"
            assert (candidate_dir / "comparisons" / "comparison-002").is_dir()
            assert "keep me" in (first_dir / "comparison.json").read_text(
                encoding="utf-8"
            )
    finally:
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


def test_api_selects_latest_run_batches_for_both_versions_by_mtime() -> None:
    captured: dict[str, Any] = {}

    def fake_generate_structured(
        model: str,
        prompt: str,
        response_model: Any,
        validation_context: dict[str, Any] | None,
    ) -> FakeGeneratedStructured:
        captured["prompt"] = prompt
        return FakeGeneratedStructured(
            ComparisonArtifact.model_validate(
                valid_comparison_payload(
                    baseline_run_batch_ids=["baseline-new"],
                    candidate_run_batch_ids=["candidate-new"],
                )
            )
        )

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fake_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline_dir, candidate_dir = write_demo_experiment(root)
            write_run_batch(
                baseline_dir, "baseline-old", version="v001", answer_prefix="old base"
            )
            write_run_batch(
                baseline_dir,
                "baseline-new",
                version="v001",
                answer_prefix="new base",
            )
            write_run_batch(
                candidate_dir,
                "candidate-old",
                version="v002",
                answer_prefix="old candidate",
            )
            write_run_batch(
                candidate_dir,
                "candidate-new",
                version="v002",
                answer_prefix="new candidate",
            )
            old_time = 1_700_000_000
            for old_dir, new_dir in [
                (
                    baseline_dir / "runs" / "baseline-old",
                    baseline_dir / "runs" / "baseline-new",
                ),
                (
                    candidate_dir / "runs" / "candidate-old",
                    candidate_dir / "runs" / "candidate-new",
                ),
            ]:
                old_dir.touch()
                new_dir.touch()
                os.utime(
                    old_dir,
                    ns=(old_time * 1_000_000_000, old_time * 1_000_000_000),
                )
                os.utime(
                    new_dir,
                    ns=(
                        (old_time + 60) * 1_000_000_000,
                        (old_time + 60) * 1_000_000_000,
                    ),
                )
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app, raise_server_exceptions=False).post(
                "/api/experiments/demo/comparisons",
                json={"baseline_version": "v001", "candidate_version": "v002"},
            )

            assert response.status_code == 200
            assert response.json()["baseline_run_batch_id"] == "baseline-new"
            assert response.json()["candidate_run_batch_id"] == "candidate-new"
            assert "baseline-new" in captured["prompt"]
            assert "candidate-new" in captured["prompt"]
    finally:
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


def test_api_rejects_comparison_metadata_mismatch_without_writing() -> None:
    def fake_generate_structured(
        model: str,
        prompt: str,
        response_model: Any,
        validation_context: dict[str, Any] | None,
    ) -> FakeGeneratedStructured:
        return FakeGeneratedStructured(
            ComparisonArtifact.model_validate(
                valid_comparison_payload(candidate_run_batch_ids=["other-batch"])
            )
        )

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fake_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline_dir, candidate_dir = write_demo_experiment(root)
            write_run_batch(
                baseline_dir,
                "baseline-batch",
                version="v001",
                answer_prefix="baseline",
            )
            write_run_batch(
                candidate_dir,
                "candidate-batch",
                version="v002",
                answer_prefix="candidate",
            )
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app, raise_server_exceptions=False).post(
                "/api/experiments/demo/comparisons",
                json={"baseline_version": "v001", "candidate_version": "v002"},
            )

            assert response.status_code == 400
            assert "Comparison candidate_run_batch_ids must be ['candidate-batch']" in (
                response.json()["detail"]
            )
            assert not (candidate_dir / "comparisons").exists()
    finally:
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


def main() -> int:
    tests = [
        test_comparison_artifact_validates_design_shape,
        test_comparison_artifact_rejects_invalid_recommendation_and_empty_items,
        test_build_comparison_prompt_includes_versions_runs_rubric_and_id_guidance,
        test_api_creates_comparison_under_candidate_version,
        test_api_allocates_next_comparison_without_overwriting,
        test_api_selects_latest_run_batches_for_both_versions_by_mtime,
        test_api_rejects_comparison_metadata_mismatch_without_writing,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
