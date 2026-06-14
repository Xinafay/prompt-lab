from __future__ import annotations

import json
from pathlib import Path, PureWindowsPath
from typing import Any

from prompt_lab.errors import NotFoundError
from prompt_lab.models.artifacts import CaseArtifact, ExperimentArtifact


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _resolve_version_local_path(version_dir: Path, relative_path: str) -> Path:
    root = version_dir.resolve()
    candidate = (root / relative_path).resolve()
    if candidate != root and not candidate.is_relative_to(root):
        raise NotFoundError("File not found")
    return candidate


def _validate_storage_id(value: str, label: str) -> None:
    windows_path = PureWindowsPath(value)
    if (
        not value
        or Path(value).is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or "/" in value
        or "\\" in value
        or value in {".", ".."}
    ):
        raise NotFoundError(f"{label} not found")


class PromptLabStore:
    """Filesystem-backed Prompt Lab artifact store."""

    def __init__(self, *, experiments_root: Path, examples_root: Path) -> None:
        self.experiments_root = experiments_root
        self.examples_root = examples_root

    def list_experiments(self) -> list[ExperimentArtifact]:
        """Return runtime experiments from `experiments/`, sorted by id."""
        if not self.experiments_root.exists():
            return []
        manifests: dict[str, ExperimentArtifact] = {}
        for manifest_path in sorted(self.experiments_root.glob("*/experiment.json")):
            artifact = ExperimentArtifact.model_validate(_read_json(manifest_path))
            manifests[artifact.id] = artifact
        return [manifests[key] for key in sorted(manifests)]

    def experiment_dir(self, experiment_id: str) -> Path:
        """Resolve an experiment directory under the runtime experiments root."""
        _validate_storage_id(experiment_id, "Experiment")
        resolved_root = self.experiments_root.resolve()
        candidate = (resolved_root / experiment_id).resolve()
        if candidate != resolved_root and not candidate.is_relative_to(resolved_root):
            raise NotFoundError("Experiment not found")
        if (candidate / "experiment.json").is_file():
            return candidate
        raise NotFoundError("Experiment not found")

    def load_experiment(self, experiment_id: str) -> ExperimentArtifact:
        path = self.experiment_dir(experiment_id) / "experiment.json"
        return ExperimentArtifact.model_validate(_read_json(path))

    def list_versions(self, experiment_id: str) -> list[str]:
        versions_root = self.experiment_dir(experiment_id) / "versions"
        if not versions_root.is_dir():
            return []
        return sorted(path.name for path in versions_root.iterdir() if path.is_dir())

    def save_experiment(
        self, experiment_id: str, artifact: ExperimentArtifact
    ) -> Path:
        """Persist an experiment manifest under the runtime experiments root."""
        if artifact.id != experiment_id:
            raise NotFoundError("Experiment not found")
        experiment_dir = self.experiment_dir(experiment_id)
        active_version_dir = experiment_dir / "versions" / artifact.active_version
        if not active_version_dir.is_dir():
            raise NotFoundError("Version not found")
        path = experiment_dir / "experiment.json"
        _write_json(path, artifact.model_dump(mode="json"))
        return path.resolve()

    def version_dir(self, experiment_id: str, version: str) -> Path:
        _validate_storage_id(version, "Version")
        versions_root = (self.experiment_dir(experiment_id) / "versions").resolve()
        candidate = (versions_root / version).resolve()
        if candidate != versions_root and not candidate.is_relative_to(versions_root):
            raise NotFoundError("Version not found")
        if not candidate.is_dir():
            raise NotFoundError("Version not found")
        return candidate

    def read_text(self, experiment_id: str, version: str, relative_path: str) -> str:
        path = _resolve_version_local_path(
            self.version_dir(experiment_id, version), relative_path
        )
        if not path.is_file():
            raise NotFoundError("File not found")
        return path.read_text(encoding="utf-8")

    def load_cases(self, experiment_id: str) -> list[CaseArtifact]:
        cases_dir = self.experiment_dir(experiment_id) / "cases"
        if not cases_dir.is_dir():
            return []
        return [
            CaseArtifact.model_validate(_read_json(path))
            for path in sorted(cases_dir.glob("*.json"))
        ]

    def write_run_artifact(self, experiment_id: str, version: str, relative_path: str, value: dict[str, Any]) -> Path:
        path = _resolve_version_local_path(
            self.version_dir(experiment_id, version), relative_path
        )
        _write_json(path, value)
        return path
