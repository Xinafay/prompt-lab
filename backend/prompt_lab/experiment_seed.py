from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from prompt_lab.models.artifacts import ExperimentArtifact
from prompt_lab.settings import PromptLabSettings


@dataclass(frozen=True)
class SeedResult:
    seeded: bool
    copied_experiment_ids: list[str]


def _has_runtime_experiment_manifests(experiments_root: Path) -> bool:
    return experiments_root.is_dir() and any(
        path.is_file() and not _is_ignored_experiment_dir(path.parent)
        for path in experiments_root.glob("*/experiment.json")
    )


def _is_ignored_experiment_dir(path: Path) -> bool:
    return path.name.endswith("_old")


def seed_experiments_from_examples(
    *,
    experiments_root: Path,
    examples_root: Path,
    settings: PromptLabSettings | None = None,
) -> SeedResult:
    """Seed local runtime experiments from committed examples exactly once."""
    if _has_runtime_experiment_manifests(experiments_root):
        return SeedResult(seeded=False, copied_experiment_ids=[])

    experiments_root.mkdir(parents=True, exist_ok=True)
    if not examples_root.is_dir():
        return SeedResult(seeded=False, copied_experiment_ids=[])

    copied: list[str] = []
    for example_dir in sorted(path for path in examples_root.iterdir() if path.is_dir()):
        if _is_ignored_experiment_dir(example_dir):
            continue
        manifest_path = example_dir / "experiment.json"
        if not manifest_path.is_file():
            continue
        destination = experiments_root / example_dir.name
        shutil.copytree(example_dir, destination)
        if settings is not None:
            _apply_settings_to_copied_manifest(
                destination / "experiment.json",
                settings,
            )
        copied.append(example_dir.name)

    return SeedResult(seeded=bool(copied), copied_experiment_ids=copied)


def _apply_settings_to_copied_manifest(
    manifest_path: Path, settings: PromptLabSettings
) -> None:
    experiment = ExperimentArtifact.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    updated = experiment.model_copy(
        update={
            "models": experiment.models.model_copy(
                update={
                    "generator_model": settings.default_generator_model,
                    "judge_model": settings.default_judge_model,
                }
            ),
            "run_defaults": experiment.run_defaults.model_copy(
                update={"repeat_count": settings.default_repeat_count}
            ),
        }
    )
    manifest_path.write_text(
        updated.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
