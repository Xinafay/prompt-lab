# Prompt Lab UI Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Experiments, Case Suites, and Global Settings use one coherent workspace model: context-specific navigation, flat work areas, settings-hosted object actions, and a shared cases browsing layout.

**Architecture:** Keep the existing React/Vite single-page app and filesystem APIs. The work is frontend-focused: route Case Suite tabs, remove management actions from navigation rails, move object-level actions into Settings, flatten the Case Suite work area, and reuse the existing `CaseBrowser`, `settings-*`, `workbench-tabs`, and modal styles instead of introducing a new visual system.

**Tech Stack:** React 19, TypeScript, Vite, existing CSS, CodeMirror, Playwright e2e, node:test frontend tests.

---

## Current State

- Experiment routes are canonicalized as `/experiments/:experimentId/:tab`.
- Case Suite routes are canonicalized as `/case-suites/:suiteId`, but the suite view has no routeable internal tab.
- `App.tsx` renders `ExperimentsList` for both experiment and global settings views, so `/global-settings` still shows the experiments rail and `New`.
- `ExperimentsList` renders `Clone` and `Delete` inside the selected row, mixing navigation and object management.
- `CaseSuiteManager` wraps its whole content in `.case-suite-manager`, which is styled like a framed panel. Inside it, another framed `CaseBrowser` appears, creating the unnecessary "frame inside frame" effect.
- `CaseSuiteManager` shows suite metadata, suite actions, suite case actions, and case preview in one screen.
- `CaseBrowser` renders suite `Edit` and `Delete` buttons inside every case row, which makes the suite case list visually noisier than the experiment cases list.
- Experiment settings and global settings already share a clearer pattern: flat detail area, `settings-header`, `Reset`/`Save`, and `settings-section` cards.

## Target UX Rules

- The left rail is navigation only. It may contain `New`, but not `Clone`, `Delete`, or destructive object actions.
- Global Settings does not show the experiments rail.
- Experiment actions live in Experiment Settings:
  - `Experiment actions`: `Clone experiment`
  - `Danger zone`: `Delete experiment`
- Case Suite actions live in Case Suite Settings:
  - identity fields
  - references/usage
  - `Danger zone`: `Delete suite`
- Case Suite Cases is a sibling of Experiment Cases visually: one flat workspace with one `CaseBrowser`, not a framed manager containing another framed cases component.
- Case Suite tabs are URL-addressable:
  - `/case-suites/:suiteId/cases`
  - `/case-suites/:suiteId/settings`
  - `/case-suites/:suiteId` redirects or resolves to `cases`
- Case-level suite actions are attached to the selected case detail, not repeated in every list row.
- Modals have two explicit variants:
  - compact form modal for new/clone/delete/create object workflows
  - large code modal for `Add case` and `Edit case payload`

## File Structure

- `frontend/src/urlState.ts`
  - Add `CaseSuiteTab`, `caseSuiteTabs`, route parsing, and path building for `/case-suites/:suiteId/:tab`.
- `frontend/src/App.tsx`
  - Render context-specific rails.
  - Hide the rail for Global Settings.
  - Pass experiment clone/delete handlers into `ExperimentSettings`.
  - Pass Case Suite active tab and tab navigation into `CaseSuiteManager`.
  - Stop passing clone/delete handlers into `ExperimentsList`.
- `frontend/src/components/ExperimentsList.tsx`
  - Remove `onClone`, `onDelete`, and selected-row management actions.
- `frontend/src/components/ExperimentSettings.tsx`
  - Add object action sections for clone and delete.
- `frontend/src/components/CaseSuiteManager.tsx`
  - Split the view into routeable `Cases` and `Settings` tabs.
  - Remove the outer framed manager layout.
  - Move suite metadata and `Delete suite` into Settings.
  - Keep `Add case`, case reset, and case save visible only in Cases.
