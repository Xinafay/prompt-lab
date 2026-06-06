from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from prompt_lab.errors import NotFoundError
from prompt_lab.models.artifacts import CaseArtifact, ExperimentArtifact


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class PromptLabStore:
    """Filesystem-backed Prompt Lab artifact store."""

    def __init__(self, *, experiments_root: Path, examples_root: Path) -> None:
        self.experiments_root = experiments_root
        self.examples_root = examples_root

    def list_experiments(self) -> list[ExperimentArtifact]:
        """Return experiments from `experiments/` and `examples/`, sorted by id."""
        manifests: dict[str, ExperimentArtifact] = {}
        for root in [self.examples_root, self.experiments_root]:
            if not root.exists():
                continue
            for manifest_path in sorted(root.glob("*/experiment.json")):
                artifact = ExperimentArtifact.model_validate(_read_json(manifest_path))
                manifests[artifact.id] = artifact
        return [manifests[key] for key in sorted(manifests)]

    def experiment_dir(self, experiment_id: str) -> Path:
        """Resolve an experiment directory, preferring editable experiments over examples."""
        for root in [self.experiments_root, self.examples_root]:
            candidate = root / experiment_id
            if (candidate / "experiment.json").is_file():
                return candidate
        raise NotFoundError(f"Experiment not found: {experiment_id}")

    def load_experiment(self, experiment_id: str) -> ExperimentArtifact:
        path = self.experiment_dir(experiment_id) / "experiment.json"
        return ExperimentArtifact.model_validate(_read_json(path))

    def version_dir(self, experiment_id: str, version: str) -> Path:
        path = self.experiment_dir(experiment_id) / "versions" / version
        if not path.is_dir():
            raise NotFoundError(f"Version not found: {experiment_id}/{version}")
        return path

    def read_text(self, experiment_id: str, version: str, relative_path: str) -> str:
        path = self.version_dir(experiment_id, version) / relative_path
        if not path.is_file():
            raise NotFoundError(f"File not found: {path}")
        return path.read_text(encoding="utf-8")

    def load_cases(self, experiment_id: str, version: str) -> list[CaseArtifact]:
        cases_dir = self.version_dir(experiment_id, version) / "cases"
        if not cases_dir.is_dir():
            return []
        return [
            CaseArtifact.model_validate(_read_json(path))
            for path in sorted(cases_dir.glob("*.json"))
        ]

    def write_run_artifact(self, experiment_id: str, version: str, relative_path: str, value: dict[str, Any]) -> Path:
        path = self.version_dir(experiment_id, version) / relative_path
        _write_json(path, value)
        return path
