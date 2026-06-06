from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from prompt_lab.config import PromptLabConfig


def test_default_config_uses_repo_local_paths() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        config = PromptLabConfig.from_env(project_root=root)

        assert config.project_root == root
        assert config.experiments_root == root / "experiments"
        assert config.examples_root == root / "examples"


def test_config_accepts_experiments_root_override() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiments = root / "custom-experiments"
        previous = os.environ.get("PROMPT_LAB_EXPERIMENTS_ROOT")
        os.environ["PROMPT_LAB_EXPERIMENTS_ROOT"] = str(experiments)
        try:
            config = PromptLabConfig.from_env(project_root=root)
        finally:
            if previous is None:
                os.environ.pop("PROMPT_LAB_EXPERIMENTS_ROOT", None)
            else:
                os.environ["PROMPT_LAB_EXPERIMENTS_ROOT"] = previous

        assert config.experiments_root == experiments


def main() -> int:
    tests = [
        test_default_config_uses_repo_local_paths,
        test_config_accepts_experiments_root_override,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
