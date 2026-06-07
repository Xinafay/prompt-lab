from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SeedResult:
    seeded: bool
    copied_experiment_ids: list[str]


def _has_runtime_experiment_manifests(experiments_root: Path) -> bool:
    return experiments_root.is_dir() and any(
        path.is_file() for path in experiments_root.glob("*/experiment.json")
    )


def seed_experiments_from_examples(
    *, experiments_root: Path, examples_root: Path
) -> SeedResult:
    """Seed local runtime experiments from committed examples exactly once."""
    if _has_runtime_experiment_manifests(experiments_root):
        return SeedResult(seeded=False, copied_experiment_ids=[])

    experiments_root.mkdir(parents=True, exist_ok=True)
    if not examples_root.is_dir():
        return SeedResult(seeded=False, copied_experiment_ids=[])

    copied: list[str] = []
    for example_dir in sorted(path for path in examples_root.iterdir() if path.is_dir()):
        manifest_path = example_dir / "experiment.json"
        if not manifest_path.is_file():
            continue
        destination = experiments_root / example_dir.name
        shutil.copytree(example_dir, destination)
        copied.append(example_dir.name)

    return SeedResult(seeded=bool(copied), copied_experiment_ids=copied)
