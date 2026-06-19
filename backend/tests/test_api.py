from __future__ import annotations

import json
from pathlib import Path
from threading import Event, Thread
from tempfile import TemporaryDirectory
from typing import Any

from fastapi.testclient import TestClient

from prompt_lab import llm_client
from prompt_lab.api import create_app
from prompt_lab.config import PromptLabConfig
from prompt_lab.settings import PromptLabSettings, save_settings


def demo_experiment_payload(
    *, experiment_id: str = "demo", active_version: str = "v001"
) -> dict[str, object]:
    return {
        "schema_version": "prompt_lab.experiment/v1",
        "id": experiment_id,
        "title": "Demo",
        "description": "",
        "active_version": active_version,
        "output": {"type": "text"},
        "template": {"engine": "jinjax", "path": "prompt.md"},
        "models": {
            "generator_model": "local/a",
            "judge_model": "openai/b",
        },
        "run_defaults": {
            "repeat_count": 1,
            "llm_cache": "disabled",
            "case_order": "case-major",
        },
    }


def file_node(value: object) -> dict[str, object]:
    return {"__carmilla_flat_file_node__": "file", "value": value}


def demo_case_payload(
    *,
    case_id: str = "a",
    title: str = "A",
    binding_name: str = "value",
    value: object = "hello",
) -> dict[str, object]:
    return {
        "schema_version": "prompt_lab.case/v2",
        "id": case_id,
        "title": title,
        "stores": {
            "case": {
                "kind": "flat_file_tree",
                "values": {binding_name: file_node(value)},
            }
        },
        "bindings": {
            binding_name: {
                "kind": "store_scope",
                "store": "case",
                "path": binding_name,
            }
        },
    }


def write_demo_experiment_manifest(root: Path) -> None:
    example = root / "examples" / "demo"
    (example / "versions" / "v001").mkdir(parents=True)
    (example / "experiment.json").write_text(
        json.dumps(demo_experiment_payload(), ensure_ascii=False),
        encoding="utf-8",
    )


