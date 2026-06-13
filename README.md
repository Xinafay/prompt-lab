# Prompt Lab

Prompt Lab is a standalone local app for improving prompts through repeated model runs, qualitative LLM judgment, human review, proposal generation, and version comparison.

Prompt Lab stores experiments as filesystem artifacts. Carmilla or another external tool may export neutral experiment bundles into this repository, but Prompt Lab does not import Carmilla workflow runtime, workflow state, or workflow classes.

The current case format is `prompt_lab.case/v2`. Cases contain serialized
`stores` and prompt-visible `bindings`; Prompt Lab materializes them into one
plain context dictionary for both jinjax prompt rendering and Pydantic
validation. See `FORMAT.md` for the artifact contract.

## Setup

Create or activate the Python environment, then install backend dependencies:

```bash
.venv/bin/python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
```

Copy and edit local configuration templates when running against real models:

```bash
cp config/servers.example.jsonc .servers.jsonc
cp config/env.example .env
```

Server prefixes are configured in `.servers.jsonc`. The tested model and judge
model are selected per experiment in `experiment.json`:

```json
"models": {
  "generator_model": "local/qwen3-14b",
  "judge_model": "openai/gpt-5-mini"
}
```

Model references use the `<server>/<model>` format, where `<server>` must match a
key in `.servers.jsonc`.

`examples/` contains committed golden templates. On backend startup, if
`experiments/` does not exist or contains no `*/experiment.json` manifests, Prompt
Lab copies examples into `experiments/`. Runtime reads, generated artifacts, and
future GUI edits use `experiments/` only. The `experiments/` directory is ignored
by git.

Each experiment version keeps one active workflow chain:

- Running a version replaces the previous active run artifacts for that version
  and clears downstream reviews, proposals, and comparisons.
- Judging the active run replaces the previous active review and clears its
  proposal.
- Generating a proposal writes it under the active review, so refreshes reload
  the current review and proposal instead of exposing a list of historical
  review IDs.

Technical artifact IDs such as run batch IDs and review IDs may still appear in
API responses and filesystem paths for debugging, but the UI treats them as the
current active artifacts.

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

Open a specific experiment by adding the experiment query parameter:

```text
http://127.0.0.1:5173/?experiment=split-scenes
```

The UI keeps the selected experiment in this parameter so refreshes preserve the current workspace.
Use the `Version` selector in the workflow toolbar to switch the experiment's
active version. Switching versions updates `experiment.json`, reloads the
version overview, and keeps the existing per-version run/review/proposal
artifacts on disk.

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
3. Open `summarize-chapter` or use `?experiment=summarize-chapter`.
4. Optionally enable `Dry-run` in the workflow toolbar to generate deterministic artifacts without calling model providers.
5. Run the active version.
6. Confirm progress shows the current case/repeat and the active run appears in the `Runs` tab.
7. Judge the active run.
8. Reject or defer at least one finding and add human notes.
9. Generate a proposal.
10. Create the next version.
11. Switch to the new version with the toolbar `Version` selector.
12. Compare the new version with `v001`.

Live smoke requires configured model servers and may make real LLM calls:

```bash
CHAT_ENV_MODELS=local/qwen3-14b,openai/gpt-5-mini \
PYTHONPATH=backend .venv/bin/python backend/tests/test_chat_env.py
```
