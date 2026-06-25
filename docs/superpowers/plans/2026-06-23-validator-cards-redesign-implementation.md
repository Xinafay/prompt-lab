# Validator Cards Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current always-visible validator editor with a read-only large-card overview and a full-screen validator editing modal.

**Architecture:** Keep the existing version-level validator draft and backend save contract. Add focused read-only card components for overview display, then make `ValidatorsView` own a modal-scoped validator draft that is applied back to the page draft only when the modal `Save changes` action succeeds. Reuse `ValidatorEditor` for structured editing and the current JSON parser helpers for advanced JSON mode.

**Tech Stack:** React 19, TypeScript, Vite, existing node:test SSR tests, Playwright e2e, existing Prompt Lab CSS.

---

## Current State

- `frontend/src/components/ValidatorsView.tsx` owns the validator draft and renders:
  - version-level actions;
  - a narrow validator list;
  - add buttons;
  - duplicate/delete controls;
  - structured/JSON editor for the selected validator.
- `frontend/src/components/ValidatorEditor.tsx` owns structured controls for one validator.
- `frontend/src/components/ValidatorsPreview.tsx` already renders read-only validator summaries, but it has no card actions and its rule prose is too technical for the target overview.
- `frontend/tests/validatorEditor.test.ts` contains SSR tests for validator helpers and `ValidatorsView`.
- `frontend/e2e/demo-prompt.spec.ts` contains current browser tests that assume the editor is visible immediately on the `Validators` tab.

## File Structure

- `frontend/src/components/ValidatorCard.tsx`
  - New read-only card component for one validator.
  - Exports small formatting helpers for automatic rule prose and metadata labels.
  - Receives action callbacks from `ValidatorsView`; does not mutate state.
- `frontend/src/components/ValidatorsPreview.tsx`
  - Simplify to reuse `ValidatorCard` when read-only previews are still needed.
- `frontend/src/components/ValidatorsView.tsx`
  - Replace the master-detail editor layout with a vertical card overview.
  - Add modal state for create/edit/duplicate workflows.
  - Keep version-level dirty state emission and save actions.
- `frontend/src/components/ValidatorEditor.tsx`
  - Keep the structured editor as the modal body.
  - No planned behavior changes; this component remains the structured editor.
- `frontend/src/styles.css`
  - Replace old validators split-layout styles with card overview and full-screen modal styles.
  - Keep reusable button, pill, empty-state, and settings field styles.
- `frontend/tests/validatorEditor.test.ts`
  - Update SSR tests to cover read-only cards and default overview behavior.
- `frontend/e2e/demo-prompt.spec.ts`
  - Update browser workflows to open the modal before editing.
  - Add coverage that all `Report shape` checks are visible without expansion.

---

### Task 1: Add Read-Only Validator Cards

**Files:**
- Create: `frontend/src/components/ValidatorCard.tsx`
- Modify: `frontend/src/components/ValidatorsPreview.tsx`
- Modify: `frontend/tests/validatorEditor.test.ts`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Write failing card rendering tests**

Append these imports and tests to `frontend/tests/validatorEditor.test.ts` after the existing `ValidatorEditor` render test:

```ts
const {
  describeAutomaticRule,
  inputScopeLabel,
  validatorTypeLabel,
  ValidatorCard
} = await import("../src/components/ValidatorCard.tsx");

test("validator card renders automatic checks as read-only prose", () => {
  const validator: ValidatorDefinition = {
    schema_version: "prompt_lab.validator/v1",
    validator_id: "report-shape",
    type: "automatic",
    title: "Report shape",
    description: "Local JSON checks that exercise automatic validators.",
    enabled: true,
    input_scope: "output_only",
    checks: [
      {
        check_id: "summary-present",
        title: "Summary present",
        description: "The structured output must include a summary field.",
        rule: {
          kind: "json_path_exists",
          source: "output_json",
          path: "$.summary"
        }
      },
      {
        check_id: "three-tags",
        title: "Three tags",
        description: "The tags list should contain exactly three items.",
        rule: {
          kind: "json_path_count",
          source: "output_json",
          path: "$.tags",
          comparison: { op: "eq", value: 3 }
        }
      }
    ]
  };

  const html = renderToStaticMarkup(
    React.createElement(ValidatorCard, {
      disabled: false,
      onDelete: () => undefined,
      onDuplicate: () => undefined,
      onEdit: () => undefined,
      validator
    })
  );

  assert.match(html, /Report shape/);
  assert.match(html, /Automatic/);
  assert.match(html, /Enabled/);
  assert.match(html, /Output only/);
  assert.match(html, /2 checks/);
  assert.match(html, /Requires \$\.summary in output_json to exist\./);
  assert.match(html, /Requires \$\.tags in output_json to contain exactly 3 items\./);
  assert.match(html, /summary-present - json_path_exists/);
  assert.doesNotMatch(html, /<input|<select|<textarea/);
});

test("validator card renders llm questionnaire checks read-only", () => {
  const validator = createDefaultValidator("llm_questionnaire", []);
  if (validator.type !== "llm_questionnaire") throw new Error("Expected llm validator");
  validator.validator_id = "report-quality";
  validator.title = "Report quality";
  validator.checks[0] = {
    check_id: "grounded-summary",
    title: "Grounded summary",
    description: "Checks whether the summary is grounded.",
    question: "Is the summary grounded in the source material?"
  };

  const html = renderToStaticMarkup(
    React.createElement(ValidatorCard, {
      disabled: false,
      onDelete: () => undefined,
      onDuplicate: () => undefined,
      onEdit: () => undefined,
      validator
    })
  );

  assert.match(html, /LLM questionnaire/);
  assert.match(html, /Asks: Is the summary grounded in the source material\?/);
  assert.match(html, /grounded-summary - llm_questionnaire/);
  assert.doesNotMatch(html, /<input|<select|<textarea/);
});

test("validator card formatting helpers use human-readable labels", () => {
  assert.equal(validatorTypeLabel("automatic"), "Automatic");
  assert.equal(validatorTypeLabel("llm_questionnaire"), "LLM questionnaire");
  assert.equal(inputScopeLabel("output_prompt_and_case"), "Output + prompt + case");
  assert.equal(
    describeAutomaticRule({
      kind: "word_count",
      source: "output_text",
      comparison: { op: "gte", value: 10 }
    }),
    "Requires output_text word count to be at least 10."
  );
});
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```bash
cd frontend && pnpm test validatorEditor.test.ts
```

Expected: FAIL because `frontend/src/components/ValidatorCard.tsx` does not exist.

- [ ] **Step 3: Create `ValidatorCard.tsx`**

Create `frontend/src/components/ValidatorCard.tsx` with these exports and component boundaries:

```tsx
import type { MouseEvent } from "react";
import type {
  AutomaticRule,
  CountComparison,
  InputScope,
  ValidatorDefinition,
  ValidatorType
} from "../types";

interface ValidatorCardProps {
  disabled: boolean;
  onDelete: (event: MouseEvent<HTMLButtonElement>) => void;
  onDuplicate: (event: MouseEvent<HTMLButtonElement>) => void;
  onEdit: (event: MouseEvent<HTMLButtonElement>) => void;
  validator: ValidatorDefinition;
}

export function validatorTypeLabel(type: ValidatorType): string {
  if (type === "llm_questionnaire") return "LLM questionnaire";
  if (type === "automatic") return "Automatic";
  return type;
}

export function inputScopeLabel(scope: InputScope): string {
  if (scope === "output_only") return "Output only";
  if (scope === "output_and_prompt") return "Output + prompt";
  if (scope === "output_and_case") return "Output + case";
  if (scope === "output_prompt_and_case") return "Output + prompt + case";
  return scope;
}

function comparisonPhrase(comparison: CountComparison | null | undefined): string {
  if (comparison === null || comparison === undefined) return "without a comparison";
  if (comparison.op === "between") {
    return `between ${comparison.min_value} and ${comparison.max_value}`;
  }
  const operatorLabels: Record<Exclude<CountComparison["op"], "between">, string> = {
    eq: "exactly",
    gt: "more than",
    gte: "at least",
    lt: "less than",
    lte: "at most"
  };
  return `${operatorLabels[comparison.op]} ${comparison.value}`;
}

export function describeAutomaticRule(rule: AutomaticRule): string {
  const source = rule.source;
  const path = rule.path ?? "the configured JSON path";

  if (rule.kind === "json_path_exists") {
    return `Requires ${path} in ${source} to exist.`;
  }
  if (rule.kind === "json_path_count") {
    return `Requires ${path} in ${source} to contain ${comparisonPhrase(
      rule.comparison
    )} items.`;
  }
  if (rule.kind === "word_count") {
    return `Requires ${source} word count to be ${comparisonPhrase(rule.comparison)}.`;
  }
  if (rule.kind === "sentence_count") {
    return `Requires ${source} sentence count to be ${comparisonPhrase(
      rule.comparison
    )}.`;
  }
  if (rule.kind === "character_count") {
    return `Requires ${source} character count to be ${comparisonPhrase(
      rule.comparison
    )}.`;
  }
  return `Applies ${rule.kind} to ${source}.`;
}

function automaticRuleMetadata(rule: AutomaticRule): string {
  const comparison = rule.comparison;
  if (comparison === null || comparison === undefined) {
    return rule.kind;
  }
  if (comparison.op === "between") {
    return `${rule.kind} - between ${comparison.min_value}..${comparison.max_value}`;
  }
  return `${rule.kind} - ${comparison.op} ${comparison.value}`;
}

