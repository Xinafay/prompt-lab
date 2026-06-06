from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from prompt_lab.errors import NotFoundError
from prompt_lab.storage import PromptLabStore


def test_store_lists_example_experiments() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        example = root / "examples" / "demo"
        version = example / "versions" / "v001"
        version.mkdir(parents=True)
        (example / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )

        store = PromptLabStore(experiments_root=root / "experiments", examples_root=root / "examples")

        assert [item.id for item in store.list_experiments()] == ["demo"]


def test_store_loads_cases_for_version() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        cases = experiment / "versions" / "v001" / "cases"
        cases.mkdir(parents=True)
        (experiment / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )
        (cases / "case-a.json").write_text(
            '{"schema_version":"prompt_lab.case/v1","id":"case-a","title":"Case A","variables":{"text":"hello"}}',
            encoding="utf-8",
        )

        store = PromptLabStore(experiments_root=root / "experiments", examples_root=root / "examples")

        loaded = store.load_cases("demo", "v001")
        assert len(loaded) == 1
        assert loaded[0].id == "case-a"


def test_store_rejects_read_path_escape() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        version = experiment / "versions" / "v001"
        version.mkdir(parents=True)
        (experiment / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
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
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
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
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
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
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
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
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
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
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
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


def test_store_prefers_experiments_root_over_examples_root() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        example = root / "examples" / "demo"
        experiment = root / "experiments" / "demo"
        (example / "versions" / "v001").mkdir(parents=True)
        (experiment / "versions" / "v002").mkdir(parents=True)
        (example / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Example Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )
        (experiment / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Editable Demo","description":"","active_version":"v002","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )

        store = PromptLabStore(experiments_root=root / "experiments", examples_root=root / "examples")

        experiments = store.list_experiments()

        assert len(experiments) == 1
        assert experiments[0].id == "demo"
        assert experiments[0].title == "Editable Demo"
        assert store.experiment_dir("demo") == experiment.resolve()


def main() -> int:
    tests = [
        test_store_lists_example_experiments,
        test_store_loads_cases_for_version,
        test_store_rejects_read_path_escape,
        test_store_rejects_write_path_escape,
        test_store_rejects_experiment_id_path_escape,
        test_store_rejects_version_path_escape_for_read,
        test_store_rejects_version_path_escape_for_write,
        test_store_writes_nested_run_artifact,
        test_store_prefers_experiments_root_over_examples_root,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
