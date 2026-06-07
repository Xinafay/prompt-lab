# Prompt Lab Backend

The backend owns filesystem experiment storage, prompt rendering, Pydantic model loading, LLM calls, run artifacts, job progress, judgments, proposals, and comparisons.

The bundled `backend/shared/llm` module keeps its original `shared.llm` import path. Prompt Lab application code should access it through `prompt_lab.llm_client`, which keeps generator-run cache disabled.

## Run

From the repository root:

```bash
PYTHONPATH=backend .venv/bin/python -m uvicorn prompt_lab.app:app --reload
```

The API serves under `http://127.0.0.1:8000`.

## Runtime Paths

Prompt Lab defaults to repository-local paths:

- `experiments/`
- `examples/`

Environment overrides:

- `PROMPT_LAB_EXPERIMENTS_ROOT`
- `PROMPT_LAB_EXAMPLES_ROOT`

## Checks

Core backend checks:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_chat.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_chat_get_structured_lite.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_structured_lite_units.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_format_validation_errors.py
.venv/bin/pyright --project pyrightconfig.json --pythonpath .venv/bin/python
```

Feature tests can be run directly, for example:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_api.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_runner.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_judge.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_proposal.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_compare.py
```

Live smoke with real models is intentionally separate:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_chat_env.py
```
