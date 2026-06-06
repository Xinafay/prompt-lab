---
name: "prompt-lab-prompt-editing"
description: "Use when editing Prompt Lab experiment prompts, rubrics, judge prompts, proposal prompts, or prompt-facing Pydantic field descriptions."
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

## Quality Rules

- Prefer concrete operational rules over vague style requests.
- Use negative rules only for confusions observed in repeated runs.
- Distinguish recurring problems from one-off stochastic deviations.
- Do not treat unstable ids as a problem by itself unless ids collide, are invalid, misleading, or violate the rubric.
- Keep generated outputs neutral, factual, and scoped to later processing needs when the experiment is about extraction or summarization.
- Re-run the experiment with at least 3 uncached repeats after substantive prompt changes.

