# Case Suites Design

## Goal

Move Prompt Lab cases out of individual experiment directories and into shared
Case Suites. A Case Suite is a named set of prompt input cases that can be used
by multiple experiments. This removes duplicated case files while keeping
experiments focused on prompts, models, validators, run defaults, and workflow
artifacts.

The working name is **Case Suite**. It reads better than "case pack" because the
feature is closer to a reusable evaluation/test suite than a bundle of files.

## Decisions

- An experiment uses at most one Case Suite.
- A Case Suite is the shared source of truth for its case payloads.
- Editing a case in a suite affects every experiment assigned to that suite.
- Per-experiment case inclusion stays on the experiment through
  `run_defaults.excluded_case_ids`.
- Experiment views may preview suite cases and toggle whether each case is run
  for that experiment, but they do not add, delete, or edit suite case payloads.
- Cloning an experiment preserves the same `case_suite_id`; it does not copy
  case payloads.
- Case Suite and suite-case management lives in a separate UI area.
- New experiments may have no Case Suite assigned. They are valid drafts, but
  cannot be run or previewed until a suite is assigned.
- There is no legacy fallback to `experiments/<id>/cases/`. Runtime experiments
  and runtime case suites should be reset after this migration and reseeded from
  `examples/`.

## Filesystem Shape

Committed templates live under `examples/`:

```text
examples/
  experiments/
    split-scenes/
      experiment.json
      versions/
        v001/
          prompt.md
          model.py
          validators/

    summarize-chapter/
      experiment.json
      versions/
        v001/
          prompt.md
          validators/

    demo-string/
      experiment.json
      versions/

    demo-json/
      experiment.json
      versions/

  case_suites/
    story-chapters/
      suite.json
      cases/
        001-after-hours-at-meridian-mall-6.json
        002-carmilla-3.json
        003-the-portrait-at-harrowick-house-5.json

    demo-string-replies/
      suite.json
      cases/
        billing-reply.json
        support-reply.json

    demo-json-briefs/
      suite.json
      cases/
        product-brief.json
        service-brief.json
```

Runtime data lives in gitignored directories:

```text
experiments/
case_suites/
```

Backend startup treats `examples/` as the golden template source. It seeds each
runtime root independently without overwriting non-empty local data:

- if `experiments/` is missing or contains no `*/experiment.json` manifests,
  copy `examples/experiments/` to `experiments/`;
- if `case_suites/` is missing or contains no `*/suite.json` manifests, copy
  `examples/case_suites/` to `case_suites/`.

An intentional reset means deleting both runtime roots so the next backend
startup recreates a matched set from `examples/`.

The committed demo experiments remain first-class fixtures because frontend e2e
and regression tests depend on them:

- `split-scenes` and `summarize-chapter` both use `story-chapters`.
- `demo-string` uses `demo-string-replies`.
- `demo-json` uses `demo-json-briefs`.

## Artifact Model

Add a Case Suite artifact:

```json
{
  "schema_version": "prompt_lab.case_suite/v1",
  "id": "story-chapters",
  "title": "Story chapters",
  "description": "Shared chapter inputs for story prompt experiments."
}
```

Add an optional `case_suite_id` field to `ExperimentArtifact`:

```json
{
  "schema_version": "prompt_lab.experiment/v1",
  "id": "split-scenes",
  "title": "Split scenes",
  "case_suite_id": "story-chapters",
  "active_version": "v001",
  "output": {
    "type": "pydantic",
    "model_file": "model.py",
    "model_entrypoint": "model.SceneList"
  },
  "template": {
    "engine": "jinjax",
    "path": "prompt.md"
  },
  "models": {
    "generator_model": "local/gpt-oss-120b",
    "validator_model": "openai/example-large-model",
    "judge_model": "openai/example-large-model"
  },
  "run_defaults": {
    "repeat_count": 3,
    "llm_cache": "disabled",
    "case_order": "case-major",
    "excluded_case_ids": []
  }
}
```

`CaseArtifact` can stay conceptually unchanged: `id`, `payload`, and API-level
`enabled`. The `enabled` value is still derived from the active experiment's
`excluded_case_ids`, not stored in the case file.

## Runtime Semantics

Prompt rendering and validation read case payloads from the experiment's
assigned Case Suite.

When a suite case payload is changed, every experiment assigned to that suite has
its generated workflow artifacts invalidated because earlier runs were produced
from different input data. The storage layer should remove runtime `runs`,
`validations`, `reviews`, and `comparisons` under each affected experiment
version after a suite payload save succeeds.

Changing `excluded_case_ids` is still an experiment-local setting. It should be
validated against the assigned suite's current case ids, and run/preview should
use only enabled cases. If the inclusion set changes, generated workflow
artifacts for that experiment are invalidated because previous runs may have
used a different case set.

Deleting an experiment never deletes a Case Suite. Deleting a Case Suite is
allowed only when no experiment references it.

## Backend Storage

Add storage methods that keep path resolution and validation centralized:

```python
def list_case_suites(self) -> list[CaseSuiteArtifact]: ...
def case_suite_dir(self, suite_id: str) -> Path: ...
def load_case_suite(self, suite_id: str) -> CaseSuiteArtifact: ...
def load_cases_for_suite(self, suite_id: str) -> list[CaseArtifact]: ...
def load_cases_for_experiment(self, experiment_id: str) -> list[CaseArtifact]: ...
def replace_suite_cases(self, suite_id: str, cases: list[CaseArtifact]) -> list[CaseArtifact]: ...
def experiments_using_case_suite(self, suite_id: str) -> list[ExperimentArtifact]: ...
def invalidate_case_suite_consumers(self, suite_id: str) -> list[str]: ...
def invalidate_experiment_case_selection(self, experiment_id: str) -> None: ...
```

