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
    example_dir = root / "examples" / "experiments" / experiment_id
    version_dir = example_dir / "versions" / "v001"
    version_dir.mkdir(parents=True)
    manifest = {
        **MANIFEST,
        "id": experiment_id,
        "title": experiment_id.title(),
        "case_suite_id": "demo-suite",
    }
    (example_dir / "experiment.json").write_text(
        json.dumps(manifest, ensure_ascii=False),
        encoding="utf-8",
    )
    (version_dir / "prompt.md").write_text("Prompt", encoding="utf-8")
    return example_dir


def write_case_suite(root: Path, suite_id: str = "demo-suite") -> Path:
    suite_dir = root / "examples" / "case_suites" / suite_id
    cases_dir = suite_dir / "cases"
    cases_dir.mkdir(parents=True)
    manifest = {
        "schema_version": "prompt_lab.case_suite/v1",
        "id": suite_id,
        "title": suite_id.replace("-", " ").title(),
        "description": "",
    }
    (suite_dir / "suite.json").write_text(
        json.dumps(manifest, ensure_ascii=False),
        encoding="utf-8",
    )
    (cases_dir / "case-a.json").write_text(
        json.dumps({"value": "alpha"}, ensure_ascii=False),
        encoding="utf-8",
    )
    return suite_dir


def test_seed_creates_experiments_root_when_missing() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_example(root)

        result = seed_experiments_from_examples(
            experiments_root=root / "experiments",
            case_suites_root=root / "case_suites",
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
            case_suites_root=root / "case_suites",
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
            (root / "examples" / "experiments" / "demo" / "experiment.json").read_text(
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
            case_suites_root=root / "case_suites",
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
            case_suites_root=root / "case_suites",
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
            case_suites_root=root / "case_suites",
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
            case_suites_root=root / "case_suites",
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
                case_suites_root=root / "case_suites",
                examples_root=root / "examples",
            )
        except FileExistsError:
            pass
        else:
            raise AssertionError("Expected conflicting seed destination to fail")

        assert (conflict_dir / "notes.txt").read_text(encoding="utf-8") == "local data"


def test_seed_copies_case_suites_independently() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_case_suite(root)

        result = seed_experiments_from_examples(
            experiments_root=root / "experiments",
            case_suites_root=root / "case_suites",
            examples_root=root / "examples",
        )

        assert result.seeded_case_suites is True
        assert result.copied_case_suite_ids == ["demo-suite"]
        assert (root / "case_suites" / "demo-suite" / "suite.json").is_file()
        assert (
            root / "case_suites" / "demo-suite" / "cases" / "case-a.json"
        ).is_file()


def test_seed_does_not_materialize_suite_cases_under_experiments() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_example(root)
        write_case_suite(root)

        result = seed_experiments_from_examples(
            experiments_root=root / "experiments",
            case_suites_root=root / "case_suites",
            examples_root=root / "examples",
        )

        assert result.seeded is True
        assert result.seeded_case_suites is True
        assert not (root / "experiments" / "demo" / "cases").exists()
        assert (root / "case_suites" / "demo-suite" / "cases" / "case-a.json").is_file()


def test_seed_does_not_overwrite_existing_case_suites() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_case_suite(root, "template-suite")
        runtime_dir = root / "case_suites" / "local-suite"
        runtime_dir.mkdir(parents=True)
        (runtime_dir / "suite.json").write_text(
            json.dumps(
                {
                    "schema_version": "prompt_lab.case_suite/v1",
                    "id": "local-suite",
                    "title": "Local Suite",
                    "description": "",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = seed_experiments_from_examples(
            experiments_root=root / "experiments",
            case_suites_root=root / "case_suites",
            examples_root=root / "examples",
        )

        assert result.seeded_case_suites is False
        assert result.copied_case_suite_ids == []
        assert not (root / "case_suites" / "template-suite").exists()


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

        expected_suites = {
            "demo-string": "demo-string-replies",
            "demo-json": "demo-json-briefs",
        }
        for experiment_id, suite_id in expected_suites.items():
            experiment_dir = root / "experiments" / experiment_id
            experiment_manifest = json.loads(
                (experiment_dir / "experiment.json").read_text(encoding="utf-8")
            )
            assert experiment_manifest["case_suite_id"] == suite_id

            suite_cases_dir = root / "case_suites" / suite_id / "cases"
            suite_case_ids = {
                path.stem for path in suite_cases_dir.glob("*.json") if path.is_file()
            }
            run_batch_dir = (
                experiment_dir / "versions" / "v002" / "runs" / "run-000002"
            )
            run_case_ids = {
                path.name for path in run_batch_dir.iterdir() if path.is_dir()
            }
            validation_dir = (
                experiment_dir
                / "versions"
                / "v002"
                / "validations"
                / "validation-000002"
            )
            validation_case_ids = {
                path.name
                for path in validation_dir.iterdir()
                if path.is_dir() and path.name != "validators_snapshot"
            }

            assert suite_case_ids == run_case_ids
            assert validation_case_ids >= suite_case_ids
            assert not (experiment_dir / "cases").exists()

            overview = client.get(f"/api/experiments/{experiment_id}/versions/v002")
            assert overview.status_code == 200
            assert {case["id"] for case in overview.json()["cases"]} == suite_case_ids

            runs = client.get(
                f"/api/experiments/{experiment_id}/versions/v002/runs"
            )
            assert runs.status_code == 200
            assert runs.json()["run_batch_id"] == "run-000002"
            assert {run["case_id"] for run in runs.json()["runs"]} == run_case_ids

            validation = client.get(
                f"/api/experiments/{experiment_id}/versions/v002/validations/latest"
            )
            assert validation.status_code == 200
            assert validation.json()["validation_batch"]["validation_batch_id"] == (
                "validation-000002"
            )
            assert len(validation.json()["validators"]) == 2
            assert {
                result["case_id"] for result in validation.json()["results"]
            } >= suite_case_ids


def main() -> int:
    tests = [
        test_seed_creates_experiments_root_when_missing,
        test_seed_applies_global_defaults_to_copied_manifest,
        test_seed_preserves_manifest_defaults_for_artifact_fixtures,
        test_seed_copies_when_experiments_root_is_empty,
        test_seed_does_nothing_when_any_runtime_manifest_exists,
        test_seed_creates_empty_experiments_when_examples_missing,
        test_seed_fails_on_conflicting_existing_directory_without_manifest,
        test_seed_copies_case_suites_independently,
        test_seed_does_not_materialize_suite_cases_under_experiments,
        test_seed_does_not_overwrite_existing_case_suites,
        test_repository_demo_examples_seed_for_ui_testing,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
