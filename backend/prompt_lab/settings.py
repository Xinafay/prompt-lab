from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PromptLabSettings(BaseModel):
    """Application-level Prompt Lab settings stored in config/settings.json."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["prompt_lab.settings/v1"] = "prompt_lab.settings/v1"
    default_generator_model: str = Field(default="local/gpt-oss-120b", min_length=1)
    default_judge_model: str = Field(
        default="openai/example-large-model", min_length=1
    )
    default_repeat_count: int = Field(default=3, ge=1)


def load_settings(path: Path) -> PromptLabSettings:
    if not path.is_file():
        return PromptLabSettings()
    return PromptLabSettings.model_validate(json.loads(path.read_text(encoding="utf-8")))


def save_settings(path: Path, settings: PromptLabSettings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(settings.model_dump(mode="json"), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
