# Prompt Lab Design

Date: 2026-06-06

## Purpose

Prompt Lab is a standalone local web application for iterative prompt and structured-output contract testing. It is intended to support the workflow currently performed manually with Carmilla workflow-step evals:

1. Run a prompt against several representative cases and several uncached repeats.
2. Inspect the generated text or Pydantic-validated JSON.
3. Validate the active run with explicit automatic and LLM questionnaire validators.
4. Review validation results and optionally exclude weak evidence before judging.
5. Ask a stronger judge model to identify recurring quality problems, one-off deviations, validation/schema issues, and useful changes.
6. Let the user accept or reject individual judge findings and add human notes.
7. Ask a stronger proposal model to create a new candidate prompt and optionally a new Pydantic model.
8. Compare versions with deterministic validation-result matrices before deciding whether to use the new prompt/model in the source project.

Prompt Lab must be independent from Carmilla workflow runtime. Carmilla can export examples into Prompt Lab's neutral format, but Prompt Lab must not import `workflow_runtime`, `WorkflowState`, Story Parser workflow classes, or flat-file context objects.

## Repository Strategy

Prompt Lab should become a separate repository. During design and bootstrapping, transfer-ready files may temporarily live under Carmilla's top-level `prompt_lab/` directory. That directory is not part of Carmilla runtime and can be copied into a new repository.

The only Carmilla code that should be reused directly is the LLM backend under `python/shared/llm`. For the first Prompt Lab implementation, copy that code into Prompt Lab, for example:

```text
prompt-lab/backend/shared/llm/
```

Prompt Lab backend code should access it through a thin local wrapper, for example `prompt_lab.llm_client`, so that the copied module can later be replaced by a shared subrepo/package without touching the whole application.

## Non-Goals

MVP does not include:

- importing or executing Carmilla workflow steps;
- overwriting source prompts or models in Carmilla or any other project;
- durable job recovery after application restart;
- user accounts, multi-user authorization, or deployment;
- numeric scorecards as the primary judgment model;
- golden expected outputs;
- automatic validator definition editing by the proposal model;
- sandboxing untrusted Pydantic code;
- preserving compatibility with old Prompt Lab experiment formats, because no such format exists yet.

## Architecture

Recommended standalone repository layout:

```text
prompt-lab/
  backend/
    prompt_lab/
      app.py
      api.py
      config.py
      storage.py
      templates.py
      pydantic_loader.py
      llm_client.py
      runner.py
      judge.py
      compare.py
      proposal.py
      jobs.py
      models/
        artifacts.py
        api.py
        judgments.py
    shared/
      llm/
    tests/
  frontend/
    package.json
    src/
  experiments/
  examples/
  docs/
```

Backend:

- Python.
- FastAPI or Starlette.
- Filesystem store as the canonical source of truth.
- Simple in-process job manager for runs, validation, judgments, comparisons, and proposals.
- SSE for progress events.
- Copied Carmilla `shared/llm` for OpenAI and OpenAI-compatible local model routing.

Frontend:

- React + Vite.
- Local tool UI; no SSR requirement.
- Uses backend REST endpoints plus SSE progress streams.

Data:

- Experiments are plain directories and files.
- SQLite may be added later as an index/cache for UI speed, but not as the canonical source.

## Core Concepts

### Experiment

An experiment is a prompt-testing workspace. It contains metadata, validator
definitions, shared cases, and one or more versions.

An experiment does not know which project created it. It only knows prompt
templates, prompt invocation cases, optional Pydantic models, model
configuration, validators, validation results, judgments, user decisions, notes,
proposals, and comparisons.

### Version

A version is an immutable test candidate once runs are created for it. It contains:

- prompt template;
- optional Pydantic model;
- run artifacts;
- validation artifacts;
- reviews;
- comparisons.

Creating a proposal does not mutate the current version. Accepting a proposal creates the next version, for example `v002`, by copying files from the proposal.

### Case

A case is a JSON file describing one concrete prompt invocation. It contains serialized source stores and bindings that materialize into the prompt/validation context. The case format is universal and simple. It is not a workflow fixture.

### Validators

Validators are experiment-level JSON definitions under `validators/`. They state
what should be checked after a run. Enabled validators run in the explicit
`Validate active run` stage before judging.