- `frontend/src/components/CaseBrowser.tsx`
  - Move suite edit/delete actions from each case row to the selected case detail header.
  - Keep experiment inclusion behavior unchanged.
- `frontend/src/components/CaseSuiteModals.tsx`
  - Keep the large CodeMirror payload modal and styled upload control, but align class names with the modal variants.
- `frontend/src/components/ExperimentManagementModals.tsx`
  - Reuse the compact modal variant class names.
- `frontend/src/styles.css`
  - Add full-width global settings layout.
  - Remove the extra Case Suite manager frame.
  - Add Case Suite workbench/tabs/settings/danger-zone styles using existing `settings-*` and `workbench-tabs` patterns.
  - Simplify case-row management action styles.
- `frontend/e2e/demo-prompt.spec.ts`
  - Update Case Suites e2e expectations for routeable tabs, no nested frame, settings actions, and experiment management moved to settings.

---

### Task 1: Lock The Desired UI In E2E Tests

**Files:**
- Modify: `frontend/e2e/demo-prompt.spec.ts`

- [ ] **Step 1: Add e2e coverage for global settings rail behavior**

Add this test after the Case Suites test:

```ts
test("global settings uses a full-width settings workspace", async ({ page }) => {
  await page.goto("/global-settings");

  await expect(page.getByRole("heading", { name: "Global settings" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Experiments" })).not.toBeVisible();
  await expect(page.getByRole("navigation", { name: "Case Suites" })).not.toBeVisible();
  await expect(page.getByRole("button", { name: "New" })).not.toBeVisible();
  await expect(page.getByRole("button", { name: "Save" })).toBeVisible();
});
```

- [ ] **Step 2: Replace the existing Case Suites expectations with tab-aware assertions**

In `demo cases tab shows suite-backed cases and opens case suites`, after clicking `Case Suites`, expect the canonical URL and tabs:

```ts
await page.getByRole("button", { name: "Case Suites" }).click();
await expect(page).toHaveURL(/\/case-suites\/demo-json-briefs\/cases$/);
await expect(page.getByRole("navigation", { name: "Case Suites" })).toBeVisible();
await expect(page.getByRole("tab", { name: "Cases" })).toHaveAttribute("aria-selected", "true");
await expect(page.getByRole("tab", { name: "Settings" })).toBeVisible();

const suiteWorkspace = page.getByRole("region", { name: "Case Suite workspace" });
await expect(suiteWorkspace).toBeVisible();
await expect(suiteWorkspace.getByRole("heading", { name: "Suite cases" })).not.toBeVisible();
await expect(suiteWorkspace.getByRole("region", { name: "Cases" })).toBeVisible();
await expect(suiteWorkspace.getByRole("button", { name: "Edit payload" })).toBeVisible();
await expect(suiteWorkspace.getByRole("button", { name: "Delete case" })).toBeVisible();
await expect(suiteWorkspace.getByRole("button", { name: "Delete suite" })).not.toBeVisible();
```

- [ ] **Step 3: Add e2e coverage for Case Suite Settings actions**

Add this assertion block in the same Case Suites test after the Cases assertions:

```ts
await page.getByRole("tab", { name: "Settings" }).click();
await expect(page).toHaveURL(/\/case-suites\/demo-json-briefs\/settings$/);
await expect(page.getByRole("heading", { name: "Case Suite settings" })).toBeVisible();
await expect(page.getByRole("button", { name: "Save" })).toBeVisible();
await expect(page.getByRole("button", { name: "Delete suite" })).toBeVisible();
await expect(page.getByRole("region", { name: "Cases" })).not.toBeVisible();

await page.reload();
await expect(page).toHaveURL(/\/case-suites\/demo-json-briefs\/settings$/);
await expect(page.getByRole("heading", { name: "Case Suite settings" })).toBeVisible();
```

- [ ] **Step 4: Add e2e coverage for experiment actions moved to settings**

Add this test:

