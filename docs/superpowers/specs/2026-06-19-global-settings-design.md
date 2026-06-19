# Global Settings Design

## Goal

Add application-level Prompt Lab settings stored in `config/settings.json`, editable from a dedicated **Global settings** UI tab. The first settings are the default generator model, default judge model, and default repeat count used when runtime experiments are created from committed examples.

## Storage Contract

Global settings are stored as formatted JSON at `config/settings.json`.

```json
{
  "schema_version": "prompt_lab.settings/v1",
  "default_generator_model": "local/llama",
  "default_judge_model": "openai/gpt-4.1-mini",
  "default_repeat_count": 3
}
```

The backend owns validation through a Pydantic model. Missing settings files return in-code defaults without creating the file. Saving from the UI writes the file and creates `config/` when needed.

## Backend

`PromptLabConfig` gains `settings_path`, defaulting to `project_root / "config" / "settings.json"`. A focused settings module provides:

- `PromptLabSettings`, a Pydantic contract with `extra="forbid"`.
- `load_settings(path)`, returning defaults when the file is absent.
- `save_settings(path, settings)`, writing stable formatted JSON.

FastAPI exposes:

- `GET /api/settings`
- `PUT /api/settings`

Both endpoints use the Pydantic settings model as the API contract.

## Experiment Seeding

When `seed_experiments_from_examples()` copies an example into the runtime `experiments/` workspace, it rewrites only the copied `experiment.json` fields that correspond to global defaults:

- `models.generator_model`
- `models.judge_model`
- `run_defaults.repeat_count`

Existing runtime experiments are not migrated or rewritten, because those values may already be intentional per-experiment choices.

## Frontend

The app adds a top-level **Global settings** tab separate from the per-experiment `Settings` tab. The view loads `GET /api/settings`, edits a local draft, and saves through `PUT /api/settings`.

The first form section is **Experiment defaults** with three controls:

- Default generator model text input.
- Default judge model text input.
- Default repeat count numeric input, minimum `1`.

The form mirrors existing experiment settings behavior: dirty detection, reset, save, validation errors, save success messages, and navigation protection for unsaved edits.

## Testing

Backend tests cover:

- Default `settings_path`.
- Loading defaults when `config/settings.json` is missing.
- Saving and reloading settings.
- API `GET /api/settings` and `PUT /api/settings`.
- Seeding examples with global defaults applied only to copied runtime experiments.

Frontend changes are verified with TypeScript/build checks and targeted tests where existing helpers make that practical.
