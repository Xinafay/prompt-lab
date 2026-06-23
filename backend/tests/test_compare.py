from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from fastapi.testclient import TestClient

from prompt_lab import llm_client
from prompt_lab.api import create_app
from prompt_lab.compare import build_compare_matrix
from prompt_lab.config import PromptLabConfig
from prompt_lab.models.validators import ValidationResultArtifact
from prompt_lab.settings import PromptLabSettings, save_settings


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def valid_case_payload(
    *,
    case_id: str = "case-a",
    title: str = "Case A",
    value: Any = "hello",
) -> dict[str, Any]:
    return {
        "id": case_id,
        "payload": {"value": value},
    }


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


def validator_snapshot(
    *,
    validator_id: str = "quality",
    validator_title: str = "Quality",
    check_id: str = "coverage",
    check_title: str = "Coverage",
    check_description: str = "Checks coverage.",
) -> dict[str, Any]:
    return {
        "schema_version": "prompt_lab.validator/v1",
        "validator_id": validator_id,
        "type": "llm_questionnaire",
        "title": validator_title,
        "description": "",
        "enabled": True,
        "input_scope": "output_only",
        "checks": [
            {
                "check_id": check_id,
                "title": check_title,
                "question": "Is this check satisfied?",
                "description": check_description,
            }
        ],
    }


def validation_result(
    *,
    version: str,
    check_id: str = "coverage",
    grade: int | None = 5,
    included: bool = True,
    result_included: bool = True,
    status: str = "ok",
    execution_error: str | None = None,
) -> ValidationResultArtifact:
    return ValidationResultArtifact.model_validate(
        {
            "schema_version": "prompt_lab.validation_result/v1",
            "validation_result_id": (
                f"validation-{version}-case-a-repeat-001-quality"
            ),
            "validation_batch_id": f"validation-{version}",
            "run_batch_id": f"run-{version}",
            "run_id": f"run-{version}-case-a-repeat-001",
            "case_id": "case-a",
            "repeat_index": 1,
            "validator_id": "quality",
            "validator_type": "llm_questionnaire",
            "status": status,
            "included_in_judge": result_included,
            "check_results": [
                {
                    "check_id": check_id,
                    "grade": grade,
                    "comment": f"grade {grade} evidence",
                    "included_in_judge": included,
                    "metrics": {},
                }
            ],
            "usage": {},
            "execution_error": execution_error,
        }
    )


def write_demo_experiment(root: Path, *, repeat_count: int = 1) -> tuple[Path, Path]:
    save_settings(
        root / "config" / "settings.json",
        PromptLabSettings(
            default_generator_model="local/a",
            default_validator_model="openai/validator",
            default_judge_model="openai/judge",
            default_repeat_count=repeat_count,
        ),
    )
    example = root / "examples" / "demo"
    baseline_dir = example / "versions" / "v001"
    candidate_dir = example / "versions" / "v002"
    write_json(example / "cases" / "case-a.json", valid_case_payload())
    for version_dir, prompt in [
        (baseline_dir, "Baseline prompt: say {{ value }}."),
        (candidate_dir, "Candidate prompt: say {{ value }}."),
    ]:
        version_dir.mkdir(parents=True)
        (version_dir / "prompt.md").write_text(prompt, encoding="utf-8")
        (version_dir / "model.py").write_text(
            "from pydantic import BaseModel\n\n"
            "class DemoOutput(BaseModel):\n"
            "    answer: str\n",
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
            "template": {"engine": "jinjax", "path": "prompt.md"},
            "models": {
                "generator_model": "local/a",
                "validator_model": "openai/validator",
                "judge_model": "openai/judge",
            },
            "run_defaults": {
                "repeat_count": repeat_count,
                "llm_cache": "disabled",
                "case_order": "case-major",
            },
        },
    )
    return baseline_dir, candidate_dir


def write_run_batch(version_dir: Path, batch_id: str, *, version: str) -> None:
    write_json(
        version_dir / "runs" / batch_id / "case-a" / "repeat-001.json",
        valid_run_payload(
            run_id=f"{batch_id}-case-a-repeat-001",
            run_batch_id=batch_id,
            version=version,
        ),
    )


