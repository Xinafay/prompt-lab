from __future__ import annotations

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


def main() -> int:
    tests = [
        test_store_lists_example_experiments,
        test_store_loads_cases_for_version,
        test_store_rejects_read_path_escape,
        test_store_rejects_write_path_escape,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
