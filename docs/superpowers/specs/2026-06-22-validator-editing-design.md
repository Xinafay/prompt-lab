# Validator Editing Design

## Summary

Add comprehensive validator editing to the `Validators` tab. Users can add,
edit, duplicate, delete, reset, overwrite, and save validator definitions as the
next version. Validators become version source files, aligned with `prompt.md`
and `model.py`, while existing experiment-level `validators/` directories remain
supported as a compatibility fallback.

## Goals

- Let users edit both supported validator types:
  - `llm_questionnaire`
  - `automatic`
- Support adding and deleting validators and checks.
- Keep validator edits consistent with the existing manual prompt/model editing
  workflow.
- Preserve historical validation results by keeping validation-batch validator
  snapshots unchanged.
- Prevent stale generated artifacts from being treated as current after
  validator changes.
- Keep the UI structured enough for normal editing, with JSON as an advanced
  escape hatch rather than the primary interface.

## Non-Goals

- Do not implement human validator execution.
- Do not let the proposal LLM edit validator definitions in this change.
- Do not migrate every existing runtime experiment eagerly.
- Do not edit committed `examples/` from the running app.
- Do not introduce new automatic validator rule kinds.

## Storage Model

Validator definitions become part of version source:

```text
experiments/<experiment-id>/
  validators/                  # legacy fallback only
  versions/
    v001/
      prompt.md
      model.py
      validators/
        <validator-id>.json
```

Read behavior:

- Prefer `versions/<version>/validators/*.json` when the version-level
  `validators/` directory exists. An existing but empty version-level directory
  means the version has no validators.
- Fall back to top-level `validators/*.json` only when the version-level
  `validators/` directory does not exist.
- `VersionOverview.validators` returns the validators effective for that version.

Write behavior:

- New writes always target `versions/<version>/validators/`.
- `create_next` copies the source version, removes runtime artifacts, writes the
  submitted validators under the new version, and returns the new version id.
  If the source version used top-level fallback validators, the submitted
  effective validators are materialized into the new version-level directory.
- `overwrite_current` writes validators under the current version and removes
  generated artifacts invalidated by validator changes.
- Top-level `validators/` remains untouched by the app. It only supports older
  experiments and example seeding.

This model keeps prompt, Pydantic model, and validators together as one
versioned source bundle.

## Artifact Invalidation

Changing validators does not change already generated run outputs. It does
change validation, review, proposal, and comparison semantics.

For `overwrite_current`, remove:

- `validations/`
- `reviews/`
- `comparisons/`

Keep:

- `runs/`

If a stale proposal directory exists under a review, it is removed together with
the containing `reviews/` directory.

For `create_next`, copy the source version, remove all generated runtime
artifacts, and create a clean version:

- remove `runs/`
- remove `validations/`
- remove `reviews/`
- remove `comparisons/`

This matches the existing source-copy behavior for prompt/model versioning.

## Backend API

Add a validator-source update endpoint:

```http
POST /api/experiments/{experiment_id}/versions/{version}/validators
```

Request:

```json
{
  "mode": "create_next",
  "validators": []
}
```

`mode` is one of:

- `create_next`
- `overwrite_current`

Response mirrors the prompt/model source endpoint:

```json
{
  "version": "v002",
  "source_version": "v001",
  "mode": "create_next",
  "version_dir": "/absolute/path/to/version"
}
```

Validation rules:

- Each validator must satisfy the existing `ValidatorDefinition` Pydantic union.
- `validator_id` values must be unique.
- `validator_id` values must be safe path segments.
- Each validator must contain at least one check.
- `check_id` values must be unique within a validator.
- `automatic` rules must follow the current rule-shape constraints:
  - JSON path rules require `source: "output_json"` and `path`.
  - `json_path_exists` cannot include `comparison`.
  - non-exists rules require a valid `comparison`.
  - `between` requires `min_value` and `max_value`.

Error responses should return the same readable API error style already used by
settings/source saves.

## Frontend UX

The `Validators` tab becomes an editor.

Header actions:

- `Reset`
- `Overwrite current version`
- `Save as next version`