def write_validation_batch(
    version_dir: Path,
    *,
    validation_batch_id: str,
    run_batch_id: str,
    version: str,
    grade: int | None,
    status: str = "completed",
) -> None:
    write_json(
        version_dir / "validations" / validation_batch_id / "batch.json",
        {
            "schema_version": "prompt_lab.validation_batch/v1",
            "validation_batch_id": validation_batch_id,
            "run_batch_id": run_batch_id,
            "version": version,
            "status": status,
            "started_at": "2026-06-19T10:00:00Z",
            "finished_at": "2026-06-19T10:01:00Z" if status == "completed" else None,
            "total_results": 1,
            "completed_results": 1 if status == "completed" else 0,
            "validator_model": "openai/validator",
            "validator_ids": ["quality"],
        },
    )
    write_json(
        version_dir
        / "validations"
        / validation_batch_id
        / "validators_snapshot"
        / "quality.json",
        validator_snapshot(),
    )
    result = validation_result(version=version, grade=grade).model_dump(mode="json")
    result["validation_batch_id"] = validation_batch_id
    result["run_batch_id"] = run_batch_id
    result["run_id"] = f"{run_batch_id}-case-a-repeat-001"
    write_json(
        version_dir
        / "validations"
        / validation_batch_id
        / "case-a"
        / "repeat-001"
        / "quality.json",
        result,
    )


def runtime_version_dir(root: Path, version: str) -> Path:
    return root / "experiments" / "demo" / "versions" / version


def validation_result_path(
    version_dir: Path,
    *,
    validation_batch_id: str,
) -> Path:
    return (
        version_dir
        / "validations"
        / validation_batch_id
        / "case-a"
        / "repeat-001"
        / "quality.json"
    )


def validation_batch_path(version_dir: Path, *, validation_batch_id: str) -> Path:
    return version_dir / "validations" / validation_batch_id / "batch.json"


def update_validation_batch_counts(
    version_dir: Path,
    *,
    validation_batch_id: str,
    total_results: int,
    completed_results: int,
) -> None:
    batch_path = validation_batch_path(
        version_dir,
        validation_batch_id=validation_batch_id,
    )
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    batch["total_results"] = total_results
    batch["completed_results"] = completed_results
    write_json(batch_path, batch)


def add_style_validator_to_batch(
    version_dir: Path,
    *,
    validation_batch_id: str,
    run_batch_id: str,
    version: str,
    write_result: bool,
) -> None:
    write_json(
        version_dir
        / "validations"
        / validation_batch_id
        / "validators_snapshot"
        / "style.json",
        validator_snapshot(
            validator_id="style",
            validator_title="Style",
            check_id="tone",
            check_title="Tone",
        ),
    )
    batch_path = validation_batch_path(
        version_dir,
        validation_batch_id=validation_batch_id,
    )
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    batch["validator_ids"] = ["quality", "style"]
    batch["total_results"] = 2
    batch["completed_results"] = 2
    write_json(batch_path, batch)
    if not write_result:
        return
    write_json(
        version_dir
        / "validations"
        / validation_batch_id
        / "case-a"
        / "repeat-001"
        / "style.json",
        {
            "schema_version": "prompt_lab.validation_result/v1",
            "validation_result_id": f"{validation_batch_id}-case-a-repeat-001-style",
            "validation_batch_id": validation_batch_id,
            "run_batch_id": run_batch_id,
            "run_id": f"{run_batch_id}-case-a-repeat-001",
            "case_id": "case-a",
            "repeat_index": 1,
            "validator_id": "style",
            "validator_type": "llm_questionnaire",
            "status": "ok",
            "included_in_judge": True,
            "check_results": [
                {
                    "check_id": "tone",
                    "grade": 5,
                    "comment": "grade 5 evidence",
                    "included_in_judge": True,
                    "metrics": {},
                }
            ],
            "usage": {},
            "execution_error": None,
        },
    )


