from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

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


def main() -> int:
    tests = [
        test_seed_creates_experiments_root_when_missing,
        test_seed_applies_global_defaults_to_copied_manifest,
        test_seed_copies_when_experiments_root_is_empty,
        test_seed_does_nothing_when_any_runtime_manifest_exists,
        test_seed_creates_empty_experiments_when_examples_missing,
        test_seed_fails_on_conflicting_existing_directory_without_manifest,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
