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
from prompt_lab.models.validators import LlmQuestionnaireResponse
from prompt_lab.settings import PromptLabSettings, save_settings
import prompt_lab.api as api_module
from test_judge import valid_case_payload, valid_run_payload, write_json


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
            "validator_model": "openai/b",
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


def write_quality_validator(root: Path, *, validator_id: str = "quality") -> None:
    validator_dir = root / "examples" / "demo" / "validators"
    validator_dir.mkdir(exist_ok=True)
    (validator_dir / "quality.json").write_text(
        json.dumps(
            {
                "schema_version": "prompt_lab.validator/v1",
                "validator_id": validator_id,
                "type": "llm_questionnaire",
                "title": "Quality",
                "checks": [
                    {
                        "check_id": "has-answer",
                        "title": "Has answer",
                        "question": "Does the output contain an answer?",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def write_runtime_preview_experiment(root: Path, *, repeat_count: int = 2) -> Path:
    experiment_dir = root / "experiments" / "demo"
    version_dir = experiment_dir / "versions" / "v001"
    cases_dir = experiment_dir / "cases"
    cases_dir.mkdir(parents=True)
    version_dir.mkdir(parents=True)
    write_json(
        experiment_dir / "experiment.json",
        {
            "schema_version": "prompt_lab.experiment/v1",
            "id": "demo",
            "title": "Demo",
            "description": "",
            "active_version": "v001",
            "output": {"type": "text"},
            "template": {"engine": "jinjax", "path": "prompt.md"},
            "models": {
                "generator_model": "local/a",
                "validator_model": "openai/validator",
                "judge_model": "openai/judge",
            },
            "run_defaults": {
                "repeat_count": repeat_count,
                "llm_cache": "disabled",
                "case_order": "case-major",
            },
        },
    )
    (version_dir / "prompt.md").write_text("Say {{ value }}", encoding="utf-8")
    for case_id, value in [("case-a", "alpha"), ("case-b", "bravo")]:
        write_json(
            cases_dir / f"{case_id}.json",
            valid_case_payload(
                id=case_id,
                title=f"Case {case_id}",
                stores={
                    "case": {
                        "kind": "flat_file_tree",
                        "values": {
                            "value": {
                                "__carmilla_flat_file_node__": "file",
                                "value": value,
                            }
                        },
                    }
                },
            ),
        )
    return version_dir


def write_preview_run_batch(version_dir: Path) -> None:
    batch_id = "run-preview-001"
    for case_id in ["case-a", "case-b"]:
        for repeat_index in [1, 2]:
            write_json(
                version_dir
                / "runs"
                / batch_id
                / case_id
                / f"repeat-{repeat_index:03d}.json",
                valid_run_payload(
                    run_id=f"{batch_id}-{case_id}-repeat-{repeat_index:03d}",
                    run_batch_id=batch_id,
                    version="v001",
                    case_id=case_id,
                    repeat_index=repeat_index,
                    rendered_prompt=f"Rendered {case_id} repeat {repeat_index}",
                    output_type="text",
                    output_text=f"Output {case_id} repeat {repeat_index}",
                    output_json=None,
                    raw_output=f"Output {case_id} repeat {repeat_index}",
                ),
            )


def write_execution_error_run_batch(version_dir: Path) -> None:
    batch_id = "run-execution-error-001"
    for case_id in ["case-a", "case-b"]:
        write_json(
            version_dir / "runs" / batch_id / case_id / "repeat-001.json",
            valid_run_payload(
                run_id=f"{batch_id}-{case_id}-repeat-001",
                run_batch_id=batch_id,
                version="v001",
                case_id=case_id,
                repeat_index=1,
                rendered_prompt=f"Rendered {case_id} repeat 1",
                status="execution_error",
                output_type="text",
                output_text=None,
                output_json=None,
                raw_output=None,
                execution_error="transport failed",
            ),
        )


def write_preview_validators(root: Path) -> None:
    validators_dir = root / "experiments" / "demo" / "validators"
    validators_dir.mkdir(parents=True)
    for validator_id in ["quality", "style"]:
        write_json(
            validators_dir / f"{validator_id}.json",
            {
                "schema_version": "prompt_lab.validator/v1",
                "validator_id": validator_id,
                "type": "llm_questionnaire",
                "title": validator_id.title(),
                "description": "",
                "enabled": True,
                "input_scope": "output_only",
                "checks": [
                    {
                        "check_id": "complete",
                        "title": "Complete",
                        "question": "Is the output complete?",
                        "description": "",
                    }
                ],
            },
        )
    write_json(
        validators_dir / "length.json",
        {
            "schema_version": "prompt_lab.validator/v1",
            "validator_id": "length",
            "type": "automatic",
            "title": "Length",
            "description": "",
            "enabled": True,
            "input_scope": "output_only",
            "checks": [
                {
                    "check_id": "short",
                    "title": "Short",
                    "description": "",
                    "rule": {
                        "kind": "word_count",
                        "source": "output_text",
                        "comparison": {"op": "gte", "value": 1},
                    },
                }
            ],
        },
    )


def test_api_lists_experiments() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        example = root / "examples" / "demo"
        (example / "versions" / "v001").mkdir(parents=True)
        (example / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","validator_model":"openai/b","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
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
                default_validator_model="openai/configured-validator",
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
            "default_validator_model": "openai/configured-validator",
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
            "default_validator_model": "openai/new-validator",
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
            "validator_model": "openai/updated",
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
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","validator_model":"openai/b","judge_model":"openai/b"},"run_defaults":{"repeat_count":1,"llm_cache":"disabled","case_order":"case-major"}}',
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
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"Demo experiment","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","validator_model":"openai/b","judge_model":"openai/b"},"run_defaults":{"repeat_count":1,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )
        (example / "rubric.md").write_text("Prefer concise answers.", encoding="utf-8")
        write_quality_validator(root)
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
        assert body["validators"][0]["validator_id"] == "quality"
        assert body["validators"][0]["checks"][0]["check_id"] == "has-answer"


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
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","validator_model":"openai/b","judge_model":"openai/b"},"run_defaults":{"repeat_count":1,"llm_cache":"disabled","case_order":"case-major"}}',
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
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","validator_model":"openai/b","judge_model":"openai/b"},"run_defaults":{"repeat_count":1,"llm_cache":"disabled","case_order":"case-major"}}',
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
                '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","validator_model":"openai/b","judge_model":"openai/b"},"run_defaults":{"repeat_count":1,"llm_cache":"disabled","case_order":"case-major"}}',
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
                '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","validator_model":"openai/b","judge_model":"openai/b"},"run_defaults":{"repeat_count":1,"llm_cache":"disabled","case_order":"case-major"}}',
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
                '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","validator_model":"openai/b","judge_model":"openai/b"},"run_defaults":{"repeat_count":1,"llm_cache":"disabled","case_order":"case-major"}}',
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
                "validations/validation-001/batch.json",
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
            assert not (runtime_version_dir / "validations").exists()
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
                '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","validator_model":"openai/b","judge_model":"openai/b"},"run_defaults":{"repeat_count":1,"llm_cache":"disabled","case_order":"case-major"}}',
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


def test_api_previews_run_prompts_and_preserves_model_marker() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_demo_pydantic_experiment(root)
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app).post(
            "/api/experiments/demo/versions/v001/runs/preview-prompts"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["workflow_kind"] == "run_version"
        assert len(body["warnings"]) == 1
        assert "identical across repeats" in body["warnings"][0]
        assert len(body["prompts"]) == 1
        prompt = body["prompts"][0]
        assert prompt["kind"] == "run"
        assert prompt["title"] == "Run case a"
        assert prompt["case_id"] == "a"
        assert prompt["repeat_index"] is None
        assert prompt["validator_id"] is None
        assert prompt["prompt"] == "Say hello\n\n<<MODEL>>"
        assert prompt["character_count"] == len("Say hello\n\n<<MODEL>>")
        assert prompt["word_count"] == 3


def test_api_previews_validation_prompts_with_first_repeat_when_too_large() -> None:
    original_limit = getattr(api_module, "PROMPT_PREVIEW_MAX_PROMPTS", 100)
    api_module.PROMPT_PREVIEW_MAX_PROMPTS = 3
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            version_dir = write_runtime_preview_experiment(root, repeat_count=2)
            write_preview_run_batch(version_dir)
            write_preview_validators(root)
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app).post(
                "/api/experiments/demo/versions/v001/validations/preview-prompts"
            )

            assert response.status_code == 200
            body = response.json()
            assert body["workflow_kind"] == "validation"
            assert len(body["warnings"]) == 1
            assert "first repeat" in body["warnings"][0]
            prompts = body["prompts"]
            assert len(prompts) == 4
            assert {prompt["case_id"] for prompt in prompts} == {"case-a", "case-b"}
            assert {prompt["validator_id"] for prompt in prompts} == {
                "quality",
                "style",
            }
            assert {prompt["repeat_index"] for prompt in prompts} == {1}
            assert {prompt["kind"] for prompt in prompts} == {"validation"}
            assert all(prompt["model"] == "openai/validator" for prompt in prompts)
            assert all("<<MODEL>>" in prompt["prompt"] for prompt in prompts)
            assert "length" not in {prompt["validator_id"] for prompt in prompts}
    finally:
        api_module.PROMPT_PREVIEW_MAX_PROMPTS = original_limit


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


def test_api_dry_run_validation_for_pydantic_experiment() -> None:
    def fail_live_generate_structured(
        model: str,
        prompt: str,
        response_model: Any,
        validation_context: dict[str, Any] | None,
    ) -> object:
        raise AssertionError("dry_run validation must not call live structured generator")

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fail_live_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_demo_pydantic_experiment(root)
            write_quality_validator(root)
            app = create_app(PromptLabConfig.from_env(project_root=root))
            client = TestClient(app, raise_server_exceptions=False)

            run_response = client.post(
                "/api/experiments/demo/versions/v001/runs",
                json={"dry_run": True},
            )
            response = client.post(
                "/api/experiments/demo/versions/v001/validations",
                json={"dry_run": True},
            )

            assert run_response.status_code == 200
            assert response.status_code == 200
            body = response.json()
            assert (
                body["validation_batch"]["run_batch_id"]
                == run_response.json()["job_id"]
            )
            assert body["results"][0]["validator_id"] == "quality"
            assert isinstance(body["results"][0]["check_results"][0]["check_id"], str)
            assert body["results"][0]["check_results"][0]["check_id"]
            check_result = body["results"][0]["check_results"][0]
            assert check_result["grade"] == 5
            assert "verdict" not in check_result
    finally:
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


def test_api_validation_skips_llm_validator_for_execution_error_runs() -> None:
    def fail_live_generate_structured(
        model: str,
        prompt: str,
        response_model: Any,
        validation_context: dict[str, Any] | None,
    ) -> object:
        raise AssertionError("execution_error runs must not call validator LLM")

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fail_live_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            version_dir = write_runtime_preview_experiment(root, repeat_count=1)
            write_execution_error_run_batch(version_dir)
            write_preview_validators(root)
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app, raise_server_exceptions=False).post(
                "/api/experiments/demo/versions/v001/validations",
                json={"dry_run": False},
            )

            assert response.status_code == 200
            body = response.json()
            assert {result["status"] for result in body["results"]} == {"skipped"}
            assert all(
                result["included_in_judge"] is False for result in body["results"]
            )
            assert all(result["check_results"] == [] for result in body["results"])
            assert all(
                "transport failed" in result["execution_error"]
                for result in body["results"]
            )
    finally:
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


def test_api_rejects_unsafe_validator_id_before_writing_artifacts() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_demo_pydantic_experiment(root)
        write_quality_validator(root, validator_id="../bad")
        app = create_app(PromptLabConfig.from_env(project_root=root))
        client = TestClient(app, raise_server_exceptions=False)

        run_response = client.post(
            "/api/experiments/demo/versions/v001/runs",
            json={"dry_run": True},
        )
        response = client.post(
            "/api/experiments/demo/versions/v001/validations",
            json={"dry_run": True},
        )

        assert run_response.status_code == 200
        assert response.status_code == 400
        assert "Unsafe validator id" in response.json()["detail"]
        runtime_version_dir = root / "experiments" / "demo" / "versions" / "v001"
        assert not (runtime_version_dir / "bad.json").exists()
        assert not (runtime_version_dir / "validations").exists()


def test_api_validation_inclusion_rejects_unknown_ids() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_demo_pydantic_experiment(root)
        write_quality_validator(root)
        app = create_app(PromptLabConfig.from_env(project_root=root))
        client = TestClient(app, raise_server_exceptions=False)

        run_response = client.post(
            "/api/experiments/demo/versions/v001/runs",
            json={"dry_run": True},
        )
        validation_response = client.post(
            "/api/experiments/demo/versions/v001/validations",
            json={"dry_run": True},
        )
        body = validation_response.json()
        validation_batch_id = body["validation_batch"]["validation_batch_id"]
        result_id = body["results"][0]["validation_result_id"]

        unknown_result_response = client.put(
            (
                "/api/experiments/demo/versions/v001/validations/"
                f"{validation_batch_id}/inclusion"
            ),
            json={
                "results": [
                    {
                        "validation_result_id": "missing-result",
                        "included_in_judge": False,
                        "check_results": [],
                    }
                ]
            },
        )
        unknown_check_response = client.put(
            (
                "/api/experiments/demo/versions/v001/validations/"
                f"{validation_batch_id}/inclusion"
            ),
            json={
                "results": [
                    {
                        "validation_result_id": result_id,
                        "included_in_judge": True,
                        "check_results": [
                            {
                                "check_id": "missing-check",
                                "included_in_judge": False,
                            }
                        ],
                    }
                ]
            },
        )

        assert run_response.status_code == 200
        assert validation_response.status_code == 200
        assert unknown_result_response.status_code == 400
        assert "unknown validation_result_id: missing-result" in (
            unknown_result_response.json()["detail"]
        )
        assert unknown_check_response.status_code == 400
        assert "unknown check_id: missing-check" in (
            unknown_check_response.json()["detail"]
        )


def test_api_latest_validation_ignores_non_completed_batches() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_demo_pydantic_experiment(root)
        app = create_app(PromptLabConfig.from_env(project_root=root))
        validations_dir = (
            root / "experiments" / "demo" / "versions" / "v001" / "validations"
        )
        for batch_id, status in [
            ("validation-001", "completed"),
            ("validation-999", "running"),
        ]:
            batch_dir = validations_dir / batch_id
            batch_dir.mkdir(parents=True)
            (batch_dir / "batch.json").write_text(
                json.dumps(
                    {
                        "schema_version": "prompt_lab.validation_batch/v1",
                        "validation_batch_id": batch_id,
                        "run_batch_id": "run-001",
                        "version": "v001",
                        "status": status,
                        "started_at": "2026-06-19T10:00:00Z",
                        "finished_at": (
                            "2026-06-19T10:01:00Z"
                            if status == "completed"
                            else None
                        ),
                        "total_results": 0,
                        "completed_results": 0,
                        "validator_model": "openai/b",
                        "validator_ids": [],
                    }
                ),
                encoding="utf-8",
            )

        response = TestClient(app, raise_server_exceptions=False).get(
            "/api/experiments/demo/versions/v001/validations/latest"
        )

        assert response.status_code == 200
        assert response.json()["validation_batch"]["validation_batch_id"] == (
            "validation-001"
        )


def test_api_failed_validation_batch_is_terminal_and_not_latest() -> None:
    class FakeGeneratedStructured:
        usage: dict[str, Any] = {"fake": True}

        def __init__(self) -> None:
            self.output = LlmQuestionnaireResponse.model_validate(
                {
                    "check_results": [
                        {
                            "check_id": "wrong-check",
                            "grade": 5,
                            "comment": "bad id",
                        }
                    ]
                }
            )

    def fake_generate_structured(
        model: str,
        prompt: str,
        response_model: Any,
        validation_context: dict[str, Any] | None,
    ) -> FakeGeneratedStructured:
        return FakeGeneratedStructured()

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fake_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_demo_pydantic_experiment(root)
            write_quality_validator(root)
            app = create_app(PromptLabConfig.from_env(project_root=root))
            client = TestClient(app, raise_server_exceptions=False)

            run_response = client.post(
                "/api/experiments/demo/versions/v001/runs",
                json={"dry_run": True},
            )
            validation_response = client.post(
                "/api/experiments/demo/versions/v001/validations"
            )
            latest_response = client.get(
                "/api/experiments/demo/versions/v001/validations/latest"
            )
            batch_paths = sorted(
                (
                    root
                    / "experiments"
                    / "demo"
                    / "versions"
                    / "v001"
                    / "validations"
                ).glob("*/batch.json")
            )

            assert run_response.status_code == 200
            assert validation_response.status_code == 400
            assert "unknown: wrong-check" in validation_response.json()["detail"]
            assert latest_response.status_code == 404
            assert len(batch_paths) == 1
            batch = json.loads(batch_paths[0].read_text(encoding="utf-8"))
            assert batch["status"] == "failed"
            assert batch["finished_at"] is not None
            assert batch["completed_results"] == 0
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
                '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","validator_model":"openai/b","judge_model":"openai/b"},"run_defaults":{"repeat_count":1,"llm_cache":"disabled","case_order":"case-major"}}',
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
                '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","validator_model":"openai/b","judge_model":"openai/b"},"run_defaults":{"repeat_count":1,"llm_cache":"disabled","case_order":"case-major"}}',
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
        test_api_previews_run_prompts_and_preserves_model_marker,
        test_api_previews_validation_prompts_with_first_repeat_when_too_large,
        test_api_dry_run_pydantic_version_avoids_live_llm,
        test_api_dry_run_validation_for_pydantic_experiment,
        test_api_validation_skips_llm_validator_for_execution_error_runs,
        test_api_rejects_unsafe_validator_id_before_writing_artifacts,
        test_api_validation_inclusion_rejects_unknown_ids,
        test_api_latest_validation_ignores_non_completed_batches,
        test_api_failed_validation_batch_is_terminal_and_not_latest,
        test_api_rejects_empty_cases_without_calling_llm,
        test_api_rejects_unsafe_case_id_without_calling_llm,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