def corrupt_validation_result(
    version_dir: Path,
    *,
    validation_batch_id: str,
    updates: dict[str, Any],
) -> None:
    path = validation_result_path(
        version_dir,
        validation_batch_id=validation_batch_id,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(updates)
    write_json(path, payload)


def test_compare_matrix_marks_low_grades_as_fail() -> None:
    matrix = build_compare_matrix(
        experiment_id="demo",
        versions=["v001", "v002"],
        validator_snapshots_by_version={
            "v001": [validator_snapshot()],
            "v002": [validator_snapshot()],
        },
        results_by_version={
            "v001": [validation_result(version="v001", grade=5)],
            "v002": [validation_result(version="v002", grade=1)],
        },
    )

    assert matrix.rows[0].cells[0].grade_5 == 1
    assert matrix.rows[0].cells[1].grade_1 == 1
    assert matrix.rows[0].cells[1].status == "fail"
    assert matrix.rows[0].cells[1].total == 1


def test_compare_matrix_ignores_excluded_checks_and_results() -> None:
    matrix = build_compare_matrix(
        experiment_id="demo",
        versions=["v001", "v002"],
        validator_snapshots_by_version={
            "v001": [validator_snapshot()],
            "v002": [validator_snapshot()],
        },
        results_by_version={
            "v001": [
                validation_result(version="v001", grade=1, included=False)
            ],
            "v002": [
                validation_result(
                    version="v002",
                    grade=1,
                    result_included=False,
                )
            ],
        },
    )

    assert matrix.rows[0].cells[0].status == "empty"
    assert matrix.rows[0].cells[0].total == 0
    assert matrix.rows[0].cells[1].status == "empty"
    assert matrix.rows[0].cells[1].total == 0


def test_compare_matrix_marks_null_grade_and_errors_as_mixed() -> None:
    matrix = build_compare_matrix(
        experiment_id="demo",
        versions=["v001", "v002"],
        validator_snapshots_by_version={
            "v001": [validator_snapshot()],
            "v002": [validator_snapshot()],
        },
        results_by_version={
            "v001": [validation_result(version="v001", grade=None)],
            "v002": [
                validation_result(
                    version="v002",
                    status="error",
                    execution_error="Validator timed out",
                )
            ],
        },
    )

    assert matrix.rows[0].cells[0].not_assessable == 1
    assert matrix.rows[0].cells[0].status == "mixed"
    assert matrix.rows[0].cells[1].error == 1
    assert matrix.rows[0].cells[1].details[0].status == "error"
    assert matrix.rows[0].cells[1].details[0].grade is None


def test_compare_matrix_marks_grade_three_as_mixed() -> None:
    matrix = build_compare_matrix(
        experiment_id="demo",
        versions=["v001"],
        validator_snapshots_by_version={"v001": [validator_snapshot()]},
        results_by_version={"v001": [validation_result(version="v001", grade=3)]},
    )

    cell = matrix.rows[0].cells[0]

    assert cell.grade_3 == 1
    assert cell.status == "mixed"
    assert cell.total == 1


def test_compare_matrix_uses_snapshot_rows_across_versions() -> None:
    matrix = build_compare_matrix(
        experiment_id="demo",
        versions=["v001", "v002"],
        validator_snapshots_by_version={
            "v001": [validator_snapshot(check_id="coverage")],
            "v002": [validator_snapshot(check_id="tone", check_title="Tone")],
        },
        results_by_version={
            "v001": [validation_result(version="v001", check_id="coverage")],
            "v002": [validation_result(version="v002", check_id="tone")],
        },
    )

    assert [row.check_id for row in matrix.rows] == ["coverage", "tone"]
    assert [cell.status for cell in matrix.rows[0].cells] == ["pass", "empty"]
    assert [cell.status for cell in matrix.rows[1].cells] == ["empty", "pass"]


def test_api_returns_compare_matrix_from_latest_completed_validation_batches() -> None:
    def fake_generate_structured(*args: Any, **kwargs: Any) -> object:
        raise AssertionError("compare must not call a structured LLM")

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fake_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline_dir, candidate_dir = write_demo_experiment(root)
            write_run_batch(baseline_dir, "baseline-run-001", version="v001")
            write_run_batch(candidate_dir, "candidate-run-001", version="v002")
            write_validation_batch(
                baseline_dir,
                validation_batch_id="validation-001",
                run_batch_id="baseline-run-001",
                version="v001",
                grade=1,
            )
            write_validation_batch(
                baseline_dir,
                validation_batch_id="validation-999",
                run_batch_id="baseline-run-001",
                version="v001",
                grade=5,
                status="running",
            )
            write_validation_batch(
                candidate_dir,
                validation_batch_id="validation-002",
                run_batch_id="candidate-run-001",
                version="v002",
                grade=5,
            )
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app, raise_server_exceptions=False).post(
                "/api/experiments/demo/comparisons",
                json={"baseline_version": "v001", "candidate_version": "v002"},
            )

            assert response.status_code == 200
            body = response.json()
            assert body["schema_version"] == "prompt_lab.compare_matrix/v1"
            assert body["versions"] == ["v001", "v002"]
            assert [cell["status"] for cell in body["rows"][0]["cells"]] == [
                "fail",
                "pass",
            ]
            assert body["rows"][0]["cells"][0]["grade_1"] == 1
            comparison_dir = (
                runtime_version_dir(root, "v002") / "comparisons" / "comparison-001"
            )
            assert (comparison_dir / "compare_matrix.json").is_file()
            assert not (comparison_dir / "comparison.md").exists()
            assert not (comparison_dir / "rubric_snapshot.md").exists()
    finally:
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


