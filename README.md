# Prompt Lab

Prompt Lab is a standalone local app for improving prompts through repeated model runs, qualitative LLM judgment, human review, proposal generation, and version comparison.

Prompt Lab stores experiments as filesystem artifacts. Carmilla or another external tool may export neutral experiment bundles into this repository, but Prompt Lab does not import Carmilla workflow runtime, workflow state, or workflow classes.

## Setup

Create or activate the Python environment, then install backend dependencies:

```bash
.venv/bin/python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
```

Copy and edit local configuration templates when running against real models:

```bash
cp config/servers.example.jsonc .servers.jsonc
cp config/models.example.jsonc .models.jsonc
cp config/env.example .env
```

Install frontend dependencies:

```bash
cd frontend
pnpm install
```

## Run Locally

Start the backend from the repository root:

```bash
PYTHONPATH=backend .venv/bin/python -m uvicorn prompt_lab.app:app --reload
```

Start the frontend in another terminal:

```bash
cd frontend
pnpm dev
```

The Vite app proxies `/api` to `http://127.0.0.1:8000`.

## Local Checks

Backend regression checks:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_chat.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_chat_get_structured_lite.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_structured_lite_units.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_format_validation_errors.py
.venv/bin/pyright --project pyrightconfig.json --pythonpath .venv/bin/python
```

Frontend checks:

```bash
cd frontend
pnpm lint
pnpm build
```

## Smoke Flow

1. Open the frontend.
2. Confirm `split-scenes` and `summarize-chapter` examples are listed.
3. Open `summarize-chapter`.
4. Run the active version.
5. Confirm progress shows the current case/repeat and run artifacts appear.
6. Judge the latest runs.
7. Reject or defer at least one finding and add human notes.
8. Generate a proposal.
9. Create the next version.
10. Compare the new version with `v001`.

Live smoke requires configured model servers and may make real LLM calls:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_chat_env.py
```