LLM questionnaire validators ask `validator_model` to grade concrete checks on
the global `grade: 1..5 | null` scale over configured input scope. Automatic
validators run local rules such as word counts or JSON-path counts without
calling an LLM; binary local rules currently map passing evidence to high grades
and failing evidence to low grades. Each validation batch stores validator
snapshots, so historical validation results remain understandable even if
validator definitions change later.

### Judgment

A judgment is a structured analysis produced by the judge model. It is
qualitative by default and must cite selected validation evidence from
cases/runs.

The judge should distinguish:

- what looks correct;
- recurring problems;
- one-off deviations;
- validation/schema issues;
- suggested changes;
- regression risks;
- user decision points.

### Review

A review combines:

- judge output;
- user decisions for individual findings;
- human notes;
- optional proposal generated from accepted findings and human notes.

Human notes override judge recommendations. Rejected findings become constraints for proposal generation.

### Proposal

A proposal is a candidate change to the prompt and optionally the Pydantic model. It is created under a review directory and does not become a version until the user explicitly creates the next version from it.

Proposal generation is conservative with `model.py`. It should change the Pydantic model only when accepted findings or human notes clearly indicate a contract issue, such as a missing field, bad field order/description, wrong type, or validator behavior.

## Filesystem Format

Recommended experiment layout:

```text
experiments/<experiment-id>/
  experiment.json
  validators/
    <validator-id>.json
  cases/
    <case-id>.json
  versions/
    v001/
      prompt.md
      model.py                 # only for pydantic output
      runs/
        <run-batch-id>/
          job.json
          <case-id>/
            repeat-001.json
            repeat-002.json
            repeat-003.json
      validations/
        <validation-batch-id>/
          batch.json
          validators_snapshot/
            <validator-id>.json
          <case-id>/
            repeat-001/
              <validator-id>.json
      reviews/
        review-001/
          judgment.json
          judgment.md
          decisions.json
          human_notes.md
          proposal/
            prompt.md
            model.py            # optional
            rationale.md
            source.json
      comparisons/
        comparison-001/
          compare_matrix.json
```

### `experiment.json`

Example for Pydantic output:

```json
{
  "schema_version": "prompt_lab.experiment/v1",
  "id": "split-scenes",
  "title": "Split scenes",
  "description": "Split a chapter into contiguous scenes.",
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
    "generator_model": "local/example-small-model",
    "validator_model": "openai/example-large-model",
    "judge_model": "openai/example-large-model"
  },
  "run_defaults": {
    "repeat_count": 3,
    "llm_cache": "disabled",
    "case_order": "case-major"
  }
}
```

Example for text output:

```json
{
  "schema_version": "prompt_lab.experiment/v1",
  "id": "summarize-chapter",
  "title": "Summarize chapter",
  "description": "Write a compact one-paragraph chapter summary.",
  "active_version": "v001",
  "output": {
    "type": "text"
  },
  "template": {
    "engine": "jinjax",
    "path": "prompt.md"
  },
  "models": {
    "generator_model": "local/example-small-model",
    "validator_model": "openai/example-large-model",
    "judge_model": "openai/example-large-model"
  },
  "run_defaults": {
    "repeat_count": 3,
    "llm_cache": "disabled",
    "case_order": "case-major"
  }
}
```

### Validator JSON

LLM questionnaire validator:

```json
{
  "schema_version": "prompt_lab.validator/v1",
  "validator_id": "scene-quality",
  "type": "llm_questionnaire",
  "title": "Scene quality",
  "description": "Checks whether structured scenes preserve source content and useful boundaries.",
  "enabled": true,
  "input_scope": "output_and_case",
  "checks": [
    {
      "check_id": "coverage",
      "title": "Coverage",
      "question": "Does the scene list cover every important source event without omission?"
    }
  ]
}
```

Automatic validator:

```json
{
  "schema_version": "prompt_lab.validator/v1",
  "validator_id": "scene-count",
  "type": "automatic",
  "title": "Scene count",
  "enabled": true,
  "input_scope": "output_only",
  "checks": [
    {
      "check_id": "has-scenes",
      "title": "Has scenes",
      "rule": {
        "kind": "json_path_count",
        "source": "output_json",
        "path": "scenes",
        "comparison": {
          "op": "gte",
          "value": 1
        }
      }
    }
  ]
}
```

### Case JSON