def test_api_rejects_compare_without_completed_validation_batch() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        baseline_dir, candidate_dir = write_demo_experiment(root)
        write_run_batch(baseline_dir, "baseline-run-001", version="v001")
        write_run_batch(candidate_dir, "candidate-run-001", version="v002")
        write_validation_batch(
            baseline_dir,
            validation_batch_id="validation-001",
            run_batch_id="baseline-run-001",
            version="v001",
            grade=5,
        )
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/experiments/demo/comparisons",
            json={"baseline_version": "v001", "candidate_version": "v002"},
        )

        assert response.status_code == 400
        assert "Compare requires completed validation batches" in response.json()["detail"]
        assert not (runtime_version_dir(root, "v002") / "comparisons").exists()


def test_api_rejects_compare_result_with_mismatched_batch_metadata() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        baseline_dir, candidate_dir = write_demo_experiment(root)
        write_run_batch(baseline_dir, "baseline-run-001", version="v001")
        write_run_batch(candidate_dir, "candidate-run-001", version="v002")
        write_validation_batch(
            baseline_dir,
            validation_batch_id="validation-001",
            run_batch_id="baseline-run-001",
            version="v001",
            grade=5,
        )
        write_validation_batch(
            candidate_dir,
            validation_batch_id="validation-002",
            run_batch_id="candidate-run-001",
            version="v002",
            grade=5,
        )
        corrupted_path = validation_result_path(
            candidate_dir,
            validation_batch_id="validation-002",
        )
        corrupted = json.loads(corrupted_path.read_text(encoding="utf-8"))
        corrupted["validation_batch_id"] = "other-validation"
        write_json(corrupted_path, corrupted)
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/experiments/demo/comparisons",
            json={"baseline_version": "v001", "candidate_version": "v002"},
        )

        assert response.status_code == 400
        assert "validation_batch_id other-validation, expected validation-002" in (
            response.json()["detail"]
        )
        assert not (runtime_version_dir(root, "v002") / "comparisons").exists()


def test_api_rejects_compare_result_with_unknown_snapshot_check_id() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        baseline_dir, candidate_dir = write_demo_experiment(root)
        write_run_batch(baseline_dir, "baseline-run-001", version="v001")
        write_run_batch(candidate_dir, "candidate-run-001", version="v002")
        write_validation_batch(
            baseline_dir,
            validation_batch_id="validation-001",
            run_batch_id="baseline-run-001",
            version="v001",
            grade=5,
        )
        write_validation_batch(
            candidate_dir,
            validation_batch_id="validation-002",
            run_batch_id="candidate-run-001",
            version="v002",
            grade=5,
        )
        corrupted_path = validation_result_path(
            candidate_dir,
            validation_batch_id="validation-002",
        )
        corrupted = json.loads(corrupted_path.read_text(encoding="utf-8"))
        corrupted["check_results"][0]["check_id"] = "missing-check"
        corrupted["check_results"][0]["included_in_judge"] = False
        write_json(corrupted_path, corrupted)
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/experiments/demo/comparisons",
            json={"baseline_version": "v001", "candidate_version": "v002"},
        )

        assert response.status_code == 400
        assert "unknown check_id missing-check" in response.json()["detail"]
        assert not (runtime_version_dir(root, "v002") / "comparisons").exists()


def test_api_rejects_compare_result_with_mismatched_run_batch_id() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        baseline_dir, candidate_dir = write_demo_experiment(root)
        write_run_batch(baseline_dir, "baseline-run-001", version="v001")
        write_run_batch(candidate_dir, "candidate-run-001", version="v002")
        write_validation_batch(
            baseline_dir,
            validation_batch_id="validation-001",
            run_batch_id="baseline-run-001",
            version="v001",
            grade=5,
        )
        write_validation_batch(
            candidate_dir,
            validation_batch_id="validation-002",
            run_batch_id="candidate-run-001",
            version="v002",
            grade=5,
        )
        corrupted_path = validation_result_path(
            candidate_dir,
            validation_batch_id="validation-002",
        )
        corrupted = json.loads(corrupted_path.read_text(encoding="utf-8"))
        corrupted["run_batch_id"] = "other-run"
        write_json(corrupted_path, corrupted)
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/experiments/demo/comparisons",
            json={"baseline_version": "v001", "candidate_version": "v002"},
        )

        assert response.status_code == 400
        assert "run_batch_id other-run, expected candidate-run-001" in (
            response.json()["detail"]
        )
        assert not (runtime_version_dir(root, "v002") / "comparisons").exists()


