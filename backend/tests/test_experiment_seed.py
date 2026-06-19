from __future__ import annotations

import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from prompt_lab.api import create_app
from prompt_lab.config import PromptLabConfig
from prompt_lab.experiment_seed import seed_experiments_from_examples
from prompt_lab.settings import PromptLabSettings


MANIFEST = {
    "schema_version": "prompt_lab.experiment/v1",
    "id": "demo",
    "title": "Demo",
    "description": "",
    "active_version": "v001",
    "output": {"type": "text"},
    "template": {"engine": "jinja2", "path": "prompt.md"},
    "models": {
        "generator_model": "local/a",
        "validator_model": "openai/validator-a",
        "judge_model": "openai/b",
    },
    "run_defaults": {
        "repeat_count": 1,
        "llm_cache": "disabled",
        "case_order": "case-major",
    },
}


def write_example(root: Path, experiment_id: str = "demo") -> Path:
    example_dir = root / "examples" / experiment_id
    version_dir = example_dir / "versions" / "v001"
    version_dir.mkdir(parents=True)
    manifest = {**MANIFEST, "id": experiment_id, "title": experiment_id.title()}
    (example_dir / "experiment.json").write_text(
        json.dumps(manifest, ensure_ascii=False),
        encoding="utf-8",
    )
    (version_dir / "prompt.md").write_text("Prompt", encoding="utf-8")
    return example_dir


