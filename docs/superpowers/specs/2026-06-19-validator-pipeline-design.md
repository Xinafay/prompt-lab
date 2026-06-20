# Validator Pipeline Design

Date: 2026-06-19

## Purpose

Replace the current rubric-centered review flow with an explicit validator
pipeline. The current judge prompt is too broad because it performs result
analysis, evidence aggregation, prompt/model diagnosis, and proposal preparation
in one LLM call. Validators split the first part of that work into smaller,
traceable checks before the judge runs.

This is a breaking format change. Runtime experiment migration is not required.
Committed examples, format documentation, backend contracts, and frontend flow
will be updated to the new model.

## Goals

- Replace `rubric.md` with experiment-level validator definitions.
- Add an explicit required `Validate active run` stage between `Run` and
  `Judge`.
- Support LLM questionnaire validators and a small set of automatic validators
  in the first implementation.
- Keep room for human validators later without implementing them in this MVP.
- Let users include or ignore validation evidence before judge generation.
- Reduce the judge prompt by feeding it selected validation results instead of
  raw run outputs and a broad rubric.
- Replace LLM-based comparison with deterministic validation-result comparison.

## Non-Goals

- No migration of existing runtime experiments.
- No full UI editor for validator definitions in the MVP.
- No human validator execution UI in the MVP.
- No NLP dependency such as NLTK for automatic validators in the MVP.
- No LLM call for version comparison.

## Domain Model

An experiment defines validators in a new `validators/` directory:

```text
experiments/<experiment-id>/
  experiment.json
  validators/
    coverage.json
    length.json
  cases/
  versions/
    v001/
      prompt.md
      model.py
```

A validator is the executable unit. A check is the question or rule inside that
validator.

MVP validator types:

- `llm_questionnaire`: one LLM call per run artifact and validator. The model
  answers all checks in that validator.
- `automatic`: built-in deterministic rules.

Future validator type:

- `human_questionnaire`: manually answered checks. This should remain a planned
  extension, not an implemented MVP feature.

Each validator has:

- `validator_id`
- `type`
- `title`
- `description`
- `enabled`
- `input_scope`
- `checks`

`enabled` controls whether the validator runs during validation. It does not
affect already saved validation results.

`input_scope` controls context size:

- `output_only`
- `output_and_prompt`
- `output_and_case`
- `output_prompt_and_case`

Each check has:

- `check_id`
- `title`
- `question` or rule configuration
- optional description

## Models

`experiment.json` gets a separate validator model:

```json
{
  "models": {
    "generator_model": "local/qwen3-14b",
    "validator_model": "openai/gpt-5-mini",
    "judge_model": "openai/gpt-5"
  }
}
```

Global settings get:

```json
{
  "default_generator_model": "...",
  "default_validator_model": "...",
  "default_judge_model": "..."
}
```

When examples are seeded into runtime experiments, `validator_model` is set from
`default_validator_model` in the same way generator and judge defaults are
applied today.

## Automatic Validators

The MVP automatic validator rule set is intentionally small:

- `word_count`
- `sentence_count`
- `character_count`
- `json_path_count`
- `json_path_exists`

Count rules support basic comparisons such as `lt`, `lte`, `gt`, `gte`, and
`between`.

`sentence_count` uses a simple local heuristic rather than an NLP package. This
is enough to exercise the backend/frontend flow for a second validator type
without expanding the dependency surface.

## Validation Results

Validation is a required stage between run and judge:

```text
Run -> Validate -> Review validation results -> Judge -> Review judge findings -> Proposal
```

Running a version clears downstream generated state:

- `validations/`
- `reviews/`
- `comparisons/`

Validation creates a validation batch under the active version:

```text
versions/v001/validations/<validation-batch-id>/
  batch.json
  validators_snapshot/
    coverage.json
    length.json
  <case-id>/
    repeat-001/
      coverage.json
      length.json
```

`batch.json` records:

- schema version
- validation batch id
- run batch id
- version
- status
- started/finished timestamps
- total/completed units
- validator model
- validator ids that were enabled and executed

The validator snapshot is required. Validator definitions can change over time,
and historical validation results must remain interpretable.

A validation result is saved per:

```text
run_batch_id * case_id * repeat_index * validator_id
```

Each validation result records:

- schema version
- validation result id
- validation batch id
- run batch id
- run id
- case id
- repeat index
- validator id
- validator type
- status: `ok`, `error`, or `skipped`
- `included_in_judge`
- check results
- usage metadata for LLM validators
- optional execution error or skip reason

Each check result records:

- check id
- grade: `1`, `2`, `3`, `4`, `5`, or `null`
- comment
- metrics for automatic validators
- `included_in_judge`

Automatic validators should normally produce only `5` or `1`. LLM validators
may produce `null` when the evidence is not assessable. If the generator run has
`execution_error`, validators are not executed and the result is saved as
`skipped` with `included_in_judge=false`. If the generator run has
`validation_error`, LLM validators receive the invalid raw output and validation
error as the subject being checked.

`pending` should be reserved for the future `human_questionnaire` type and
should not be emitted by the MVP implementation.

Effective inclusion is:

```text
validation_result.included_in_judge && check_result.included_in_judge
```

This supports a checkbox for the whole validator result and separate check-level
checkboxes. Disabling the whole result excludes all checks without needing to
overwrite their individual settings.

## LLM Questionnaire Prompting

The LLM questionnaire prompt includes:

- validator definition and checks
- exact expected check ids
- run metadata
- run status
- generator validation or execution errors
- selected output fields according to `input_scope`
- optional rendered prompt according to `input_scope`
- optional materialized case context according to `input_scope`
- response schema

The response must include one result for every check id. Missing, duplicate, or
unknown check ids are response validation errors and should become validation
result errors, not suite failures.

The validator prompt should not ask for prompt improvement. It answers only the
validator checks.

## Judge Flow

Judge requires an existing validation batch. It no longer reads `rubric.md` and
does not receive raw run outputs by default.

Judge input includes:

- source prompt
- `model.py` for Pydantic experiments
- output declaration
- validation batch metadata
- validator/check snapshots
- effectively included check results only
- run statuses
- generator validation errors and execution errors

Judge remains responsible for synthesis:

- what looks correct
- recurring problems
- one-off deviations
- validation/schema issues
- suggested prompt/model changes
- regression risks
- user decision points

Human decisions stay at the judge finding level. Accepted findings feed proposal
generation. Rejected findings become constraints. Deferred findings are ignored
unless human notes mention them. Human notes override judge findings.

## Proposal Flow

Proposal generation remains a separate stage under a review. It still consumes:

- current prompt
- current model source when present
- accepted judge findings
- rejected judge findings as constraints
- human notes

It no longer receives `rubric_snapshot.md`. Instead, proposal source metadata
and prompt context should include:

- validation batch id
- validator snapshots
- included validation evidence used by judge

Proposal generation should still prefer prompt changes over `model.py` changes
when the output contract is adequate. `model.py` changes are appropriate when
accepted findings or human notes show missing fields, wrong field order, unclear
descriptions, wrong types, or validator behavior problems.

## Compare Flow

Comparison becomes deterministic and uses validation results, not an LLM.

The compare UI lets the user choose two or more versions. For each version, the
backend uses its latest validation batch. It returns a matrix grouped by
validator, with rows for checks and columns for versions.

Each cell includes aggregate counts over included validation evidence:

- grade 5 count
- grade 4 count
- grade 3 count
- grade 2 count
- grade 1 count
- not assessable count
- missing count, with room for future pending human-validator data
- error count
- total count
- detail rows with case id, repeat index, grade, and comment

Initial cell status rules:

- green/pass: all assessable included grades are `4` or `5`, with no null,
  missing, pending, or error data
