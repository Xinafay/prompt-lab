# Prompt Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add preview-before-send workflow support for run, validation, judge, and proposal prompts.

**Architecture:** Backend preview endpoints reuse the same prompt renderers/builders as the real workflow actions but never start jobs, call LLMs, or write runtime artifacts. Frontend API helpers feed a reusable full-page modal; accepting the modal invokes the existing workflow handlers.

**Tech Stack:** FastAPI, Pydantic, existing Prompt Lab storage/builders, React/Vite, TypeScript, node:test frontend tests.

---

## File Structure

- Modify `backend/prompt_lab/api.py`: add preview response models, shared prompt item helpers, four preview endpoints, and small extraction helpers for judge/proposal prompt inputs if needed.
- Modify `backend/tests/test_api.py`: add run and validation preview endpoint tests using local fixtures.
- Modify `backend/tests/test_reviews.py`: add judge preview endpoint test.
- Modify `backend/tests/test_proposal.py`: add proposal preview endpoint test.
- Modify `frontend/src/types.ts`: add `PromptPreviewItem` and `PromptPreviewResponse`.
- Modify `frontend/src/api.ts`: add four preview API helpers.
- Create `frontend/src/components/PromptPreviewModal.tsx`: reusable modal and count display.
- Create `frontend/tests/promptPreviewModal.test.ts`: render-to-static-markup tests for modal content and controls.
- Modify `frontend/src/App.tsx`: add preview state, handlers, modal wiring, and secondary action passing.
- Modify `frontend/src/components/WorkflowToolbar.tsx`: support optional secondary action next to the primary toolbar action.
- Modify `frontend/src/components/ValidationView.tsx`: add optional preview button prop in section actions.
- Modify `frontend/src/components/ReviewView.tsx`: add optional preview button prop beside judge action.
- Modify `frontend/src/components/ProposalView.tsx`: add optional preview button prop beside proposal action.
- Modify `frontend/src/styles.css`: add full-page preview modal styles.

## Task 1: Backend Run And Validation Preview Tests

**Files:**
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Write failing tests**

Add tests that call:

```python
response = TestClient(app).post("/api/experiments/demo/versions/v001/runs/preview-prompts")
```

and assert:

```python
assert response.status_code == 200
body = response.json()
assert body["workflow_kind"] == "run_version"
assert body["prompts"][0]["prompt"] == "Say hello\n\n<<MODEL>>"
assert body["prompts"][0]["character_count"] == len("Say hello\n\n<<MODEL>>")
assert body["prompts"][0]["word_count"] == 3
```

Add a validation preview test with 2 cases, 2 repeats, and enough LLM validators to exceed the preview threshold by monkeypatching the backend constant to `3`. Assert every case and validator appears, only repeat `1` appears, and a warning is returned.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_api.py
```

Expected: FAIL because preview endpoints do not exist.

## Task 2: Backend Preview Implementation

**Files:**
- Modify: `backend/prompt_lab/api.py`

- [ ] **Step 1: Implement response models and helpers**

Add:

```python
PROMPT_PREVIEW_MAX_PROMPTS = 100

class PromptPreviewItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    title: str
    model: str
    prompt: str
    character_count: int
    word_count: int
    case_id: str | None = None
    repeat_index: int | None = None
    validator_id: str | None = None

class PromptPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workflow_kind: str
    prompts: list[PromptPreviewItem]
    warnings: list[str] = Field(default_factory=list)
```

Add `_prompt_preview_item(...)` to compute counts from rendered prompt text.

- [ ] **Step 2: Implement run preview endpoint**

Use `materialize_case_context(case)` and `render_prompt(template_text, context)` for every case/repeat. Return `PromptPreviewResponse(workflow_kind="run_version", ...)`.

- [ ] **Step 3: Implement validation preview endpoint**

Load the latest validated run batch, filter to `LlmQuestionnaireValidatorDefinition`, and build prompts with `build_llm_validator_prompt`. If `len(run_artifacts) * len(llm_validators) > PROMPT_PREVIEW_MAX_PROMPTS`, filter run artifacts to the first repeat per case before generating prompts and add a warning.

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_api.py
```

Expected: PASS.

## Task 3: Backend Judge And Proposal Preview Tests

**Files:**
- Modify: `backend/tests/test_reviews.py`
- Modify: `backend/tests/test_proposal.py`

- [ ] **Step 1: Write failing tests**

Add a judge preview test that prepares a completed run plus validation artifacts, calls:

```python
response = client.post("/api/experiments/demo/versions/v001/judgments/preview-prompts")
```

and asserts one prompt containing `JUDGMENT_METADATA_JSON` without creating a new `reviews/review-002` directory.

