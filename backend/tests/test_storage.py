from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from pydantic import ValidationError

import prompt_lab.storage as storage_module
from prompt_lab.errors import NotFoundError
from prompt_lab.settings import PromptLabSettings
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
            '{"text":"hello"}',
            encoding="utf-8",
        )

        store = PromptLabStore(experiments_root=root / "experiments", examples_root=root / "examples")

        loaded = store.load_cases("demo")
        assert len(loaded) == 1
        assert loaded[0].id == "case-a"
        assert loaded[0].payload == {"text": "hello"}


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
        validators = experiment / "versions" / "v001" / "validators"
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

        loaded = store.load_validators("demo", "v001")

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

        assert store.load_validators("demo", "v001") == []


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


def test_store_creates_text_experiment_with_unique_slug() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        existing = root / "experiments" / "demo-title"
        (existing / "versions" / "v001").mkdir(parents=True)
        write_experiment_manifest(
            existing / "experiment.json",
            experiment_id="demo-title",
        )
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )
        settings = PromptLabSettings(
            schema_version="prompt_lab.settings/v1",
            default_generator_model="openai/generator",
            default_validator_model="openai/validator",
            default_judge_model="openai/judge",
            default_repeat_count=4,
        )

        created = store.create_experiment(
            title="Demo Title",
            output_type="text",
            model_entrypoint=None,
            settings=settings,
        )

        created_dir = root / "experiments" / "demo-title-2"
        assert created.id == "demo-title-2"
        assert created.title == "Demo Title"
        assert created.active_version == "v001"
        assert created.output.type == "text"
        assert created.models.generator_model == "openai/generator"
        assert created.models.validator_model == "openai/validator"
        assert created.models.judge_model == "openai/judge"
        assert created.run_defaults.repeat_count == 4
        assert (created_dir / "experiment.json").is_file()
        assert (created_dir / "versions" / "v001" / "prompt.md").read_text(
            encoding="utf-8"
        ) == ""
        assert not (created_dir / "versions" / "v001" / "model.py").exists()


def test_store_creates_pydantic_experiment_with_empty_model_file() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )
        settings = PromptLabSettings(
            schema_version="prompt_lab.settings/v1",
            default_generator_model="local/generator",
            default_validator_model="local/validator",
            default_judge_model="local/judge",
            default_repeat_count=1,
        )

        created = store.create_experiment(
            title="Structured Output",
            output_type="pydantic",
            model_entrypoint="model.Output",
            settings=settings,
        )

        version_dir = root / "experiments" / "structured-output" / "versions" / "v001"
        assert created.id == "structured-output"
        assert created.output.type == "pydantic"
        assert created.output.model_file == "model.py"
        assert created.output.model_entrypoint == "model.Output"
        assert (version_dir / "prompt.md").read_text(encoding="utf-8") == ""
        assert (version_dir / "model.py").read_text(encoding="utf-8") == ""


def test_store_create_experiment_slug_falls_back_for_symbol_title() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )
        settings = PromptLabSettings(
            schema_version="prompt_lab.settings/v1",
            default_generator_model="local/generator",
            default_validator_model="local/validator",
            default_judge_model="local/judge",
            default_repeat_count=1,
        )

        created = store.create_experiment(
            title="!!!",
            output_type="text",
            model_entrypoint=None,
            settings=settings,
        )

        assert created.id == "experiment"
        assert (root / "experiments" / "experiment" / "experiment.json").is_file()


def test_store_create_experiment_rejects_whitespace_title() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )
        settings = PromptLabSettings(
            schema_version="prompt_lab.settings/v1",
            default_generator_model="local/generator",
            default_validator_model="local/validator",
            default_judge_model="local/judge",
            default_repeat_count=1,
        )

        try:
            store.create_experiment(
                title="   ",
                output_type="text",
                model_entrypoint=None,
                settings=settings,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("Expected whitespace title to be rejected")

        assert not (root / "experiments").exists()


def test_store_create_experiment_rejects_invalid_output_type() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )
        settings = PromptLabSettings(
            schema_version="prompt_lab.settings/v1",
            default_generator_model="local/generator",
            default_validator_model="local/validator",
            default_judge_model="local/judge",
            default_repeat_count=1,
        )

        try:
            store.create_experiment(
                title="Demo",
                output_type="typo",  # type: ignore[reportArgumentType]
                model_entrypoint=None,
                settings=settings,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("Expected invalid output type to be rejected")

        assert not (root / "experiments").exists()


def test_store_create_experiment_rejects_pydantic_missing_model_entrypoint() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )
        settings = PromptLabSettings(
            schema_version="prompt_lab.settings/v1",
            default_generator_model="local/generator",
            default_validator_model="local/validator",
            default_judge_model="local/judge",
            default_repeat_count=1,
        )

        for bad_model_entrypoint in (None, "", "   "):
            try:
                store.create_experiment(
                    title="Structured Output",
                    output_type="pydantic",
                    model_entrypoint=bad_model_entrypoint,
                    settings=settings,
                )
            except ValueError:
                pass
            else:
                raise AssertionError(
                    "Expected pydantic missing/blank model entrypoint to be rejected"
                )

        assert not (root / "experiments").exists()