export function ValidatorCard({
  disabled,
  onDelete,
  onDuplicate,
  onEdit,
  validator
}: ValidatorCardProps) {
  const title = validator.title || "(untitled)";
  const checkCount = validator.checks.length;
  const checkLabel = checkCount === 1 ? "1 check" : `${checkCount} checks`;

  return (
    <article
      className={`validator-card${validator.enabled ? "" : " is-disabled"}`}
      aria-label={`${title} validator`}
    >
      <div className="validator-card-header">
        <div>
          <h3>{title}</h3>
          <div className="validator-card-meta">
            <span>{validatorTypeLabel(validator.type)}</span>
            <span>{validator.enabled ? "Enabled" : "Disabled"}</span>
            <span>{inputScopeLabel(validator.input_scope)}</span>
            <span>{checkLabel}</span>
          </div>
        </div>
        <div className="validator-card-actions">
          <button
            className="primary-action"
            disabled={disabled}
            onClick={onEdit}
            type="button"
            aria-label={`Edit ${title} validator`}
          >
            Edit
          </button>
          <button
            className="secondary-action"
            disabled={disabled}
            onClick={onDuplicate}
            type="button"
            aria-label={`Duplicate ${title} validator`}
          >
            Duplicate
          </button>
          <button
            className="secondary-action danger-action"
            disabled={disabled}
            onClick={onDelete}
            type="button"
            aria-label={`Delete ${title} validator`}
          >
            Delete
          </button>
        </div>
      </div>

      {validator.description.trim().length > 0 ? (
        <p className="validator-card-description">{validator.description}</p>
      ) : null}

      <div className="validator-card-checks" aria-label={`${title} checks`}>
        {validator.checks.map((check) => {
          const body =
            validator.type === "llm_questionnaire"
              ? `Asks: ${check.question}`
              : describeAutomaticRule(check.rule);
          const metadata =
            validator.type === "llm_questionnaire"
              ? `${check.check_id} - llm_questionnaire`
              : `${check.check_id} - ${automaticRuleMetadata(check.rule)}`;

          return (
            <section className="validator-card-check" key={check.check_id}>
              <div>
                <h4>{check.title || check.check_id}</h4>
                {check.description.trim().length > 0 ? (
                  <p>{check.description}</p>
                ) : null}
              </div>
              <div>
                <p>{body}</p>
                <span>{metadata}</span>
              </div>
            </section>
          );
        })}
      </div>
    </article>
  );
}
```

- [ ] **Step 4: Reuse `ValidatorCard` in `ValidatorsPreview.tsx`**

Replace the current helper functions and card markup in `frontend/src/components/ValidatorsPreview.tsx` with:

```tsx
import type { ValidatorDefinition } from "../types";
import { ValidatorCard } from "./ValidatorCard";

interface ValidatorsPreviewProps {
  validators: ValidatorDefinition[];
}

export function ValidatorsPreview({ validators }: ValidatorsPreviewProps) {
  return (
    <div className="validators-preview">
      {validators.length === 0 ? (
        <div className="empty-state compact-empty-state">
          <h2>No validators configured</h2>
          <p>Add validators before running validation.</p>
        </div>
      ) : (
        validators.map((validator) => (
          <ValidatorCard
            disabled={true}
            key={validator.validator_id}
            onDelete={() => undefined}
            onDuplicate={() => undefined}
            onEdit={() => undefined}
            validator={validator}
          />
        ))
      )}
    </div>
  );
}
```

- [ ] **Step 5: Add card styles**

In `frontend/src/styles.css`, keep `.validators-preview` but replace the old `.validator-preview-*` block with card styles:

```css
.validators-preview {
  display: grid;
  gap: 16px;
}

.validator-card {
  display: grid;
  gap: 16px;
  padding: 18px;
  border: 1px solid #d8dee8;
  border-radius: 8px;
  background: #ffffff;
}

.validator-card.is-disabled {
  background: #f8fafc;
}

.validator-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.validator-card-header h3 {
  margin: 0;
  color: #111827;
  font-size: 18px;
  font-weight: 760;
  line-height: 1.25;
}

.validator-card-meta,
.validator-card-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.validator-card-meta {
  margin-top: 8px;
}

.validator-card-meta span {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 8px;
  border-radius: 999px;
  background: #eef2f6;
  color: #344054;
  font-size: 12px;
  font-weight: 750;
  line-height: 1;
}

.validator-card-description {
  margin: 0;
  max-width: 900px;
  color: #475467;
  font-size: 14px;
  line-height: 1.5;
}

.validator-card-checks {
  display: grid;
  gap: 10px;
}

.validator-card-check {
  display: grid;
  grid-template-columns: minmax(180px, 280px) minmax(0, 1fr);
  gap: 16px;
  padding: 12px;
  border: 1px solid #eef1f5;
  border-radius: 8px;
  background: #fcfcfd;
}

.validator-card-check h4,
.validator-card-check p {
  margin: 0;
}

.validator-card-check h4 {
  color: #111827;
  font-size: 14px;
  font-weight: 750;
  line-height: 1.35;
}