Add a proposal preview test that calls:

```python
response = client.post("/api/experiments/demo/versions/v001/reviews/review-001/proposal/preview-prompts")
```

and asserts one prompt containing `ACCEPTED_FINDINGS_JSON` and that `review-001/proposal` was not created.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_reviews.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_proposal.py
```

Expected: FAIL because judge/proposal preview endpoints do not exist.

## Task 4: Backend Judge And Proposal Preview Implementation

**Files:**
- Modify: `backend/prompt_lab/api.py`

- [ ] **Step 1: Implement judge preview endpoint**

Reuse the same loading, validation, evidence building, model source, output declaration, and `build_judge_prompt` logic as `judge_experiment_version`, but do not call `start_workflow_job`, `_remove_runtime_children`, or write review files.

- [ ] **Step 2: Implement proposal preview endpoint**

Reuse the same review loading, decisions validation, human notes, validation context, model source, and `build_proposal_prompt` logic as `generate_review_proposal`, but do not start a job or write proposal files.

- [ ] **Step 3: Run tests to verify pass**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_reviews.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_proposal.py
```

Expected: PASS.

## Task 5: Frontend Modal And API Tests

**Files:**
- Create: `frontend/src/components/PromptPreviewModal.tsx`
- Create: `frontend/tests/promptPreviewModal.test.ts`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api.ts`

- [ ] **Step 1: Write failing modal test**

Render `PromptPreviewModal` with one warning and one prompt using `react-dom/server`, then assert the HTML contains `Preview prompts`, `Accept`, `Reject`, `42 characters`, metadata, warning text, and prompt body.

- [ ] **Step 2: Run frontend tests to verify failure**

Run:

```bash
cd frontend && pnpm test
```

Expected: FAIL because the modal component does not exist.

- [ ] **Step 3: Implement modal, types, and API helpers**

Add typed helpers:

```ts
previewRunPrompts(experimentId, version)
previewValidationPrompts(experimentId, version)
previewJudgePrompts(experimentId, version)
previewProposalPrompts(experimentId, version, reviewId)
```

Implement `PromptPreviewModal` with `role="dialog"`, warning list, prompt cards, counts, and footer buttons.

- [ ] **Step 4: Run frontend tests to verify pass**

Run:

```bash
cd frontend && pnpm test
```

Expected: PASS.

## Task 6: Frontend Wiring

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/WorkflowToolbar.tsx`
- Modify: `frontend/src/components/ValidationView.tsx`
- Modify: `frontend/src/components/ReviewView.tsx`
- Modify: `frontend/src/components/ProposalView.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Add preview state and handlers**

In `App.tsx`, add state for preview response, accepted callback, and loading/error message. Each preview handler calls the matching API helper and opens the modal. `Accept` closes the modal and calls the matching existing handler.

- [ ] **Step 2: Add secondary preview buttons**

Pass `Preview prompts` buttons to the toolbar and local views. Use existing disabled states and disabled reasons.

- [ ] **Step 3: Add CSS**

Add `.prompt-preview-modal`, `.prompt-preview-list`, `.prompt-preview-card`, `.prompt-preview-body`, `.prompt-preview-footer`, and warning styles with near-full-page dimensions and sticky footer.

- [ ] **Step 4: Run typecheck/build**

Run:

```bash
cd frontend && pnpm lint && pnpm test && pnpm build
```

Expected: PASS.

## Task 7: Focused Final Verification

**Files:**
- Verify only

- [ ] **Step 1: Run backend focused tests**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_api.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_reviews.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_proposal.py
```

Expected: PASS.

- [ ] **Step 2: Inspect current UI with in-app browser**

Use the in-app browser on `http://127.0.0.1:5173/demo-string/proposal` to verify the proposal screen has a secondary preview button, opens the modal, shows prompt counts, and `Reject` closes without sending.

- [ ] **Step 3: Commit implementation**

Stage only the files changed for prompt preview and commit:

```bash
git add backend/prompt_lab/api.py backend/tests/test_api.py backend/tests/test_reviews.py backend/tests/test_proposal.py frontend/src/types.ts frontend/src/api.ts frontend/src/components/PromptPreviewModal.tsx frontend/tests/promptPreviewModal.test.ts frontend/src/App.tsx frontend/src/components/WorkflowToolbar.tsx frontend/src/components/ValidationView.tsx frontend/src/components/ReviewView.tsx frontend/src/components/ProposalView.tsx frontend/src/styles.css docs/superpowers/plans/2026-06-20-prompt-preview-implementation.md
git commit -m "feat: preview prompts before workflow send"
```
