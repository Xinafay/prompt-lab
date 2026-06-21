# Prompt Lab Artifact Format

This file documents the neutral artifact format used by committed examples and
the local `experiments/` runtime workspace.

Prompt Lab is independent from Carmilla runtime code. Carmilla may export these
artifacts, but Prompt Lab consumes only plain JSON files and prompt/model source
files.

## Experiment

```json
{
  "schema_version": "prompt_lab.experiment/v1",
  "id": "split-scenes",
  "title": "Split scenes",
  "description": "Split a chapter into contiguous structured scenes.",
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

Text-output experiments use:

```json
"output": {
  "type": "text"
}
```

Pydantic validation receives the same materialized case context that prompt
rendering uses.

## Directory Layout

An experiment directory keeps cases at the experiment level and version-specific
prompt/model files under `versions/`. Validator definitions live in
experiment-level `validators/` files and apply to every version:

```text
validators/
  scene-quality.json
  scene-count.json
cases/
  case-id.json
versions/v001/
  prompt.md
  model.py       # only for Pydantic experiments
```

State cases are shared by all versions. Creating a new version copies or writes
only prompt/model files; state inputs are not duplicated.

## Validators

Validators replace the old free-form rubric file in committed examples. Each
validator is a JSON file under `validators/` with schema version
`prompt_lab.validator/v1`.

LLM questionnaire validators ask `validator_model` to answer explicit checks:

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

Automatic validators run deterministic checks without an LLM:

```json
{
  "schema_version": "prompt_lab.validator/v1",
  "validator_id": "summary-length",
  "type": "automatic",
  "title": "Summary length",
  "enabled": true,
  "input_scope": "output_only",
  "checks": [
    {
      "check_id": "word-count",
      "title": "Word count",
      "rule": {
        "kind": "word_count",
        "source": "output_text",
        "comparison": {
          "op": "lte",
          "value": 180
        }
      }
    }
  ]
}
```

`input_scope` controls whether validator prompts receive only output, output plus
the rendered prompt, output plus case context, or all three. LLM validator
prompts omit run metadata and run status; they receive the questionnaire plus
one subject section: `OUTPUT_TEXT`, `OUTPUT_JSON`, or `INVALID_OUTPUT_TEXT` with
`VALIDATION_ERROR`. Runs with `execution_error` are not sent to LLM validators;
their validation results are saved as `skipped`. Automatic validators ignore
extra prompt/case scope and read the configured `source`.

Validation check results use `grade: 1..5 | null`, not pass/fail verdicts.
`5` means very good, `4` good, `3` acceptable but improvable, `2` weak,
`1` bad, and `null` not assessable from the provided evidence.

Supported automatic rule kinds include `word_count`, `sentence_count`,
`character_count`, `json_path_count`, and `json_path_exists`.

Validation is an explicit workflow stage after running a version and before
judging it. Users can review validation results and exclude weak validation
evidence before asking the judge model to synthesize findings.

## Case

Cases use `prompt_lab.case/v2`. A case represents one concrete prompt
invocation.

```json
{
  "schema_version": "prompt_lab.case/v2",
  "id": "case-id",
  "title": "Case title",
  "source": {
    "type": "carmilla.workflow_step_eval"
  },
  "stores": {
    "case": {
      "kind": "flat_file_tree",
      "values": {
        "chapter": {
          "__carmilla_flat_file_node__": "file",
          "value": {
            "title": "Chapter One",
            "paragraphs": ["..."]
          }
        }
      }
    }
  },
  "bindings": {
    "chapter": {
      "kind": "store_scope",
      "store": "case",
      "path": "chapter"
    },
    "current_entities": {
      "kind": "value",
      "value": ["Ada", "Mina"]
    }
  }
}
```

### Stores

`stores` hold serialized source data. The supported store kind is
`flat_file_tree`.

Flat-file tree directories are plain JSON objects. File leaves use this exact
shape:

```json
{
  "__carmilla_flat_file_node__": "file",
  "value": "any JSON value"
}
```

The explicit file-node wrapper is required so a directory named
`__carmilla_flat_file_node__` can still be represented without ambiguity.

### Bindings

`bindings` define the top-level names visible in jinjax prompt templates and in
Pydantic validation context.

`store_scope` binds a top-level name to a path inside a store:

```json
{
  "kind": "store_scope",
  "store": "case",
  "path": "chapter"
}
```

`value` binds a top-level name directly to a JSON value. Use it for computed
inputs that are produced during workflow-step replay and are not naturally stored
in the flat-file tree:

```json
{
  "kind": "value",
  "value": {
    "name": "Ada",
    "rank": 2
  }
}
```

Prompt Lab materializes `stores + bindings` into one plain dictionary before
rendering and validation. For the case above, templates can reference
`{{ chapter.title }}` and `{{ current_entities }}`.

## Version

```text
versions/v001/
  prompt.md
  model.py       # only for Pydantic experiments
```

Generated runs, validations, reviews, proposals, and comparisons are written
inside the version directory in the runtime `experiments/` workspace. Compare
artifacts are deterministic validation-result matrices; comparison does not call
an LLM or use `judge_model`.

Existing runtime experiments do not need migration. They remain local
filesystem artifacts; new validator files affect newly seeded or explicitly
edited experiments.