.validator-card-check p {
  color: #344054;
  font-size: 13px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.validator-card-check h4 + p {
  margin-top: 4px;
  color: #667085;
}

.validator-card-check span {
  display: block;
  margin-top: 6px;
  color: #667085;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.35;
  overflow-wrap: anywhere;
}
```

- [ ] **Step 6: Run the focused test**

Run:

```bash
cd frontend && pnpm test validatorEditor.test.ts
```

Expected: PASS.

- [ ] **Step 7: Commit Task 1**

```bash
git add frontend/src/components/ValidatorCard.tsx frontend/src/components/ValidatorsPreview.tsx frontend/src/styles.css frontend/tests/validatorEditor.test.ts
git commit -m "feat: add validator overview cards"
```

---

### Task 2: Replace the Split Editor With Card Overview and Modal State

**Files:**
- Modify: `frontend/src/components/ValidatorsView.tsx`
- Modify: `frontend/tests/validatorEditor.test.ts`

- [ ] **Step 1: Update the SSR test for default overview behavior**

Replace the existing test named `ValidatorsView renders add duplicate delete and save actions` in `frontend/tests/validatorEditor.test.ts` with:

```ts
test("ValidatorsView renders validator cards instead of the editor by default", () => {
  const validator = createDefaultValidator("automatic", []);
  validator.validator_id = "report-shape";
  validator.title = "Report shape";

  const html = renderToStaticMarkup(
    React.createElement(ValidatorsView, {
      isBusy: false,
      message: null,
      onDraftChange: () => undefined,
      onOverwriteCurrent: () => undefined,
      onReset: () => undefined,
      onSaveAsNext: () => undefined,
      validators: [validator]
    })
  );

  assert.match(html, /Add validator/);
  assert.match(html, /Report shape/);
  assert.match(html, /Edit/);
  assert.match(html, /Duplicate/);
  assert.match(html, /Delete/);
  assert.match(html, /Overwrite current version/);
  assert.match(html, /Save as next version/);
  assert.doesNotMatch(html, /aria-label="Validator editor"/);
  assert.doesNotMatch(html, /Validator JSON/);
});
```

- [ ] **Step 2: Run the focused test to verify it fails against current UI assumptions**

Run:

```bash
cd frontend && pnpm test validatorEditor.test.ts
```

Expected: FAIL because the current default view still renders `Validator editor`.

- [ ] **Step 3: Add modal state types and helper functions**

In `frontend/src/components/ValidatorsView.tsx`, update imports to include `type KeyboardEvent` and `ValidatorCard`:

```tsx
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent
} from "react";

import { ValidatorCard } from "./ValidatorCard";
```

Add these types near the existing `ValidatorJsonParseResult` type:

```tsx
type ValidatorModalMode = "create" | "edit";
type ValidatorEditMode = "structured" | "json";

interface ValidatorModalState {
  mode: ValidatorModalMode;
  sourceIndex: number | null;
  initialValidator: ValidatorDefinition;
  validator: ValidatorDefinition;
  viewMode: ValidatorEditMode;
  jsonText: string;
  jsonError: string | null;
  discardConfirming: boolean;
}
```

Add this helper near `cloneValidators`:

```tsx
function validatorModalTitle(state: ValidatorModalState): string {
  const label = state.validator.title || state.validator.validator_id || "new validator";
  return state.mode === "create"
    ? "Add validator"
    : `Edit validator: ${label}`;
}
```

- [ ] **Step 4: Replace selected-editor state with modal state**

Inside `ValidatorsView`, remove `selectedIndex`, `viewMode`, `jsonText`, and `jsonError` top-level state. Add modal state instead:

```tsx
const [modalState, setModalState] = useState<ValidatorModalState | null>(null);
const closeButtonRef = useRef<HTMLButtonElement | null>(null);
const modalReturnFocusRef = useRef<HTMLElement | null>(null);
```

Keep `draft` and `lastDraftEmissionRef`. Compute validation/action state with modal JSON errors excluded from version-level persistence:

```tsx
const isDirty = useMemo(() => !validatorsEqual(draft, validators), [
  draft,
  validators
]);
const validationErrors = useMemo(() => validateValidatorDraft(draft), [draft]);
const modalValidationErrors = useMemo(
  () =>
    modalState === null
      ? []
      : validateValidatorDraft(nextDraftWithModalValidator(modalState)),
  [draft, modalState]
);
const actionState = getValidatorEditorActionState({
  isBusy,
  isDirty,
  jsonError: null,
  validationErrorCount: validationErrors.length
});
```

In the `useEffect` that resets from `validators`, set only:

```tsx
setDraft(cloneValidators(validators));
setModalState(null);
```

- [ ] **Step 5: Add modal open/apply helpers**

Add these functions inside `ValidatorsView`:

```tsx
function openModal(
  state: Omit<
    ValidatorModalState,
    "initialValidator" | "viewMode" | "jsonText" | "jsonError" | "discardConfirming"
  >,
  eventTarget?: EventTarget | null
) {
  modalReturnFocusRef.current =
    eventTarget instanceof HTMLElement ? eventTarget : null;
  setModalState({
    ...state,
    initialValidator: cloneValidators([state.validator])[0],
    viewMode: "structured",
    jsonText: JSON.stringify(state.validator, null, 2),
    jsonError: null,
    discardConfirming: false
  });
}

