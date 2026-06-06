# Prompt Lab MVP Rollout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute `IMPLEMENTATION_PLAN.md` in a controlled order that produces a working Prompt Lab MVP with verified backend artifacts, local LLM wrapper boundaries, REST/SSE workflow, and React/Vite UI.

**Architecture:** Treat `IMPLEMENTATION_PLAN.md` as the code-level source of truth and this document as the rollout layer. Build a thin vertical slice first: filesystem artifacts -> prompt rendering -> LLM wrapper -> runs -> API. Add review, proposal, comparison, and frontend only after the run pipeline is stable.

**Tech Stack:** Python 3.14, FastAPI, Pydantic v2, Jinja2, copied `backend/shared/llm`, React, Vite, TypeScript, filesystem artifacts, SSE, direct Python test scripts, pyright.

---

## Source Plan

Use `/Users/karol/Projects/sinafai/prompt-lab/IMPLEMENTATION_PLAN.md` as the implementation script.

Relevant task map:

- Task 1: Repository Bootstrap
- Task 2: Artifact Pydantic Models
- Task 3: Filesystem Storage
- Task 4: Prompt Rendering
- Task 5: Pydantic Model Loader
- Task 6: LLM Client Wrapper
- Task 7: Generator Runner
- Task 8: In-Process Jobs And SSE Events
- Task 9: Backend API Skeleton
- Task 10: Run Version Endpoint
- Task 11: Structured Run Endpoint
- Task 12: Judgment Models
- Task 13: Single-Version Judge
- Task 14: Review Decisions And Human Notes
- Task 15: Proposal Generation
- Task 16: Comparison Judgment
- Task 17: Frontend Scaffold
- Task 18: Frontend Experiment Overview And Runs
- Task 19: Frontend Review, Proposal, And Comparison Views
- Task 20: End-To-End Local Smoke

## Execution Strategy

Run in five phases:

1. Backend foundations: Tasks 1-6.
2. Run pipeline vertical slice: Tasks 7-11.
3. Review intelligence workflow: Tasks 12-16.
4. Frontend workflow UI: Tasks 17-19.
5. End-to-end smoke and docs: Task 20.

Do not start frontend implementation before the backend has at least Task 9 complete. Prefer waiting until Task 16 before building full review/proposal/comparison UI, unless using frontend mocks deliberately.

Use one commit per `IMPLEMENTATION_PLAN.md` task, matching the commit messages already specified there.

## Files Created By This Rollout

