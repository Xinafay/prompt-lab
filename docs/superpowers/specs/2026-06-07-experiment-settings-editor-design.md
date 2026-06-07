# Experiment Settings Editor Design

## Goal

Add a simple GUI editor for `experiment.json` so users can inspect and update an
experiment manifest from the Prompt Lab UI without editing JSON files by hand.

## Scope

This is a v1 manifest editor only.

Included:

- Add a `Settings` workbench tab.
- Show a form backed by the selected experiment's `experiment.json`.
- Treat `id` as read-only because it maps to the experiment directory.
- Save the whole manifest through one backend endpoint.
- Validate the saved manifest with the existing Pydantic artifact model.
- Keep writes under `experiments/`, never under `examples/`.

Excluded:

- Renaming experiment IDs or directories.
- Editing `prompt.md`, `rubric.md`, `model.py`, cases, runs, reviews, or
  comparisons.
- Advanced raw JSON editing.
- Autosave.
- Version creation or deletion.

## User Experience

The workbench gets a new `Settings` tab next to the existing tabs. `Overview`
stays focused on quick inspection and workflow execution. `Settings` is the
configuration surface for the experiment manifest.

The form is split into compact sections:

- Identity: read-only `id`, editable `title`, editable `description`.
- Version: editable `active_version`.
- Models: editable `generator_model`, editable `judge_model`.
- Output: editable `type`; when `type` is `pydantic`, show `model_file`,
  `model_entrypoint`, and `validation_context_from_case`.
- Template: read-only `engine` set to `jinja2`, editable `path`.
- Run defaults: editable `repeat_count`, read-only `llm_cache` and
  `case_order`.

Controls:

- `Save` persists the manifest.
- `Reset` restores the last manifest loaded from the backend.
- Dirty state is local to the Settings tab.
- A successful save refreshes the selected experiment, the experiments list, and
  the active version overview.
- Validation or save errors are shown inside the Settings tab without changing
  the current form values.

## Backend API

Add:

```http
PUT /api/experiments/{experiment_id}
```

Request body:

- Full `ExperimentArtifact` JSON payload.

Response body:

- The saved `ExperimentArtifact` JSON payload.

Validation:

- `experiment_id` path segment is validated through the same storage ID rules as
  existing store lookups.
- The experiment must already exist under `experiments/`.
- The body must validate as `ExperimentArtifact`.
- `body.id` must exactly equal the path `experiment_id`.
- `active_version` must point to an existing directory under
  `experiments/<id>/versions/`.
- For `output.type = "text"`, pydantic-only fields must be absent or `null`;
  this is already enforced by `OutputConfig`.
- For `output.type = "pydantic"`, `model_file` and `model_entrypoint` are
  required; this is already enforced by `OutputConfig`.

Write behavior:

- Write only to `experiments/<id>/experiment.json`.
- Format JSON with `ensure_ascii=False`, `indent=2`, and a trailing newline,
  matching existing artifact writes.
- Do not touch `examples/`.

## Storage

Add this storage method:

```python
def save_experiment(self, experiment_id: str, artifact: ExperimentArtifact) -> Path:
    ...
```

The method should:

- Resolve the experiment directory through `experiment_dir(experiment_id)`.
- Reject mismatched IDs.
- Reject missing `versions/<active_version>`.
- Write `experiment.json` using the existing JSON writer.
- Return the written path.

This keeps filesystem rules centralized in `PromptLabStore` instead of encoding
path logic in the API route.

## Frontend Data Flow

Add an API helper:

```ts
updateExperiment(experimentId: string, experiment: Experiment): Promise<Experiment>
```

Add a Settings component that receives:

- Current `Experiment`.
- Save callback.
- Reset or reload callback.
- Busy state and save message.

State behavior:

- The form initializes from `detailState.overview.experiment` when a loaded
  overview changes.
- Editing fields updates local draft state only.
- Switching experiments or active versions resets the draft to the newly loaded
  manifest.
- Saving a text output clears pydantic-only fields before sending.
- Saving a pydantic output keeps the visible pydantic fields.
- After save, `App` refreshes `/api/experiments`, selects the returned
  experiment, reloads active version details, and leaves the user on `Settings`.

## Error Handling

Backend:

- Missing experiment returns 404 through existing `NotFoundError` handling.
- Invalid body returns FastAPI/Pydantic validation errors.
- ID mismatch returns 400 with a clear message.
- Missing `active_version` directory returns 400 with a clear message.

Frontend:

- Show backend error text in the Settings tab.
- Keep unsaved draft values after a failed save.
- Disable Save while a save request is in flight.
- Disable Save when there are no local changes.

## Testing

Backend tests:

- `PUT /api/experiments/{id}` saves editable manifest fields under
  `experiments/`.
- The endpoint rejects `body.id` mismatch.
- The endpoint rejects missing `active_version`.
- The endpoint does not write to `examples/`.
- Storage unit tests cover successful save, ID mismatch, and missing active
  version directory.

Frontend tests or validation:

- TypeScript compile via `pnpm lint`.
- Production build via `pnpm build`.
- Manual browser check:
  - Open `Settings`.
  - Edit title, description, generator model, judge model, and repeat count.
  - Save.
  - Refresh the page and confirm values persist.
  - Switch output type between `text` and `pydantic` and confirm conditional
    fields behave correctly.

## Acceptance Criteria

- Users can edit supported `experiment.json` fields from the GUI.
- `id`, `template.engine`, `run_defaults.llm_cache`, and
  `run_defaults.case_order` are visible but not editable.
- Saves are validated by the backend and persisted under `experiments/`.
- `examples/` remains unchanged.
- Invalid active versions and mismatched IDs are rejected.
- The experiments list and active overview reflect saved values after save.
- Backend tests, pyright, frontend lint, and frontend build pass.