function openCreateValidator(eventTarget?: EventTarget | null) {
  const nextValidator = createDefaultValidator(
    "llm_questionnaire",
    draft.map((validator) => validator.validator_id)
  );
  openModal(
    {
      mode: "create",
      sourceIndex: null,
      validator: nextValidator
    },
    eventTarget
  );
}

function openEditValidator(index: number, eventTarget?: EventTarget | null) {
  const validator = draft[index];
  if (validator === undefined) return;
  openModal(
    {
      mode: "edit",
      sourceIndex: index,
      validator: cloneValidators([validator])[0]
    },
    eventTarget
  );
}

function duplicateValidatorFromCard(index: number, eventTarget?: EventTarget | null) {
  const validator = draft[index];
  if (validator === undefined) return;
  const copy = duplicateValidator(
    validator,
    draft.map((candidate) => candidate.validator_id)
  );
  openModal(
    {
      mode: "create",
      sourceIndex: null,
      validator: copy
    },
    eventTarget
  );
}

function deleteValidatorFromCard(index: number) {
  if (actionState.jsonUnsafeActionsDisabled) return;
  setDraft((current) =>
    current.filter((_validator, validatorIndex) => validatorIndex !== index)
  );
}

function updateModalValidator(validator: ValidatorDefinition) {
  setModalState((current) =>
    current === null
      ? null
      : {
          ...current,
          validator,
          jsonText:
            current.viewMode === "json"
              ? current.jsonText
              : JSON.stringify(validator, null, 2)
        }
  );
}

function nextDraftWithModalValidator(state: ValidatorModalState): ValidatorDefinition[] {
  if (state.sourceIndex === null) {
    return [...draft, state.validator];
  }
  return draft.map((validator, index) =>
    index === state.sourceIndex ? state.validator : validator
  );
}

function saveModalValidator() {
  if (modalState === null || modalState.jsonError !== null) return;
  const nextDraft = nextDraftWithModalValidator(modalState);
  if (validateValidatorDraft(nextDraft).length > 0) return;
  setDraft(nextDraft);
  setModalState(null);
}

function closeModal() {
  setModalState(null);
}

function isModalDirty(state: ValidatorModalState): boolean {
  return !validatorsEqual([state.validator], [state.initialValidator]);
}

function requestCloseModal() {
  if (modalState !== null && isModalDirty(modalState)) {
    setModalState({ ...modalState, discardConfirming: true });
    return;
  }
  closeModal();
}
```

- [ ] **Step 6: Add focus restoration for modal open/close**

Add this effect inside `ValidatorsView`:

```tsx
const isModalOpen = modalState !== null;

useEffect(() => {
  if (!isModalOpen) {
    modalReturnFocusRef.current?.focus();
    modalReturnFocusRef.current = null;
    return;
  }
  window.requestAnimationFrame(() => closeButtonRef.current?.focus());
}, [isModalOpen]);
```

Add this keyboard handler:

```tsx
function handleModalKeyDown(event: KeyboardEvent<HTMLElement>) {
  if (event.key === "Escape") {
    event.preventDefault();
    requestCloseModal();
  }
  if (event.key !== "Tab") return;

  const container = event.currentTarget;
  const focusable = Array.from(
    container.querySelectorAll<HTMLElement>(
      'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [href], [tabindex]:not([tabindex="-1"])'
    )
  );
  if (focusable.length === 0) return;

  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}
```

- [ ] **Step 7: Replace the JSX split layout with overview cards and modal shell**

Replace the `<div className="validators-editor-layout">...</div>` block with this structure:

```tsx
<div className="validators-overview-toolbar">
  <button
    className="secondary-action"
    disabled={actionState.jsonUnsafeActionsDisabled}
    onClick={(event) => openCreateValidator(event.currentTarget)}
    type="button"
  >
    Add validator
  </button>
</div>

