from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from prompt_lab.errors import NotFoundError
from prompt_lab.models.artifacts import ExperimentArtifact
from prompt_lab.models.validators import (
    AutomaticValidatorDefinition,
    ValidationBatchArtifact,
)
from prompt_lab.storage import PromptLabStore


def test_store_does_not_list_examples_directly() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        example = root / "examples" / "demo"
        version = example / "versions" / "v001"
        version.mkdir(parents=True)
        (example / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","validator_model":"openai/b","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )

        store = PromptLabStore(experiments_root=root / "experiments", examples_root=root / "examples")

        assert store.list_experiments() == []


def test_store_ignores_old_runtime_experiment_directories() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        for directory, title in (
            (root / "experiments" / "demo", "Demo"),
            (root / "experiments" / "demo_old", "Old Demo"),
        ):
            (directory / "versions" / "v001").mkdir(parents=True)
            payload = {
                "schema_version": "prompt_lab.experiment/v1",
                "id": "demo",
                "title": title,
                "description": "",
                "active_version": "v001",
                "output": {"type": "text"},
                "template": {"engine": "jinja2", "path": "prompt.md"},
                "models": {"generator_model": "local/a", "validator_model": "openai/b", "judge_model": "openai/b"},
                "run_defaults": {
                    "repeat_count": 3,
                    "llm_cache": "disabled",
                    "case_order": "case-major",
                },
            }
            (directory / "experiment.json").write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )

        store = PromptLabStore(experiments_root=root / "experiments", examples_root=root / "examples")

        experiments = store.list_experiments()
        assert len(experiments) == 1
        assert experiments[0].title == "Demo"


def test_store_loads_cases_for_experiment() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        cases = experiment / "cases"
        cases.mkdir(parents=True)
        (experiment / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","validator_model":"openai/b","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )
        (cases / "case-a.json").write_text(
            '{"schema_version":"prompt_lab.case/v2","id":"case-a","title":"Case A","stores":{"case":{"kind":"flat_file_tree","values":{"text":{"__carmilla_flat_file_node__":"file","value":"hello"}}}},"bindings":{"text":{"kind":"store_scope","store":"case","path":"text"}}}',
            encoding="utf-8",
        )

        store = PromptLabStore(experiments_root=root / "experiments", examples_root=root / "examples")

        loaded = store.load_cases("demo")
        assert len(loaded) == 1
        assert loaded[0].id == "case-a"


def test_store_rejects_read_path_escape() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        version = experiment / "versions" / "v001"
        version.mkdir(parents=True)
        (experiment / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","validator_model":"openai/b","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )
        (experiment / "secret.txt").write_text("secret", encoding="utf-8")

        store = PromptLabStore(experiments_root=root / "experiments", examples_root=root / "examples")

        try:
            store.read_text("demo", "v001", "../../secret.txt")
        except NotFoundError:
            pass
        else:
            raise AssertionError("Expected read path escape to be rejected")


def test_store_rejects_write_path_escape() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        version = experiment / "versions" / "v001"
        version.mkdir(parents=True)
        (experiment / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","validator_model":"openai/b","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )

        store = PromptLabStore(experiments_root=root / "experiments", examples_root=root / "examples")

        try:
            store.write_run_artifact("demo", "v001", "../../escaped.json", {"ok": True})
        except NotFoundError:
            pass
        else:
            raise AssertionError("Expected write path escape to be rejected")
        assert not (experiment / "escaped.json").exists()


def test_store_rejects_experiment_id_path_escape() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        (experiment / "versions" / "v001").mkdir(parents=True)
        (experiment / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","validator_model":"openai/b","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )

        store = PromptLabStore(experiments_root=root / "experiments", examples_root=root / "examples")

        for experiment_id in ["../demo", str(root / "experiments" / "demo")]:
            try:
                store.experiment_dir(experiment_id)
            except NotFoundError as exc:
                assert str(root) not in str(exc)
            else:
                raise AssertionError("Expected experiment id path escape to be rejected")


def test_store_rejects_version_path_escape_for_read() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        version = experiment / "versions" / "v001"
        version.mkdir(parents=True)
        (experiment / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","validator_model":"openai/b","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )
        (experiment / "secret.txt").write_text("secret", encoding="utf-8")

        store = PromptLabStore(experiments_root=root / "experiments", examples_root=root / "examples")

        try:
            store.read_text("demo", "..", "secret.txt")
        except NotFoundError as exc:
            assert str(root) not in str(exc)
        else:
            raise AssertionError("Expected version path escape to be rejected")


def test_store_rejects_version_path_escape_for_write() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        version = experiment / "versions" / "v001"
        version.mkdir(parents=True)
        (experiment / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","validator_model":"openai/b","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )

        store = PromptLabStore(experiments_root=root / "experiments", examples_root=root / "examples")

        try:
            store.write_run_artifact("demo", "..", "escaped.json", {"ok": True})
        except NotFoundError as exc:
            assert str(root) not in str(exc)
        else:
            raise AssertionError("Expected version path escape to be rejected")
        assert not (experiment / "escaped.json").exists()