```ts
test("experiment clone and delete actions live in settings", async ({ page }) => {
  await page.goto("/experiments/demo-json/prompt");

  const experimentRail = page.getByRole("navigation", { name: "Experiments" });
  await expect(experimentRail.getByRole("button", { name: "Clone" })).not.toBeVisible();
  await expect(experimentRail.getByRole("button", { name: "Delete" })).not.toBeVisible();

  await page.getByRole("tab", { name: "Settings" }).click();
  await expect(page).toHaveURL(/\/experiments\/demo-json\/settings$/);
  await expect(page.getByRole("button", { name: "Clone experiment" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Delete experiment" })).toBeVisible();

  await page.getByRole("button", { name: "Clone experiment" }).click();
  await expect(page.getByRole("dialog", { name: "Clone experiment" })).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();

  await page.getByRole("button", { name: "Delete experiment" }).click();
  await expect(page.getByRole("dialog", { name: "Delete experiment" })).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();
});
```

- [ ] **Step 5: Run the e2e test and verify failure**

Run:

```bash
cd frontend
pnpm test:e2e -- demo-prompt.spec.ts
```

Expected: fail because the app still renders global settings with the experiments rail, Case Suite tabs do not exist, Case Suite route lacks `/cases`, and experiment clone/delete actions still live in the rail.

- [ ] **Step 6: Commit the failing test changes**

```bash
git add frontend/e2e/demo-prompt.spec.ts
git commit -m "test: capture prompt lab UI consistency targets"
```

---

### Task 2: Make Case Suite Tabs Routeable And Global Settings Full Width

**Files:**
- Modify: `frontend/src/urlState.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Extend `urlState.ts` with Case Suite tabs**

Add these exports near `workbenchTabs`:

```ts
export const caseSuiteTabs = ["cases", "settings"] as const;
export type CaseSuiteTab = (typeof caseSuiteTabs)[number];
```

Change `CaseSuitesRoute` to:

```ts
export interface CaseSuitesRoute {
  suiteId: string | null;
  tab: CaseSuiteTab;
}
```

Add:

```ts
const DEFAULT_CASE_SUITE_TAB: CaseSuiteTab = "cases";

function isCaseSuiteTab(value: string | undefined): value is CaseSuiteTab {
  return caseSuiteTabs.includes(value as CaseSuiteTab);
}
```

Update `parseCaseSuitesRoute`:

```ts
export function parseCaseSuitesRoute(url: URL): CaseSuitesRoute {
  const segments = url.pathname
    .split("/")
    .map((segment) => segment.trim())
    .filter((segment) => segment !== "");
  const tabSegment = segments[2];
  return {
    suiteId: decodePathSegment(segments[1]),
    tab: isCaseSuiteTab(tabSegment) ? tabSegment : DEFAULT_CASE_SUITE_TAB
  };
}
```

Update `buildCaseSuitesPath`:

```ts
export function buildCaseSuitesPath(
  suiteId: string | null = null,
  tab: CaseSuiteTab = DEFAULT_CASE_SUITE_TAB
): string {
  if (suiteId === null) {
    return `/${CASE_SUITES_SEGMENT}`;
  }
  return `/${CASE_SUITES_SEGMENT}/${encodeURIComponent(suiteId)}/${tab}`;
}
```

- [ ] **Step 2: Update `App.tsx` imports and route writes**

Import `CaseSuiteTab`. Update all `buildCaseSuitesPath(selectedId)` calls to pass the active or default tab.

When parsing `currentCaseSuitesRoute()`, preserve `tab`. When selecting the Case Suites top-nav item from an experiment, route to the resolved suite with `"cases"`.

Add a handler:

```ts
function handleCaseSuiteTabSelection(tab: CaseSuiteTab) {
  if (selectedCaseSuiteId === null) return;
  writeCaseSuitesRoute("push", selectedCaseSuiteId, tab);
}
```

Use the existing dirty-case navigation guard before allowing tab changes if `caseSuiteCasesDirty` is true and the user is leaving the `cases` tab.

- [ ] **Step 3: Render Global Settings without a rail**

In `App.tsx`, change the workspace layout wrapper to use a full-width class for global settings:

```tsx
<div
  className={
    appView === "globalSettings"
      ? "tool-layout tool-layout-full"
      : "tool-layout"
  }
