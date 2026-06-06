# Transfer Checklist

Use this file when bootstrapping a standalone Prompt Lab repository from this seed.

## Already Included

- `DESIGN.md` - standalone product and implementation design.
- `FORMAT.md` - neutral experiment/case format.
- `IMPLEMENTATION_PLAN.md` - staged MVP implementation plan for a fresh agent conversation.
- `examples/` - two seed experiments:
  - `split-scenes` with Pydantic output;
  - `summarize-chapter` with text output.
- `backend/shared/llm/` - bundled LLM routing layer.
- `backend/tests/` - local/mock LLM tests and one live smoke probe.
- `backend/requirements.txt` and `backend/requirements-dev.txt`.
- `config/` - example `.servers.jsonc`, `.env`, and model list files.
- `.agents/skills/` - Prompt Lab specific runbooks.
- `AGENTS.md`, `.gitignore`, `pyrightconfig.json`.

## First Steps In The New Repository

1. Put these files at the new repository root.
2. Rename `config/servers.example.jsonc` to `.servers.jsonc` and adjust model servers.
3. Copy `config/env.example` to `.env` or export equivalent environment variables.
4. Create a Python virtual environment.
5. Install backend dependencies:

```bash
pip install -r backend/requirements-dev.txt
```

6. Run local LLM tests:

```bash
PYTHONPATH=backend python backend/tests/test_chat.py
PYTHONPATH=backend python backend/tests/test_chat_get_structured_lite.py
PYTHONPATH=backend python backend/tests/test_structured_lite_units.py
PYTHONPATH=backend python backend/tests/test_format_validation_errors.py
```

7. Run live smoke only after configuring reachable models:

```bash
PYTHONPATH=backend python backend/tests/test_chat_env.py
```

8. Start implementation from:

```text
IMPLEMENTATION_PLAN.md
```

## Keep Out Of Prompt Lab

Do not add Carmilla workflow runtime, Story Parser workflow classes, `WorkflowState`, or `FlatFileSystem` to Prompt Lab. Carmilla should export neutral bundles; Prompt Lab should import those bundles without knowing how they were produced.

## Later Extraction

The bundled `backend/shared/llm` module should eventually become a shared subrepo/package. Until then, keep application code behind a thin Prompt Lab wrapper so replacing the bundled module does not require broad edits.
