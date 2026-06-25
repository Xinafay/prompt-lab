# Prompt Lab

Prompt Lab is a standalone local app for improving prompts through repeated
model runs, explicit validation, qualitative LLM judgment, human review,
proposal generation, and deterministic version comparison.

Prompt Lab stores experiments as filesystem artifacts. Carmilla or another external tool may export neutral experiment bundles into this repository, but Prompt Lab does not import Carmilla workflow runtime, workflow state, or workflow classes.

Cases are plain JSON objects grouped into Case Suites. Experiments point to one
suite with `case_suite_id`; the suite owns payload files, while each experiment
owns run inclusion through `run_defaults.excluded_case_ids`. See `FORMAT.md` for
the artifact contract.

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

Server prefixes are configured in `.servers.jsonc`. The tested, validation, and
judge models are selected per experiment in `experiment.json`:

```json
"models": {
  "generator_model": "local/qwen3-14b",
  "validator_model": "openai/gpt-5-mini",
  "judge_model": "openai/gpt-5-mini"
}
```

Model references use the `<server>/<model>` format, where `<server>` must match a
key in `.servers.jsonc`.

`examples/` contains committed golden templates split into
`examples/experiments/` and `examples/case_suites/`. On backend startup, Prompt
Lab seeds experiments and Case Suites with different overwrite rules. Experiment
seeding is workspace-style: if the runtime `experiments/` root already contains
any experiment manifests, committed example experiments are not copied over it.
Case Suite seeding is per-suite: missing example suite directories are copied
into an existing runtime `case_suites/` root, and existing runtime suite
directories are never overwritten. Runtime reads, generated artifacts, and
future GUI edits use `experiments/` and `case_suites/` only. Both runtime roots
are ignored by git.

Existing runtime experiments and existing runtime suite directories are not
migrated when committed examples change. Delete or move `experiments/` only when
you intentionally want to reseed the experiment workspace; delete or move a
specific runtime suite directory only when you intentionally want that suite
reseeded from examples.

Carmilla can export a complete Prompt Lab experiment directly from saved workflow
eval fixtures. From the Carmilla repository root, run:

```bash
python -m python.workflow_runtime.eval_runner \
  --workflow story_parser \
  --test split-scenes \
  --export-prompt-lab /Users/karol/Projects/sinafai/prompt-lab/examples/experiments/split-scenes
```

The export command writes the experiment manifest, validator definitions, and
initial version files for the experiment. Case payloads should live in a Case
Suite under `examples/case_suites/` and experiments should reference that suite
by `case_suite_id`. The exporter prints created, existing, and skipped file
events to stderr so callers can see what changed without parsing generated
files.

Each experiment version keeps one active workflow chain:

- Running a version replaces the previous active run artifacts for that version
  and clears downstream validations, reviews, proposals, and comparisons.
- Validating the active run replaces the previous active validation batch for
  that version. Validation results can be reviewed and excluded from judge input
  before judging.
- Judging the validated active run replaces the previous active review and
  clears its proposal.
- Generating a proposal writes it under the active review, so refreshes reload
  the current review and proposal instead of exposing a list of historical
  review IDs.
- Comparing versions reads their latest validation batches and returns a
  deterministic validation matrix. Compare does not call an LLM.

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
pnpm test
pnpm build
```

## Smoke Flow

1. Open the frontend.
2. Confirm `split-scenes` and `summarize-chapter` examples are listed.
3. Open `summarize-chapter` or use `?experiment=summarize-chapter`.
4. Optionally enable `Dry-run` in the workflow toolbar to generate deterministic artifacts without calling model providers.
5. Run the active version.
6. Validate the active run.
7. Review validation results and optionally exclude weak evidence, then save
   inclusion changes from the sticky workflow toolbar if prompted.
8. Judge the validated run.
9. Reject or defer at least one finding and add human notes, then save review
   changes from the sticky workflow toolbar if prompted.
10. Generate a proposal.
11. Create the next version.
12. Compare validation results between versions.

Live smoke requires configured model servers and may make real LLM calls:

```bash
CHAT_ENV_MODELS=local/qwen3-14b,openai/gpt-5-mini \
PYTHONPATH=backend .venv/bin/python backend/tests/test_chat_env.py
```