def test_api_rejects_compare_result_with_unknown_snapshot_validator_id() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        baseline_dir, candidate_dir = write_demo_experiment(root)
        write_run_batch(baseline_dir, "baseline-run-001", version="v001")
        write_run_batch(candidate_dir, "candidate-run-001", version="v002")
        write_validation_batch(
            baseline_dir,
            validation_batch_id="validation-001",
            run_batch_id="baseline-run-001",
            version="v001",
            grade=5,
        )
        write_validation_batch(
            candidate_dir,
            validation_batch_id="validation-002",
            run_batch_id="candidate-run-001",
            version="v002",
            grade=5,
        )
        corrupted_path = validation_result_path(
            candidate_dir,
            validation_batch_id="validation-002",
        )
        corrupted = json.loads(corrupted_path.read_text(encoding="utf-8"))
        corrupted["validator_id"] = "missing-validator"
        write_json(corrupted_path, corrupted)
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/experiments/demo/comparisons",
            json={"baseline_version": "v001", "candidate_version": "v002"},
        )

        assert response.status_code == 400
        assert "unknown validator_id missing-validator" in response.json()["detail"]
        assert not (runtime_version_dir(root, "v002") / "comparisons").exists()


def test_api_rejects_compare_with_missing_validation_result_file() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        baseline_dir, candidate_dir = write_demo_experiment(root)
        write_run_batch(baseline_dir, "baseline-run-001", version="v001")
        write_run_batch(candidate_dir, "candidate-run-001", version="v002")
        write_validation_batch(
            baseline_dir,
            validation_batch_id="validation-001",
            run_batch_id="baseline-run-001",
            version="v001",
            grade=5,
        )
        write_validation_batch(
            candidate_dir,
            validation_batch_id="validation-002",
            run_batch_id="candidate-run-001",
            version="v002",
            grade=5,
        )
        validation_result_path(
            candidate_dir,
            validation_batch_id="validation-002",
        ).unlink()
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/experiments/demo/comparisons",
            json={"baseline_version": "v001", "candidate_version": "v002"},
        )

        assert response.status_code == 400
        assert "has 0 validation results, expected 1" in response.json()["detail"]
        assert not (runtime_version_dir(root, "v002") / "comparisons").exists()


def test_api_rejects_compare_with_duplicate_validation_result_id() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        baseline_dir, candidate_dir = write_demo_experiment(root)
        write_run_batch(baseline_dir, "baseline-run-001", version="v001")
        write_run_batch(candidate_dir, "candidate-run-001", version="v002")
        write_validation_batch(
            baseline_dir,
            validation_batch_id="validation-001",
            run_batch_id="baseline-run-001",
            version="v001",
            grade=5,
        )
        write_validation_batch(
            candidate_dir,
            validation_batch_id="validation-002",
            run_batch_id="candidate-run-001",
            version="v002",
            grade=5,
        )
        add_style_validator_to_batch(
            baseline_dir,
            validation_batch_id="validation-001",
            run_batch_id="baseline-run-001",
            version="v001",
            write_result=True,
        )
        add_style_validator_to_batch(
            candidate_dir,
            validation_batch_id="validation-002",
            run_batch_id="candidate-run-001",
            version="v002",
            write_result=False,
        )
        original_path = validation_result_path(
            candidate_dir,
            validation_batch_id="validation-002",
        )
        duplicate = json.loads(original_path.read_text(encoding="utf-8"))
        write_json(original_path.with_name("quality-copy.json"), duplicate)
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/experiments/demo/comparisons",
            json={"baseline_version": "v001", "candidate_version": "v002"},
        )

        assert response.status_code == 400
        assert "duplicate validation_result_id" in response.json()["detail"]
        assert not (runtime_version_dir(root, "v002") / "comparisons").exists()


def test_api_rejects_compare_with_duplicate_logical_validation_result() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        baseline_dir, candidate_dir = write_demo_experiment(root)
        write_run_batch(baseline_dir, "baseline-run-001", version="v001")
        write_run_batch(candidate_dir, "candidate-run-001", version="v002")
        write_validation_batch(
            baseline_dir,
            validation_batch_id="validation-001",
            run_batch_id="baseline-run-001",
            version="v001",
            grade=5,
        )
        write_validation_batch(
            candidate_dir,
            validation_batch_id="validation-002",
            run_batch_id="candidate-run-001",
            version="v002",
            grade=5,
        )
        add_style_validator_to_batch(
            baseline_dir,
            validation_batch_id="validation-001",
            run_batch_id="baseline-run-001",
            version="v001",
            write_result=True,
        )
        add_style_validator_to_batch(
            candidate_dir,
            validation_batch_id="validation-002",
            run_batch_id="candidate-run-001",
            version="v002",
            write_result=False,
        )
        original_path = validation_result_path(
            candidate_dir,
            validation_batch_id="validation-002",
        )
        duplicate = json.loads(original_path.read_text(encoding="utf-8"))
        duplicate["validation_result_id"] = "validation-002-case-a-repeat-001-copy"
        write_json(original_path.with_name("quality-copy.json"), duplicate)
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/experiments/demo/comparisons",
            json={"baseline_version": "v001", "candidate_version": "v002"},
        )

        assert response.status_code == 400
        assert "duplicate validation result for case case-a repeat 1 validator quality" in (
            response.json()["detail"]
        )
        assert not (runtime_version_dir(root, "v002") / "comparisons").exists()


