# Validator Check Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the structured validator check editor with vertical check cards, friendly select labels/hints, and add/delete check actions.

**Architecture:** Keep all editor behavior in `frontend/src/components/ValidatorEditor.tsx`, because the current file already owns validator draft mutations and validation helpers. Add no schema or backend changes. CSS changes stay in `frontend/src/styles.css`.

**Tech Stack:** React, TypeScript, existing Node SSR component tests, Vite.

---

### Task 1: Add Editor Helpers And Tests

**Files:**
- Modify: `frontend/src/components/ValidatorEditor.tsx`
- Modify: `frontend/tests/validatorEditor.test.ts`

- [ ] Write failing tests for friendly select labels and hints in `ValidatorEditor` SSR output.
- [ ] Write failing tests for appending and removing default LLM checks.
- [ ] Write failing tests for appending and removing default automatic checks.
- [ ] Implement exported helper functions in `ValidatorEditor.tsx`.
- [ ] Run `cd frontend && pnpm test` and confirm the new tests pass.
- [ ] Commit with `feat: add validator check editor helpers`.

### Task 2: Add Check Card Controls

**Files:**
- Modify: `frontend/src/components/ValidatorEditor.tsx`
- Modify: `frontend/tests/validatorEditor.test.ts`

- [ ] Write failing SSR tests that `Add check` and `Delete` controls render in both LLM and automatic editors.
- [ ] Write failing SSR test that the last check delete button is disabled.
- [ ] Wire `Add check` and `Delete` into `LlmChecksEditor` and `AutomaticChecksEditor`.
- [ ] Render human labels in all select options and hint text under key select fields.
- [ ] Run `cd frontend && pnpm test` and confirm tests pass.
- [ ] Commit with `feat: edit validator checks structurally`.

### Task 3: Refine Layout And Verify

**Files:**
- Modify: `frontend/src/styles.css`
- Optionally modify: `frontend/e2e/demo-prompt.spec.ts`

- [ ] Change `.validator-check-editor` and related checks section styles so check editors are full-width vertical cards.
- [ ] Run `cd frontend && pnpm test && pnpm lint && pnpm build`.
- [ ] Use the in-app browser on `/demo-json/validators` to verify the modal: vertical cards, friendly labels, add/delete controls, no horizontal overflow on desktop/mobile.
- [ ] If browser behavior changes need regression coverage, update `frontend/e2e/demo-prompt.spec.ts` and run `cd frontend && pnpm test:e2e`.
- [ ] Commit with `style: stack validator check editors`.