- red/fail: at least one included result is grade `1` or `2`
- yellow/mixed: grade `3`, not assessable data, missing data, future `pending`
  data, or errors, when no grade `1` or `2` is present
- gray/empty: no included data

The UI can show compact grade distributions in the table cell, such as
`8/9 grade 5, 1 grade 1`, and expand or click through to case/repeat details.

No LLM call is made for compare.

## UI Flow

The frontend gets a `Validation` tab between `Runs` and `Review`.

Workflow actions become:

- `Run version`
- `Validate active run`
- `Judge validated run`
- `Generate proposal`
- `Compare versions`

`Review` is disabled until a validation batch exists. `Proposal` remains
disabled until review decisions and human notes are saved.

The Validation tab shows:

- latest validation batch metadata
- enabled validator list and statuses
- grouped validation results by case/repeat and validator
- check grades and comments
- result-level and check-level `included in judge` checkboxes
- save action for inclusion edits

Validator definition editing can remain file-based in the MVP. A simple
enable/disable UI may be added if it stays small, but a full question/rule editor
is out of scope.

## API Shape

Expected API additions and changes:

- `GET /api/experiments/{experiment_id}/validators`
- `POST /api/experiments/{experiment_id}/versions/{version}/validations`
- `GET /api/experiments/{experiment_id}/versions/{version}/validations/latest`
- `PUT /api/experiments/{experiment_id}/versions/{version}/validations/{validation_batch_id}/inclusion`
- `POST /api/experiments/{experiment_id}/versions/{version}/judgments`
  requires a validation batch
- compare endpoint returns deterministic validation matrix data

Existing run, review decision, human notes, proposal, and create-version APIs
remain conceptually similar, but their payloads stop referencing rubric
snapshots.

## Examples

`split-scenes` should define:

- an LLM questionnaire for scene quality:
  - coverage of source content
  - scene order
  - scene boundary quality
  - no hallucinated events
  - concise titles and summaries
- automatic checks such as:
  - `json_path_count` for `scenes`
  - optional title/summary length checks when useful

The scene-quality validator should use `output_and_case` because it needs source
case context.

`summarize-chapter` should define:

- an LLM questionnaire for completeness, hallucination avoidance, and usefulness
  as context for later processing
- automatic `word_count` or `sentence_count`

Committed examples should be updated to the new format. Runtime experiments do
not need migration.

## Testing

Backend tests should cover:

- Pydantic validation for validator definitions
- Pydantic validation for validation batches and results
- automatic validator rule execution
- LLM questionnaire prompt construction and `input_scope`
- dry-run or fake-LLM `Validate active run`
- inclusion updates at result and check level
- judge prompt construction without raw outputs and without rubric
- proposal prompt construction without rubric snapshot
- deterministic compare matrix aggregation and statuses
- global settings and seeding for `default_validator_model`

Frontend tests should cover:

- workflow action states around validation and judge
- validation inclusion state changes
- compare cell status/color logic
- proposal disabled state with unsaved review changes

## Implementation Notes

`backend/prompt_lab/api.py` is already large. Implementation should introduce
focused modules instead of adding all validation behavior to that file:

- `backend/prompt_lab/models/validators.py`
- `backend/prompt_lab/validation.py`
- `backend/prompt_lab/automatic_validators.py`
- `backend/prompt_lab/system_prompts/validator.md.jinja`

The existing `backend/shared/llm` module remains vendor code and should be used
through the Prompt Lab wrapper.

Generator-run LLM cache remains disabled.

Validation and parsing errors are meaningful eval artifacts. They should be
stored as run or validation artifacts, not treated as suite-level failures.

## Acceptance Criteria

- New examples run without `rubric.md` as a required input.
- An experiment can run, validate, judge, generate a proposal, and compare
  versions through the UI.
- Judge prompts include selected validation evidence and exclude raw outputs by
  default.
- Compare does not call an LLM.
- Validator model defaults are configurable globally and saved in experiment
  manifests.
- Validation results can be excluded from judge at result and check granularity.
