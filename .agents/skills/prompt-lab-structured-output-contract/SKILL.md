---
name: "prompt-lab-structured-output-contract"
description: "Use when creating or changing Prompt Lab Pydantic models, validators, structured-output prompts, or model entrypoints."
---

# Prompt Lab Structured Output Contract

Use this skill when an experiment uses `output.type = "pydantic"` or when a text prompt is being converted to structured output.

## Quick Start

1. Treat the current prompt/rubric as the semantic source of truth.
2. Define or update `model.py` with explicit Pydantic fields and descriptions.
3. Keep the prompt's output instruction minimal and include exactly one literal `<<MODEL>>`.
4. Set `experiment.json`:

```json
{
  "output": {
    "type": "pydantic",
    "model_file": "model.py",
    "model_entrypoint": "model.YourModel"
  }
}
```

5. Use `prompt_lab.case/v2` cases with `stores` and `bindings`; Prompt Lab
   materializes that case context for both prompt rendering and Pydantic
   validation.
6. Preserve validation errors as run artifacts. They are evidence for prompt/model improvement.

## Contract Rules

- `<<MODEL>>` is the only place where the response model schema should enter the prompt. Do not also render `model_json_schema()` or a `*_SCHEMA_JSON` section for the same response model.
- Keep `<<MODEL>>` visible in the prompt template itself, not hidden in a Jinja variable supplied by Python code.
- Put the `<<MODEL>>` block near the end of the prompt, after contextual/evidence sections.
- Field order can affect LLM behavior; put fields in the order you want the model to reason about them.
- Field descriptions are prompt text. Keep them concrete and aligned with `prompt.md`.
- Validators should enforce hard constraints, not subjective quality preferences.
- Prefer prompt changes over model changes when the output shape is already adequate.
- Change `model.py` when accepted findings or human notes show missing fields, wrong field order, unclear descriptions, wrong types, or validator problems.