{draft.length === 0 ? (
  <div className="empty-state compact-empty-state">
    <h2>No validators configured</h2>
    <p>Add validator definitions before running validation.</p>
  </div>
) : (
  <div className="validators-card-list">
    {draft.map((validator, validatorIndex) => (
      <ValidatorCard
        disabled={actionState.jsonUnsafeActionsDisabled}
        key={`${validator.validator_id}-${validatorIndex}`}
        onDelete={() => deleteValidatorFromCard(validatorIndex)}
        onDuplicate={(event) =>
          duplicateValidatorFromCard(validatorIndex, event.currentTarget)
        }
        onEdit={(event) => openEditValidator(validatorIndex, event.currentTarget)}
        validator={validator}
      />
    ))}
  </div>
)}
```

Then render the modal after the overview list:

```tsx
{modalState !== null ? (
  <div className="modal-backdrop" role="presentation">
    <section
      aria-labelledby="validator-edit-modal-title"
      aria-modal="true"
      className="validator-edit-modal"
      onKeyDown={handleModalKeyDown}
      role="dialog"
    >
      <div className="validator-edit-modal-header">
        <div>
          <h2 id="validator-edit-modal-title">
            {validatorModalTitle(modalState)}
          </h2>
          <p>
            Save changes here to update the local validators draft, then use the
            version actions to persist it.
          </p>
        </div>
        <button
          className="secondary-action"
          onClick={requestCloseModal}
          ref={closeButtonRef}
          type="button"
        >
          Cancel
        </button>
      </div>

      <div className="validators-editor-detail-actions">
        <div
          aria-label="Validator edit mode"
          className="proposal-tabs"
          role="tablist"
        >
          <button
            aria-selected={modalState.viewMode === "structured"}
            className={
              modalState.viewMode === "structured"
                ? "proposal-tab is-active"
                : "proposal-tab"
            }
            disabled={modalState.jsonError !== null}
            onClick={() =>
              setModalState({
                ...modalState,
                viewMode: "structured",
                jsonError: null,
                jsonText: JSON.stringify(modalState.validator, null, 2)
              })
            }
            role="tab"
            type="button"
          >
            Structured
          </button>
          <button
            aria-selected={modalState.viewMode === "json"}
            className={
              modalState.viewMode === "json"
                ? "proposal-tab is-active"
                : "proposal-tab"
            }
            disabled={modalState.jsonError !== null}
            onClick={() =>
              setModalState({
                ...modalState,
                viewMode: "json",
                jsonError: null,
                jsonText: JSON.stringify(modalState.validator, null, 2)
              })
            }
            role="tab"
            type="button"
          >
            JSON
          </button>
        </div>
      </div>

      {modalState.jsonError !== null ? (
        <div className="settings-error">
          Invalid validator JSON: {modalState.jsonError}
        </div>
      ) : null}

      {modalValidationErrors.length > 0 ? (
        <div className="settings-error">
          {modalValidationErrors.join(" ")}
        </div>
      ) : null}

      {modalState.discardConfirming ? (
        <div className="settings-error" role="alert">
          Discard unsaved validator edits?
        </div>
      ) : null}

      <div className="validator-edit-modal-body">
        {modalState.viewMode === "json" ? (
          <label className="validator-json-field">
            <span>Validator JSON</span>
            <textarea
              aria-label="Validator JSON"
              className="validator-json-editor"
              rows={18}
              value={modalState.jsonText}
              onChange={(event) => {
                const nextState = applyValidatorJsonDraftEdit(
                  [modalState.validator],
                  0,
                  event.target.value
                );
                setModalState({
                  ...modalState,
                  validator: nextState.draft[0],
                  jsonError: nextState.jsonError,
                  jsonText: nextState.jsonText
                });
              }}
            />
          </label>
        ) : (
          <ValidatorEditor
            existingValidatorIds={draft.map((validator) => validator.validator_id)}
            onChange={updateModalValidator}
            validator={modalState.validator}
          />
        )}
      </div>

      <div className="validator-edit-modal-footer">
        {modalState.discardConfirming ? (
          <>
            <button
              className="secondary-action"
              onClick={() =>
                setModalState({ ...modalState, discardConfirming: false })
              }
              type="button"
            >
              Keep editing
            </button>
            <button
              className="secondary-action danger-action"
              onClick={closeModal}
              type="button"
            >
              Discard edits
            </button>
          </>
        ) : (
          <>
            <button
              className="secondary-action"
              onClick={requestCloseModal}
              type="button"
            >
              Cancel
            </button>
            <button
              className="primary-action"
              disabled={
                modalState.jsonError !== null ||
                modalValidationErrors.length > 0
              }
              onClick={saveModalValidator}
              type="button"
            >
              Save changes
            </button>
          </>
        )}
      </div>
    </section>
  </div>
) : null}
```

After this step, remove unused functions and imports from `ValidatorsView.tsx`: `setDraftAndSelect`, `addValidator`, `updateSelected`, `duplicateSelected`, `deleteSelected`, `toggleViewMode`, `updateJson`, and `ValidatorsPreview`.

- [ ] **Step 8: Run the focused test**

Run:

```bash
cd frontend && pnpm test validatorEditor.test.ts
```

Expected: PASS.

- [ ] **Step 9: Commit Task 2**

```bash
git add frontend/src/components/ValidatorsView.tsx frontend/tests/validatorEditor.test.ts
git commit -m "feat: show validators as overview cards"
```

---

### Task 3: Style the Full-Screen Validator Editor Modal

**Files:**
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Add modal layout styles**

In `frontend/src/styles.css`, remove now-unused split editor rules for `.validators-editor-layout`, `.validators-editor-list`, and `.validator-list-item`. Keep `.validators-editor-panel`, `.validators-editor-actions`, `.validators-editor-detail-actions`, `.validator-editor`, `.validator-json-field`, `.validator-check-editor`, and `.validator-json-editor`.

Add these styles near the existing validators styles:

```css
.validators-overview-toolbar {
  display: flex;
  justify-content: flex-start;
}

.validators-card-list {
  display: grid;
  gap: 16px;
}

