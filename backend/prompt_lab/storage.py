from __future__ import annotations

import json
import re
import shutil
from pathlib import Path, PureWindowsPath
from typing import Any, Literal

from pydantic import TypeAdapter

from prompt_lab.errors import NotFoundError
from prompt_lab.settings import PromptLabSettings
from prompt_lab.models.artifacts import CaseArtifact, CaseSuiteArtifact, ExperimentArtifact
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


def _slugify_title(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "experiment"


class PromptLabStore:
    """Filesystem-backed Prompt Lab artifact store."""

    def __init__(
        self,
        *,
        experiments_root: Path,
        examples_root: Path,
        case_suites_root: Path | None = None,
    ) -> None:
        self.experiments_root = experiments_root
        self.examples_root = examples_root
        self.case_suites_root = (
            case_suites_root or experiments_root.parent / "case_suites"
        )

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

    def list_case_suites(self) -> list[CaseSuiteArtifact]:
        """Return runtime case suites from `case_suites/`, sorted by id."""
        if not self.case_suites_root.exists():
            return []
        manifests: dict[str, CaseSuiteArtifact] = {}
        for manifest_path in sorted(self.case_suites_root.glob("*/suite.json")):
            artifact = CaseSuiteArtifact.model_validate(_read_json(manifest_path))
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

    def case_suite_dir(self, suite_id: str) -> Path:
        """Resolve a case suite directory under the runtime case suites root."""
        _validate_storage_id(suite_id, "Case Suite")
        resolved_root = self.case_suites_root.resolve()
        candidate = (resolved_root / suite_id).resolve()
        if candidate != resolved_root and not candidate.is_relative_to(resolved_root):
            raise NotFoundError("Case Suite not found")
        if (candidate / "suite.json").is_file():
            return candidate
        raise NotFoundError("Case Suite not found")

    def load_case_suite(self, suite_id: str) -> CaseSuiteArtifact:
        path = self.case_suite_dir(suite_id) / "suite.json"
        return CaseSuiteArtifact.model_validate(_read_json(path))

    def _available_experiment_id(self, title: str) -> str:
        base = _slugify_title(title)
        resolved_root = self.experiments_root.resolve()
        self.experiments_root.mkdir(parents=True, exist_ok=True)
        candidate = base
        suffix = 2
        while True:
            _validate_storage_id(candidate, "Experiment")
            candidate_dir = (resolved_root / candidate).resolve()
            if candidate_dir != resolved_root and not candidate_dir.is_relative_to(
                resolved_root
            ):
                raise NotFoundError("Experiment not found")
            if not candidate_dir.exists():
                return candidate
            candidate = f"{base}-{suffix}"
            suffix += 1

    def _available_case_suite_id(self, title: str) -> str:
        base = _slugify_title(title)
        resolved_root = self.case_suites_root.resolve()
        self.case_suites_root.mkdir(parents=True, exist_ok=True)
        candidate = base
        suffix = 2
        while True:
            _validate_storage_id(candidate, "Case Suite")
            candidate_dir = (resolved_root / candidate).resolve()
            if candidate_dir != resolved_root and not candidate_dir.is_relative_to(
                resolved_root
            ):
                raise NotFoundError("Case Suite not found")
            if not candidate_dir.exists():
                return candidate
            candidate = f"{base}-{suffix}"
            suffix += 1

    def create_case_suite(
        self, *, title: str, description: str = ""
    ) -> CaseSuiteArtifact:
        if title.strip() == "":
            raise ValueError("Case Suite title cannot be blank")
        suite_id = self._available_case_suite_id(title)
        suite_dir = self.case_suites_root.resolve() / suite_id
        artifact = CaseSuiteArtifact.model_validate(
            {
                "schema_version": "prompt_lab.case_suite/v1",
                "id": suite_id,
                "title": title,
                "description": description,
            }
        )
        try:
            (suite_dir / "cases").mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            raise FileExistsError("Case Suite already exists")
        _write_json(suite_dir / "suite.json", artifact.model_dump(mode="json"))
        return artifact

    def save_case_suite(
        self, suite_id: str, artifact: CaseSuiteArtifact
    ) -> CaseSuiteArtifact:
        if artifact.id != suite_id:
            raise NotFoundError("Case Suite not found")
        suite_dir = self.case_suite_dir(suite_id)
        _write_json(suite_dir / "suite.json", artifact.model_dump(mode="json"))
        return artifact

    def delete_case_suite(self, suite_id: str) -> None:
        _validate_storage_id(suite_id, "Case Suite")
        if self.experiments_using_case_suite(suite_id):
            raise ValueError("Case Suite is used by one or more experiments")
        if (self.case_suites_root / suite_id).is_symlink():
            raise NotFoundError("Case Suite not found")
        suite_dir = self.case_suite_dir(suite_id)
        shutil.rmtree(suite_dir)

    def create_experiment(
        self,
        *,
        title: str,
        output_type: Literal["text", "pydantic"],
        model_entrypoint: str | None,
        settings: PromptLabSettings,
    ) -> ExperimentArtifact:
        if title.strip() == "":
            raise ValueError("Experiment title cannot be blank")
        if output_type not in {"text", "pydantic"}:
            raise ValueError("Unsupported output type")
        output: dict[str, Any]
        if output_type == "pydantic":
            if model_entrypoint is None or model_entrypoint.strip() == "":
                raise ValueError("pydantic output requires model_entrypoint")
            output = {
                "type": "pydantic",
                "model_file": "model.py",
                "model_entrypoint": model_entrypoint.strip(),
            }
        else:
            output = {"type": "text"}
        experiment_id = self._available_experiment_id(title)
        experiment_dir = self.experiments_root.resolve() / experiment_id
        version_dir = experiment_dir / "versions" / "v001"
        artifact = ExperimentArtifact.model_validate(
            {
                "schema_version": "prompt_lab.experiment/v1",
                "id": experiment_id,
                "title": title,
                "description": "",
                "active_version": "v001",
                "output": output,
                "template": {"engine": "jinjax", "path": "prompt.md"},
                "models": {
                    "generator_model": settings.default_generator_model,
                    "validator_model": settings.default_validator_model,
                    "judge_model": settings.default_judge_model,
                },
                "run_defaults": {
                    "repeat_count": settings.default_repeat_count,
                    "llm_cache": "disabled",
                    "case_order": "case-major",
                    "excluded_case_ids": [],
                },
            }
        )
        try:
            version_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            raise FileExistsError("Experiment already exists")
        _write_json(experiment_dir / "experiment.json", artifact.model_dump(mode="json"))
        (version_dir / "prompt.md").write_text("", encoding="utf-8")
        if output_type == "pydantic":
            (version_dir / "model.py").write_text("", encoding="utf-8")
        return artifact

    def clone_experiment(
        self,
        *,
        source_experiment_id: str,
        title: str,
    ) -> ExperimentArtifact:
        if title.strip() == "":
            raise ValueError("Experiment title cannot be blank")
        _validate_storage_id(source_experiment_id, "Experiment")
        if (self.experiments_root / source_experiment_id).is_symlink():
            raise NotFoundError("Experiment not found")
        source_dir = self.experiment_dir(source_experiment_id)
        for path in source_dir.rglob("*"):
            if path.is_symlink():
                raise NotFoundError("Experiment not found")
        source_artifact = self.load_experiment(source_experiment_id)
        experiment_id = self._available_experiment_id(title)
        destination = self.experiments_root.resolve() / experiment_id
        cloned = source_artifact.model_copy(
            update={
                "id": experiment_id,
                "title": title,
            }
        )
        try:
            shutil.copytree(source_dir, destination)
        except FileExistsError:
            raise FileExistsError("Experiment already exists")
        except Exception:
            if destination.exists():
                shutil.rmtree(destination)
            raise
        try:
            _write_json(destination / "experiment.json", cloned.model_dump(mode="json"))
        except Exception:
            if destination.exists():
                shutil.rmtree(destination)
            raise
        return cloned

    def delete_experiment(self, experiment_id: str) -> None:
        _validate_storage_id(experiment_id, "Experiment")
        if (self.experiments_root / experiment_id).is_symlink():
            raise NotFoundError("Experiment not found")
        experiment_dir = self.experiment_dir(experiment_id)
        shutil.rmtree(experiment_dir)

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
        experiment = self.load_experiment(experiment_id)
        if experiment.case_suite_id is None:
            raise NotFoundError("Case Suite not assigned")
        return self.load_cases_for_suite(experiment.case_suite_id)

    def load_cases_for_suite(self, suite_id: str) -> list[CaseArtifact]:
        cases_dir = self.case_suite_dir(suite_id) / "cases"
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

    def case_suite_case_path(self, suite_id: str, case_id: str) -> Path:
        _validate_storage_id(case_id, "Case")
        cases_dir = self.case_suite_dir(suite_id) / "cases"
        resolved_cases_dir = cases_dir.resolve()
        candidate = (resolved_cases_dir / f"{case_id}.json").resolve()
        if candidate != resolved_cases_dir and not candidate.is_relative_to(
            resolved_cases_dir
        ):
            raise NotFoundError("Case not found")
        return candidate

    def write_case_to_suite(
        self,
        suite_id: str,
        case_id: str,
        payload: dict[str, Any],
        *,
        overwrite: bool = False,
    ) -> CaseArtifact:
        path = self.case_suite_case_path(suite_id, case_id)
        if path.exists() and not overwrite:
            raise FileExistsError("Case already exists")
        _write_json(path, payload)
        self.invalidate_case_suite_consumers(suite_id)
        return CaseArtifact.model_validate({"id": case_id, "payload": payload})

    def delete_case_from_suite(self, suite_id: str, case_id: str) -> None:
        path = self.case_suite_case_path(suite_id, case_id)
        if not path.is_file():
            raise NotFoundError("Case not found")
        path.unlink()
        self.invalidate_case_suite_consumers(suite_id)

    def replace_suite_cases(
        self, suite_id: str, cases: list[CaseArtifact]
    ) -> list[CaseArtifact]:
        suite_dir = self.case_suite_dir(suite_id)
        cases_dir = suite_dir / "cases"
        case_paths = {
            artifact_case.id: self.case_suite_case_path(suite_id, artifact_case.id)
            for artifact_case in cases
        }
        cases_dir.mkdir(parents=True, exist_ok=True)
        case_ids = set(case_paths)
        for path in cases_dir.glob("*.json"):
            if path.stem not in case_ids:
                path.unlink()
        for artifact_case in cases:
            _write_json(case_paths[artifact_case.id], artifact_case.payload)
        self.invalidate_case_suite_consumers(suite_id)
        return self.load_cases_for_suite(suite_id)

    def experiments_using_case_suite(
        self, suite_id: str
    ) -> list[ExperimentArtifact]:
        _validate_storage_id(suite_id, "Case Suite")
        return [
            experiment
            for experiment in self.list_experiments()
            if experiment.case_suite_id == suite_id
        ]

    def invalidate_experiment_generated_artifacts(self, experiment_id: str) -> None:
        for version in self.list_versions(experiment_id):
            version_dir = self.version_dir(experiment_id, version)
            for name in ["runs", "validations", "reviews", "comparisons"]:
                path = version_dir / name
                if path.exists():
                    shutil.rmtree(path)

    def invalidate_case_suite_consumers(self, suite_id: str) -> list[str]:
        experiments = self.experiments_using_case_suite(suite_id)
        for experiment in experiments:
            self.invalidate_experiment_generated_artifacts(experiment.id)
        return [experiment.id for experiment in experiments]

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