List area:

- Shows all validators in stable order.
- Each row shows title, `validator_id`, type, enabled state, and check count.
- Supports selecting a validator.
- Supports `Add validator`, `Duplicate`, and `Delete`.

Editor area:

- Shared fields:
  - `validator_id`
  - `title`
  - `description`
  - `enabled`
  - `input_scope`
  - `type`
- `llm_questionnaire` checks:
  - `check_id`
  - `title`
  - `question`
  - `description`
- `automatic` checks:
  - `check_id`
  - `title`
  - `description`
  - `rule.kind`
  - `rule.source`
  - `rule.path` when required
  - `rule.comparison` when required

The editor should use structured controls for normal editing:

- toggles or checkboxes for booleans;
- selects for type, input scope, rule kind, source, and comparison operator;
- text inputs for ids and titles;
- textareas for descriptions and LLM questions;
- numeric inputs for comparison values.

Advanced JSON mode:

- Available for the selected validator only.
- Uses a JSON editor textarea or code editor surface.
- Parses and validates locally before saving to the backend.
- Does not replace the structured editor as the default mode.

Empty state:

- If no validators exist, show an empty state with `Add validator`.
- Validation workflow actions should continue to reject running validation when
  no enabled validators exist.

## Dirty Navigation

Validator edits participate in the same unsaved-change pattern as Settings and
Prompt:

- Leaving the `Validators` tab while dirty opens the shared unsaved-change
  confirmation flow.
- Saving as next version creates the new version, switches active version to it,
  refreshes detail state, and stays on `Validators`.
- Overwriting current version asks for explicit confirmation because it deletes
  validation, review, proposal, and comparison artifacts for that version.
- Reset discards the local draft and stays on `Validators`.

## Frontend State And API Types

Add frontend request/response types matching the backend:

- `VersionValidatorsSaveMode`
- `VersionValidatorsUpdateRequest`
- `VersionValidatorsUpdateResponse`

Add API helper:

```ts
updateVersionValidators(experimentId, version, request)
```

`ValidatorsView` receives:

- current validators;
- busy/message state;
- draft-change callback;
- reset callback;
- save-as-next callback;
- overwrite-current callback.

The `App` component remains responsible for cross-tab dirty navigation,
version switching, workflow messages, and refreshing experiment detail state.

## Compatibility And Migration

No eager migration is required.

When a user edits validators for an experiment that only has top-level
validators, the first save writes `versions/<version>/validators/`. From that
point on, that version no longer depends on top-level validators.

Creating a next version from an older version copies effective validators into
the new version, even if the source validators came from the top-level fallback.
This makes the new version self-contained.

## Testing

Backend tests:

- version overview prefers version-level validators over top-level validators;
- version overview falls back to top-level validators for existing experiments;
- validator `create_next` writes validators into the new version and clears all
  runtime artifacts in the new version;
- validator `overwrite_current` writes validators into the current version,
  clears `validations`, `reviews`, and `comparisons`, and keeps `runs`;
- duplicate `validator_id` is rejected;
- unsafe `validator_id` is rejected;
- malformed automatic rule shape is rejected;
- active experiment version is not switched by the backend endpoint itself.

Frontend tests:

- `ValidatorsView` renders empty state and add action;
- structured LLM validator editing updates title, input scope, and checks;
- structured automatic validator editing updates rule kind and comparison;
- duplicate/delete validator actions update the draft;
- save buttons are disabled when the draft is clean or invalid;
- dirty navigation recognizes unsaved validator edits;
- proposal/source flows still switch to `Prompt` where expected.

E2E tests:

- edit an existing validator, save as next version, and verify the app switches
  to the new version on `Validators`;
- overwrite current validators and verify validation/review/proposal state is no
  longer shown while runs remain available;
- add an automatic validator in `demo-json`, save, and run validation against
  existing runs.

## Rollout Notes

This change should be implemented behind normal application behavior, not a
feature flag. The fallback read path keeps existing runtime workspaces usable.
Once version-level validators have existed for a while, a later cleanup can
remove top-level validator fallback after an explicit migration plan.