def test_api_rejects_compare_ok_result_missing_snapshot_check() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        baseline_dir, candidate_dir = write_demo_experiment(root)
        write_run_batch(baseline_dir, "baseline-run-001", version="v001")
        write_run_batch(candidate_dir, "candidate-run-001", version="v002")
        write_validation_batch(
            baseline_dir,
            validation_batch_id="validation-001",
            run_batch_id="baseline-run-001",
            version="v001",
            grade=5,
        )
        write_validation_batch(
            candidate_dir,
            validation_batch_id="validation-002",
            run_batch_id="candidate-run-001",
            version="v002",
            grade=5,
        )
        corrupted_path = validation_result_path(
            candidate_dir,
            validation_batch_id="validation-002",
        )
        corrupted = json.loads(corrupted_path.read_text(encoding="utf-8"))
        corrupted["check_results"] = []
        write_json(corrupted_path, corrupted)
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/experiments/demo/comparisons",
            json={"baseline_version": "v001", "candidate_version": "v002"},
        )

        assert response.status_code == 400
        assert "check_ids [] do not match snapshot check_ids ['coverage']" in (
            response.json()["detail"]
        )
        assert not (runtime_version_dir(root, "v002") / "comparisons").exists()


def test_api_rejects_compare_result_with_unknown_run_case_repeat() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        baseline_dir, candidate_dir = write_demo_experiment(root)
        write_run_batch(baseline_dir, "baseline-run-001", version="v001")
        write_run_batch(candidate_dir, "candidate-run-001", version="v002")
        write_validation_batch(
            baseline_dir,
            validation_batch_id="validation-001",
            run_batch_id="baseline-run-001",
            version="v001",
            grade=5,
        )
        write_validation_batch(
            candidate_dir,
            validation_batch_id="validation-002",
            run_batch_id="candidate-run-001",
            version="v002",
            grade=5,
        )
        corrupt_validation_result(
            candidate_dir,
            validation_batch_id="validation-002",
            updates={
                "case_id": "missing-case",
                "run_id": "candidate-run-001-missing-case-repeat-001",
            },
        )
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/experiments/demo/comparisons",
            json={"baseline_version": "v001", "candidate_version": "v002"},
        )

        assert response.status_code == 400
        assert "references unknown run case missing-case repeat 1" in (
            response.json()["detail"]
        )
        assert not (runtime_version_dir(root, "v002") / "comparisons").exists()


def test_api_rejects_compare_result_with_mismatched_run_id() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        baseline_dir, candidate_dir = write_demo_experiment(root)
        write_run_batch(baseline_dir, "baseline-run-001", version="v001")
        write_run_batch(candidate_dir, "candidate-run-001", version="v002")
        write_validation_batch(
            baseline_dir,
            validation_batch_id="validation-001",
            run_batch_id="baseline-run-001",
            version="v001",
            grade=5,
        )
        write_validation_batch(
            candidate_dir,
            validation_batch_id="validation-002",
            run_batch_id="candidate-run-001",
            version="v002",
            grade=5,
        )
        corrupt_validation_result(
            candidate_dir,
            validation_batch_id="validation-002",
            updates={"run_id": "wrong-run-id"},
        )
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/experiments/demo/comparisons",
            json={"baseline_version": "v001", "candidate_version": "v002"},
        )

        assert response.status_code == 400
        assert "has run_id wrong-run-id, expected candidate-run-001-case-a-repeat-001" in (
            response.json()["detail"]
        )
        assert not (runtime_version_dir(root, "v002") / "comparisons").exists()


