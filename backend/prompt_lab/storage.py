from __future__ import annotations

import json
from pathlib import Path, PureWindowsPath
from typing import Any

from pydantic import TypeAdapter

from prompt_lab.errors import NotFoundError
from prompt_lab.models.artifacts import CaseArtifact, ExperimentArtifact
from prompt_lab.models.validators import (
    ValidationBatchArtifact,
    ValidationResultArtifact,
    ValidatorDefinition,
)


_VALIDATOR_DEFINITION_ADAPTER = TypeAdapter(ValidatorDefinition)


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
            if manifest_path.parent.name.endswith("_old"):
                continue
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
        cases: list[CaseArtifact] = []
        for path in sorted(cases_dir.glob("*.json")):
            cases.append(
                CaseArtifact.model_validate(
                    {
                        "id": path.stem,
                        "payload": _read_json(path),
                    }
                )
            )
        return cases

    def case_path(self, experiment_id: str, case_id: str) -> Path:
        _validate_storage_id(case_id, "Case")
        cases_dir = self.experiment_dir(experiment_id) / "cases"
        resolved_cases_dir = cases_dir.resolve()
        candidate = (resolved_cases_dir / f"{case_id}.json").resolve()
        if candidate != resolved_cases_dir and not candidate.is_relative_to(
            resolved_cases_dir
        ):
            raise NotFoundError("Case not found")
        return candidate

    def write_case(
        self,
        experiment_id: str,
        case_id: str,
        payload: dict[str, Any],
        *,
        overwrite: bool = False,
    ) -> CaseArtifact:
        path = self.case_path(experiment_id, case_id)
        if path.exists() and not overwrite:
            raise FileExistsError("Case already exists")
        _write_json(path, payload)
        return CaseArtifact.model_validate({"id": case_id, "payload": payload})

    def delete_case(self, experiment_id: str, case_id: str) -> None:
        path = self.case_path(experiment_id, case_id)
        if not path.is_file():
            raise NotFoundError("Case not found")
        path.unlink()

    def replace_cases(
        self, experiment_id: str, cases: list[CaseArtifact]
    ) -> list[CaseArtifact]:
        cases_dir = self.experiment_dir(experiment_id) / "cases"
        cases_dir.mkdir(parents=True, exist_ok=True)
        case_ids = {artifact_case.id for artifact_case in cases}
        for path in cases_dir.glob("*.json"):
            if path.stem not in case_ids:
                path.unlink()
        for artifact_case in cases:
            _write_json(
                self.case_path(experiment_id, artifact_case.id),
                artifact_case.payload,
            )
        return self.load_cases(experiment_id)

    def load_validators(
        self, experiment_id: str, version: str
    ) -> list[ValidatorDefinition]:
        validators_dir = self.version_dir(experiment_id, version) / "validators"
        if not validators_dir.is_dir():
            return []
        return [
            _VALIDATOR_DEFINITION_ADAPTER.validate_python(_read_json(path))
            for path in sorted(validators_dir.glob("*.json"))
        ]

    def write_run_artifact(self, experiment_id: str, version: str, relative_path: str, value: dict[str, Any]) -> Path:
        path = _resolve_version_local_path(
            self.version_dir(experiment_id, version), relative_path
        )
        _write_json(path, value)
        return path

    def write_validation_artifact(
        self,
        experiment_id: str,
        version: str,
        relative_path: str,
        value: dict[str, Any],
    ) -> Path:
        path = _resolve_version_local_path(
            self.version_dir(experiment_id, version), relative_path
        )
        _write_json(path, value)
        return path

    def load_validation_batch(
        self,
        experiment_id: str,
        version: str,
        validation_batch_id: str,
    ) -> ValidationBatchArtifact:
        path = self._validation_batch_dir(
            experiment_id,
            version,
            validation_batch_id,
        ) / "batch.json"
        if not path.is_file():
            raise NotFoundError("Validation batch not found")
        return ValidationBatchArtifact.model_validate(_read_json(path))

    def load_validation_results(
        self,
        experiment_id: str,
        version: str,
        validation_batch_id: str,
    ) -> list[ValidationResultArtifact]:
        batch_dir = self._validation_batch_dir(
            experiment_id,
            version,
            validation_batch_id,
        )
        if not batch_dir.is_dir():
            raise NotFoundError("Validation batch not found")
        results: list[ValidationResultArtifact] = []
        for path in sorted(batch_dir.rglob("*.json")):
            relative = path.relative_to(batch_dir)
            if relative.parts == ("batch.json",):
                continue
            if relative.parts and relative.parts[0] == "validators_snapshot":
                continue
            results.append(ValidationResultArtifact.model_validate(_read_json(path)))
        return results

    def _validation_batch_dir(
        self,
        experiment_id: str,
        version: str,
        validation_batch_id: str,
    ) -> Path:
        _validate_storage_id(validation_batch_id, "Validation batch")
        return (
            self.version_dir(experiment_id, version) / "validations" / validation_batch_id
        ).resolve()