>
```

Render the left rail only for `caseSuites` and `experiment` views:

```tsx
{appView === "caseSuites" ? (
  <CaseSuitesList ... />
) : null}

{appView === "experiment" ? (
  <ExperimentsList ... />
) : null}
```

- [ ] **Step 4: Add full-width layout CSS**

Add:

```css
.tool-layout-full {
  grid-template-columns: 1fr;
}
```

- [ ] **Step 5: Run targeted checks**

Run:

```bash
cd frontend
pnpm lint
pnpm test:e2e -- demo-prompt.spec.ts
```

Expected: TypeScript passes after route updates. E2e still fails on Case Suite visual structure and experiment actions until later tasks are done.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/urlState.ts frontend/src/App.tsx frontend/src/styles.css
git commit -m "feat: route case suite tabs and simplify settings shell"
```

---

### Task 3: Move Experiment Clone And Delete Into Experiment Settings

**Files:**
- Modify: `frontend/src/components/ExperimentsList.tsx`
- Modify: `frontend/src/components/ExperimentSettings.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Remove management props from `ExperimentsList`**

Delete `onClone` and `onDelete` from `ExperimentsListProps`, function arguments, and the selected-row JSX block that renders `.experiment-nav-actions`.

Keep only:

```ts
interface ExperimentsListProps {
  experiments: Experiment[];
  selectedExperimentId: string | null;
  onCreate?: () => void;
  onSelect: (experiment: Experiment) => void;
}
```

- [ ] **Step 2: Add management callbacks to `ExperimentSettings`**

Add props:

```ts
onClone: (experiment: Experiment) => void;
onDelete: (experiment: Experiment) => void;
```

Append these sections after `Run defaults`:

```tsx
<section className="settings-section settings-section-actions">
  <h3>Experiment actions</h3>
  <p className="settings-section-description">
    Create a local copy of this experiment with its versions and artifacts.
  </p>
  <button
    className="secondary-action"
    disabled={isBusy}
    onClick={() => onClone(experiment)}
    type="button"
  >
    Clone experiment
  </button>
</section>

<section className="settings-section settings-section-danger">
  <h3>Danger zone</h3>
  <p className="settings-section-description">
    Delete this experiment from the local workspace.
  </p>
  <button
    className="secondary-action danger-action"
    disabled={isBusy}
    onClick={() => onDelete(experiment)}
    type="button"
  >
    Delete experiment
  </button>
</section>
```

- [ ] **Step 3: Pass callbacks from `App.tsx`**

Remove `onClone` and `onDelete` from `ExperimentsList`.

Where `ExperimentSettings` is rendered, pass:

```tsx
onClone={requestCloneExperiment}
onDelete={requestDeleteExperiment}
```

- [ ] **Step 4: Add action-section CSS**

Add:

```css
.settings-section-description {
  grid-column: 1 / -1;
  margin: -4px 0 0;
  color: #667085;
  font-size: 13px;
  line-height: 1.45;
}

.settings-section-actions,
.settings-section-danger {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
}

.settings-section-actions h3,
.settings-section-danger h3,
.settings-section-actions .settings-section-description,
.settings-section-danger .settings-section-description {
  grid-column: 1;
}

.settings-section-actions button,
.settings-section-danger button {
  grid-column: 2;
  grid-row: 1 / span 2;
  align-self: center;
}