def test_seed_creates_experiments_root_when_missing() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_example(root)

        result = seed_experiments_from_examples(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        assert result.seeded is True
        assert result.copied_experiment_ids == ["demo"]
        assert (root / "experiments" / "demo" / "experiment.json").is_file()
        assert (
            root / "experiments" / "demo" / "versions" / "v001" / "prompt.md"
        ).read_text(encoding="utf-8") == "Prompt"


def test_seed_applies_global_defaults_to_copied_manifest() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_example(root)
        settings = PromptLabSettings(
            default_generator_model="local/default-generator",
            default_validator_model="openai/default-validator",
            default_judge_model="openai/default-judge",
            default_repeat_count=7,
        )

        result = seed_experiments_from_examples(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
            settings=settings,
        )

        assert result.seeded is True
        copied_manifest = json.loads(
            (root / "experiments" / "demo" / "experiment.json").read_text(
                encoding="utf-8"
            )
        )
        assert copied_manifest["models"] == {
            "generator_model": "local/default-generator",
            "validator_model": "openai/default-validator",
            "judge_model": "openai/default-judge",
        }
        assert copied_manifest["run_defaults"]["repeat_count"] == 7
        source_manifest = json.loads(
            (root / "examples" / "demo" / "experiment.json").read_text(
                encoding="utf-8"
            )
        )
        assert source_manifest["models"] == {
            "generator_model": "local/a",
            "validator_model": "openai/validator-a",
            "judge_model": "openai/b",
        }
        assert source_manifest["run_defaults"]["repeat_count"] == 1


def test_seed_preserves_manifest_defaults_for_artifact_fixtures() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        example_dir = write_example(root)
        artifact_dir = example_dir / "versions" / "v001" / "runs" / "run-000001"
        artifact_dir.mkdir(parents=True)
        settings = PromptLabSettings(
            default_generator_model="local/default-generator",
            default_validator_model="openai/default-validator",
            default_judge_model="openai/default-judge",
            default_repeat_count=7,
        )

        result = seed_experiments_from_examples(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
            settings=settings,
        )

        assert result.seeded is True
        copied_manifest = json.loads(
            (root / "experiments" / "demo" / "experiment.json").read_text(
                encoding="utf-8"
            )
        )
        assert copied_manifest["models"] == {
            "generator_model": "local/a",
            "validator_model": "openai/validator-a",
            "judge_model": "openai/b",
        }
        assert copied_manifest["run_defaults"]["repeat_count"] == 1


def test_seed_copies_when_experiments_root_is_empty() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "experiments").mkdir()
        write_example(root)

        result = seed_experiments_from_examples(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        assert result.seeded is True
        assert result.copied_experiment_ids == ["demo"]
        assert (root / "experiments" / "demo" / "experiment.json").is_file()


def test_seed_does_nothing_when_any_runtime_manifest_exists() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_example(root, "template")
        runtime_dir = root / "experiments" / "existing"
        runtime_dir.mkdir(parents=True)
        (runtime_dir / "experiment.json").write_text(
            json.dumps({**MANIFEST, "id": "existing"}, ensure_ascii=False),
            encoding="utf-8",
        )

        result = seed_experiments_from_examples(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        assert result.seeded is False
        assert result.copied_experiment_ids == []
        assert not (root / "experiments" / "template").exists()


def test_seed_creates_empty_experiments_when_examples_missing() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)

        result = seed_experiments_from_examples(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        assert result.seeded is False
        assert result.copied_experiment_ids == []
        assert (root / "experiments").is_dir()


def test_seed_fails_on_conflicting_existing_directory_without_manifest() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_example(root, "demo")
        conflict_dir = root / "experiments" / "demo"
        conflict_dir.mkdir(parents=True)
        (conflict_dir / "notes.txt").write_text("local data", encoding="utf-8")

        try:
            seed_experiments_from_examples(
                experiments_root=root / "experiments",
                examples_root=root / "examples",
            )
        except FileExistsError:
            pass
        else:
            raise AssertionError("Expected conflicting seed destination to fail")

        assert (conflict_dir / "notes.txt").read_text(encoding="utf-8") == "local data"


def test_repository_demo_examples_seed_for_ui_testing() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        shutil.copytree(repository_root / "examples", root / "examples")

        app = create_app(PromptLabConfig.from_env(project_root=root))
        client = TestClient(app)

        experiments = client.get("/api/experiments")
        assert experiments.status_code == 200
        experiment_ids = [item["id"] for item in experiments.json()]
        assert "demo-string" in experiment_ids
        assert "demo-json" in experiment_ids

        for experiment_id in ("demo-string", "demo-json"):
            runs = client.get(
                f"/api/experiments/{experiment_id}/versions/v002/runs"
            )
            assert runs.status_code == 200
            assert runs.json()["run_batch_id"] == "run-000002"
            assert len(runs.json()["runs"]) == 1

            validation = client.get(
                f"/api/experiments/{experiment_id}/versions/v002/validations/latest"
            )
            assert validation.status_code == 200
            assert validation.json()["validation_batch"]["validation_batch_id"] == (
                "validation-000002"
            )
            assert len(validation.json()["validators"]) == 2
            assert len(validation.json()["results"]) == 2

            review = client.get(
                f"/api/experiments/{experiment_id}/versions/v002/reviews/latest"
            )
            assert review.status_code == 200
            review_id = review.json()["review_id"]
            proposal = client.get(
                f"/api/experiments/{experiment_id}/versions/v002/reviews/"
                f"{review_id}/proposal"
            )
            assert proposal.status_code == 200
            assert proposal.json()["source"]["validation_batch_id"] == (
                "validation-000002"
            )

            comparison = client.post(
                f"/api/experiments/{experiment_id}/comparisons",
                json={
                    "baseline_version": "v001",
                    "candidate_version": "v002",
                    "dry_run": True,
                },
            )
            assert comparison.status_code == 200
            assert comparison.json()["schema_version"] == (
                "prompt_lab.compare_matrix/v1"
            )
            assert comparison.json()["versions"] == ["v001", "v002"]
            assert comparison.json()["rows"]


def main() -> int:
    tests = [
        test_seed_creates_experiments_root_when_missing,
        test_seed_applies_global_defaults_to_copied_manifest,
        test_seed_preserves_manifest_defaults_for_artifact_fixtures,
        test_seed_copies_when_experiments_root_is_empty,
        test_seed_does_nothing_when_any_runtime_manifest_exists,
        test_seed_creates_empty_experiments_when_examples_missing,
        test_seed_fails_on_conflicting_existing_directory_without_manifest,
        test_repository_demo_examples_seed_for_ui_testing,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
