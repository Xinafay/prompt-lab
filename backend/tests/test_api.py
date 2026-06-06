from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from fastapi.testclient import TestClient

from prompt_lab import llm_client
from prompt_lab.api import create_app
from prompt_lab.config import PromptLabConfig


def test_api_lists_experiments() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        example = root / "examples" / "demo"
        (example / "versions" / "v001").mkdir(parents=True)
        (example / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app).get("/api/experiments")

        assert response.status_code == 200
        assert response.json()[0]["id"] == "demo"


def test_api_starts_run_job() -> None:
    class FakeGeneratedText:
        output = "ok"
        usage: dict[str, Any] = {}

    original_generate_text = llm_client.generate_text
    llm_client.generate_text = lambda model, prompt: FakeGeneratedText()  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            example = root / "examples" / "demo"
            version_dir = example / "versions" / "v001"
            (version_dir / "cases").mkdir(parents=True)
            (example / "experiment.json").write_text(
                '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":1,"llm_cache":"disabled","case_order":"case-major"}}',
                encoding="utf-8",
            )
            (version_dir / "prompt.md").write_text("Say {{ value }}", encoding="utf-8")
            (version_dir / "cases" / "a.json").write_text(
                '{"schema_version":"prompt_lab.case/v1","id":"a","title":"A","variables":{"value":"hello"}}',
                encoding="utf-8",
            )
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app).post(
                "/api/experiments/demo/versions/v001/runs"
            )

            assert response.status_code == 200
            body = response.json()
            assert body["kind"] == "run_version"
            assert body["status"] in {"running", "completed"}
            artifact_path = (
                version_dir
                / "runs"
                / body["job_id"]
                / "a"
                / "repeat-001.json"
            )
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            assert artifact["status"] == "ok"
            assert artifact["output_text"] == "ok"
            assert artifact["rendered_prompt"] == "Say hello"
            assert artifact["case_id"] == "a"
            assert artifact["repeat_index"] == 1
    finally:
        llm_client.generate_text = original_generate_text  # type: ignore[assignment]


def test_api_rejects_empty_cases_without_calling_llm() -> None:
    calls: list[tuple[str, str]] = []

    class FakeGeneratedText:
        output = "ok"
        usage: dict[str, Any] = {}

    def fake_generate_text(model: str, prompt: str) -> FakeGeneratedText:
        calls.append((model, prompt))
        return FakeGeneratedText()

    original_generate_text = llm_client.generate_text
    llm_client.generate_text = fake_generate_text  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            example = root / "examples" / "demo"
            version_dir = example / "versions" / "v001"
            (version_dir / "cases").mkdir(parents=True)
            (example / "experiment.json").write_text(
                '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":1,"llm_cache":"disabled","case_order":"case-major"}}',
                encoding="utf-8",
            )
            (version_dir / "prompt.md").write_text("Say {{ value }}", encoding="utf-8")
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app, raise_server_exceptions=False).post(
                "/api/experiments/demo/versions/v001/runs"
            )

            assert response.status_code == 400
            assert response.json()["detail"] == "Version has no cases"
            assert calls == []
    finally:
        llm_client.generate_text = original_generate_text  # type: ignore[assignment]


def test_api_rejects_unsafe_case_id_without_calling_llm() -> None:
    calls: list[tuple[str, str]] = []

    class FakeGeneratedText:
        output = "ok"
        usage: dict[str, Any] = {}

    def fake_generate_text(model: str, prompt: str) -> FakeGeneratedText:
        calls.append((model, prompt))
        return FakeGeneratedText()

    original_generate_text = llm_client.generate_text
    llm_client.generate_text = fake_generate_text  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            example = root / "examples" / "demo"
            version_dir = example / "versions" / "v001"
            (version_dir / "cases").mkdir(parents=True)
            (example / "experiment.json").write_text(
                '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":1,"llm_cache":"disabled","case_order":"case-major"}}',
                encoding="utf-8",
            )
            (version_dir / "prompt.md").write_text("Say {{ value }}", encoding="utf-8")
            (version_dir / "cases" / "a.json").write_text(
                '{"schema_version":"prompt_lab.case/v1","id":"../escape","title":"A","variables":{"value":"hello"}}',
                encoding="utf-8",
            )
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app, raise_server_exceptions=False).post(
                "/api/experiments/demo/versions/v001/runs"
            )

            assert response.status_code == 400
            assert response.json()["detail"] == "Unsafe case id"
            assert calls == []
    finally:
        llm_client.generate_text = original_generate_text  # type: ignore[assignment]


def main() -> int:
    tests = [
        test_api_lists_experiments,
        test_api_starts_run_job,
        test_api_rejects_empty_cases_without_calling_llm,
        test_api_rejects_unsafe_case_id_without_calling_llm,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