def test_store_writes_nested_run_artifact() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        version = experiment / "versions" / "v001"
        version.mkdir(parents=True)
        (experiment / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","validator_model":"openai/b","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )

        store = PromptLabStore(experiments_root=root / "experiments", examples_root=root / "examples")

        path = store.write_run_artifact(
            "demo",
            "v001",
            "runs/run-001/repeats/repeat-001.json",
            {"ok": True},
        )

        assert path == (version / "runs" / "run-001" / "repeats" / "repeat-001.json").resolve()
        assert json.loads(path.read_text(encoding="utf-8")) == {"ok": True}


def test_store_loads_validators_sorted_by_filename() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        validators = experiment / "validators"
        (experiment / "versions" / "v001").mkdir(parents=True)
        validators.mkdir(parents=True)
        write_experiment_manifest(experiment / "experiment.json")
        (validators / "b.json").write_text(
            json.dumps(
                {
                    "schema_version": "prompt_lab.validator/v1",
                    "validator_id": "word-count",
                    "type": "automatic",
                    "title": "Word count",
                    "checks": [
                        {
                            "check_id": "under-100",
                            "title": "Under 100 words",
                            "rule": {
                                "kind": "word_count",
                                "source": "output_text",
                                "comparison": {"op": "lte", "value": 100},
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (validators / "a.json").write_text(
            json.dumps(
                {
                    "schema_version": "prompt_lab.validator/v1",
                    "validator_id": "clarity",
                    "type": "llm_questionnaire",
                    "title": "Clarity",
                    "checks": [
                        {
                            "check_id": "direct",
                            "title": "Direct",
                            "question": "Is the output direct?",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        loaded = store.load_validators("demo")

        assert [validator.validator_id for validator in loaded] == [
            "clarity",
            "word-count",
        ]
        assert isinstance(loaded[1], AutomaticValidatorDefinition)


def test_store_returns_empty_validators_when_directory_missing() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        (experiment / "versions" / "v001").mkdir(parents=True)
        write_experiment_manifest(experiment / "experiment.json")
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        assert store.load_validators("demo") == []


def test_store_writes_validation_artifact_and_rejects_path_escape() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        version = experiment / "versions" / "v001"
        version.mkdir(parents=True)
        write_experiment_manifest(experiment / "experiment.json")
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        path = store.write_validation_artifact(
            "demo",
            "v001",
            "validations/validation-001/batch.json",
            {"ok": True},
        )

        assert path == (version / "validations" / "validation-001" / "batch.json").resolve()
        assert json.loads(path.read_text(encoding="utf-8")) == {"ok": True}
        try:
            store.write_validation_artifact("demo", "v001", "../../escaped.json", {"ok": True})
        except NotFoundError:
            pass
        else:
            raise AssertionError("Expected validation artifact path escape to be rejected")
        assert not (experiment / "escaped.json").exists()


def test_store_loads_validation_batch_and_results() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        batch_dir = experiment / "versions" / "v001" / "validations" / "validation-001"
        (batch_dir / "validators_snapshot").mkdir(parents=True)
        write_experiment_manifest(experiment / "experiment.json")
        batch_payload = {
            "schema_version": "prompt_lab.validation_batch/v1",
            "validation_batch_id": "validation-001",
            "run_batch_id": "run-001",
            "version": "v001",
            "status": "completed",
            "started_at": "2026-06-19T10:00:00Z",
            "finished_at": "2026-06-19T10:01:00Z",
            "total_results": 1,
            "completed_results": 1,
            "validator_model": "openai/validator",
            "validator_ids": ["auto-length"],
        }
        result_payload = {
            "schema_version": "prompt_lab.validation_result/v1",
            "validation_result_id": "result-001",
            "validation_batch_id": "validation-001",
            "run_batch_id": "run-001",
            "run_id": "run-001-case-a-repeat-001",
            "case_id": "case-a",
            "repeat_index": 1,
            "validator_id": "auto-length",
            "validator_type": "automatic",
            "status": "ok",
            "included_in_judge": True,
            "check_results": [
                {
                    "check_id": "under-100",
                    "grade": 5,
                    "included_in_judge": True,
                    "metrics": {"value": 3},
                }
            ],
            "usage": {},
        }
        (batch_dir / "batch.json").write_text(json.dumps(batch_payload), encoding="utf-8")
        (batch_dir / "result-001.json").write_text(json.dumps(result_payload), encoding="utf-8")
        (batch_dir / "validators_snapshot" / "auto-length.json").write_text(
            '{"ignored": true}',
            encoding="utf-8",
        )
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        batch = store.load_validation_batch("demo", "v001", "validation-001")
        results = store.load_validation_results("demo", "v001", "validation-001")

        assert isinstance(batch, ValidationBatchArtifact)
        assert batch.validation_batch_id == "validation-001"
        assert [result.validation_result_id for result in results] == ["result-001"]
        assert results[0].check_results[0].metrics == {"value": 3}


def test_store_load_validation_batch_rejects_missing_or_escaped_id() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        (experiment / "versions" / "v001").mkdir(parents=True)
        write_experiment_manifest(experiment / "experiment.json")
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        for validation_batch_id in ["missing", "../secret"]:
            try:
                store.load_validation_batch("demo", "v001", validation_batch_id)
            except NotFoundError as exc:
                assert str(root) not in str(exc)
            else:
                raise AssertionError("Expected validation batch lookup to be rejected")


def test_store_resolves_only_experiments_root() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        example = root / "examples" / "demo"
        experiment = root / "experiments" / "demo"
        (example / "versions" / "v001").mkdir(parents=True)
        (experiment / "versions" / "v002").mkdir(parents=True)
        (example / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Example Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","validator_model":"openai/b","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )
        (experiment / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Editable Demo","description":"","active_version":"v002","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","validator_model":"openai/b","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )

        store = PromptLabStore(experiments_root=root / "experiments", examples_root=root / "examples")

        experiments = store.list_experiments()

        assert len(experiments) == 1
        assert experiments[0].id == "demo"
        assert experiments[0].title == "Editable Demo"
        assert store.experiment_dir("demo") == experiment.resolve()


def write_experiment_manifest(
    path: Path, *, experiment_id: str = "demo", active_version: str = "v001"
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "prompt_lab.experiment/v1",
                "id": experiment_id,
                "title": "Demo",
                "description": "",
                "active_version": active_version,
                "output": {"type": "text"},
                "template": {"engine": "jinja2", "path": "prompt.md"},
                "models": {
                    "generator_model": "local/a",
                    "validator_model": "openai/b",
                    "judge_model": "openai/b",
                },
                "run_defaults": {
                    "repeat_count": 3,
                    "llm_cache": "disabled",
                    "case_order": "case-major",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_store_saves_experiment_manifest_under_experiments_root() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        (experiment / "versions" / "v001").mkdir(parents=True)
        write_experiment_manifest(experiment / "experiment.json")
        example = root / "examples" / "demo"
        (example / "versions" / "v001").mkdir(parents=True)
        write_experiment_manifest(example / "experiment.json")
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )
        payload = store.load_experiment("demo").model_dump(mode="json")
        payload["title"] = "Updated Demo"
        payload["description"] = "Edited from settings"
        payload["models"] = {
            "generator_model": "local/new",
            "validator_model": "openai/new",
            "judge_model": "openai/new",
        }
        payload["run_defaults"] = {
            "repeat_count": 5,
            "llm_cache": "disabled",
            "case_order": "case-major",
        }
        artifact = ExperimentArtifact.model_validate(payload)

        path = store.save_experiment("demo", artifact)

        assert path == (experiment / "experiment.json").resolve()
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["title"] == "Updated Demo"
        assert saved["description"] == "Edited from settings"
        assert saved["models"]["generator_model"] == "local/new"
        assert saved["run_defaults"]["repeat_count"] == 5
        example_saved = json.loads(
            (example / "experiment.json").read_text(encoding="utf-8")
        )
        assert example_saved["title"] == "Demo"


def test_store_rejects_save_experiment_id_mismatch() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        (experiment / "versions" / "v001").mkdir(parents=True)
        write_experiment_manifest(experiment / "experiment.json")
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )
        artifact = store.load_experiment("demo").model_copy(update={"id": "other"})

        try:
            store.save_experiment("demo", artifact)
        except NotFoundError as exc:
            assert str(root) not in str(exc)
        else:
            raise AssertionError("Expected id mismatch to be rejected")


def test_store_rejects_save_missing_active_version() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        (experiment / "versions" / "v001").mkdir(parents=True)
        write_experiment_manifest(experiment / "experiment.json")
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )
        artifact = store.load_experiment("demo").model_copy(
            update={"active_version": "v999"}
        )

        try:
            store.save_experiment("demo", artifact)
        except NotFoundError as exc:
            assert str(root) not in str(exc)
        else:
            raise AssertionError("Expected missing active version to be rejected")


def main() -> int:
    tests = [
        test_store_does_not_list_examples_directly,
        test_store_ignores_old_runtime_experiment_directories,
        test_store_loads_cases_for_experiment,
        test_store_rejects_read_path_escape,
        test_store_rejects_write_path_escape,
        test_store_rejects_experiment_id_path_escape,
        test_store_rejects_version_path_escape_for_read,
        test_store_rejects_version_path_escape_for_write,
        test_store_writes_nested_run_artifact,
        test_store_loads_validators_sorted_by_filename,
        test_store_returns_empty_validators_when_directory_missing,
        test_store_writes_validation_artifact_and_rejects_path_escape,
        test_store_loads_validation_batch_and_results,
        test_store_load_validation_batch_rejects_missing_or_escaped_id,
        test_store_resolves_only_experiments_root,
        test_store_saves_experiment_manifest_under_experiments_root,
        test_store_rejects_save_experiment_id_mismatch,
        test_store_rejects_save_missing_active_version,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