```json
{
  "schema_version": "prompt_lab.case/v2",
  "id": "after-hours-at-meridian-mall-6",
  "title": "After Hours at Meridian Mall 6",
  "source": {
    "type": "carmilla.workflow_step_eval"
  },
  "stores": {
    "case": {
      "kind": "flat_file_tree",
      "values": {
        "chapter_text_with_paragraphs": {
          "__carmilla_flat_file_node__": "file",
          "value": "..."
        },
        "parts": {
          "__carmilla_flat_file_node__": "file",
          "value": []
        }
      }
    }
  },
  "bindings": {
    "chapter_text_with_paragraphs": {
      "kind": "store_scope",
      "store": "case",
      "path": "chapter_text_with_paragraphs"
    },
    "parts": {
      "kind": "store_scope",
      "store": "case",
      "path": "parts"
    }
  }
}
```

`stores` hold serialized source data. `bindings` define the top-level names
visible to prompt templates and Pydantic validation. A `store_scope` binding
selects a path inside a store. A `value` binding stores a computed JSON value for
the invocation.

Prompt Lab materializes `stores + bindings` into one plain context dictionary.

### Run Batch

`job.json`:

```json
{
  "schema_version": "prompt_lab.run_batch/v1",
  "run_batch_id": "run-20260606-102000",
  "version": "v001",
  "status": "completed",
  "repeat_count": 3,
  "case_order": "case-major",
  "llm_cache": "disabled",
  "started_at": "2026-06-06T10:20:00+02:00",
  "finished_at": "2026-06-06T10:31:00+02:00",
  "total_runs": 9,
  "completed_runs": 9
}
```

Run artifact:

```json
{
  "schema_version": "prompt_lab.run/v1",
  "run_id": "run-20260606-102000-after-hours-at-meridian-mall-6-repeat-001",
  "run_batch_id": "run-20260606-102000",
  "version": "v001",
  "case_id": "after-hours-at-meridian-mall-6",
  "repeat_index": 1,
  "generator_model": "local/example-small-model",
  "status": "ok",
  "rendered_prompt": "...",
  "raw_output": "...",
  "output_type": "pydantic",
  "output_json": {},
  "output_text": null,
  "validation_error": null,
  "execution_error": null,
  "usage": {}
}
```

Validation and parse failures are normal run results, not whole-experiment failures. They must be saved and passed to the judge because they often indicate prompt/schema problems.

### Validation Batch

Validation runs after a run batch and before judgment. It executes every enabled
validator against every run artifact and saves one result per
case/repeat/validator.

`batch.json`:

```json
{
  "schema_version": "prompt_lab.validation_batch/v1",
  "validation_batch_id": "validation-20260606-103500",
  "run_batch_id": "run-20260606-102000",
  "version": "v001",
  "status": "completed",
  "started_at": "2026-06-06T10:35:00+02:00",
  "finished_at": "2026-06-06T10:39:00+02:00",
  "total_results": 18,
  "completed_results": 18,
  "validator_model": "openai/example-large-model",
  "validator_ids": ["scene-quality", "scene-count"]
}
```

Validation results include check grades and `included_in_judge` flags. Users
can exclude a whole validator result or individual checks before the judge prompt
is built. Runs with generator `execution_error` create `skipped` validation
results with `included_in_judge=false`; no validator LLM call is made because no
model output exists to validate.

### Judgment JSON

The judge output should be structured. Suggested contract:

```json
{
  "schema_version": "prompt_lab.judgment/v1",
  "judgment_id": "judgment-20260606-104500",
  "version": "v001",
  "run_batch_ids": ["run-20260606-102000"],
  "judge_model": "openai/example-large-model",
  "summary": "...",
  "what_looks_correct": [
    {
      "finding_id": "correct-001",
      "description": "...",
      "evidence": ["case after-hours repeat 1"]
    }
  ],
  "findings": [
    {
      "finding_id": "f001",
      "severity": "recommended",
      "area": "prompt",
      "category": "recurring_problem",
      "description": "...",
      "evidence": ["case carmilla repeat 2", "case harrowick repeat 1"],
      "suggested_change": "..."
    }
  ],
  "decision_points": [
    {
      "decision_id": "d001",
      "description": "...",
      "options": ["..."],
      "recommended_option": "..."
    }
  ]
}
```

Findings should use severities:

- `recommended`: should probably be addressed in the next proposal;
- `optional`: useful but not required;
- `do_not_change_yet`: a tempting change that should not be made yet;
- `regression_risk`: something to protect in future versions.

### Decisions JSON

All judge findings default to `accepted`.

```json
{
  "schema_version": "prompt_lab.decisions/v1",
  "finding_decisions": {
    "f001": {
      "decision": "accepted"
    },
    "f002": {
      "decision": "rejected",
      "reason": "Weather should remain available as world-state information."
    },
    "f003": {
      "decision": "deferred",
      "reason": "Check after the next run."
    }
  }
}
```

Proposal generation rules:

- accepted findings are requested changes;
- rejected findings are constraints and must not be implemented indirectly;
- deferred findings are ignored in the current proposal unless human notes mention them;
- human notes override all judge findings.

### Compare Matrix JSON

Comparison is separate from single-version judgment. It is deterministic and
uses validation results, not an LLM prompt.

```json
{
  "schema_version": "prompt_lab.compare_matrix/v1",
  "comparison_id": "comparison-20260606-110000",
  "versions": ["v001", "v002"],
  "validators": [
    {
      "validator_id": "scene-quality",
      "title": "Scene quality",
      "checks": [
        {
          "check_id": "coverage",
          "title": "Coverage",
          "cells": {
            "v001": {
              "status": "mixed",
              "grade_5": 6,
              "grade_4": 1,
              "grade_3": 2,
              "grade_2": 0,
              "grade_1": 0,
              "not_assessable": 0,
              "missing": 0,
              "error": 0,
              "total": 9
            },
            "v002": {
              "status": "pass",
              "grade_5": 8,
              "grade_4": 1,
              "grade_3": 0,
              "grade_2": 0,
              "grade_1": 0,
              "not_assessable": 0,
              "missing": 0,
              "error": 0,
              "total": 9
            }
          }
        }
      ]
    }
  ]
}
```

Each compare cell aggregates included validation evidence from the latest
validation batch for that version. Status values are `pass`, `fail`, `mixed`,
or `empty`. No `judge_model` is used.

## Backend Behavior

### Template Rendering

Use the copied `shared.jinjax` package for prompt templates. A version's
`prompt.md` is rendered with the materialized context produced from a case's
`stores + bindings`.

The structured-output schema placeholder should remain `<<MODEL>>` inside prompts. Before calling the generator model, Prompt Lab replaces `<<MODEL>>` with a schema/instruction derived from the Pydantic model using the selected LLM backend's structured-output path. The exact mechanism may follow Carmilla's `chat_get_structured_lite` behavior.

### Pydantic Loading

For `output.type = "pydantic"`:

1. Load the version's `model.py`.
2. Resolve `model_entrypoint`, for example `model.SceneList`.
3. Pass the model to the structured-output LLM call.
4. Validate returned data with the materialized case context.
5. Save `output_json` on success or `validation_error` on failure.

MVP assumes trusted local Pydantic code. Import errors and validation errors are saved as run artifacts.

### Generator Runs

Rules:

- LLM cache is always disabled for generator runs.
- No UI option should enable cache in MVP; cached repeats would defeat variance testing.
- Default `repeat_count` is 3.
- Run order is case-major: `A-A-A-B-B-B`, not `A-B-A-B-A-B`, to improve provider-side prompt-cache locality while still disabling the application LLM cache.
- Save each run artifact immediately after it completes.
- One failed run does not stop the batch unless the user cancels the job.

### Jobs and Progress

Use an in-process job manager for MVP.

Job status:

```json
{
  "job_id": "run-20260606-102000",
  "kind": "run_version",
  "status": "running",
  "experiment_id": "split-scenes",
  "version": "v001",
  "total_runs": 9,
  "completed_runs": 4,
  "current_case": "carmilla-3",
  "current_repeat": 1,
  "message": "Calling generator model"
}
```

Validation jobs report the same current case/repeat shape plus the active
validator. Expose progress through SSE. After application restart, an in-memory
job may be lost; already written artifacts remain valid and the previous job can
be shown as interrupted.

### Validation

Validation input:

- experiment metadata;
- validator definitions;
- latest active run batch;
- cases;
- run artifacts, including Pydantic validation and execution errors.