.settings-section-danger {
  border-color: #fecaca;
  background: #fffafa;
}
```

- [ ] **Step 5: Run targeted checks**

Run:

```bash
cd frontend
pnpm lint
pnpm test:e2e -- demo-prompt.spec.ts
```

Expected: experiment action e2e assertions pass. Case Suite layout assertions still fail until Task 4 and Task 5.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ExperimentsList.tsx frontend/src/components/ExperimentSettings.tsx frontend/src/App.tsx frontend/src/styles.css
git commit -m "feat: move experiment actions into settings"
```

---

### Task 4: Flatten And Split The Case Suite Workspace

**Files:**
- Modify: `frontend/src/components/CaseSuiteManager.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Update `CaseSuiteManager` props**

Add:

```ts
import type { CaseSuiteTab } from "../urlState";
```

Add props:

```ts
activeTab: CaseSuiteTab;
onTabChange: (tab: CaseSuiteTab) => void;
```

- [ ] **Step 2: Replace the outer manager frame**

Change the top-level element from:

```tsx
<section className="case-suite-manager" aria-label="Case Suite details">
```

to:

```tsx
<section className="case-suite-workbench" aria-label="Case Suite workspace">
```

Remove the `.case-suite-detail` wrapper as a visual frame. Keep a simple content wrapper only if needed for layout, without border/background.

- [ ] **Step 3: Add a Case Suite header and tabs**

When `selectedSuite` exists, render:

```tsx
<div className="settings-header case-suite-workbench-header">
  <div>
    <h2>{selectedSuite.title}</h2>
    <p>{selectedSuite.id}</p>
  </div>
  {activeTab === "cases" ? (
    <div className="settings-actions">
      <TooltipButton
        className="secondary-action"
        disabled={isBusy || !caseSuiteCasesDirty}
        disabledReason="Change suite cases before resetting."
        onClick={onResetCases}
        type="button"
      >
        Reset
      </TooltipButton>
      <TooltipButton
        className="primary-action"
        disabled={saveSuiteCasesDisabled}
        disabledReason="Change suite cases before saving."
        onClick={onSaveCases}
        type="button"
      >
        Save
      </TooltipButton>
    </div>
  ) : (
    <div className="settings-actions">
      <TooltipButton ...>Reset</TooltipButton>
      <TooltipButton ...>Save</TooltipButton>
    </div>
  )}
</div>

<div className="workbench-tabs" role="tablist" aria-label="Case Suite tabs">
  <button
    aria-selected={activeTab === "cases"}
    className={activeTab === "cases" ? "workbench-tab is-active" : "workbench-tab"}
    onClick={() => onTabChange("cases")}
    role="tab"
    type="button"
  >
    Cases
  </button>
  <button
    aria-selected={activeTab === "settings"}
    className={activeTab === "settings" ? "workbench-tab is-active" : "workbench-tab"}
    onClick={() => onTabChange("settings")}
    role="tab"
    type="button"
  >
    Settings
  </button>
