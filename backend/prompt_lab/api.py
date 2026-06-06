from __future__ import annotations

from fastapi import FastAPI

from prompt_lab.config import PromptLabConfig
from prompt_lab.storage import PromptLabStore


def create_app(config: PromptLabConfig | None = None) -> FastAPI:
    resolved_config = config or PromptLabConfig.from_env()
    store = PromptLabStore(
        experiments_root=resolved_config.experiments_root,
        examples_root=resolved_config.examples_root,
    )
    app = FastAPI(title="Prompt Lab")

    @app.get("/api/experiments")
    def list_experiments() -> list[dict[str, object]]:
        return [item.model_dump(mode="json") for item in store.list_experiments()]

    return app