LLM questionnaire validation uses `validator_model`. Automatic validation uses
local rule evaluation. Unknown or malformed LLM check IDs are saved as validation
errors so the batch remains inspectable.

### Judge

Single-version judgment input:

- experiment metadata;
- prompt;
- Pydantic model or text-output declaration;
- cases;
- validation batch metadata;
- included validation results;
- run artifacts referenced by validation evidence, including generator
  validation and execution errors.

Judge output must be structured and also rendered as Markdown for human reading.

The judge must identify recurring problems before one-off stochastic deviations. It must not assume a single run is authoritative.

### Deterministic Comparison

Comparison input:

- selected versions;
- latest validation batch for each selected version;
- validator snapshots and included validation results.

Comparison output is a grouped matrix by validator and check. It is intended for
human comparison of grade distributions across versions.

### Proposal Generator

Proposal input:

- current prompt;
- current model if present;
- accepted findings;
- rejected findings as constraints;
- human notes;
- included validation evidence used by judge;
- relevant run evidence.

Proposal output:

- full proposed `prompt.md`;
- optional proposed `model.py`;
- `rationale.md`;
- `source.json` identifying review/judgment/decisions/human notes used.

The proposal generator must not edit the active version. The user explicitly creates the next version from a proposal.

## API Sketch

REST endpoints:

```text
GET    /api/experiments
POST   /api/experiments/import
GET    /api/experiments/{experiment_id}
GET    /api/experiments/{experiment_id}/versions/{version}
PUT    /api/experiments/{experiment_id}/versions/{version}/prompt
PUT    /api/experiments/{experiment_id}/versions/{version}/model
POST   /api/experiments/{experiment_id}/versions/{version}/runs
POST   /api/experiments/{experiment_id}/versions/{version}/validations
GET    /api/experiments/{experiment_id}/versions/{version}/validations/latest
PUT    /api/experiments/{experiment_id}/versions/{version}/validations/{validation_batch_id}/inclusion
POST   /api/experiments/{experiment_id}/versions/{version}/judgments
PUT    /api/experiments/{experiment_id}/versions/{version}/reviews/{review_id}/decisions
PUT    /api/experiments/{experiment_id}/versions/{version}/reviews/{review_id}/human-notes
POST   /api/experiments/{experiment_id}/versions/{version}/reviews/{review_id}/proposal
POST   /api/experiments/{experiment_id}/versions/{version}/reviews/{review_id}/proposal/create-version
POST   /api/experiments/{experiment_id}/comparisons
GET    /api/jobs/{job_id}
GET    /api/jobs/{job_id}/events
```

SSE event names:

- `job_started`;
- `job_progress`;
- `run_started`;
- `run_saved`;
- `validation_started`;
- `validation_saved`;
- `judgment_started`;
- `judgment_saved`;
- `compare_matrix_saved`;
- `proposal_saved`;
- `job_failed`;
- `job_completed`.

## Frontend UX

Main views:

1. Experiments list
2. Experiment overview
3. Runs
4. Validation
5. Judgment/review
6. Proposal
7. Comparison

### Experiments List

Show:

- title;
- output type;
- active version;
- number of cases;
- last run;
- last judgment/comparison.

### Prompt

Show:

- active version selector;
- prompt editor;
- Pydantic model editor or text-output notice;
- buttons: `Run version`.

### Validators

Show:

- validator list;
- validator type, input scope, and enabled status;
- configured checks.

### Runs

Show a table:

- case;
- repeat;
- status;
- model;
- elapsed time;
- short output preview.

Run detail:

- prompt context bindings;
- serialized source stores;
- rendered prompt;
- raw output;
- validated JSON or output text;
- validation error;
- execution error;
- usage.

### Validation

Show grouped validation results by case, repeat, validator, and check. Allow the
user to exclude a whole validation result or individual checks from judge input.
Judge is disabled until a validation batch exists.

### Judgment / Review

Show:

- qualitative sections from judgment;
- evidence links to run details;
- each finding with decision control: `Accepted`, `Rejected`, `Deferred`;
- optional reason field for rejected/deferred findings;
- human notes textarea.

Default finding decision is `Accepted`.

### Proposal

Show:

- proposed prompt;
- proposed model if changed;
- rationale;
- source judgment/review;
- button: `Create next version`.

### Comparison

Show:

- baseline version selector;
- candidate version selector;
- deterministic validation matrix grouped by validator/check;
- per-version grade distributions and status for validation evidence.

## Carmilla Export Boundary

Carmilla should keep the existing GUI fixture capture:

1. User opens a story.
2. User reaches the target step.
3. User clicks `Save test state`.
4. User repeats this for several stories using the same eval name.

Then a Carmilla-side exporter replays each saved workflow-step fixture with
prompt/chat capture enabled and converts the captured prompt invocation into a
neutral Prompt Lab bundle:

```bash
PYTHONPATH=python ./.venv/bin/python -m workflow_runtime.export_prompt_lab \
  --workflow story_parser \
  --eval split-scenes \
  --output /path/to/prompt-lab/imports/split-scenes
```

Input:

```text
data-override/evals/workflow/story_parser/<eval-name>/
  <case-name>/fixture.json
```

Output:

```text
<eval-name>/
  experiment.json
  validators/
    <validator-id>.json
  cases/
    <case-name>.json
  versions/
    v001/
      prompt.md
      model.py
```

The exporter is allowed to understand Carmilla workflow steps. Prompt Lab is not.

Initial Carmilla exporters needed:

- `SPLIT_SCENES[...]` to Pydantic experiment:
  - prompt from Story Parser `prompts/divide_chapter.md`, preserved as jinjax;
  - model from Story Parser `models/scenes.py`;
  - case bindings include `previous_summaries`, `chapter_text_with_paragraphs`,
    and validation-relevant chapter data from the same materialized context.
- `SUMMARIZE_CHAPTER[...]` to text experiment:
  - prompt from Story Parser `prompts/chapter_summary.md`, preserved as jinjax;
  - case bindings include `chapter_text_with_scenes`.

## Initial Example Experiments

Use the saved Carmilla evals as initial examples:

- `split-scenes`: structured/Pydantic output;
- `summarize-chapter`: plain text output.

Each example should include the three cases currently saved in Carmilla:

- `after-hours-at-meridian-mall-6`;
- `carmilla-3`;
- `the-portrait-at-harrowick-house-5`.

## Testing Plan

Backend tests:

- load experiment metadata;
- load validator definitions;
- render prompt with materialized case context;
- load Pydantic model by entrypoint;
- validate a successful structured output;
- store validation errors as run artifacts;
- create validation batches and validation results;
- aggregate deterministic compare matrices from validation results;
- run repeat order case-major;
- create default accepted decisions for judge findings;
- ensure rejected findings are included as constraints in proposal input;
- create next version from proposal without mutating previous version.

Frontend tests:

- experiments list renders;
- run progress updates from mocked SSE;
- run detail shows JSON output and validation errors;
- validation results can be reviewed and excluded from judge input;
- finding decisions default to accepted and can be changed;
- human notes are saved;
- proposal view can create next version.

Manual smoke tests:

1. Import `split-scenes`.
2. Run 3 repeats on 3 cases.
3. Confirm progress displays current case/repeat.
4. Confirm structured JSON and validation errors are visible.
5. Validate the active run.
6. Review validation results and optionally exclude weak evidence.
7. Judge the validated run.
8. Reject one finding and add human notes.
9. Generate proposal.
10. Create `v002`.
11. Run and validate `v002`.
12. Compare validation results between `v002` and `v001`.

## Open Decisions For Implementation

These should be decided in the implementation conversation:

- exact FastAPI vs Starlette choice;
- exact frontend component library, if any;
- exact LLM structured-output wrapper API after copying `shared/llm`;
- exact generated schema text used to replace `<<MODEL>>`;
- whether imported examples live under `examples/` or are copied into `experiments/` on first launch.

## Implementation Sequence

Recommended order:

1. Create separate `prompt-lab` repo.
2. Copy Carmilla `python/shared/llm` into `backend/shared/llm`.
3. Implement filesystem store and artifact Pydantic models.
4. Add example experiments from the transfer seed.
5. Implement backend prompt rendering and Pydantic loading.
6. Implement generator runs with case-major repeat order and cache disabled.
7. Implement job progress and SSE.
8. Implement frontend experiment/runs views.
9. Implement single-version judgment.
10. Implement review decisions and human notes.
11. Implement proposal generation and create-next-version.
12. Implement deterministic validation-result comparison.
13. Add Carmilla exporter script after Prompt Lab import format is stable.
