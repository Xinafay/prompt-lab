# Prompt Lab Backend

The backend owns filesystem experiment storage, prompt rendering, Pydantic model loading, LLM calls, run artifacts, job progress, judgments, proposals, and comparisons.

The bundled `backend/shared/llm` module keeps its original `shared.llm` import path. Prompt Lab application code should access it through `prompt_lab.llm_client`, which keeps generator-run cache disabled.

## Run

From the repository root:

```bash
PYTHONPATH=backend .venv/bin/python -m uvicorn prompt_lab.app:app --reload
```

The API serves under `http://127.0.0.1:8000`.

## Dry-Run Workflows

Workflow endpoints default to live model calls. Send `{"dry_run": true}` to generate deterministic fake artifacts without provider transport:

```bash
curl -X POST http://127.0.0.1:8000/api/experiments/split-scenes/versions/v001/runs \
  -H 'content-type: application/json' \
  -d '{"dry_run": true}'

curl -X POST http://127.0.0.1:8000/api/experiments/split-scenes/versions/v001/judgments \
  -H 'content-type: application/json' \
  -d '{"dry_run": true}'
```

Proposal generation accepts the same body at the review proposal endpoint. Comparisons accept `dry_run` alongside `baseline_version` and `candidate_version`.

## Prompt Templates

Experiment prompts are rendered with the copied `shared.jinjax` package. Each
case uses `prompt_lab.case/v2`; the backend materializes its `stores + bindings`
into the plain context dictionary passed to prompt rendering and Pydantic
validation.

Cases live once per experiment under `cases/` and are shared by all versions.
Version directories hold the active prompt/model files plus generated run,
review, proposal, and comparison artifacts.

Judge, proposal, and comparison system prompts live in editable Markdown/Jinja files:

- `backend/prompt_lab/system_prompts/judge.md.jinja`
- `backend/prompt_lab/system_prompts/proposal.md.jinja`
- `backend/prompt_lab/system_prompts/comparison.md.jinja`

Python code builds structured context and renders these templates through `prompt_lab.prompt_templates`. Keep the structured-output marker `<<MODEL>>` in templates that rely on fake structured responses.

## Runtime Paths

Prompt Lab has two repository-local experiment roots:

- `examples/` - committed golden templates, used only to seed a new workspace.
- `experiments/` - local runtime workspace, ignored by git.

On backend startup, if `experiments/` does not exist or contains no
`*/experiment.json` manifests, Prompt Lab copies top-level example experiment
directories from `examples/` into `experiments/`. Once seeded, the backend lists,
loads, and writes only `experiments/`.

Carmilla exports complete Prompt Lab experiments through its eval runner. From
the Carmilla repository root:

```bash
python -m python.workflow_runtime.eval_runner \
  --workflow story_parser \
  --test split-scenes \
  --export-prompt-lab /Users/karol/Projects/sinafai/prompt-lab/examples/split-scenes
```

The command writes shared `cases/`, version files, and top-level experiment
metadata, then reports created, existing, and skipped file events to stderr.

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
CHAT_ENV_MODELS=local/qwen3-14b,openai/gpt-5-mini \
PYTHONPATH=backend .venv/bin/python backend/tests/test_chat_env.py
```