`load_cases_for_experiment()` should:

1. Load the experiment.
2. Require `case_suite_id`.
3. Validate the suite id as a safe storage segment.
4. Load cases from `case_suites/<case_suite_id>/cases/`.
5. Return a clear not-found or bad-request error if the suite is missing.

There is no read path for `experiments/<id>/cases/`.

## Backend API

Add Case Suite endpoints:

```http
GET /api/case-suites
POST /api/case-suites
GET /api/case-suites/{suite_id}
PATCH /api/case-suites/{suite_id}
DELETE /api/case-suites/{suite_id}
GET /api/case-suites/{suite_id}/cases
POST /api/case-suites/{suite_id}/cases
PUT /api/case-suites/{suite_id}/cases
PUT /api/case-suites/{suite_id}/cases/{case_id}
DELETE /api/case-suites/{suite_id}/cases/{case_id}
```

Keep experiment-facing case endpoints focused on preview and run inclusion:

```http
GET /api/experiments/{experiment_id}/versions/{version}
PATCH /api/experiments/{experiment_id}/cases/{case_id}/run-inclusion
PUT /api/experiments/{experiment_id}/case-inclusion
```

Those endpoints should now operate through the assigned Case Suite:

- version overview returns cases from the assigned suite;
- experiment case views expose case payloads as read-only preview data;
- saving suite payload changes happens only through Case Suite endpoints;
- saving changed suite payloads invalidates generated artifacts for every
  experiment assigned to the suite and returns the affected experiment ids;
- saving inclusion updates only the experiment manifest and invalidates
  generated artifacts for that experiment;
- missing `case_suite_id` returns a clear error for experiment case inclusion,
  run, validation, and prompt preview workflows.

Add experiment settings support for assigning an existing `case_suite_id`.

## Frontend UX

The existing experiment Cases tab remains the place to inspect the active
experiment's assigned suite cases and decide which cases should run for that
experiment.

When an experiment has a Case Suite assigned, the Cases tab shows the suite title
and shows read-only payload previews. Per-case run inclusion remains editable
and local to the active experiment. Saving changed inclusion reports that the
experiment's generated workflow artifacts were invalidated.

When no Case Suite is assigned:

- Settings shows a Case Suite selector.
- Cases shows an empty assigned-suite state.
- run and prompt preview controls are blocked with a direct message that a Case
  Suite must be assigned first.

Experiment creation does not create a Case Suite. Clone experiment keeps the
source `case_suite_id`.

Case Suite management lives in a separate UI area, not inside the experiment
Cases tab. It includes:

- listing suites with title, id, case count, and referencing experiments;
- creating a suite with title, generated id, and optional description;
- editing suite title and description;
- deleting a suite only when no experiment references it;
- adding a case to a suite;
- editing an existing case payload;
- deleting a case from a suite.

Suite case edits should use the shared `CodeViewer`/editor patterns already used
for JSON-like artifact displays. After suite case additions, deletions, or
payload saves, the UI reports which referencing experiments had generated
workflow artifacts invalidated.

## Validation Rules

- `case_suite_id` uses the same safe storage segment rules as experiment ids and
  case ids.
- If an experiment has `case_suite_id`, the suite must exist for run, preview,
  validation, and experiment case inclusion workflows.
- `excluded_case_ids` may contain only ids that exist in the assigned suite when
  case settings are saved.
- A suite cannot contain duplicate case ids.
- A suite cannot be deleted while any experiment references it.
- A case id still comes from the filename stem under `cases/`.
- Case files remain plain JSON objects and are passed directly to prompt
  rendering and validation.

## Migration

The migration is a template/runtime reset, not a compatibility layer.

1. Move committed experiment templates from `examples/<experiment>/` to
   `examples/experiments/<experiment>/`.
2. Move committed case files into `examples/case_suites/<suite_id>/cases/`.
3. Add `suite.json` files for `story-chapters`, `demo-string-replies`, and
   `demo-json-briefs`.
4. Add `case_suite_id` to every committed example experiment.
5. Update seeding to copy both `examples/experiments/` and
   `examples/case_suites/`.
6. Add runtime `case_suites/` to `.gitignore`.
7. Delete local runtime `experiments/` and `case_suites/` when applying the
   migration so the new examples reseed cleanly.

## Tests

Backend tests should cover:

- seeding experiments and case suites from `examples/`;
- listing and loading Case Suites;
- loading cases through `experiment.case_suite_id`;
- missing suite assignment blocks run and prompt preview;
- missing referenced suite returns a clear error;
- `excluded_case_ids` validation against suite case ids;
- changing experiment case inclusion invalidates generated artifacts for that
  experiment;
- cloning an experiment preserves `case_suite_id` and does not copy cases;
- deleting an experiment leaves the suite untouched;
- deleting a referenced Case Suite is rejected;
- saving suite case payloads invalidates generated artifacts for experiments
  assigned to that suite;
- storage rejects path escapes for suite ids and case ids.

Frontend tests should cover:

- `demo-string` and `demo-json` still load stable cases through suites;
- Cases tab shows assigned suite context;
- experiment Cases tab previews payloads without add/delete/payload-edit
  controls;
- no-suite experiments show the empty assigned-suite state;
- Settings can assign a Case Suite;
- separate Case Suite UI can create, edit, and delete unreferenced suites;
- separate Case Suite UI can add, edit, and delete suite cases;
- clone experiment preserves Case Suite assignment;
- run controls surface the no-suite error clearly.
