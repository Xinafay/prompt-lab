# Agents Guide - Prompt Lab

Prompt Lab is a local-first tool for iterative prompt and Pydantic structured-output evaluation.

## Boundaries

- Keep Prompt Lab independent from Carmilla workflow runtime.
- Do not import `workflow_runtime`, Story Parser workflow classes, `WorkflowState`, or Carmilla flat-file workflow context.
- Carmilla is only an external producer of neutral experiment/case bundles.
- The bundled `backend/shared/llm` module should be treated as imported vendor code until it is replaced by a shared package or subrepo.
- Prefer making many small commits after changes so individual steps can be reverted easily if needed.

## Python

- Use `backend/shared/llm` through a thin Prompt Lab wrapper when implementing application code.
- Keep generator-run LLM cache disabled.
- Store validation errors as run artifacts; they are meaningful eval results.
- Use Pydantic models for artifact contracts.
- Prefer filesystem artifacts as the source of truth.

## Frontend

- Use React/Vite for the standalone UI.
- Keep UI text in English unless explicitly requested otherwise.
- Show run progress with current case and repeat.
- Show structured output as JSON and preserve raw output/validation errors.
- In-app browser automation may not visually trigger CSS hover tooltips even when
  the tooltip wrapper and accessible description are present; verify tooltip DOM
  state and, when needed, ask for/perform a manual visual check.

## Validation

From the future Prompt Lab repository root:

```bash
PYTHONPATH=backend python backend/tests/test_chat.py
PYTHONPATH=backend python backend/tests/test_chat_get_structured_lite.py
PYTHONPATH=backend python backend/tests/test_structured_lite_units.py
PYTHONPATH=backend python backend/tests/test_format_validation_errors.py
pyright --pythonpath .venv/bin/python
```
