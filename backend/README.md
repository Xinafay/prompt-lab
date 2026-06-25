# Prompt Lab Backend

The backend owns filesystem experiment storage, prompt rendering, Pydantic model
loading, LLM calls, run artifacts, validator execution, job progress, judgments,
proposals, and deterministic comparisons.

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

curl -X POST http://127.0.0.1:8000/api/experiments/split-scenes/versions/v001/validations \
  -H 'content-type: application/json' \
  -d '{"dry_run": true}'

curl -X POST http://127.0.0.1:8000/api/experiments/split-scenes/versions/v001/judgments \
  -H 'content-type: application/json' \
  -d '{"dry_run": true}'
```

Proposal generation accepts the same body at the review proposal endpoint.
Comparisons use saved validation batches and return a deterministic matrix; no
comparison model call is made.

## Prompt Templates

Experiment prompts are rendered with the copied `shared.jinjax` package. Each
case is a plain JSON object, and the backend passes it directly as the context
dictionary for prompt rendering and Pydantic validation.

Cases live in Case Suites under `case_suites/<suite_id>/cases/` and are shared
by every experiment that references the suite with `case_suite_id`. Experiments
own run inclusion through `run_defaults.excluded_case_ids`. Version directories
hold the active prompt/model files plus generated run, validation, review,
proposal, and comparison artifacts.

Validator, judge, and proposal system prompts live in editable Markdown/Jinja files:

- `backend/prompt_lab/system_prompts/validator.md.jinja`
- `backend/prompt_lab/system_prompts/judge.md.jinja`
- `backend/prompt_lab/system_prompts/proposal.md.jinja`

Python code builds structured context and renders these templates through `prompt_lab.prompt_templates`. Keep the structured-output marker `<<MODEL>>` in templates that rely on fake structured responses.

## Runtime Paths

Prompt Lab has repository-local experiment and Case Suite roots:

- `examples/experiments/` - committed golden experiment templates.
- `examples/case_suites/` - committed golden Case Suite templates.
- `experiments/` - local runtime experiment workspace, ignored by git.
- `case_suites/` - local runtime Case Suite workspace, ignored by git.

On backend startup, Prompt Lab independently seeds experiments and Case Suites.
Experiment seeding is workspace-style: if `experiments/` already contains any
`*/experiment.json` manifests, example experiments are not copied over the
runtime workspace. Case Suite seeding is per-suite: missing example suite
directories from `examples/case_suites/` are copied into the runtime
`case_suites/` root, and existing runtime suite directories are never
overwritten. Once seeded, the backend lists, loads, and writes only the runtime
roots.

Carmilla exports complete Prompt Lab experiments through its eval runner. From
the Carmilla repository root:

```bash
python -m python.workflow_runtime.eval_runner \
  --workflow story_parser \
  --test split-scenes \
  --export-prompt-lab /Users/karol/Projects/sinafai/prompt-lab/examples/experiments/split-scenes
```

The command writes validator definitions, version files, and top-level
experiment metadata. Case payloads belong in a Case Suite under
`examples/case_suites/`, with the experiment manifest referencing that suite by
`case_suite_id`. The exporter reports created, existing, and skipped file events
to stderr.

Existing runtime experiments and existing runtime suite directories are not
migrated when examples change. The backend may add newly missing example suites
to `case_suites/`, but it leaves any existing runtime suite directory untouched
unless the user edits or replaces it.

Environment overrides:

- `PROMPT_LAB_EXPERIMENTS_ROOT`
- `PROMPT_LAB_EXAMPLES_ROOT`
- `PROMPT_LAB_CASE_SUITES_ROOT`

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
PYTHONPATH=backend .venv/bin/python backend/tests/test_validators.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_proposal.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_compare.py
```

Live smoke with real models is intentionally separate:

```bash
CHAT_ENV_MODELS=local/qwen3-14b,openai/gpt-5-mini \
PYTHONPATH=backend .venv/bin/python backend/tests/test_chat_env.py
```