def test_api_rejects_compare_missing_expected_logical_result() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        baseline_dir, candidate_dir = write_demo_experiment(root, repeat_count=1)
        write_json(
            root / "examples" / "demo" / "cases" / "case-b.json",
            valid_case_payload(case_id="case-b", title="Case B", value="goodbye"),
        )
        write_run_batch(baseline_dir, "baseline-run-001", version="v001")
        write_run_batch(candidate_dir, "candidate-run-001", version="v002")
        write_json(
            baseline_dir / "runs" / "baseline-run-001" / "case-b" / "repeat-001.json",
            valid_run_payload(
                run_id="baseline-run-001-case-b-repeat-001",
                run_batch_id="baseline-run-001",
                version="v001",
                case_id="case-b",
                repeat_index=1,
            ),
        )
        write_json(
            candidate_dir / "runs" / "candidate-run-001" / "case-b" / "repeat-001.json",
            valid_run_payload(
                run_id="candidate-run-001-case-b-repeat-001",
                run_batch_id="candidate-run-001",
                version="v002",
                case_id="case-b",
                repeat_index=1,
            ),
        )
        write_validation_batch(
            baseline_dir,
            validation_batch_id="validation-001",
            run_batch_id="baseline-run-001",
            version="v001",
            grade=5,
        )
        write_validation_batch(
            candidate_dir,
            validation_batch_id="validation-002",
            run_batch_id="candidate-run-001",
            version="v002",
            grade=5,
        )
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/experiments/demo/comparisons",
            json={"baseline_version": "v001", "candidate_version": "v002"},
        )

        assert response.status_code == 400
        assert "total_results 1, expected 2" in response.json()["detail"]
        assert not (runtime_version_dir(root, "v002") / "comparisons").exists()


def test_api_rejects_compare_validation_batch_id_mismatching_directory_name() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        baseline_dir, candidate_dir = write_demo_experiment(root)
        write_run_batch(baseline_dir, "baseline-run-001", version="v001")
        write_run_batch(candidate_dir, "candidate-run-001", version="v002")
        write_validation_batch(
            baseline_dir,
            validation_batch_id="validation-001",
            run_batch_id="baseline-run-001",
            version="v001",
            grade=5,
        )
        write_validation_batch(
            candidate_dir,
            validation_batch_id="validation-001",
            run_batch_id="candidate-run-001",
            version="v002",
            grade=5,
        )
        write_validation_batch(
            candidate_dir,
            validation_batch_id="validation-999",
            run_batch_id="candidate-run-001",
            version="v002",
            grade=1,
        )
        batch_path = validation_batch_path(
            candidate_dir,
            validation_batch_id="validation-999",
        )
        batch = json.loads(batch_path.read_text(encoding="utf-8"))
        batch["validation_batch_id"] = "validation-001"
        write_json(batch_path, batch)
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/experiments/demo/comparisons",
            json={"baseline_version": "v001", "candidate_version": "v002"},
        )

        assert response.status_code == 400
        assert (
            "Validation batch file validation-999 has validation_batch_id "
            "validation-001"
        ) in response.json()["detail"]
        assert not (runtime_version_dir(root, "v002") / "comparisons").exists()


def test_api_rejects_compare_ok_result_with_duplicate_check_ids() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        baseline_dir, candidate_dir = write_demo_experiment(root)
        write_run_batch(baseline_dir, "baseline-run-001", version="v001")
        write_run_batch(candidate_dir, "candidate-run-001", version="v002")
        write_validation_batch(
            baseline_dir,
            validation_batch_id="validation-001",
            run_batch_id="baseline-run-001",
            version="v001",
            grade=5,
        )
        write_validation_batch(
            candidate_dir,
            validation_batch_id="validation-002",
            run_batch_id="candidate-run-001",
            version="v002",
            grade=5,
        )
        result_path = validation_result_path(
            candidate_dir,
            validation_batch_id="validation-002",
        )
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["check_results"].append(dict(result["check_results"][0]))
        write_json(result_path, result)
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/experiments/demo/comparisons",
            json={"baseline_version": "v001", "candidate_version": "v002"},
        )

        assert response.status_code == 400
        assert "duplicate check_id coverage" in response.json()["detail"]
        assert not (runtime_version_dir(root, "v002") / "comparisons").exists()


def test_api_rejects_compare_error_result_with_duplicate_check_ids() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        baseline_dir, candidate_dir = write_demo_experiment(root)
        write_run_batch(baseline_dir, "baseline-run-001", version="v001")
        write_run_batch(candidate_dir, "candidate-run-001", version="v002")
        write_validation_batch(
            baseline_dir,
            validation_batch_id="validation-001",
            run_batch_id="baseline-run-001",
            version="v001",
            grade=5,
        )
        write_validation_batch(
            candidate_dir,
            validation_batch_id="validation-002",
            run_batch_id="candidate-run-001",
            version="v002",
            grade=5,
        )
        result_path = validation_result_path(
            candidate_dir,
            validation_batch_id="validation-002",
        )
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["status"] = "error"
        result["execution_error"] = "Validator failed"
        result["check_results"].append(dict(result["check_results"][0]))
        write_json(result_path, result)
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/experiments/demo/comparisons",
            json={"baseline_version": "v001", "candidate_version": "v002"},
        )

        assert response.status_code == 400
        assert "duplicate check_id coverage" in response.json()["detail"]
        assert not (runtime_version_dir(root, "v002") / "comparisons").exists()


