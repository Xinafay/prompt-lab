---
name: "prompt-lab-prompt-editing"
description: "Use when editing Prompt Lab experiment prompts, rubrics, validator prompts, judge prompts, proposal prompts, system prompt templates, or prompt-facing Pydantic field descriptions."
---

# Prompt Lab Prompt Editing

Use this skill when improving prompts or prompt-facing Pydantic model descriptions inside Prompt Lab experiments.

## Quick Start

1. Read the experiment `prompt.md`, `rubric.md`, and `model.py` if present.
2. Inspect recent runs and judge findings before editing.
3. Preserve the task scope unless the user explicitly changes it.
4. Keep prompts in English unless the user requests otherwise.
5. For structured output, keep `<<MODEL>>` as the schema marker.
6. If prompt changes alter field semantics, category boundaries, or allowed outputs, update `model.py` descriptions/validators if needed.
7. Create a new version instead of mutating a version that already has run artifacts.

## Structured Prompt Construction

- Put exactly one literal `<<MODEL>>` in every active structured-output prompt template.
- Keep `<<MODEL>>` visible in the `.jinja` or experiment `prompt.md`; do not hide it inside builder-provided variables.
- Place the `<<MODEL>>` block near the end of the prompt, after task evidence/context sections, so large schemas do not disrupt human-readable tables or instructions.
- Do not also inject `model_json_schema()` / `*_SCHEMA_JSON` when `<<MODEL>>` is present; the structured-output wrapper owns schema insertion.
- Runtime `rendered_prompt` artifacts for structured generator runs must contain the executed prompt after schema substitution. If an artifact still contains `<<MODEL>>`, rerun the generator before validation.
- Judge and proposal prompts embed generator prompts with `[OUTPUT_MODEL_SCHEMA: see CURRENT_MODEL_PY]` so their own final `<<MODEL>>` remains the judge/proposal response schema marker.
- Delete obsolete prompt templates and their artifact models/fake responses when the workflow no longer calls them.

## Quality Rules

- Prefer concrete operational rules over vague style requests.
- Use negative rules only for confusions observed in repeated runs.
- Distinguish recurring problems from one-off stochastic deviations.
- Do not treat unstable ids as a problem by itself unless ids collide, are invalid, misleading, or violate the rubric.
- Keep generated outputs neutral, factual, and scoped to later processing needs when the experiment is about extraction or summarization.
- Re-run the experiment with at least 3 uncached repeats after substantive prompt changes.