def test_store_clones_experiment_directory_and_rewrites_manifest() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "experiments" / "demo"
        version_dir = source / "versions" / "v001"
        validators_dir = version_dir / "validators"
        cases_dir = source / "cases"
        validators_dir.mkdir(parents=True)
        cases_dir.mkdir(parents=True)
        write_experiment_manifest(source / "experiment.json")
        (version_dir / "prompt.md").write_text("Say {{ value }}", encoding="utf-8")
        (validators_dir / "quality.json").write_text(
            '{"schema_version":"prompt_lab.validator/v1","validator_id":"quality","type":"llm_questionnaire","title":"Quality","checks":[{"check_id":"ok","title":"OK","question":"OK?"}]}',
            encoding="utf-8",
        )
        (cases_dir / "case-a.json").write_text('{"value":"alpha"}', encoding="utf-8")
        (version_dir / "runs" / "run-001").mkdir(parents=True)
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        cloned = store.clone_experiment(
            source_experiment_id="demo",
            title="Demo Clone",
        )

        clone_dir = root / "experiments" / "demo-clone"
        assert cloned.id == "demo-clone"
        assert cloned.title == "Demo Clone"
        assert (clone_dir / "cases" / "case-a.json").is_file()
        assert (clone_dir / "versions" / "v001" / "prompt.md").read_text(
            encoding="utf-8"
        ) == "Say {{ value }}"
        assert (clone_dir / "versions" / "v001" / "validators" / "quality.json").is_file()
        assert (clone_dir / "versions" / "v001" / "runs" / "run-001").is_dir()
        saved = json.loads((clone_dir / "experiment.json").read_text(encoding="utf-8"))
        assert saved["id"] == "demo-clone"
        assert saved["title"] == "Demo Clone"


def test_store_clone_uses_unique_slug_when_destination_exists() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "experiments" / "demo"
        collision = root / "experiments" / "demo-clone"
        (source / "versions" / "v001").mkdir(parents=True)
        (collision / "versions" / "v001").mkdir(parents=True)
        write_experiment_manifest(source / "experiment.json")
        write_experiment_manifest(
            collision / "experiment.json",
            experiment_id="demo-clone",
        )
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        cloned = store.clone_experiment(
            source_experiment_id="demo",
            title="Demo Clone",
        )

        clone_dir = root / "experiments" / "demo-clone-2"
        assert cloned.id == "demo-clone-2"
        assert clone_dir.is_dir()
        saved = json.loads((clone_dir / "experiment.json").read_text(encoding="utf-8"))
        assert saved["id"] == "demo-clone-2"
        assert saved["title"] == "Demo Clone"


def test_store_clone_rejects_whitespace_title_without_creating_fallback() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "experiments" / "demo"
        (source / "versions" / "v001").mkdir(parents=True)
        write_experiment_manifest(source / "experiment.json")
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        try:
            store.clone_experiment(
                source_experiment_id="demo",
                title="   ",
            )
        except ValueError:
            pass
        else:
            raise AssertionError("Expected whitespace clone title to be rejected")

        assert not (root / "experiments" / "experiment").exists()


def test_store_clone_removes_destination_when_source_manifest_is_invalid() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "experiments" / "demo"
        (source / "versions" / "v001").mkdir(parents=True)
        (source / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo"}',
            encoding="utf-8",
        )
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        try:
            store.clone_experiment(
                source_experiment_id="demo",
                title="Demo Clone",
            )
        except ValidationError:
            pass
        else:
            raise AssertionError("Expected invalid source manifest to be rejected")

        assert not (root / "experiments" / "demo-clone").exists()


def test_store_clone_rejects_source_symlink_before_copying() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "experiments" / "demo"
        version = source / "versions" / "v001"
        version.mkdir(parents=True)
        write_experiment_manifest(source / "experiment.json")
        secret = root / "secret"
        secret.write_text("hidden", encoding="utf-8")
        try:
            (version / "secret-link").symlink_to(secret)
        except (OSError, NotImplementedError):
            return
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        try:
            store.clone_experiment(
                source_experiment_id="demo",
                title="Demo Clone",
            )
        except NotFoundError:
            pass
        else:
            raise AssertionError("Expected source symlink to be rejected")

        assert not (root / "experiments" / "demo-clone").exists()