def test_api_rejects_compare_result_with_mismatched_validator_type() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        baseline_dir, candidate_dir = write_demo_experiment(root)
        write_run_batch(baseline_dir, "baseline-run-001", version="v001")
        write_run_batch(candidate_dir, "candidate-run-001", version="v002")
        write_validation_batch(
            baseline_dir,
            validation_batch_id="validation-001",
            run_batch_id="baseline-run-001",
            version="v001",
            grade=5,
        )
        write_validation_batch(
            candidate_dir,
            validation_batch_id="validation-002",
            run_batch_id="candidate-run-001",
            version="v002",
            grade=5,
        )
        corrupt_validation_result(
            candidate_dir,
            validation_batch_id="validation-002",
            updates={"validator_type": "automatic"},
        )
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/experiments/demo/comparisons",
            json={"baseline_version": "v001", "candidate_version": "v002"},
        )

        assert response.status_code == 400
        assert "validator_type automatic, expected llm_questionnaire" in (
            response.json()["detail"]
        )
        assert not (runtime_version_dir(root, "v002") / "comparisons").exists()


def test_api_rejects_compare_completed_batch_with_no_validators() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        baseline_dir, candidate_dir = write_demo_experiment(root)
        write_run_batch(baseline_dir, "baseline-run-001", version="v001")
        write_run_batch(candidate_dir, "candidate-run-001", version="v002")
        write_validation_batch(
            baseline_dir,
            validation_batch_id="validation-001",
            run_batch_id="baseline-run-001",
            version="v001",
            grade=5,
        )
        write_validation_batch(
            candidate_dir,
            validation_batch_id="validation-002",
            run_batch_id="candidate-run-001",
            version="v002",
            grade=5,
        )
        validation_result_path(
            candidate_dir,
            validation_batch_id="validation-002",
        ).unlink()
        validators_snapshot = (
            candidate_dir / "validations" / "validation-002" / "validators_snapshot"
        )
        for path in validators_snapshot.glob("*.json"):
            path.unlink()
        batch_path = validation_batch_path(
            candidate_dir,
            validation_batch_id="validation-002",
        )
        batch = json.loads(batch_path.read_text(encoding="utf-8"))
        batch["validator_ids"] = []
        batch["total_results"] = 0
        batch["completed_results"] = 0
        write_json(batch_path, batch)
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/experiments/demo/comparisons",
            json={"baseline_version": "v001", "candidate_version": "v002"},
        )

        assert response.status_code == 400
        assert "has no validator snapshots" in response.json()["detail"]
        assert not (runtime_version_dir(root, "v002") / "comparisons").exists()


def main() -> int:
    tests = [
        test_compare_matrix_marks_low_grades_as_fail,
        test_compare_matrix_ignores_excluded_checks_and_results,
        test_compare_matrix_marks_null_grade_and_errors_as_mixed,
        test_compare_matrix_marks_grade_three_as_mixed,
        test_compare_matrix_uses_snapshot_rows_across_versions,
        test_api_returns_compare_matrix_from_latest_completed_validation_batches,
        test_api_rejects_compare_without_completed_validation_batch,
        test_api_rejects_compare_result_with_mismatched_batch_metadata,
        test_api_rejects_compare_result_with_unknown_snapshot_check_id,
        test_api_rejects_compare_result_with_mismatched_run_batch_id,
        test_api_rejects_compare_result_with_unknown_snapshot_validator_id,
        test_api_rejects_compare_with_missing_validation_result_file,
        test_api_rejects_compare_with_duplicate_validation_result_id,
        test_api_rejects_compare_with_duplicate_logical_validation_result,
        test_api_rejects_compare_ok_result_missing_snapshot_check,
        test_api_rejects_compare_result_with_unknown_run_case_repeat,
        test_api_rejects_compare_result_with_mismatched_run_id,
        test_api_rejects_compare_missing_expected_logical_result,
        test_api_rejects_compare_validation_batch_id_mismatching_directory_name,
        test_api_rejects_compare_ok_result_with_duplicate_check_ids,
        test_api_rejects_compare_error_result_with_duplicate_check_ids,
        test_api_rejects_compare_result_with_mismatched_validator_type,
        test_api_rejects_compare_completed_batch_with_no_validators,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
