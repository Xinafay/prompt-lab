from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

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


def main() -> int:
    tests = [test_api_lists_experiments]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