def test_store_clone_rejects_manifest_symlink_before_reading() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "experiments" / "demo"
        (source / "versions" / "v001").mkdir(parents=True)
        secret_manifest = root / "secret-experiment.json"
        write_experiment_manifest(secret_manifest)
        try:
            (source / "experiment.json").symlink_to(secret_manifest)
        except (OSError, NotImplementedError):
            return
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        secret_manifest.chmod(0)
        try:
            try:
                store.clone_experiment(
                    source_experiment_id="demo",
                    title="Demo Clone",
                )
            except NotFoundError:
                pass
            else:
                raise AssertionError("Expected manifest symlink to be rejected")

            assert not (root / "experiments" / "demo-clone").exists()
        finally:
            secret_manifest.chmod(0o600)


def test_store_clone_rejects_top_level_source_symlink() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        real_source = root / "experiments" / "real-demo"
        (real_source / "versions" / "v001").mkdir(parents=True)
        write_experiment_manifest(
            real_source / "experiment.json",
            experiment_id="real-demo",
        )
        try:
            (root / "experiments" / "demo").symlink_to(
                real_source,
                target_is_directory=True,
            )
        except (OSError, NotImplementedError):
            return
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        try:
            store.clone_experiment(
                source_experiment_id="demo",
                title="Demo Clone",
            )
        except NotFoundError:
            pass
        else:
            raise AssertionError("Expected top-level source symlink to be rejected")

        assert not (root / "experiments" / "demo-clone").exists()


def test_store_clone_rolls_back_destination_when_manifest_write_fails() -> None:
    class DeliberateWriteError(Exception):
        pass

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "experiments" / "demo"
        (source / "versions" / "v001").mkdir(parents=True)
        write_experiment_manifest(source / "experiment.json")
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )
        destination_manifest = (
            root / "experiments" / "demo-clone" / "experiment.json"
        )
        original_write_json = storage_module._write_json

        def failing_write_json(path: Path, value: dict[str, Any]) -> None:
            if path.resolve() == destination_manifest.resolve():
                raise DeliberateWriteError("deliberate clone manifest write failure")
            original_write_json(path, value)

        storage_module._write_json = failing_write_json
        try:
            try:
                store.clone_experiment(
                    source_experiment_id="demo",
                    title="Demo Clone",
                )
            except DeliberateWriteError:
                pass
            else:
                raise AssertionError("Expected clone manifest rewrite to fail")

            assert not (root / "experiments" / "demo-clone").exists()
        finally:
            storage_module._write_json = original_write_json


def test_store_delete_experiment_removes_directory() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        (experiment / "versions" / "v001").mkdir(parents=True)
        write_experiment_manifest(experiment / "experiment.json")
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        store.delete_experiment("demo")

        assert not experiment.exists()


def test_store_delete_experiment_rejects_top_level_symlink() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        real_experiment = root / "experiments" / "real-demo"
        (real_experiment / "versions" / "v001").mkdir(parents=True)
        write_experiment_manifest(
            real_experiment / "experiment.json",
            experiment_id="real-demo",
        )
        link = root / "experiments" / "demo"
        try:
            link.symlink_to(real_experiment, target_is_directory=True)
        except (OSError, NotImplementedError):
            return
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        try:
            store.delete_experiment("demo")
        except NotFoundError:
            pass
        else:
            raise AssertionError("Expected top-level experiment symlink to be rejected")

        assert real_experiment.is_dir()
        assert link.is_symlink()


def test_store_delete_experiment_rejects_path_escape() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        (experiment / "versions" / "v001").mkdir(parents=True)
        write_experiment_manifest(experiment / "experiment.json")
        outside = root / "secret"
        outside.mkdir()
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        try:
            store.delete_experiment("../secret")
        except NotFoundError as exc:
            assert str(root) not in str(exc)
        else:
            raise AssertionError("Expected escaped delete to be rejected")
        assert outside.is_dir()


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
        test_store_creates_text_experiment_with_unique_slug,
        test_store_creates_pydantic_experiment_with_empty_model_file,
        test_store_create_experiment_slug_falls_back_for_symbol_title,
        test_store_create_experiment_rejects_whitespace_title,
        test_store_create_experiment_rejects_invalid_output_type,
        test_store_create_experiment_rejects_pydantic_missing_model_entrypoint,
        test_store_clones_experiment_directory_and_rewrites_manifest,
        test_store_clone_uses_unique_slug_when_destination_exists,
        test_store_clone_rejects_whitespace_title_without_creating_fallback,
        test_store_clone_removes_destination_when_source_manifest_is_invalid,
        test_store_clone_rejects_source_symlink_before_copying,
        test_store_clone_rejects_manifest_symlink_before_reading,
        test_store_clone_rejects_top_level_source_symlink,
        test_store_clone_rolls_back_destination_when_manifest_write_fails,
        test_store_delete_experiment_removes_directory,
        test_store_delete_experiment_rejects_top_level_symlink,
        test_store_delete_experiment_rejects_path_escape,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
