# Prompt Lab Frontend

The frontend is a React/Vite local tool UI for the Prompt Lab backend.

## Run

Install dependencies:

```bash
pnpm install
```

Start the dev server:

```bash
pnpm dev
```

The Vite dev server proxies `/api` to `http://127.0.0.1:8000`, so keep the backend running from the repository root:

```bash
PYTHONPATH=backend .venv/bin/python -m uvicorn prompt_lab.app:app --reload
```

Open or bookmark a specific experiment with:

```text
http://127.0.0.1:5173/?experiment=split-scenes
```

## Checks

```bash
pnpm lint
pnpm build
pnpm test:e2e
```

Playwright e2e tests use `demo-string` and `demo-json` examples. The Playwright
config starts the backend on `127.0.0.1:8000` and the Vite frontend on
`127.0.0.1:5173` when they are not already running.

## Workflow

The UI supports the MVP flow:

- list experiments;
- inspect the active version through `Prompt`, `Settings`, `Validators`, `Cases`, `Runs`, `Validation`, `Review`, `Proposal`, and `Compare` tabs;
- browse cases with title/id filtering, variable-key filtering, compact value previews, and collapsed raw JSON;
- run the active version and stream job progress over SSE;
- enable `Dry-run` in the workflow toolbar to exercise run, judge, proposal, and comparison paths without real model calls;
- scan run artifacts with status filters and a selected-run detail panel;
- judge latest runs;
- save accepted/rejected/deferred finding decisions and human notes;
- generate a prompt/model proposal;
- create the next version;
- compare baseline and candidate versions.
