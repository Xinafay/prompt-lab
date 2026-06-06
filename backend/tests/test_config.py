from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from prompt_lab.config import PromptLabConfig


def test_default_config_uses_repo_local_paths() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        config = PromptLabConfig.from_env(project_root=root)
        resolved_root = root.resolve()

        assert config.project_root == resolved_root
        assert config.experiments_root == resolved_root / "experiments"
        assert config.examples_root == resolved_root / "examples"


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

        assert config.experiments_root == experiments.resolve()


def test_config_accepts_examples_root_override() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        examples = root / "custom-examples"
        previous = os.environ.get("PROMPT_LAB_EXAMPLES_ROOT")
        os.environ["PROMPT_LAB_EXAMPLES_ROOT"] = str(examples)
        try:
            config = PromptLabConfig.from_env(project_root=root)
        finally:
            if previous is None:
                os.environ.pop("PROMPT_LAB_EXAMPLES_ROOT", None)
            else:
                os.environ["PROMPT_LAB_EXAMPLES_ROOT"] = previous

        assert config.examples_root == examples.resolve()


def test_config_resolves_relative_paths_against_current_working_directory() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        previous_cwd = Path.cwd()
        previous_experiments = os.environ.get("PROMPT_LAB_EXPERIMENTS_ROOT")
        previous_examples = os.environ.get("PROMPT_LAB_EXAMPLES_ROOT")
        os.environ["PROMPT_LAB_EXPERIMENTS_ROOT"] = "relative-experiments"
        os.environ["PROMPT_LAB_EXAMPLES_ROOT"] = "relative-examples"
        try:
            os.chdir(root)
            config = PromptLabConfig.from_env(project_root=Path("."))
        finally:
            os.chdir(previous_cwd)
            if previous_experiments is None:
                os.environ.pop("PROMPT_LAB_EXPERIMENTS_ROOT", None)
            else:
                os.environ["PROMPT_LAB_EXPERIMENTS_ROOT"] = previous_experiments
            if previous_examples is None:
                os.environ.pop("PROMPT_LAB_EXAMPLES_ROOT", None)
            else:
                os.environ["PROMPT_LAB_EXAMPLES_ROOT"] = previous_examples

        assert config.project_root == root.resolve()
        assert config.experiments_root == (root / "relative-experiments").resolve()
        assert config.examples_root == (root / "relative-examples").resolve()


def main() -> int:
    tests = [
        test_default_config_uses_repo_local_paths,
        test_config_accepts_experiments_root_override,
        test_config_accepts_examples_root_override,
        test_config_resolves_relative_paths_against_current_working_directory,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