</div>
```

Use real `disabledReason` text based on dirty/busy state. Do not keep `Save changes` or `Reset suite case changes` labels.

- [ ] **Step 4: Implement the `Cases` tab**

Render only the status messages, a small toolbar, and `CaseBrowser`:

```tsx
{activeTab === "cases" ? (
  <div className="case-suite-cases-view">
    <div className="section-heading case-suite-cases-toolbar">
      <div>
        <h3>Cases</h3>
        <p>{formatCaseCount(cases.length)} in this suite</p>
      </div>
      <button
        className="secondary-action"
        disabled={isBusy || selectedSuite === null}
        onClick={onAddCase}
        type="button"
      >
        Add case
      </button>
    </div>
    {cases.length === 0 ? (
      <div className="case-browser-empty">No cases in this suite.</div>
    ) : (
      <CaseBrowser
        cases={cases}
        isBusy={isBusy}
        onDeleteCase={handleDeleteCase}
        onEditCase={setEditingCase}
        suiteTitle={selectedSuite.title}
      />
    )}
  </div>
) : null}
```

- [ ] **Step 5: Implement the `Settings` tab**

Move title/description editing and delete suite into a settings form:

```tsx
{activeTab === "settings" ? (
  <form className="settings-form" onSubmit={handleSaveSuiteSettings}>
    <section className="settings-section">
      <h3>Identity</h3>
      <label className="settings-field">
        <span>ID</span>
        <input readOnly value={selectedSuite.id} />
      </label>
      <label className="settings-field">
        <span>Title</span>
        <input ... />
      </label>
      <label className="settings-field settings-field-wide">
        <span>Description</span>
        <textarea ... />
      </label>
    </section>

    <section className="settings-section">
      <h3>Usage</h3>
      <p className="settings-section-description">
        {referencedBy.length === 0
          ? "This suite is not referenced by any experiment."
          : `Referenced by ${referencedBy.join(", ")}.`}
      </p>
    </section>

    <section className="settings-section settings-section-danger">
      <h3>Danger zone</h3>
      <p className="settings-section-description">
        Delete this reusable Case Suite from the local workspace.
      </p>
      <TooltipButton
        className="secondary-action danger-action"
        disabled={deleteDisabled}
        disabledReason={deleteDisabledReason}
        onClick={handleDeleteSuite}
        type="button"
      >
        Delete suite
      </TooltipButton>
    </section>
  </form>
) : null}
```

Rename the existing `handleSaveChanges` into `handleSaveSuiteSettings` and make it save only title/description. Case saving happens from the Cases tab header.

- [ ] **Step 6: Wire tabs in `App.tsx`**

Pass:

```tsx
activeTab={currentCaseSuitesRoute().tab}
onTabChange={handleCaseSuiteTabSelection}
```

When selecting a Case Suite from the rail, route to `/case-suites/:suiteId/cases`.

- [ ] **Step 7: Replace Case Suite manager CSS**

Remove `.case-suite-manager` from the shared framed selector:

```css
.overview-section,
.runs-panel,
.case-browser {
  ...
}
```

Add:

```css
.case-suite-workbench {
  display: grid;
  align-content: start;
  gap: 14px;
  min-width: 0;
}

.case-suite-workbench-header {
  min-width: 0;
}

.case-suite-cases-view {
  display: grid;
  gap: 12px;
  min-width: 0;
}

.case-suite-cases-toolbar {
  align-items: center;
}

.case-suite-cases-toolbar p {
  margin: 4px 0 0;
  color: #667085;
  font-size: 13px;
  line-height: 1.4;
}
```

Delete or stop using `.case-suite-detail`, `.case-suite-editor`, `.case-suite-cases-heading`, and `.case-suite-actions` rules if no longer referenced.

- [ ] **Step 8: Run targeted checks**

Run:

```bash
cd frontend
pnpm lint
pnpm test:e2e -- demo-prompt.spec.ts
```

Expected: Case Suite route/tab and "no nested Suite cases heading" assertions pass. Case edit/delete placement assertions may still fail until Task 5.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/CaseSuiteManager.tsx frontend/src/App.tsx frontend/src/styles.css
git commit -m "feat: flatten case suite workspace"
```

---

### Task 5: Move Suite Case Edit/Delete To The Selected Case Detail

**Files:**
- Modify: `frontend/src/components/CaseBrowser.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/e2e/demo-prompt.spec.ts` if accessible names need adjustment

- [ ] **Step 1: Remove suite action buttons from case rows**

In `CaseBrowser`, keep the `Include in runs` row control for experiment mode. Remove row rendering of `onEditCase` and `onDeleteCase` buttons from `.case-browser-item-actions`.

The row actions block should become:

```tsx
{canEdit ? (
  <div className="case-browser-item-actions">
    <label
      className="case-run-toggle"
      onClick={(event) => event.stopPropagation()}
    >
      <input ... />
      <span>Include in runs</span>
    </label>
  </div>
) : null}
```