- Create: `backend/prompt_lab/__init__.py`
- Create: `backend/prompt_lab/app.py`
- Create: `backend/prompt_lab/api.py`
- Create: `backend/prompt_lab/config.py`
- Create: `backend/prompt_lab/errors.py`
- Create: `backend/prompt_lab/template_renderer.py`
- Create: `backend/prompt_lab/pydantic_loader.py`
- Create: `backend/prompt_lab/llm_client.py`
- Create: `backend/prompt_lab/storage.py`
- Create: `backend/prompt_lab/runner.py`
- Create: `backend/prompt_lab/jobs.py`
- Create: `backend/prompt_lab/judge.py`
- Create: `backend/prompt_lab/compare.py`
- Create: `backend/prompt_lab/proposal.py`
- Create: `backend/prompt_lab/models/__init__.py`
- Create: `backend/prompt_lab/models/artifacts.py`
- Create: `backend/prompt_lab/models/api.py` for request and response contracts that are shared by multiple API endpoints.
- Create: `backend/prompt_lab/models/judgments.py`
- Create: `backend/tests/test_config.py`
- Create: `backend/tests/test_artifacts.py`
- Create: `backend/tests/test_storage.py`
- Create: `backend/tests/test_template_renderer.py`
- Create: `backend/tests/test_pydantic_loader.py`
- Create: `backend/tests/test_llm_client.py`
- Create: `backend/tests/test_runner.py`
- Create: `backend/tests/test_jobs.py`
- Create: `backend/tests/test_judge.py`
- Create: `backend/tests/test_reviews.py`
- Create: `backend/tests/test_proposal.py`
- Create: `backend/tests/test_compare.py`
- Create: `backend/tests/test_api.py`
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/api.ts`
- Create: `frontend/src/types.ts`
- Create: `frontend/src/styles.css`
- Create: `frontend/src/components/ExperimentsList.tsx`
- Create: `frontend/src/components/ExperimentOverview.tsx`
- Create: `frontend/src/components/RunsView.tsx`
- Create: `frontend/src/components/RunDetail.tsx` for readable JSON, raw output, validation error, and rendered prompt inspection.
- Create: `frontend/src/components/ReviewView.tsx`
- Create: `frontend/src/components/ProposalView.tsx`
- Create: `frontend/src/components/ComparisonView.tsx`
- Modify: `backend/README.md`
- Modify: `backend/requirements-dev.txt`
- Modify: `README.md`
- Modify: `pyrightconfig.json` only if imports require it.

Do not modify or import Carmilla runtime files. `backend/shared/llm` remains treated as vendor code and must be reached through `backend/prompt_lab/llm_client.py`.

---

### Task 0: Preflight And Branch Hygiene

**Files:**
- Read: `AGENTS.md`
- Read: `IMPLEMENTATION_PLAN.md`
- Read: `DESIGN.md`
- Read: `FORMAT.md`
- Read: `pyrightconfig.json`
- Read: `backend/requirements.txt`
- Read: `backend/requirements-dev.txt`

- [ ] **Step 1: Confirm repository state**

Run:

```bash
git status --short
```

Expected: either no output or only user-known unrelated changes. Do not revert unrelated changes.

- [ ] **Step 2: Confirm baseline tests**

Run:

```bash
PYTHONPATH=backend python backend/tests/test_chat.py
PYTHONPATH=backend python backend/tests/test_chat_get_structured_lite.py
PYTHONPATH=backend python backend/tests/test_structured_lite_units.py
PYTHONPATH=backend python backend/tests/test_format_validation_errors.py
```

Expected: all pass before adding Prompt Lab application code. If a baseline fails, stop and debug that failure before continuing, because later failures will be harder to attribute.

- [ ] **Step 3: Confirm pyright availability**

Run:

```bash
pyright --project pyrightconfig.json --pythonpath .venv/bin/python
```

Expected: pass or a clear environment error. If pyright is not installed, record that blocker and continue backend test-first implementation.

---

### Task 1: Backend Foundation Pass

**Files:**
- Create/modify the files listed in `IMPLEMENTATION_PLAN.md` Tasks 1-6.

- [ ] **Step 1: Execute Task 1 exactly**

Implement repository bootstrap from `IMPLEMENTATION_PLAN.md` Task 1.

Run:

```bash
PYTHONPATH=backend python backend/tests/test_config.py
```

Expected: both config tests print `OK`.

- [ ] **Step 2: Execute Task 2 exactly**

Implement artifact Pydantic contracts from `IMPLEMENTATION_PLAN.md` Task 2.

Run:

```bash
PYTHONPATH=backend python backend/tests/test_artifacts.py
```

Expected: artifact validation tests print `OK`.

- [ ] **Step 3: Execute Task 3 exactly**

Implement filesystem storage from `IMPLEMENTATION_PLAN.md` Task 3.

Run:

```bash
PYTHONPATH=backend python backend/tests/test_storage.py
```

Expected: storage tests print `OK`.

- [ ] **Step 4: Execute Task 4 exactly**

Implement Jinja2 rendering from `IMPLEMENTATION_PLAN.md` Task 4.

Run:

```bash
PYTHONPATH=backend python backend/tests/test_template_renderer.py
```

Expected: renderer tests print `OK`.

- [ ] **Step 5: Execute Task 5 exactly**

Implement local Pydantic model loading from `IMPLEMENTATION_PLAN.md` Task 5.

Run:

```bash
PYTHONPATH=backend python backend/tests/test_pydantic_loader.py
```

Expected: loader test prints `OK`.

- [ ] **Step 6: Execute Task 6 exactly**

Implement the `shared.llm` wrapper from `IMPLEMENTATION_PLAN.md` Task 6.

Run:

```bash
PYTHONPATH=backend python backend/tests/test_llm_client.py
```

Expected: wrapper tests print `OK` and confirm `cache_enabled=False`.

- [ ] **Step 7: Run foundation regression gate**

Run:

```bash
PYTHONPATH=backend python backend/tests/test_chat.py
PYTHONPATH=backend python backend/tests/test_chat_get_structured_lite.py
PYTHONPATH=backend python backend/tests/test_structured_lite_units.py
PYTHONPATH=backend python backend/tests/test_format_validation_errors.py
pyright --project pyrightconfig.json --pythonpath .venv/bin/python
```

Expected: all available checks pass. If pyright is unavailable, record it in the task notes before committing.

---

### Task 2: Run Pipeline Vertical Slice

**Files:**
- Create/modify the files listed in `IMPLEMENTATION_PLAN.md` Tasks 7-11.

- [ ] **Step 1: Execute Task 7 exactly**

Implement text and structured case runners from `IMPLEMENTATION_PLAN.md` Task 7.

Run:

```bash
PYTHONPATH=backend python backend/tests/test_runner.py
```

Expected: case-major order, text output, and structured JSON output tests print `OK`.

- [ ] **Step 2: Execute Task 8 exactly**

Implement in-memory jobs from `IMPLEMENTATION_PLAN.md` Task 8.

Run:

```bash
PYTHONPATH=backend python backend/tests/test_jobs.py
```

Expected: progress and completion tests print `OK`.

- [ ] **Step 3: Execute Task 9 exactly**

Implement the FastAPI app skeleton from `IMPLEMENTATION_PLAN.md` Task 9.

Run:

```bash
PYTHONPATH=backend python backend/tests/test_api.py
```

Expected: `/api/experiments` returns the temp example.

- [ ] **Step 4: Execute Task 10 exactly**

Implement text version run endpoint from `IMPLEMENTATION_PLAN.md` Task 10.

Run:

```bash
PYTHONPATH=backend python backend/tests/test_api.py
```

Expected: starting a text run returns a `run_version` job and writes run artifacts. Use a monkeypatched LLM boundary in tests so this does not call a live model.

- [ ] **Step 5: Execute Task 11 exactly**

Implement Pydantic version run endpoint from `IMPLEMENTATION_PLAN.md` Task 11.

Run:

```bash
PYTHONPATH=backend python backend/tests/test_api.py
```

Expected: the copied `examples/split-scenes` fixture can run with a fake structured generator and produce `output_json`.

- [ ] **Step 6: Run pipeline regression gate**

Run:

```bash
PYTHONPATH=backend python backend/tests/test_config.py
PYTHONPATH=backend python backend/tests/test_artifacts.py
PYTHONPATH=backend python backend/tests/test_storage.py
PYTHONPATH=backend python backend/tests/test_template_renderer.py
PYTHONPATH=backend python backend/tests/test_pydantic_loader.py
PYTHONPATH=backend python backend/tests/test_llm_client.py
PYTHONPATH=backend python backend/tests/test_runner.py
PYTHONPATH=backend python backend/tests/test_jobs.py
PYTHONPATH=backend python backend/tests/test_api.py
PYTHONPATH=backend python backend/tests/test_chat.py
PYTHONPATH=backend python backend/tests/test_chat_get_structured_lite.py
PYTHONPATH=backend python backend/tests/test_structured_lite_units.py
PYTHONPATH=backend python backend/tests/test_format_validation_errors.py
pyright --project pyrightconfig.json --pythonpath .venv/bin/python
```

Expected: run pipeline is stable before building review/proposal features.

---

### Task 3: Review, Proposal, And Comparison Pass

**Files:**
- Create/modify the files listed in `IMPLEMENTATION_PLAN.md` Tasks 12-16.

- [ ] **Step 1: Execute Task 12 exactly**

Implement judgment and decision Pydantic models from `IMPLEMENTATION_PLAN.md` Task 12.

Run:

```bash
PYTHONPATH=backend python backend/tests/test_judge.py
```

Expected: judgment validation and default accepted decisions pass.

- [ ] **Step 2: Execute Task 13 exactly**

Implement judge prompt builder and judgment endpoint from `IMPLEMENTATION_PLAN.md` Task 13.

Run:

```bash
PYTHONPATH=backend python backend/tests/test_judge.py
```

Expected: judge prompt includes rubric, prompt, cases, repeated outputs, validation errors, and fake structured judgment creates review artifacts.

- [ ] **Step 3: Execute Task 14 exactly**

Implement review decisions and human notes endpoints from `IMPLEMENTATION_PLAN.md` Task 14.

Run:

```bash
PYTHONPATH=backend python backend/tests/test_reviews.py
```

Expected: decisions can be updated, `human_notes.md` can be saved, and review state can be read.

- [ ] **Step 4: Execute Task 15 exactly**

Implement proposal prompt builder, proposal endpoint, and create-next-version endpoint from `IMPLEMENTATION_PLAN.md` Task 15.

Run:

```bash
PYTHONPATH=backend python backend/tests/test_proposal.py
```

Expected: proposal input respects accepted findings, rejected constraints, deferred omissions, human notes precedence, and creates `vNNN` without mutating the current version.

- [ ] **Step 5: Execute Task 16 exactly**

Implement comparison models, comparison prompt, and comparison endpoint from `IMPLEMENTATION_PLAN.md` Task 16.

Run:

```bash
PYTHONPATH=backend python backend/tests/test_compare.py
```

Expected: comparison prompt includes baseline and candidate material and evaluates semantic quality and stability rather than literal id equality.

- [ ] **Step 6: Run backend MVP gate**

Run:

```bash
PYTHONPATH=backend python backend/tests/test_config.py
PYTHONPATH=backend python backend/tests/test_artifacts.py
PYTHONPATH=backend python backend/tests/test_storage.py
PYTHONPATH=backend python backend/tests/test_template_renderer.py
PYTHONPATH=backend python backend/tests/test_pydantic_loader.py
PYTHONPATH=backend python backend/tests/test_llm_client.py
PYTHONPATH=backend python backend/tests/test_runner.py
PYTHONPATH=backend python backend/tests/test_jobs.py
PYTHONPATH=backend python backend/tests/test_api.py
PYTHONPATH=backend python backend/tests/test_judge.py
PYTHONPATH=backend python backend/tests/test_reviews.py
PYTHONPATH=backend python backend/tests/test_proposal.py
PYTHONPATH=backend python backend/tests/test_compare.py
PYTHONPATH=backend python backend/tests/test_chat.py
PYTHONPATH=backend python backend/tests/test_chat_get_structured_lite.py
PYTHONPATH=backend python backend/tests/test_structured_lite_units.py
PYTHONPATH=backend python backend/tests/test_format_validation_errors.py
pyright --project pyrightconfig.json --pythonpath .venv/bin/python
```

Expected: all backend workflow checks pass before frontend work begins.

---

### Task 4: Frontend Product UI Pass

**Files:**
- Create/modify the files listed in `IMPLEMENTATION_PLAN.md` Tasks 17-19.

- [ ] **Step 1: Create a frontend design checkpoint**

Because this is a new React/Vite tool UI and the Build Web Apps plugin was requested, use `build-web-apps:frontend-app-builder` before implementing Task 17. Produce a practical local-tool design direction for:

- experiments list;
- experiment overview;
- run progress with current case/repeat;
- run results with JSON/raw output/validation errors;
- review findings and human decisions;
- proposal and comparison screens.

Expected: the design is dense enough for repeated prompt-evaluation work and does not become a marketing landing page.

- [ ] **Step 2: Execute Task 17 exactly**

Scaffold React/Vite TypeScript frontend from `IMPLEMENTATION_PLAN.md` Task 17.

Run:

```bash
cd frontend
pnpm lint
pnpm build
```

Expected: lint and production build pass. If `pnpm install` needs network approval, request approval instead of substituting a different package manager.

- [ ] **Step 3: Execute Task 18 exactly**

Implement experiments list, overview, and run results from `IMPLEMENTATION_PLAN.md` Task 18.

Run:

```bash
cd frontend
pnpm lint
pnpm build
```

Expected: the frontend shows experiment metadata, prompt/rubric/cases, run button, and run artifacts.

- [ ] **Step 4: Execute Task 19 exactly**

Implement review, proposal, and comparison views from `IMPLEMENTATION_PLAN.md` Task 19.

Run:

```bash
cd frontend
pnpm lint
pnpm build
```

Expected: user can inspect judgments, accept/reject/defer findings, save notes, inspect proposals, create next version, and compare versions through the UI.

- [ ] **Step 5: Browser verification gate**

Run backend and frontend:

```bash
PYTHONPATH=backend uvicorn prompt_lab.app:app --reload
cd frontend
pnpm dev
```

Use the Browser plugin against the Vite URL.

Expected desktop checks:

- `split-scenes` and `summarize-chapter` are visible.
- Selected experiment details do not overflow.
- Run progress includes current case and repeat.
- Structured output is shown as JSON.
- Raw output and validation errors remain visible.
- Review/proposal/comparison controls are reachable without layout overlap.

Expected mobile checks:

- navigation remains usable;
- tables or result lists remain readable through responsive stacking or horizontal containment;
- buttons and controls do not clip text.

---

### Task 5: End-To-End Smoke And Documentation

**Files:**
- Modify: `README.md`
- Modify: `backend/README.md`
- Modify: `frontend/README.md`

- [ ] **Step 1: Execute Task 20 exactly**

Run the local smoke sequence from `IMPLEMENTATION_PLAN.md` Task 20.

Expected manual workflow:

```text
list examples -> open summarize-chapter -> run version -> inspect artifacts -> judge -> reject one finding -> add notes -> generate proposal -> create v002 -> compare v002 to v001
```

- [ ] **Step 2: Final validation**

Run:

```bash
PYTHONPATH=backend python backend/tests/test_chat.py
PYTHONPATH=backend python backend/tests/test_chat_get_structured_lite.py
PYTHONPATH=backend python backend/tests/test_structured_lite_units.py
PYTHONPATH=backend python backend/tests/test_format_validation_errors.py
pyright --project pyrightconfig.json --pythonpath .venv/bin/python
cd frontend && pnpm lint && pnpm build
```

Expected: all configured checks pass, or each unavailable dependency is explicitly documented.

- [ ] **Step 3: Coverage checklist**

Confirm every item in `IMPLEMENTATION_PLAN.md` Coverage Checklist is true:

- backend loads examples and experiments from filesystem;
- text prompt versions run with case-major repeats;
- Pydantic prompt versions run with case-major repeats;
- generator cache is disabled;
- run artifacts include rendered prompt, raw output, parsed output/text, validation errors, execution errors, and usage;
- job progress exposes current case/repeat;
- judge creates structured judgment and default accepted decisions;
- user can reject/defer findings and write human notes;
- proposal creates prompt/model/rationale without mutating current version;
- user can create next version from proposal;
- comparison detects improvements/regressions between versions;
- frontend exposes the full MVP workflow.

---

## Parallelization Guidance

Default to sequential execution through Task 11. The foundational code changes touch shared contracts, storage, runner, and API, so parallel edits would create unnecessary merge risk.

After Task 11 passes, limited parallelization is possible:

- One worker can implement Tasks 12-13.
- A second worker can prepare frontend design and scaffold after Task 9, using mocked API responses if necessary.
- Do not implement Task 15 before Task 14, because proposal generation depends on decisions and human notes.
- Do not implement Task 16 before enough run/review artifacts exist to define comparison inputs.

Recommended execution mode: `superpowers:subagent-driven-development` with one subagent per task and a review checkpoint between tasks. Inline execution is acceptable if the branch is kept small and each task is committed before the next begins.

## Risk Register

- **Live LLM calls in tests:** Tests for runner/API/judge/proposal/comparison must monkeypatch `llm_client` boundaries. Unit tests must not require configured local or OpenAI models.
- **Cache policy regression:** Every generator path must go through `prompt_lab.llm_client` and keep `cache_enabled=False`.
- **Filesystem mutation:** Proposal creation must create `vNNN`; it must not mutate a version that already has run artifacts.
- **Validation errors as data:** Structured validation failures must be stored as run artifacts and shown in UI; they are not merely exceptions to hide.
- **Pydantic loader trust boundary:** MVP intentionally loads local experiment code. Do not present this as a sandbox.
- **Frontend dependency install:** `pnpm create vite` and `pnpm install` may require network approval. Ask for approval when the sandbox blocks package download.
- **Pyright invocation:** If local pyright is unavailable or the `.venv` path is missing, record the environment issue and keep running direct Python tests.
- **Carmilla boundary:** Do not import `workflow_runtime`, Story Parser classes, `WorkflowState`, or flat-file workflow context anywhere in Prompt Lab.

## Definition Of Done

The rollout is complete when:

- all 20 tasks from `IMPLEMENTATION_PLAN.md` are implemented or intentionally deferred with documented reason;
- backend direct tests and available pyright checks pass;
- frontend lint and build pass;
- Browser verification confirms the core local workflow works;
- docs explain install, config templates, backend start, frontend start, tests, and live smoke;
- git history contains focused commits matching the task boundaries.
