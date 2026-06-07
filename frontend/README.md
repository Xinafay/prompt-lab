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

## Checks

```bash
pnpm lint
pnpm build
```

## Workflow

The UI supports the MVP flow:

- list experiments;
- inspect the active version prompt, rubric, cases, and run artifacts;
- run the active version and poll job progress;
- judge latest runs;
- save accepted/rejected/deferred finding decisions and human notes;
- generate a prompt/model proposal;
- create the next version;
- compare baseline and candidate versions.