def write_demo_pydantic_experiment(root: Path) -> None:
    example = root / "examples" / "demo"
    version_dir = example / "versions" / "v001"
    (example / "cases").mkdir(parents=True)
    version_dir.mkdir(parents=True)
    (example / "experiment.json").write_text(
        json.dumps(
            {
                **demo_experiment_payload(),
                "output": {
                    "type": "pydantic",
                    "model_file": "model.py",
                    "model_entrypoint": "model.DemoOutput",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (version_dir / "prompt.md").write_text(
        "Say {{ value }}\n\n<<MODEL>>", encoding="utf-8"
    )
    (version_dir / "model.py").write_text(
        "from pydantic import BaseModel\n\nclass DemoOutput(BaseModel):\n    answer: str\n",
        encoding="utf-8",
    )
    (example / "cases" / "a.json").write_text(
        json.dumps(demo_case_payload(), ensure_ascii=False),
        encoding="utf-8",
    )


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


def test_api_returns_global_settings() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        settings_path = root / "config" / "settings.json"
        save_settings(
            settings_path,
            PromptLabSettings(
                default_generator_model="local/configured-generator",
                default_judge_model="openai/configured-judge",
                default_repeat_count=6,
            ),
        )
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app).get("/api/settings")

        assert response.status_code == 200
        assert response.json() == {
            "schema_version": "prompt_lab.settings/v1",
            "default_generator_model": "local/configured-generator",
            "default_judge_model": "openai/configured-judge",
            "default_repeat_count": 6,
        }


def test_api_updates_global_settings() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        app = create_app(PromptLabConfig.from_env(project_root=root))
        payload = {
            "schema_version": "prompt_lab.settings/v1",
            "default_generator_model": "local/new-generator",
            "default_judge_model": "openai/new-judge",
            "default_repeat_count": 4,
        }

        response = TestClient(app).put("/api/settings", json=payload)

        assert response.status_code == 200
        assert response.json() == payload
        saved = json.loads(
            (root / "config" / "settings.json").read_text(encoding="utf-8")
        )
        assert saved == payload


def test_api_updates_experiment_manifest_under_experiments() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_demo_experiment_manifest(root)
        app = create_app(PromptLabConfig.from_env(project_root=root))
        payload = demo_experiment_payload()
        payload["title"] = "Updated"
        payload["description"] = "Saved from Settings"
        payload["models"] = {
            "generator_model": "local/updated",
            "judge_model": "openai/updated",
        }
        payload["run_defaults"] = {
            "repeat_count": 4,
            "llm_cache": "disabled",
            "case_order": "case-major",
        }

        response = TestClient(app).put("/api/experiments/demo", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body["title"] == "Updated"
        saved = json.loads(
            (root / "experiments" / "demo" / "experiment.json").read_text(
                encoding="utf-8"
            )
        )
        assert saved["description"] == "Saved from Settings"
        assert saved["models"]["generator_model"] == "local/updated"
        assert saved["run_defaults"]["repeat_count"] == 4
        example_saved = json.loads(
            (root / "examples" / "demo" / "experiment.json").read_text(
                encoding="utf-8"
            )
        )
        assert example_saved["title"] == "Demo"


def test_api_rejects_experiment_update_id_mismatch() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_demo_experiment_manifest(root)
        app = create_app(PromptLabConfig.from_env(project_root=root))
        payload = demo_experiment_payload(experiment_id="other")

        response = TestClient(app, raise_server_exceptions=False).put(
            "/api/experiments/demo",
            json=payload,
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Experiment id mismatch"


def test_api_rejects_experiment_update_missing_active_version() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_demo_experiment_manifest(root)
        app = create_app(PromptLabConfig.from_env(project_root=root))
        payload = demo_experiment_payload(active_version="v999")

        response = TestClient(app, raise_server_exceptions=False).put(
            "/api/experiments/demo",
            json=payload,
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Version not found"


def test_api_seeds_examples_into_experiments_on_startup() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        example = root / "examples" / "demo"
        version = example / "versions" / "v001"
        version.mkdir(parents=True)
        (example / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":1,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )
        (version / "prompt.md").write_text("Hello {{ name }}", encoding="utf-8")
        cases = example / "cases"
        cases.mkdir()
        (cases / "case-a.json").write_text(
            json.dumps(
                demo_case_payload(
                    case_id="case-a",
                    title="Case A",
                    binding_name="name",
                    value="Ada",
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        app = create_app(PromptLabConfig.from_env(project_root=root))
        response = TestClient(app).get("/api/experiments")

        assert response.status_code == 200
        assert [item["id"] for item in response.json()] == ["demo"]
        assert (root / "experiments" / "demo" / "experiment.json").is_file()
        assert (
            root / "experiments" / "demo" / "versions" / "v001" / "prompt.md"
        ).is_file()


def test_api_ignores_old_example_directories_when_seeding() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        for directory, title in (
            (root / "examples" / "demo", "Demo"),
            (root / "examples" / "demo_old", "Old Demo"),
        ):
            (directory / "versions" / "v001").mkdir(parents=True)
            payload = demo_experiment_payload()
            payload["title"] = title
            (directory / "experiment.json").write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
            (directory / "versions" / "v001" / "prompt.md").write_text(
                "Hello", encoding="utf-8"
            )

        app = create_app(PromptLabConfig.from_env(project_root=root))
        response = TestClient(app).get("/api/experiments")

        assert response.status_code == 200
        assert [item["title"] for item in response.json()] == ["Demo"]
        assert (root / "experiments" / "demo" / "experiment.json").is_file()
        assert not (root / "experiments" / "demo_old").exists()


def test_api_gets_version_overview() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        example = root / "examples" / "demo"
        version_dir = example / "versions" / "v001"
        (example / "cases").mkdir(parents=True)
        version_dir.mkdir(parents=True, exist_ok=True)
        (example / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"Demo experiment","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":1,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )
        (example / "rubric.md").write_text("Prefer concise answers.", encoding="utf-8")
        (version_dir / "prompt.md").write_text("Say {{ value }}", encoding="utf-8")
        (example / "cases" / "a.json").write_text(
            json.dumps(demo_case_payload(), ensure_ascii=False),
            encoding="utf-8",
        )
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app).get("/api/experiments/demo/versions/v001")

        assert response.status_code == 200
        body = response.json()
        assert body["experiment"]["id"] == "demo"
        assert body["version"] == "v001"
        assert body["prompt"] == "Say {{ value }}"
        assert body["rubric"] == "Prefer concise answers."
        assert body["cases"][0]["id"] == "a"


def test_api_lists_experiment_versions() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        example = root / "examples" / "demo"
        (example / "versions" / "v002").mkdir(parents=True)
        (example / "versions" / "v001").mkdir()
        (example / "experiment.json").write_text(
            json.dumps(
                demo_experiment_payload(active_version="v002"),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app).get("/api/experiments/demo/versions")

        assert response.status_code == 200
        assert response.json() == {
            "active_version": "v002",
            "versions": [
                {"version": "v001", "is_active": False},
                {"version": "v002", "is_active": True},
            ],
        }


def test_api_lists_latest_run_artifacts() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        example = root / "examples" / "demo"
        version_dir = example / "versions" / "v001"
        run_dir = version_dir / "runs" / "run_version-000001" / "a"
        run_dir.mkdir(parents=True)
        (example / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":1,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )
        (version_dir / "prompt.md").write_text("Say {{ value }}", encoding="utf-8")
        (example / "cases").mkdir()
        version_dir.mkdir(parents=True, exist_ok=True)
        (example / "cases" / "a.json").write_text(
            json.dumps(demo_case_payload(), ensure_ascii=False),
            encoding="utf-8",
        )
        (run_dir / "repeat-001.json").write_text(
            '{"schema_version":"prompt_lab.run/v1","run_id":"r1","run_batch_id":"run_version-000001","version":"v001","case_id":"a","repeat_index":1,"generator_model":"local/a","status":"ok","rendered_prompt":"Say hello","raw_output":"ok","output_type":"text","output_text":"ok","usage":{}}',
            encoding="utf-8",
        )
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app).get("/api/experiments/demo/versions/v001/runs")

        assert response.status_code == 200
        body = response.json()
        assert body["run_batch_id"] == "run_version-000001"
        assert body["runs"][0]["case_id"] == "a"
        assert body["runs"][0]["output_text"] == "ok"


def test_api_lists_empty_runs_when_version_has_no_batches() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        example = root / "examples" / "demo"
        version_dir = example / "versions" / "v001"
        version_dir.mkdir(parents=True)
        (example / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":1,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app).get("/api/experiments/demo/versions/v001/runs")

        assert response.status_code == 200
        assert response.json() == {"run_batch_id": None, "runs": []}


def test_api_missing_experiment_returns_404() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app, raise_server_exceptions=False).get(
            "/api/experiments/missing/versions/v001"
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Experiment not found"


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
            (example / "cases").mkdir(parents=True)
            version_dir.mkdir(parents=True, exist_ok=True)
            (example / "experiment.json").write_text(
                '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":1,"llm_cache":"disabled","case_order":"case-major"}}',
                encoding="utf-8",
            )
            (version_dir / "prompt.md").write_text("Say {{ value }}", encoding="utf-8")
            (example / "cases" / "a.json").write_text(
                json.dumps(demo_case_payload(), ensure_ascii=False),
                encoding="utf-8",
            )
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app).post(
                "/api/experiments/demo/versions/v001/runs"
            )

            assert response.status_code == 200
            body = response.json()
            assert body["kind"] == "run_version"
            assert body["status"] == "running"
            job_response = TestClient(app).get(f"/api/jobs/{body['job_id']}")
            assert job_response.status_code == 200
            assert job_response.json()["status"] == "completed"
            events_response = TestClient(app).get(
                f"/api/jobs/{body['job_id']}/events"
            )
            assert events_response.status_code == 200
            messages = [event["message"] for event in events_response.json()]
            assert "Running a repeat 1" in messages
            assert "Completed a repeat 1" in messages
            stream_response = TestClient(app).get(
                f"/api/jobs/{body['job_id']}/events/stream"
            )
            assert stream_response.status_code == 200
            assert stream_response.headers["content-type"].startswith(
                "text/event-stream"
            )
            assert "Running a repeat 1" in stream_response.text
            assert "Completed a repeat 1" in stream_response.text
            artifact_path = (
                root
                / "experiments"
                / "demo"
                / "versions"
                / "v001"
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


def test_api_reports_active_job_and_rejects_second_run() -> None:
    class FakeGeneratedText:
        output = "ok"
        usage: dict[str, Any] = {}

    started = Event()
    release = Event()

    def slow_generate_text(model: str, prompt: str) -> FakeGeneratedText:
        del model, prompt
        started.set()
        if not release.wait(timeout=5):
            raise TimeoutError("test timed out waiting to release fake LLM")
        return FakeGeneratedText()

    original_generate_text = llm_client.generate_text
    llm_client.generate_text = slow_generate_text  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            example = root / "examples" / "demo"
            version_dir = example / "versions" / "v001"
            (example / "cases").mkdir(parents=True)
            version_dir.mkdir(parents=True, exist_ok=True)
            (example / "experiment.json").write_text(
                '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":1,"llm_cache":"disabled","case_order":"case-major"}}',
                encoding="utf-8",
            )
            (version_dir / "prompt.md").write_text("Say {{ value }}", encoding="utf-8")
            (example / "cases" / "a.json").write_text(
                json.dumps(demo_case_payload(), ensure_ascii=False),
                encoding="utf-8",
            )
            app = create_app(PromptLabConfig.from_env(project_root=root))
            client = TestClient(app, raise_server_exceptions=False)
            responses: list[Any] = []

            def start_run() -> None:
                responses.append(
                    client.post("/api/experiments/demo/versions/v001/runs")
                )

            thread = Thread(target=start_run)
            thread.start()
            try:
                assert started.wait(timeout=5)

                active_response = client.get("/api/jobs/active")
                assert active_response.status_code == 200
                active_job = active_response.json()["job"]
                assert active_job["kind"] == "run_version"
                assert active_job["status"] == "running"

                duplicate_response = client.post(
                    "/api/experiments/demo/versions/v001/runs"
                )
                assert duplicate_response.status_code == 409
                assert active_job["job_id"] in duplicate_response.json()["detail"]

                cancel_response = client.post(
                    f"/api/jobs/{active_job['job_id']}/cancel"
                )
                assert cancel_response.status_code == 200
                assert cancel_response.json()["status"] == "cancelled"
                assert client.get("/api/jobs/active").json() == {"job": None}
            finally:
                release.set()
                thread.join(timeout=5)
            assert responses
    finally:
        release.set()
        llm_client.generate_text = original_generate_text  # type: ignore[assignment]


def test_api_starting_run_clears_existing_runtime_chain() -> None:
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
            (example / "cases").mkdir(parents=True)
            version_dir.mkdir(parents=True, exist_ok=True)
            (example / "experiment.json").write_text(
                '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":1,"llm_cache":"disabled","case_order":"case-major"}}',
                encoding="utf-8",
            )
            (version_dir / "prompt.md").write_text("Say {{ value }}", encoding="utf-8")
            (example / "cases" / "a.json").write_text(
                json.dumps(demo_case_payload(), ensure_ascii=False),
                encoding="utf-8",
            )
            app = create_app(PromptLabConfig.from_env(project_root=root))
            runtime_version_dir = root / "experiments" / "demo" / "versions" / "v001"
            for relative_path in [
                "runs/old-batch/a/repeat-001.json",
                "reviews/review-001/judgment.json",
                "comparisons/comparison-001/comparison.json",
            ]:
                path = runtime_version_dir / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}", encoding="utf-8")

            response = TestClient(app).post(
                "/api/experiments/demo/versions/v001/runs"
            )

            assert response.status_code == 200
            assert not (runtime_version_dir / "runs" / "old-batch").exists()
            assert not (runtime_version_dir / "reviews").exists()
            assert not (runtime_version_dir / "comparisons").exists()
            assert (
                runtime_version_dir
                / "runs"
                / response.json()["job_id"]
                / "a"
                / "repeat-001.json"
            ).is_file()
    finally:
        llm_client.generate_text = original_generate_text  # type: ignore[assignment]


def test_api_dry_run_text_version_avoids_live_llm() -> None:
    def fail_live_generate_text(model: str, prompt: str) -> object:
        raise AssertionError("dry_run must not call live text generator")

    original_generate_text = llm_client.generate_text
    llm_client.generate_text = fail_live_generate_text  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            example = root / "examples" / "demo"
            version_dir = example / "versions" / "v001"
            (example / "cases").mkdir(parents=True)
            version_dir.mkdir(parents=True, exist_ok=True)
            (example / "experiment.json").write_text(
                '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":1,"llm_cache":"disabled","case_order":"case-major"}}',
                encoding="utf-8",
            )
            (version_dir / "prompt.md").write_text("Say {{ value }}", encoding="utf-8")
            (example / "cases" / "a.json").write_text(
                json.dumps(demo_case_payload(), ensure_ascii=False),
                encoding="utf-8",
            )
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app).post(
                "/api/experiments/demo/versions/v001/runs",
                json={"dry_run": True},
            )

            assert response.status_code == 200
            body = response.json()
            artifact_path = (
                root
                / "experiments"
                / "demo"
                / "versions"
                / "v001"
                / "runs"
                / body["job_id"]
                / "a"
                / "repeat-001.json"
            )
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            assert (
                root
                / "experiments"
                / "demo"
                / "versions"
                / "v001"
                / "runs"
                / body["job_id"]
            ).is_dir()
            assert not (
                root
                / "examples"
                / "demo"
                / "versions"
                / "v001"
                / "runs"
            ).exists()
            assert artifact["status"] == "ok"
            assert artifact["rendered_prompt"] == "Say hello"
            assert artifact["output_text"] == "Dry run response for case a repeat 1."
            assert artifact["usage"] == {"dry_run": True}
    finally:
        llm_client.generate_text = original_generate_text  # type: ignore[assignment]


def test_api_runs_pydantic_version() -> None:
    class FakeGeneratedStructured:
        def __init__(self, output: Any) -> None:
            self.output = output
            self.usage: dict[str, Any] = {}

    def fake_generate_structured(
        model: str,
        prompt: str,
        response_model: Any,
        validation_context: dict[str, Any] | None,
    ) -> FakeGeneratedStructured:
        output = response_model.model_validate({"answer": "ok"})
        return FakeGeneratedStructured(output)

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fake_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_demo_pydantic_experiment(root)
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app, raise_server_exceptions=False).post(
                "/api/experiments/demo/versions/v001/runs"
            )

            assert response.status_code == 200
            body = response.json()
            artifact_paths = sorted(
                (
                    root
                    / "experiments"
                    / "demo"
                    / "versions"
                    / "v001"
                    / "runs"
                    / body["job_id"]
                ).glob("*/*.json")
            )
            assert artifact_paths
            artifacts = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in artifact_paths
            ]
            assert any(artifact.get("output_json") for artifact in artifacts)
    finally:
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


def test_api_dry_run_pydantic_version_avoids_live_llm() -> None:
    def fail_live_generate_structured(
        model: str,
        prompt: str,
        response_model: Any,
        validation_context: dict[str, Any] | None,
    ) -> object:
        raise AssertionError("dry_run must not call live structured generator")

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fail_live_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_demo_pydantic_experiment(root)
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app, raise_server_exceptions=False).post(
                "/api/experiments/demo/versions/v001/runs",
                json={"dry_run": True},
            )

            assert response.status_code == 200
            body = response.json()
            artifact_paths = sorted(
                (
                    root
                    / "experiments"
                    / "demo"
                    / "versions"
                    / "v001"
                    / "runs"
                    / body["job_id"]
                ).glob("*/*.json")
            )
            assert artifact_paths
            artifacts = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in artifact_paths
            ]
            assert all(artifact["status"] == "ok" for artifact in artifacts)
            assert all(artifact["usage"] == {"dry_run": True} for artifact in artifacts)
            assert any(artifact.get("output_json") for artifact in artifacts)
    finally:
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


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
            (example / "cases").mkdir(parents=True)
            version_dir.mkdir(parents=True, exist_ok=True)
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
            (example / "cases").mkdir(parents=True)
            version_dir.mkdir(parents=True, exist_ok=True)
            (example / "experiment.json").write_text(
                '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":1,"llm_cache":"disabled","case_order":"case-major"}}',
                encoding="utf-8",
            )
            (version_dir / "prompt.md").write_text("Say {{ value }}", encoding="utf-8")
            (example / "cases" / "a.json").write_text(
                json.dumps(
                    demo_case_payload(case_id="../escape"),
                    ensure_ascii=False,
                ),
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
        test_api_returns_global_settings,
        test_api_updates_global_settings,
        test_api_updates_experiment_manifest_under_experiments,
        test_api_rejects_experiment_update_id_mismatch,
        test_api_rejects_experiment_update_missing_active_version,
        test_api_seeds_examples_into_experiments_on_startup,
        test_api_ignores_old_example_directories_when_seeding,
        test_api_gets_version_overview,
        test_api_lists_experiment_versions,
        test_api_lists_latest_run_artifacts,
        test_api_lists_empty_runs_when_version_has_no_batches,
        test_api_missing_experiment_returns_404,
        test_api_starts_run_job,
        test_api_reports_active_job_and_rejects_second_run,
        test_api_starting_run_clears_existing_runtime_chain,
        test_api_dry_run_text_version_avoids_live_llm,
        test_api_runs_pydantic_version,
        test_api_dry_run_pydantic_version_avoids_live_llm,
        test_api_rejects_empty_cases_without_calling_llm,
        test_api_rejects_unsafe_case_id_without_calling_llm,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