- [ ] **Step 2: Add selected case management actions to the detail header**

Inside `.case-detail-heading`, add:

```tsx
<div className="case-detail-summary">
  <span>
    {selectedPayloadEntries.length} of {selectedPayloadCount} payload
    key{selectedPayloadCount === 1 ? "" : "s"}
  </span>
  {selectedCase.enabled ? null : (
    <span className="case-state-badge">Excluded</span>
  )}
  {onEditCase === undefined && onDeleteCase === undefined ? null : (
    <div className="case-detail-actions">
      {onEditCase === undefined ? null : (
        <button
          className="secondary-action"
          disabled={isBusy}
          onClick={() => onEditCase(selectedCase)}
          type="button"
        >
          Edit payload
        </button>
      )}
      {onDeleteCase === undefined ? null : (
        <button
          className="secondary-action danger-action"
          disabled={isBusy}
          onClick={() => onDeleteCase(selectedCase)}
          type="button"
        >
          Delete case
        </button>
      )}
    </div>
  )}
</div>
```

- [ ] **Step 3: Add detail action CSS**

Add:

```css
.case-detail-summary {
  display: grid;
  justify-items: end;
  gap: 8px;
  min-width: 180px;
}

.case-detail-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.case-detail-actions .secondary-action {
  min-height: 30px;
  padding: 0 10px;
  font-size: 12px;
}
```

Remove now-unused `.case-browser-item-actions .danger-action` rules.

- [ ] **Step 4: Run targeted checks**

Run:

```bash
cd frontend
pnpm lint
pnpm test:e2e -- demo-prompt.spec.ts
```

Expected: Case Suite edit/delete assertions pass with `Edit payload` and `Delete case`. Experiment `Include in runs` behavior remains unchanged.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/CaseBrowser.tsx frontend/src/styles.css frontend/e2e/demo-prompt.spec.ts
git commit -m "feat: move suite case actions to detail pane"
```

---

### Task 6: Normalize Modal Variants And Upload Styling

**Files:**
- Modify: `frontend/src/components/CaseSuiteModals.tsx`
- Modify: `frontend/src/components/ExperimentManagementModals.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Rename modal classes to explicit variants**

Use:

```tsx
className="modal-card modal-card-compact"
```

for `NewExperimentModal`, `CloneExperimentModal`, `DeleteExperimentModal`, and `NewCaseSuiteModal`.

Use:

```tsx
className="modal-card modal-card-large-code"
```

for `AddCaseModal` and `EditCasePayloadModal`.

- [ ] **Step 2: Keep backward-compatible CSS during migration**

Replace modal sizing CSS with:

```css
.modal-card,
.settings-navigation-modal {
  display: grid;
  gap: 16px;
  width: min(520px, 100%);
  padding: 18px;
  border: 1px solid #d0d5dd;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 24px 60px rgb(16 24 40 / 0.22);
}

.modal-card h2,
.settings-navigation-modal h2 {
  margin: 0;
  color: #111827;
  font-size: 18px;
  font-weight: 760;
  line-height: 1.25;
}

.modal-card p,
.settings-navigation-modal p {
  margin: 6px 0 0;
  color: #667085;
  font-size: 14px;
  line-height: 1.45;
}

.modal-card-compact,
.experiment-management-modal {
  width: min(560px, 100%);
}

.modal-card-large-code,
.case-payload-modal {
  width: min(1040px, 100%);
  max-height: calc(100vh - 48px);
  overflow: auto;
}
```

After all modal JSX uses `modal-card-*`, delete obsolete `.settings-navigation-modal`, `.experiment-management-modal`, and `.case-payload-modal` selectors if no longer used.

- [ ] **Step 3: Keep the styled upload control as the only file input UI**

Verify that `AddCaseModal` still hides the native input with `.case-file-input` and shows only:

```tsx
<span className="case-file-picker-button">Choose JSON file</span>
<span className="case-file-picker-name">
  {uploadFileName ?? "No file selected"}
</span>
```

Do not reintroduce browser-native file input chrome.

- [ ] **Step 4: Run targeted checks**

Run:

```bash
cd frontend
pnpm lint
pnpm test:e2e -- demo-prompt.spec.ts
```

Expected: modal tests still pass. Screenshots should show compact management modals and large CodeMirror payload modals.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/CaseSuiteModals.tsx frontend/src/components/ExperimentManagementModals.tsx frontend/src/styles.css
git commit -m "style: clarify modal size variants"
```

---

### Task 7: Browser QA And Visual Cleanup

**Files:**
- Modify only files from previous tasks if QA reveals visual defects.

- [ ] **Step 1: Run full frontend verification**

Run:

```bash
cd frontend
pnpm test
pnpm lint
pnpm build
pnpm test:e2e
```

Expected: all commands pass.

- [ ] **Step 2: Inspect the running app in the in-app browser**

Use the user-visible browser tab and verify:

- `/experiments/demo-json/prompt`
- `/experiments/demo-json/settings`
- `/experiments/demo-json/cases`
- `/case-suites/demo-json-briefs/cases`
- `/case-suites/demo-json-briefs/settings`
- `/case-suites/story-chapters/cases`
- `/global-settings`

For each view, check:

- no Vite overlay
- no console errors
- no text overlap
- no nested Case Suite frame around `CaseBrowser`
- `Global settings` has no experiments rail
- `Clone experiment` and `Delete experiment` appear only in Experiment Settings
- `Delete suite` appears only in Case Suite Settings
- Case Suite `Add case` opens the large code modal with styled upload
- `Edit payload` opens the large code modal

- [ ] **Step 3: Capture screenshots**

Save screenshots for:

- Case Suite Cases
- Case Suite Settings
- Experiment Settings
- Global Settings
- Add Case modal
- Edit Case Payload modal

Use these screenshots to compare against the audit screenshots in `/private/tmp/prompt-lab-ui-audit-1782403533035`.

- [ ] **Step 4: Apply small CSS fixes only if needed**

Allowed cleanup examples:

- reduce excessive vertical blank space in `CaseBrowser`
- adjust `.case-detail-summary` wrapping
- make danger-zone buttons align on mobile
- ensure `workbench-tabs` on Case Suite matches experiment tabs

Do not introduce a new palette, new card system, or unrelated layout refactor.

- [ ] **Step 5: Re-run verification after any fixes**

Run:

```bash
cd frontend
pnpm lint
pnpm build
pnpm test:e2e
```

Expected: all pass.

- [ ] **Step 6: Commit QA fixes**

If Step 4 changed files:

```bash
git add frontend/src
git commit -m "style: polish prompt lab workspace consistency"
```

If Step 4 changed no files, do not create an empty commit.

---

## Self-Review

- Spec coverage:
  - Context-specific navigation is covered by Tasks 1 and 2.
  - Experiment clone/delete relocation is covered by Task 3.
  - Case Suite frame removal and clearer layout are covered by Task 4.
  - Case Suite case action noise is covered by Task 5.
  - Modal consistency and upload styling are covered by Task 6.
  - Browser screenshots and full verification are covered by Task 7.
- Placeholder scan:
  - No unfinished-placeholder markers are left in executable steps.
- Scope check:
  - This plan is frontend-focused and does not require backend API changes.
  - Case Suite data persistence already exists; this plan reorganizes existing UI actions and routes.
- Risk:
  - `App.tsx` is large, so route and dirty-navigation changes should be reviewed carefully after each task.
  - Case Suite settings dirty-state is currently local to `CaseSuiteManager`; if implementation reveals navigation-loss risk, mirror the existing `ExperimentSettings` `onDirtyChange` pattern in a small follow-up commit.
