from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from prompt_lab.api import create_app
from prompt_lab.config import PromptLabConfig


def write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def write_demo_experiment(root: Path) -> Path:
    experiment_dir = root / "examples" / "demo"
    version_dir = experiment_dir / "versions" / "v001"
    version_dir.mkdir(parents=True)
    write_json(
        experiment_dir / "experiment.json",
        {
            "schema_version": "prompt_lab.experiment/v1",
            "id": "demo",
            "title": "Demo",
            "description": "",
            "active_version": "v001",
            "output": {"type": "text"},
            "template": {"engine": "jinja2", "path": "prompt.md"},
            "models": {
                "generator_model": "local/a",
                "validator_model": "openai/b",
                "judge_model": "openai/b",
            },
            "run_defaults": {
                "repeat_count": 1,
                "llm_cache": "disabled",
                "case_order": "case-major",
            },
        },
    )
    (version_dir / "prompt.md").write_text("Say {{ value }}", encoding="utf-8")
    write_json(version_dir / "validators" / "quality.json", quality_validator())
    return version_dir


def quality_validator() -> dict[str, object]:
    return {
        "schema_version": "prompt_lab.validator/v1",
        "validator_id": "quality",
        "type": "llm_questionnaire",
        "title": "Quality",
        "checks": [
            {
                "check_id": "has-answer",
                "title": "Has answer",
                "question": "Does the output contain an answer?",
            }
        ],
    }


def length_validator() -> dict[str, object]:
    return {
        "schema_version": "prompt_lab.validator/v1",
        "validator_id": "length",
        "type": "automatic",
        "title": "Length",
        "checks": [
            {
                "check_id": "short",
                "title": "Short",
                "rule": {
                    "kind": "word_count",
                    "source": "output_text",
                    "comparison": {"op": "gte", "value": 1},
                },
            }
        ],
    }


def add_runtime_artifacts(version_dir: Path) -> None:
    for relative_path in [
        "runs/run-001/a/repeat-001.json",
        "validations/validation-001/batch.json",
        "reviews/review-001/judgment.json",
        "comparisons/comparison-001/comparison.json",
    ]:
        path = version_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")


def test_create_next_writes_validators_and_clears_runtime_artifacts() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_demo_experiment(root)
        app = create_app(PromptLabConfig.from_env(project_root=root))
        current_version_dir = root / "experiments" / "demo" / "versions" / "v001"
        add_runtime_artifacts(current_version_dir)

        response = TestClient(app).post(
            "/api/experiments/demo/versions/v001/validators",
            json={
                "mode": "create_next",
                "validators": [length_validator(), quality_validator()],
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["version"] == "v002"
        assert body["source_version"] == "v001"
        assert body["mode"] == "create_next"
        new_version_dir = root / "experiments" / "demo" / "versions" / "v002"
        assert Path(body["version_dir"]).resolve() == new_version_dir.resolve()
        assert (new_version_dir / "prompt.md").read_text(encoding="utf-8") == (
            "Say {{ value }}"
        )
        assert {
            path.name for path in (new_version_dir / "validators").glob("*.json")
        } == {"length.json", "quality.json"}
        assert json.loads(
            (new_version_dir / "validators" / "length.json").read_text(
                encoding="utf-8"
            )
        )["validator_id"] == "length"
        assert json.loads(
            (new_version_dir / "validators" / "quality.json").read_text(
                encoding="utf-8"
            )
        )["validator_id"] == "quality"
        assert not (new_version_dir / "runs").exists()
        assert not (new_version_dir / "validations").exists()
        assert not (new_version_dir / "reviews").exists()
        assert not (new_version_dir / "comparisons").exists()
        manifest = json.loads(
            (root / "experiments" / "demo" / "experiment.json").read_text(
                encoding="utf-8"
            )
        )
        assert manifest["active_version"] == "v001"


def test_overwrite_current_replaces_validators_and_preserves_runs() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_demo_experiment(root)
        app = create_app(PromptLabConfig.from_env(project_root=root))
        current_version_dir = root / "experiments" / "demo" / "versions" / "v001"
        add_runtime_artifacts(current_version_dir)

        response = TestClient(app).post(
            "/api/experiments/demo/versions/v001/validators",
            json={"mode": "overwrite_current", "validators": [length_validator()]},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["version"] == "v001"
        assert body["source_version"] == "v001"
        assert body["mode"] == "overwrite_current"
        assert Path(body["version_dir"]).resolve() == current_version_dir.resolve()
        assert {
            path.name for path in (current_version_dir / "validators").glob("*.json")
        } == {"length.json"}
        assert (
            current_version_dir / "runs" / "run-001" / "a" / "repeat-001.json"
        ).is_file()
        assert not (current_version_dir / "validations").exists()
        assert not (current_version_dir / "reviews").exists()
        assert not (current_version_dir / "comparisons").exists()


def test_duplicate_validator_ids_are_rejected() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_demo_experiment(root)
        app = create_app(PromptLabConfig.from_env(project_root=root))
        duplicate_quality = {**quality_validator(), "title": "Other Quality"}

        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/experiments/demo/versions/v001/validators",
            json={
                "mode": "overwrite_current",
                "validators": [quality_validator(), duplicate_quality],
            },
        )

        assert response.status_code == 400
        assert "duplicate validator_id: quality" in response.json()["detail"]


def test_unsafe_validator_ids_are_rejected() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_demo_experiment(root)
        app = create_app(PromptLabConfig.from_env(project_root=root))
        unsafe = {**quality_validator(), "validator_id": "../bad"}

        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/experiments/demo/versions/v001/validators",
            json={"mode": "overwrite_current", "validators": [unsafe]},
        )

        assert response.status_code == 400
        assert "Unsafe validator id" in response.json()["detail"]


def main() -> int:
    tests = [
        test_create_next_writes_validators_and_clears_runtime_artifacts,
        test_overwrite_current_replaces_validators_and_preserves_runs,
        test_duplicate_validator_ids_are_rejected,
        test_unsafe_validator_ids_are_rejected,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
