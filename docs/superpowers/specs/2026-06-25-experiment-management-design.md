# Experiment Management Design

## Goal

Let users create, clone, and delete Prompt Lab experiments from the UI without
editing the filesystem by hand.

The feature should feel like the existing Prompt Lab workbench: compact,
local-first, explicit about filesystem effects, and consistent with the current
settings, cases, and overwrite confirmation dialogs.

## Scope

Included:

- Add experiment creation from the experiments sidebar.
- Generate a unique experiment id from the entered title.
- Create the initial filesystem structure for a new experiment.
- Clone an existing experiment directory into a new experiment id.
- Delete an experiment directory after an in-app confirmation dialog.
- Refresh selection, routing, and loaded details after each operation.

Excluded:

- Restoring deleted experiments.
- Renaming experiment ids after creation.
- Deleting individual versions.
- Importing experiments from arbitrary external folders.
- Creating cases during experiment creation.
- Changing how Carmilla or other external producers emit neutral experiment
  bundles.

## User Experience

Experiment management lives in the left `Experiments` panel because that panel
already owns experiment selection. The workflow toolbar remains focused on the
active version workflow.

The panel heading gains a compact `New` action. The selected experiment gains
small contextual `Clone` and `Delete` actions using existing button styles:

- `New` and `Clone` use the normal secondary action treatment.
- `Delete` uses the existing danger action treatment.

All multi-step operations use Prompt Lab modals, not JavaScript
`alert()`/`confirm()` dialogs.

### New Experiment

`New experiment` opens a modal with:

- `Title`
- `Output type`: `text` or `pydantic`
- `Model entrypoint`, shown only for `pydantic`, defaulting to `model.Output`

The backend generates the final id by slugifying the title. If the slug already
exists, it appends a numeric suffix such as `-2`, then `-3`, until it finds a
free id.

The title is a starting display name and remains editable later from Settings.
The generated id is not editable later. Output structure is chosen at creation
time so Prompt Lab can create the right initial files.

After creation, the app refreshes the experiment list, selects the created
experiment, routes to `/<id>/prompt`, and shows version `v001`.

### Clone Experiment

`Clone experiment` opens a modal with:

- `Title`, defaulting to `Copy of <source title>`

The dialog explains that clone copies the selected experiment's manifest, cases,
versions, prompts, models, validators, and existing artifacts. This is a full
local copy, not a link to the source experiment.

The backend generates a unique id from the new title, copies the full source
experiment directory, and rewrites the cloned `experiment.json` with the new id
and title.

After cloning, the app refreshes the list, selects the clone, and routes to its
Settings tab so the user can adjust title, description, models, or run defaults.

### Delete Experiment

`Delete experiment` opens a custom modal with a clear destructive message. The
copy should state that deletion removes the experiment manifest, versions,
prompts, models, cases, runs, validations, reviews, proposals, and comparisons.

The dialog has:

- `Cancel`
- `Delete experiment`

Deletion physically removes the experiment directory immediately after
confirmation. There is no soft-delete or `_old` rename.

After deletion, the app refreshes the list. If experiments remain, it selects
the next available experiment and routes to its prompt tab. If none remain, it
shows the existing empty state.

## Filesystem Shape

New `text` experiments create:

```text
experiments/<generated-id>/
  experiment.json
  versions/
    v001/
      prompt.md
```

New `pydantic` experiments create:

```text
experiments/<generated-id>/
  experiment.json
  versions/
    v001/
      prompt.md
      model.py
```

`prompt.md` starts empty. `model.py` starts as an empty file so the user can
edit it from the existing prompt/model editing flow without creating the file by
hand.

The generated manifest uses:

- `schema_version`: `prompt_lab.experiment/v1`
- `active_version`: `v001`
- `template.engine`: `jinjax`
- `template.path`: `prompt.md`
- `output.type`: selected output type
- `output.model_file`: `model.py` for pydantic experiments
- `output.model_entrypoint`: entered model entrypoint for pydantic experiments
- model names and repeat count from global settings
- `llm_cache`: `disabled`
- `case_order`: `case-major`
- `excluded_case_ids`: `[]`

## Backend API

Add request and response models near the existing experiment routes.

```http
POST /api/experiments
```

Request:

```json
{
  "title": "Experiment title",
  "output_type": "text"
}
```

For pydantic:

```json
{
  "title": "Experiment title",
  "output_type": "pydantic",
  "model_entrypoint": "model.Output"
}
```

Response:

- The created `ExperimentArtifact`.

```http
POST /api/experiments/{experiment_id}/clone
```

Request:

```json
{
  "title": "Copy of Experiment title"
}
```

Response:

- The cloned `ExperimentArtifact`.

```http
DELETE /api/experiments/{experiment_id}
```

Response:

```json
{
  "experiment_id": "deleted-id"
}
```

Validation:

- Empty titles are rejected with a clear 400 response.
- Generated ids must pass the same storage id rules as other experiment ids.
- Source experiment ids are resolved through `PromptLabStore`.
- Clone source and destination must both stay under `experiments/`.
- Delete uses the same id validation and must not delete outside the
  experiments root.

## Storage

Add storage methods to keep path and filesystem rules centralized:

```python
def create_experiment(
    self,
    *,
    title: str,
    output_type: Literal["text", "pydantic"],
    model_entrypoint: str | None,
    settings: PromptLabSettings,
) -> ExperimentArtifact:
    ...

def clone_experiment(
    self,
    *,
    source_experiment_id: str,
    title: str,
) -> ExperimentArtifact:
    ...

def delete_experiment(self, experiment_id: str) -> None:
    ...
```

The store owns:

- slug generation,
- uniqueness checks,
- directory creation,
- `copytree` for cloning,
- manifest rewriting,
- recursive directory deletion after path validation.

Slug rules:

- Lowercase title.
- Replace runs of non-alphanumeric characters with `-`.
- Trim leading and trailing `-`.
- Fall back to `experiment` when the title produces an empty slug.
- Append `-2`, `-3`, and so on for conflicts.

## Frontend Data Flow

Add API helpers:

```ts
createExperiment(request): Promise<Experiment>
cloneExperiment(experimentId, request): Promise<Experiment>
deleteExperiment(experimentId): Promise<{ experiment_id: string }>
```

Extend `ExperimentsList` with props for:

- create action,
- clone action,
- delete action,
- busy action id or mode,
- selected experiment id.

Keep modal state in `App` so a successful operation can refresh global
experiment state, selected experiment state, details, route, and messages in one
place.

Selection behavior:

- Create: select created experiment, load `v001`, route to prompt tab.
- Clone: select clone, load its active version, route to settings tab.
- Delete selected experiment: select next experiment by current list order, or
  show no-experiments state.
- Delete non-selected experiment, if supported later: keep current selection.

Unsaved navigation:

- If an operation would leave the current experiment while Settings, Prompt,
  Validators, Cases, Validation, or Review has unsaved changes, reuse the
  existing pending-navigation confirmation path where practical.
- The delete confirmation itself remains separate because it is destructive and
  should clearly describe the filesystem deletion.

## Settings Interaction

Creation-time structural fields are read-only from Settings:

- `id` remains read-only.
- `output.type` is read-only.
- `output.model_file` is read-only for pydantic experiments.
- `output.model_entrypoint` is read-only for pydantic experiments.
- `template.path` is read-only and remains the generated `prompt.md`.

The title remains editable from Settings because it is display metadata, not the
directory id.

Read-only structural fields use the same visual treatment as existing read-only
settings fields such as `id`, `template.engine`, `llm_cache`, and `case_order`.
A separate future migration workflow can support changing output structure if
that becomes necessary.

## Error Handling

Backend:

- Duplicate generated ids are avoided automatically.
- Invalid path segments return 404 or 400 without exposing host paths.
- Filesystem conflicts during create or clone return 409.
- Missing source experiment returns 404.
- Delete of a missing experiment returns 404.

Frontend:

- Modal-local errors are shown inside the modal.
- Submit buttons are disabled while their request is in flight.
- Failed create/clone/delete keeps the modal open with the user's entered
  title.
- The experiments list is refreshed after successful mutation.

## Testing

Backend tests:

- Creating a text experiment writes the expected manifest and empty `prompt.md`.
- Creating a pydantic experiment writes the expected manifest, empty `prompt.md`,
  and empty `model.py`.
- Slug generation appends numeric suffixes for duplicate titles.
- Clone copies cases, versions, validators, and artifacts while rewriting id and
  title.
- Delete removes the experiment directory and rejects path escapes.
- API endpoints return useful status codes for invalid title, missing source,
  conflicts, and missing delete target.

Frontend tests:

- `ExperimentsList` renders the new action controls in the existing panel.
- Create modal conditionally shows pydantic fields.
- Delete modal text describes the destructive filesystem scope.
- App source includes refresh and routing behavior for create, clone, and
  delete.

Browser QA:

- Open `http://127.0.0.1:5173/demo-json/settings`.
- Create a text experiment and confirm it appears in the sidebar and routes to
  prompt tab.
- Create a pydantic experiment and confirm `model.py` appears in the model
  editor.
- Clone `demo-json` and confirm the clone has cases, versions, validators, and
  settings.
- Delete the clone through the custom modal and confirm the sidebar selection
  moves to another experiment.
- Check console errors and visual layout at the normal in-app browser viewport.

## Acceptance Criteria

- Users can create, clone, and delete experiments without filesystem editing.
- New experiment ids are generated from titles and are unique.
- New experiments include initial `v001` source files.
- Clone produces an independent full local copy.
- Delete physically removes the selected experiment only after a custom
  confirmation modal.
- The UI uses the existing Prompt Lab action, danger, modal, and panel styles.
- Routing and selection remain valid after every operation.
- Backend tests, frontend tests, typecheck, build, and browser QA pass.
