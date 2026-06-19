from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from prompt_lab.settings import (
    PromptLabSettings,
    load_settings,
    save_settings,
)


def test_load_settings_returns_defaults_when_file_is_missing() -> None:
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "config" / "settings.json"

        settings = load_settings(path)

        assert settings == PromptLabSettings()
        assert not path.exists()


def test_save_settings_writes_formatted_json_and_loads_it_back() -> None:
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "config" / "settings.json"
        settings = PromptLabSettings(
            default_generator_model="local/generator",
            default_judge_model="openai/judge",
            default_repeat_count=5,
        )

        save_settings(path, settings)

        raw = path.read_text(encoding="utf-8")
        assert raw.endswith("\n")
        payload = json.loads(raw)
        assert payload == {
            "schema_version": "prompt_lab.settings/v1",
            "default_generator_model": "local/generator",
            "default_judge_model": "openai/judge",
            "default_repeat_count": 5,
        }
        assert load_settings(path) == settings


def main() -> int:
    tests = [
        test_load_settings_returns_defaults_when_file_is_missing,
        test_save_settings_writes_formatted_json_and_loads_it_back,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