.validator-edit-modal {
  display: grid;
  grid-template-rows: auto auto auto minmax(0, 1fr) auto;
  gap: 14px;
  width: min(1180px, 100%);
  max-height: calc(100vh - 48px);
  padding: 18px;
  border: 1px solid #d0d5dd;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 24px 60px rgb(16 24 40 / 0.22);
}

.validator-edit-modal-header,
.validator-edit-modal-footer {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.validator-edit-modal-header h2 {
  margin: 0;
  color: #111827;
  font-size: 18px;
  font-weight: 760;
  line-height: 1.25;
}

.validator-edit-modal-header p {
  margin: 6px 0 0;
  color: #667085;
  font-size: 14px;
  line-height: 1.45;
}

.validator-edit-modal-body {
  min-height: 0;
  overflow: auto;
  padding-right: 2px;
}

.validator-edit-modal-footer {
  justify-content: flex-end;
}
```

Update the existing responsive block near the bottom of `frontend/src/styles.css` so narrow screens collapse cards and modal header/footer actions cleanly:

```css
@media (max-width: 760px) {
  .validator-card-header,
  .validator-edit-modal-header,
  .validator-edit-modal-footer {
    display: grid;
  }

  .validator-card-actions {
    justify-content: flex-start;
  }

  .validator-card-check,
  .validator-check-editor {
    grid-template-columns: 1fr;
  }

  .validator-edit-modal {
    max-height: calc(100vh - 24px);
    padding: 14px;
  }
}
```

- [ ] **Step 2: Run lint to catch stale class/type issues**

Run:

```bash
cd frontend && pnpm lint
```

Expected: PASS.

- [ ] **Step 3: Commit Task 3**

```bash
git add frontend/src/styles.css
git commit -m "style: refine validator card editor layout"
```

---

### Task 4: Update Browser Workflows for Modal Editing

**Files:**
- Modify: `frontend/e2e/demo-prompt.spec.ts`

- [ ] **Step 1: Update the demo-string source-section test**

In `frontend/e2e/demo-prompt.spec.ts`, replace the validator assertions in `demo string prompt and validators tabs show source sections` with:

```ts
const validators = page.getByRole("region", { name: "Validators" });
await expect(validators.getByRole("heading", { name: "Validators" })).toBeVisible();
await expect(
  validators.getByRole("article", { name: /Reply quality validator/i })
).toBeVisible();
await expect(
  validators.getByRole("article", { name: /Reply stats validator/i })
).toBeVisible();
await expect(
  validators.getByRole("button", { name: /Edit Reply quality validator/i })
).toBeVisible();
await expect(
  validators.getByRole("region", { name: "Validator editor" })
).not.toBeVisible();
```

- [ ] **Step 2: Add card content assertions for demo-json validators**

Add this new e2e test before the save-as-next validator test:

```ts
test("demo json validators show large read-only cards with all checks", async ({
  page
}) => {
  await page.goto("/demo-json/validators");
  await selectVersion(page, "v002");

  const validators = page.getByRole("region", { name: "Validators" });
  const reportShape = validators.getByRole("article", {
    name: /Report shape validator/i
  });

  await expect(reportShape).toBeVisible();
  await expect(reportShape.getByText("Automatic")).toBeVisible();
  await expect(reportShape.getByText("Enabled")).toBeVisible();
  await expect(reportShape.getByText("Output only")).toBeVisible();
  await expect(reportShape.getByText("3 checks")).toBeVisible();
  await expect(reportShape.getByText("Summary present")).toBeVisible();
  await expect(
    reportShape.getByText("Requires $.summary in output_json to exist.")
  ).toBeVisible();
  await expect(reportShape.getByText("Three tags")).toBeVisible();
  await expect(
    reportShape.getByText("Requires $.tags in output_json to contain exactly 3 items.")
  ).toBeVisible();
  await expect(reportShape.getByText("Risk count")).toBeVisible();
  await expect(
    reportShape.getByText("Requires $.risks in output_json to contain between 1 and 3 items.")
  ).toBeVisible();
});
```

- [ ] **Step 3: Update save-as-next e2e to open the modal**

In `demo json validators can be saved as next version`, replace the old list-click/editor lines with:

```ts
const validators = page.getByRole("region", { name: "Validators" });
await validators
  .getByRole("button", { name: /Edit Report quality validator/i })
  .click();

const editedTitle = `Report quality e2e ${Date.now()}`;
const dialog = page.getByRole("dialog", {
  name: /Edit validator: Report quality/i
});
const editor = dialog.getByRole("region", { name: "Validator editor" });
await editor.getByLabel("Title").first().fill(editedTitle);
await dialog.getByRole("button", { name: "Save changes" }).click();
```

Keep the existing `Save as next version` click and final assertions, but change the final editor assertion to a card assertion:

```ts
await expect(validators.getByText(editedTitle)).toBeVisible();
await expect(page.getByRole("dialog")).not.toBeVisible();
```

- [ ] **Step 4: Update overwrite e2e to open the modal**

In `demo json validators can overwrite current version`, replace the old list-click/editor lines with:

```ts
const validators = page.getByRole("region", { name: "Validators" });
await validators
  .getByRole("button", { name: /Edit Report quality validator/i })
  .click();

const editedDescription = `Checks whether the structured report is useful and grounded. e2e ${Date.now()}`;
const editDialog = page.getByRole("dialog", {
  name: /Edit validator: Report quality/i
});
const editor = editDialog.getByRole("region", { name: "Validator editor" });
await editor.getByLabel("Description").first().fill(editedDescription);
await editDialog.getByRole("button", { name: "Save changes" }).click();
await expect(page.getByRole("dialog")).not.toBeVisible();
```

Keep the overwrite confirmation and downstream Runs/Validation assertions unchanged.

- [ ] **Step 5: Add e2e coverage for dirty modal close**

Add this test after `demo json validators show large read-only cards with all checks`:

```ts
test("demo json validator edit modal confirms discarding unsaved edits", async ({
  page
}) => {
  await page.goto("/demo-json/validators");
  await selectVersion(page, "v002");

  const validators = page.getByRole("region", { name: "Validators" });
  await validators
    .getByRole("button", { name: /Edit Report quality validator/i })
    .click();

  const dialog = page.getByRole("dialog", {
    name: /Edit validator: Report quality/i
  });
  const editor = dialog.getByRole("region", { name: "Validator editor" });
  await editor.getByLabel("Title").first().fill("Discard me");
  await dialog.getByRole("button", { name: "Cancel" }).first().click();

  await expect(dialog.getByRole("alert")).toContainText(
    "Discard unsaved validator edits?"
  );
  await dialog.getByRole("button", { name: "Keep editing" }).click();
  await expect(editor.getByLabel("Title").first()).toHaveValue("Discard me");

  await dialog.getByRole("button", { name: "Cancel" }).first().click();
  await dialog.getByRole("button", { name: "Discard edits" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(validators.getByText("Discard me")).not.toBeVisible();
});
```

- [ ] **Step 6: Run the focused e2e file**

Run:

```bash
cd frontend && pnpm test:e2e demo-prompt.spec.ts
```

Expected: PASS.

- [ ] **Step 7: Commit Task 4**

```bash
git add frontend/e2e/demo-prompt.spec.ts
git commit -m "test: cover validator card workflows"
```

---

### Task 5: Final Verification and Browser QA

**Files:**
- Modify only files needed for fixes found by verification.

- [ ] **Step 1: Run frontend unit tests**

Run:

```bash
cd frontend && pnpm test
```

Expected: PASS.

- [ ] **Step 2: Run frontend lint**

Run:

```bash
cd frontend && pnpm lint
```

Expected: PASS.

- [ ] **Step 3: Run production build**

Run:

```bash
cd frontend && pnpm build
```

Expected: PASS.

- [ ] **Step 4: Run e2e tests**

Run:

```bash
cd frontend && pnpm test:e2e
```

Expected: PASS.

- [ ] **Step 5: Inspect the current app in the in-app browser**

Use the Browser plugin on `http://127.0.0.1:5173/demo-json/validators`.

Verify:

- the page opens on the read-only card overview;
- `Report shape` and `Report quality` cards are visible as large cards;
- all checks in `Report shape` are visible without expanding anything;
- no `Validator editor` region is visible until `Edit` is clicked;
- clicking `Edit` opens a full-screen modal;
- editing a title and clicking `Save changes` updates the overview card;
- `Save as next version` remains disabled until modal changes are applied;
- after modal save, `Save as next version` becomes enabled;
- text does not overlap at desktop width and at a narrow mobile viewport.

- [ ] **Step 6: Fix issues found by verification**

If verification finds a problem, make the smallest scoped fix in the file responsible for the problem, rerun the failing command, and commit the fix:

```bash
git add frontend/src/components/ValidatorCard.tsx frontend/src/components/ValidatorsPreview.tsx frontend/src/components/ValidatorsView.tsx frontend/src/styles.css frontend/tests/validatorEditor.test.ts frontend/e2e/demo-prompt.spec.ts
git commit -m "fix: polish validator cards redesign"
```

- [ ] **Step 7: Record final status**

Before final response, run:

```bash
git status --short
```

Expected: no output.

Report the verification commands that passed and any command that could not be run.

---

## Self-Review Notes

- Spec coverage:
  - large read-only cards: Task 1 and Task 2;
  - all checks visible without expansion: Task 1 and Task 4;
  - full-screen modal editing: Task 2 and Task 3;
  - dirty-close confirmation for modal edits: Task 2 and Task 4;
  - one normal `Add validator` action: Task 2;
  - version-level save workflow unchanged: Task 2 and Task 4;
  - accessibility and responsive behavior: Task 2, Task 3, and Task 5.
- Backend remains untouched because the approved design is a frontend UX redesign over the existing validator editing API.
- The plan uses frequent commits after independently testable chunks.
