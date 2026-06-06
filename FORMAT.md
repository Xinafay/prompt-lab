# Prompt Lab Example Format

This file documents the neutral artifact format used by the seed examples.
The full product design is in `docs/superpowers/specs/2026-06-06-prompt-lab-design.md`.

## Experiment

```json
{
  "schema_version": "prompt_lab.experiment/v1",
  "id": "split-scenes",
  "title": "Split scenes",
  "active_version": "v001",
  "output": {
    "type": "pydantic",
    "model_file": "model.py",
    "model_entrypoint": "model.SceneList",
    "validation_context_from_case": "structured_validation_context"
  },
  "template": {
    "engine": "jinja2",
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

## Case

```json
{
  "schema_version": "prompt_lab.case/v1",
  "id": "case-id",
  "title": "Case title",
  "variables": {},
  "structured_validation_context": {}
}
```

`structured_validation_context` is used only by Pydantic experiments.

## Version

```text
versions/v001/
  prompt.md
  model.py       # only for Pydantic experiments
  cases/
    case-id.json
```

Generated runs, reviews, proposals, and comparisons should be written inside the version directory when the application is implemented.

