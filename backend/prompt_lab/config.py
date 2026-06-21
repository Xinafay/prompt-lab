from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PromptLabConfig:
    """Runtime paths for a local Prompt Lab backend."""

    project_root: Path
    experiments_root: Path
    examples_root: Path
    settings_path: Path

    @classmethod
    def from_env(cls, *, project_root: Path | None = None) -> "PromptLabConfig":
        root = (project_root or Path.cwd()).resolve()
        experiments_override = os.getenv("PROMPT_LAB_EXPERIMENTS_ROOT")
        examples_override = os.getenv("PROMPT_LAB_EXAMPLES_ROOT")
        return cls(
            project_root=root,
            experiments_root=Path(experiments_override).resolve() if experiments_override else root / "experiments",
            examples_root=Path(examples_override).resolve() if examples_override else root / "examples",
            settings_path=root / "config" / "settings.json",
        )
