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
  cases/
    case-id.json
```

Generated runs, reviews, proposals, and comparisons are written inside the
version directory in the runtime `experiments/` workspace.
