# CodeMirror Prompt And Model Viewers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace plain prompt/model `<pre>` rendering with read-only CodeMirror viewers, add Pydantic model visibility on overview, and add unified proposal diffs.

**Architecture:** Backend overview responses will expose the current Pydantic model source alongside the current prompt. Frontend viewer components will encapsulate CodeMirror setup, read-only state, language selection, and unified diff rendering. Existing overview/proposal components will consume those viewers while preserving current workflow actions and empty states.

**Tech Stack:** Python 3.14, FastAPI, Pydantic, filesystem artifacts, React 19, Vite, TypeScript, CodeMirror 6, Node test runner, Playwright e2e.

---

## File Structure

- Modify `backend/prompt_lab/api.py`: include current `model_py` and `model_file` in version overview responses for Pydantic experiments.
- Modify `backend/tests/test_api.py`: assert text overview returns null model fields and Pydantic overview returns model source.
- Modify `frontend/package.json` and `frontend/pnpm-lock.yaml`: add CodeMirror 6 packages.
- Modify `frontend/src/types.ts`: extend `VersionOverview` with optional model source fields.
- Create `frontend/src/components/CodeViewer.tsx`: read-only CodeMirror single-file and unified diff viewers.
- Create `frontend/src/components/CodeViewer.css`: CodeMirror styling, Jinja token styling, fixed viewer dimensions.
- Create `frontend/tests/codeViewer.test.ts`: SSR fallback coverage for `CodeViewer` and `DiffViewer`.
- Modify `frontend/src/components/ExperimentOverview.tsx`: render prompt/model viewers in an artifact grid.
- Create `frontend/tests/experimentOverview.test.ts`: SSR coverage for text and Pydantic overview layout.
- Modify `frontend/src/components/ProposalView.tsx`: render new-version/diff modes with rationale and artifact panels.
- Create `frontend/tests/proposalView.test.ts`: SSR coverage for text and Pydantic proposal layout.
- Modify `frontend/src/App.tsx`: pass current prompt/model baseline into `ProposalView`.
- Modify `frontend/src/styles.css`: overview/proposal artifact grid and responsive styles.
- Modify `frontend/e2e/demo-overview.spec.ts`: cover demo-json overview and proposal diff interactions.

## Task 1: Backend Overview Contract

**Files:**
- Modify: `backend/tests/test_api.py`
- Modify: `backend/prompt_lab/api.py:1324-1342`

- [ ] **Step 1: Write failing backend tests**

In `backend/tests/test_api.py`, update `test_api_gets_version_overview` after the existing prompt/rubric assertions:

```python
        assert body["prompt"] == "Say {{ value }}"
        assert body["model_py"] is None
        assert body["model_file"] is None
        assert body["rubric"] == "Prefer concise answers."
```

Add this test immediately after `test_api_gets_version_overview`:

```python
def test_api_gets_pydantic_version_overview_model_source() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_demo_pydantic_experiment(root)
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app).get("/api/experiments/demo/versions/v001")

        assert response.status_code == 200
        body = response.json()
        assert body["experiment"]["output"]["type"] == "pydantic"
        assert body["version"] == "v001"
        assert body["prompt"] == "Say {{ value }}\n\n<<MODEL>>"
        assert body["model_file"] == "model.py"
        assert body["model_py"] == (
            "from pydantic import BaseModel\n\n"
            "class DemoOutput(BaseModel):\n"
            "    answer: str\n"
        )
```

- [ ] **Step 2: Run backend test to verify failure**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_api.py
```

Expected: FAIL because `model_py` and `model_file` are absent from the overview response.

- [ ] **Step 3: Implement backend response fields**

In `backend/prompt_lab/api.py`, replace the `get_experiment_version` body from the `prompt_template = store.read_text(` statement through the returned dict with:

```python
        prompt_template = store.read_text(
            experiment_id, version, experiment.template.path
        )
        model_file = None
        model_source = None
        if experiment.output.type == "pydantic":
            model_file = experiment.output.model_file
            assert model_file is not None
            model_source = store.read_text(experiment_id, version, model_file)
        cases = store.load_cases(experiment_id)
        validators = store.load_validators(experiment_id)
        return {
            "experiment": experiment.model_dump(mode="json"),
            "version": version,
            "prompt": prompt_template,
            "model_py": model_source,
            "model_file": model_file,
            "rubric": _read_optional_text(experiment_dir / "rubric.md"),
            "cases": [case.model_dump(mode="json") for case in cases],
            "validators": [validator.model_dump(mode="json") for validator in validators],
        }
```

- [ ] **Step 4: Run backend test to verify pass**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_api.py
```

Expected: PASS.

- [ ] **Step 5: Commit backend contract**

```bash
git add backend/prompt_lab/api.py backend/tests/test_api.py
git commit -m "Expose model source in version overview"
```

## Task 2: CodeMirror Dependencies And Types

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/pnpm-lock.yaml`
- Modify: `frontend/src/types.ts`

- [ ] **Step 1: Install current CodeMirror packages**

Run from the repository root:

```bash
cd frontend && pnpm add codemirror@6.0.2 @codemirror/lang-markdown@6.5.0 @codemirror/lang-python@6.2.1 @codemirror/merge@6.12.2 @codemirror/state@6.6.0 @codemirror/view@6.43.1
```

Expected: `frontend/package.json` and `frontend/pnpm-lock.yaml` update. `@codemirror/state` and `@codemirror/view` are installed directly because the viewer implementation imports read-only facets and decoration APIs under `pnpm`.

- [ ] **Step 2: Extend frontend overview type**

In `frontend/src/types.ts`, update `VersionOverview` to:

```ts
export interface VersionOverview {
  experiment: Experiment;
  version: string;
  prompt: string;
  model_py?: string | null;
  model_file?: string | null;
  rubric: string;
  cases: Case[];
  validators: ValidatorDefinition[];
}
```

- [ ] **Step 3: Run TypeScript check**

Run:

```bash
cd frontend && pnpm lint
```

Expected: PASS.

- [ ] **Step 4: Commit dependencies and type contract**

```bash
git add frontend/package.json frontend/pnpm-lock.yaml frontend/src/types.ts
git commit -m "Add CodeMirror dependencies and model overview type"
```

## Task 3: Read-Only CodeMirror Viewer Components

**Files:**
- Create: `frontend/src/components/CodeViewer.tsx`
- Create: `frontend/src/components/CodeViewer.css`
- Create: `frontend/tests/codeViewer.test.ts`

- [ ] **Step 1: Write viewer SSR tests**

Create `frontend/tests/codeViewer.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { CodeViewer, DiffViewer } from "../src/components/CodeViewer.tsx";

test("code viewer renders an SSR fallback with language and label", () => {
  const html = renderToStaticMarkup(
    React.createElement(CodeViewer, {
      label: "Prompt",
      language: "markdown-jinja",
      value: "Hello {{ name }}\n\n<<MODEL>>"
    })
  );

  assert.match(html, /aria-label="Prompt"/);
  assert.match(html, /data-language="markdown-jinja"/);
  assert.match(html, /Hello \{\{ name \}\}/);
  assert.match(html, /&lt;&lt;MODEL&gt;&gt;/);
});

test("diff viewer renders an SSR fallback with original and proposed text", () => {
  const html = renderToStaticMarkup(
    React.createElement(DiffViewer, {
      label: "Prompt diff",
      language: "markdown-jinja",
      original: "Old prompt",
      value: "New prompt"
    })
  );

  assert.match(html, /aria-label="Prompt diff"/);
  assert.match(html, /data-language="markdown-jinja"/);
  assert.match(html, /Original/);
  assert.match(html, /Old prompt/);
  assert.match(html, /Proposed/);
  assert.match(html, /New prompt/);
});
```

- [ ] **Step 2: Run viewer tests to verify failure**

Run:

```bash
cd frontend && pnpm test -- codeViewer.test.ts
```

Expected: FAIL because `frontend/src/components/CodeViewer.tsx` does not exist.

- [ ] **Step 3: Implement CodeMirror viewers**

Create `frontend/src/components/CodeViewer.tsx`:

```tsx
import { useEffect, useMemo, useRef } from "react";
import { EditorState, type Extension } from "@codemirror/state";
import {
  Decoration,
  EditorView,
  MatchDecorator,
  ViewPlugin,
  type DecorationSet,
  type ViewUpdate
} from "@codemirror/view";
import { markdown } from "@codemirror/lang-markdown";
import { python } from "@codemirror/lang-python";
import { unifiedMergeView } from "@codemirror/merge";
import { basicSetup } from "codemirror";

import "./CodeViewer.css";

export type CodeViewerLanguage = "markdown-jinja" | "python";

interface CodeViewerProps {
  label: string;
  language: CodeViewerLanguage;
  value: string;
}

interface DiffViewerProps {
  label: string;
  language: CodeViewerLanguage;
  original: string;
  value: string;
}

const jinjaMatcher = new MatchDecorator({
  regexp: /{{[\s\S]*?}}|{%[\s\S]*?%}|{#[\s\S]*?#}|<<MODEL>>/g,
  decoration: (match) =>
    Decoration.mark({
      class:
        match[0] === "<<MODEL>>"
          ? "cm-promptlab-model-marker"
          : "cm-promptlab-jinja"
    })
});

const jinjaHighlight = ViewPlugin.fromClass(
  class {
    decorations: DecorationSet;

    constructor(view: EditorView) {
      this.decorations = jinjaMatcher.createDeco(view);
    }

    update(update: ViewUpdate) {
      this.decorations = jinjaMatcher.updateDeco(update, this.decorations);
    }
  },
  {
    decorations: (plugin) => plugin.decorations
  }
);

function languageExtensions(language: CodeViewerLanguage): Extension[] {
  if (language === "python") {
    return [python()];
  }
  return [markdown(), jinjaHighlight];
}

function baseExtensions(language: CodeViewerLanguage): Extension[] {
  return [
    basicSetup,
    EditorState.readOnly.of(true),
    EditorView.editable.of(false),
    EditorView.lineWrapping,
    EditorView.theme({
      "&": {
        fontSize: "13px"
      },
      ".cm-content": {
        fontFamily:
          "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace"
      },
      ".cm-scroller": {
        fontFamily:
          "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace"
      }
    }),
    languageExtensions(language)
  ];
}

function ssrCodeFallback({
  label,
  language,
  value
}: CodeViewerProps) {
  return (
    <pre
      aria-label={label}
      className="code-viewer code-viewer-ssr"
      data-language={language}
    >
      {value}
    </pre>
  );
}

export function CodeViewer({ label, language, value }: CodeViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const extensions = useMemo(() => baseExtensions(language), [language]);

  useEffect(() => {
    if (containerRef.current === null) {
      return undefined;
    }

    const view = new EditorView({
      doc: value,
      extensions,
      parent: containerRef.current
    });

    return () => view.destroy();
  }, [extensions, value]);

  if (typeof document === "undefined") {
    return ssrCodeFallback({ label, language, value });
  }

  return (
    <div
      aria-label={label}
      className="code-viewer"
      data-language={language}
      ref={containerRef}
    />
  );
}

export function DiffViewer({
  label,
  language,
  original,
  value
}: DiffViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const extensions = useMemo(
    () => [
      ...baseExtensions(language),
      unifiedMergeView({
        original,
        highlightChanges: true,
        gutter: true
      })
    ],
    [language, original]
  );

  useEffect(() => {
    if (containerRef.current === null) {
      return undefined;
    }

    const view = new EditorView({
      doc: value,
      extensions,
      parent: containerRef.current
    });

    return () => view.destroy();
  }, [extensions, value]);

  if (typeof document === "undefined") {
    return (
      <div
        aria-label={label}
        className="code-viewer code-viewer-ssr code-viewer-diff-ssr"
        data-language={language}
      >
        <pre>Original{"\n"}{original}</pre>
        <pre>Proposed{"\n"}{value}</pre>
      </div>
    );
  }

  return (
    <div
      aria-label={label}
      className="code-viewer code-viewer-diff"
      data-language={language}
      ref={containerRef}
    />
  );
}
```

- [ ] **Step 4: Add viewer styles**

Create `frontend/src/components/CodeViewer.css`:

```css
.code-viewer {
  min-height: 220px;
  max-height: 520px;
  overflow: auto;
  border: 1px solid #e4e7ec;
  border-radius: 8px;
  background: #f9fafb;
}

.code-viewer .cm-editor {
  min-height: 220px;
  background: #f9fafb;
}

.code-viewer .cm-scroller {
  max-height: 520px;
  overflow: auto;
}

.code-viewer .cm-gutters {
  border-right-color: #e4e7ec;
  background: #f2f4f7;
  color: #667085;
}

.code-viewer .cm-activeLine,
.code-viewer .cm-activeLineGutter {
  background: transparent;
}

.code-viewer .cm-promptlab-jinja {
  color: #9a3412;
  font-weight: 700;
}

.code-viewer .cm-promptlab-model-marker {
  color: #1d4ed8;
  font-weight: 800;
}

.code-viewer-ssr {
  margin: 0;
  padding: 12px;
  color: #344054;
  font-size: 13px;
  line-height: 1.55;
  white-space: pre-wrap;
}

.code-viewer-diff-ssr {
  display: grid;
  gap: 10px;
  padding: 12px;
}

.code-viewer-diff-ssr pre {
  margin: 0;
  white-space: pre-wrap;
}
```

- [ ] **Step 5: Run viewer tests and lint**

Run:

```bash
cd frontend && pnpm test -- codeViewer.test.ts && pnpm lint
```

Expected: PASS.

- [ ] **Step 6: Commit viewer components**

```bash
git add frontend/src/components/CodeViewer.tsx frontend/src/components/CodeViewer.css frontend/tests/codeViewer.test.ts
git commit -m "Add read-only CodeMirror viewers"
```

## Task 4: Overview Prompt And Model Viewers

**Files:**
- Modify: `frontend/src/components/ExperimentOverview.tsx`
- Modify: `frontend/src/styles.css`
- Create: `frontend/tests/experimentOverview.test.ts`

- [ ] **Step 1: Write overview render tests**

Create `frontend/tests/experimentOverview.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { ExperimentOverview } from "../src/components/ExperimentOverview.tsx";
import type { VersionOverview } from "../src/types.ts";

function baseOverview(outputType: "text" | "pydantic"): VersionOverview {
  return {
    experiment: {
      schema_version: "prompt_lab.experiment/v1",
      id: "demo",
      title: "Demo",
      description: "Demo experiment",
      active_version: "v001",
      output:
        outputType === "pydantic"
          ? {
              type: "pydantic",
              model_file: "model.py",
              model_entrypoint: "model.DemoOutput"
            }
          : { type: "text" },
      template: { engine: "jinjax", path: "prompt.md" },
      models: {
        generator_model: "local/generator",
        validator_model: "local/validator",
        judge_model: "local/judge"
      },
      run_defaults: {
        repeat_count: 1,
        llm_cache: "disabled",
        case_order: "case-major"
      }
    },
    version: "v001",
    prompt: "Say {{ value }}",
    model_py:
      outputType === "pydantic"
        ? "from pydantic import BaseModel\n\nclass DemoOutput(BaseModel):\n    answer: str\n"
        : null,
    model_file: outputType === "pydantic" ? "model.py" : null,
    rubric: "",
    cases: [],
    validators: []
  };
}

test("overview renders prompt viewer without model panel for text output", () => {
  const html = renderToStaticMarkup(
    React.createElement(ExperimentOverview, {
      overview: baseOverview("text"),
      isRunning: false,
      onRunVersion: () => undefined
    })
  );

  assert.match(html, /Prompt/);
  assert.match(html, /Say \{\{ value \}\}/);
  assert.doesNotMatch(html, /Model/);
  assert.doesNotMatch(html, /model.py/);
});

test("overview renders prompt and model viewers for pydantic output", () => {
  const html = renderToStaticMarkup(
    React.createElement(ExperimentOverview, {
      overview: baseOverview("pydantic"),
      isRunning: false,
      onRunVersion: () => undefined
    })
  );

  assert.match(html, /Prompt/);
  assert.match(html, /Model/);
  assert.match(html, /model.py/);
  assert.match(html, /DemoOutput/);
});
```

- [ ] **Step 2: Run overview tests to verify failure**

Run:

```bash
cd frontend && pnpm test -- experimentOverview.test.ts
```

Expected: FAIL because overview still renders `<pre className="code-block">` and no model panel.

- [ ] **Step 3: Update overview component**

In `frontend/src/components/ExperimentOverview.tsx`, add the import:

```ts
import { CodeViewer } from "./CodeViewer";
```

Inside `ExperimentOverview`, before `return`, add:

```ts
  const hasPydanticModel = overview.experiment.output.type === "pydantic";
```

Replace the current prompt section with:

```tsx
      <div
        className={
          hasPydanticModel
            ? "overview-source-grid"
            : "overview-source-grid overview-source-grid-single"
        }
      >
        <div className="overview-section">
          <div className="section-heading">
            <h3>Prompt</h3>
            <span>{overview.version}</span>
          </div>
          <CodeViewer
            label="Prompt"
            language="markdown-jinja"
            value={overview.prompt}
          />
        </div>

        {hasPydanticModel ? (
          <div className="overview-section">
            <div className="section-heading">
              <h3>Model</h3>
              <span>{overview.model_file ?? "model.py"}</span>
            </div>
            {overview.model_py ? (
              <CodeViewer
                label="Model"
                language="python"
                value={overview.model_py}
              />
            ) : (
              <div className="empty-inline">Model source unavailable.</div>
            )}
          </div>
        ) : null}
      </div>
```

- [ ] **Step 4: Add overview grid styles**

In `frontend/src/styles.css`, after `.overview-grid`, add:

```css
.overview-source-grid {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.overview-source-grid-single {
  grid-template-columns: minmax(0, 1fr);
}
```

In the existing mobile media block that already changes `.overview-grid`, add:

```css
  .overview-source-grid {
    grid-template-columns: minmax(0, 1fr);
  }
```

- [ ] **Step 5: Run overview tests and lint**

Run:

```bash
cd frontend && pnpm test -- experimentOverview.test.ts && pnpm lint
```

Expected: PASS.

- [ ] **Step 6: Commit overview UI**

```bash
git add frontend/src/components/ExperimentOverview.tsx frontend/src/styles.css frontend/tests/experimentOverview.test.ts
git commit -m "Show prompt and model viewers on overview"
```

## Task 5: Proposal New-Version And Unified Diff Views

**Files:**
- Modify: `frontend/src/components/ProposalView.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`
- Create: `frontend/tests/proposalView.test.ts`

- [ ] **Step 1: Write proposal render tests**

Create `frontend/tests/proposalView.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { ProposalView } from "../src/components/ProposalView.tsx";
import type { ProposalResponse } from "../src/types.ts";

function proposal(model_py?: string | null): ProposalResponse {
  return {
    proposal_dir: "/tmp/proposal",
    source: { output_type: model_py ? "pydantic" : "text" },
    proposal: {
      prompt_md: "Improved prompt\n\n<<MODEL>>",
      model_py,
      rationale_md: "This change addresses accepted findings."
    }
  };
}

const commonProps = {
  reviewState: null,
  createdVersion: null,
  isBusy: false,
  hasUnsavedReviewChanges: false,
  onGenerateProposal: () => undefined,
  onCreateVersion: () => undefined
};

test("text proposal renders rationale and prompt without model panel", () => {
  const html = renderToStaticMarkup(
    React.createElement(ProposalView, {
      ...commonProps,
      currentPrompt: "Current prompt",
      currentModel: null,
      currentModelFile: null,
      proposalResponse: proposal(null)
    })
  );

  assert.match(html, /New version/);
  assert.match(html, /Diff/);
  assert.match(html, /Rationale/);
  assert.match(html, /Proposed prompt/);
  assert.match(html, /Improved prompt/);
  assert.doesNotMatch(html, /Proposed model/);
});

test("pydantic proposal renders prompt and model artifact panels", () => {
  const html = renderToStaticMarkup(
    React.createElement(ProposalView, {
      ...commonProps,
      currentPrompt: "Current prompt\n\n<<MODEL>>",
      currentModel: "class OldModel: pass\n",
      currentModelFile: "model.py",
      proposalResponse: proposal("class NewModel: pass\n")
    })
  );

  assert.match(html, /New version/);
  assert.match(html, /Diff/);
  assert.match(html, /Rationale/);
  assert.match(html, /Proposed prompt/);
  assert.match(html, /Proposed model/);
  assert.match(html, /model.py/);
  assert.match(html, /NewModel/);
});
```

- [ ] **Step 2: Run proposal tests to verify failure**

Run:

```bash
cd frontend && pnpm test -- proposalView.test.ts
```

Expected: FAIL because `ProposalView` does not accept current baseline props and still renders section tabs.

- [ ] **Step 3: Update ProposalView props and state**

In `frontend/src/components/ProposalView.tsx`, replace the imports and local section type with:

```tsx
import { useState } from "react";

import type { CreatedVersionResponse, ProposalResponse, ReviewState } from "../types";
import { CodeViewer, DiffViewer } from "./CodeViewer";
import { TooltipButton } from "./TooltipButton";

type ProposalViewMode = "new" | "diff";
```

Extend `ProposalViewProps` with:

```ts
  currentPrompt: string;
  currentModel: string | null;
  currentModelFile: string | null;
```

Inside `ProposalView`, replace the active section state and derived section logic with:

```tsx
  const [viewMode, setViewMode] = useState<ProposalViewMode>("new");
  const hasModel = Boolean(proposalResponse?.proposal.model_py);
```

- [ ] **Step 4: Replace proposal content rendering**

In `ProposalView`, replace the current proposal content block from `<div className="proposal-content">` through the created-version success paragraph with:

```tsx
        <div className="proposal-content">
          <div className="proposal-toolbar">
            <div className="proposal-tabs" role="tablist" aria-label="Proposal view">
              {(["new", "diff"] as ProposalViewMode[]).map((mode) => (
                <button
                  aria-selected={viewMode === mode}
                  className={
                    viewMode === mode ? "proposal-tab is-active" : "proposal-tab"
                  }
                  key={mode}
                  onClick={() => setViewMode(mode)}
                  role="tab"
                  type="button"
                >
                  {mode === "new" ? "New version" : "Diff"}
                </button>
              ))}
            </div>
            <TooltipButton
              className="primary-action"
              disabled={isBusy}
              disabledReason="Wait for the current workflow action to finish."
              onClick={onCreateVersion}
              type="button"
            >
              Create next version
            </TooltipButton>
          </div>

          <div className="proposal-section proposal-rationale">
            <h4>Rationale</h4>
            <pre className="text-block">{proposalResponse.proposal.rationale_md}</pre>
          </div>

          <div
            className={
              hasModel
                ? "proposal-artifact-grid"
                : "proposal-artifact-grid proposal-artifact-grid-single"
            }
          >
            <div className="proposal-section">
              <h4>{viewMode === "diff" ? "Prompt diff" : "Proposed prompt"}</h4>
              {viewMode === "diff" ? (
                <DiffViewer
                  label="Prompt diff"
                  language="markdown-jinja"
                  original={currentPrompt}
                  value={proposalResponse.proposal.prompt_md}
                />
              ) : (
                <CodeViewer
                  label="Proposed prompt"
                  language="markdown-jinja"
                  value={proposalResponse.proposal.prompt_md}
                />
              )}
            </div>

            {proposalResponse.proposal.model_py ? (
              <div className="proposal-section">
                <h4>{viewMode === "diff" ? "Model diff" : "Proposed model"}</h4>
                <p className="artifact-caption">{currentModelFile ?? "model.py"}</p>
                {viewMode === "diff" ? (
                  <DiffViewer
                    label="Model diff"
                    language="python"
                    original={currentModel ?? ""}
                    value={proposalResponse.proposal.model_py}
                  />
                ) : (
                  <CodeViewer
                    label="Proposed model"
                    language="python"
                    value={proposalResponse.proposal.model_py}
                  />
                )}
              </div>
            ) : null}
          </div>

          {createdVersion !== null ? (
            <p className="success-copy">Created {createdVersion.version}</p>
          ) : null}
        </div>
```

- [ ] **Step 5: Pass baseline props from App**

In `frontend/src/App.tsx`, update the `ProposalView` call:

```tsx
                      <ProposalView
                        createdVersion={createdVersion}
                        currentModel={detailState.overview.model_py ?? null}
                        currentModelFile={detailState.overview.model_file ?? null}
                        currentPrompt={detailState.overview.prompt}
                        hasUnsavedReviewChanges={hasUnsavedReviewChanges}
                        isBusy={workflowLocked}
                        onCreateVersion={handleCreateVersion}
                        onGenerateProposal={handleGenerateProposal}
                        proposalResponse={proposalResponse}
                        reviewState={reviewState}
                      />
```

- [ ] **Step 6: Add proposal layout styles**

In `frontend/src/styles.css`, after `.proposal-content`, add:

```css
.proposal-artifact-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.proposal-artifact-grid-single {
  grid-template-columns: minmax(0, 1fr);
}

.proposal-rationale {
  min-width: 0;
}

.artifact-caption {
  margin: -4px 0 8px;
  color: #667085;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.4;
}
```

In the existing mobile media block, add:

```css
  .proposal-artifact-grid {
    grid-template-columns: minmax(0, 1fr);
  }
```

- [ ] **Step 7: Run proposal tests and lint**

Run:

```bash
cd frontend && pnpm test -- proposalView.test.ts && pnpm lint
```

Expected: PASS.

- [ ] **Step 8: Commit proposal UI**

```bash
git add frontend/src/components/ProposalView.tsx frontend/src/App.tsx frontend/src/styles.css frontend/tests/proposalView.test.ts
git commit -m "Add proposal new version and diff views"
```

## Task 6: E2E Coverage For Demo Workflows

**Files:**
- Modify: `frontend/e2e/demo-overview.spec.ts`

- [ ] **Step 1: Add e2e tests**

Append these tests to `frontend/e2e/demo-overview.spec.ts`:

```ts
test("demo json overview shows prompt and pydantic model viewers", async ({
  page
}) => {
  await page.goto("/demo-json/overview");

  const overview = page.getByRole("region", { name: "Experiment overview" });
  await expect(overview.getByRole("heading", { name: "Demo JSON" })).toBeVisible();
  await expect(overview.getByRole("heading", { name: "Prompt" })).toBeVisible();
  await expect(overview.getByText("Create a concise launch-readiness report")).toBeVisible();
  await expect(overview.getByRole("heading", { name: "Model" })).toBeVisible();
  await expect(overview.getByText("model.py")).toBeVisible();
  await expect(overview.getByText("class DemoReport")).toBeVisible();
});

test("demo json proposal switches between new version and unified diff", async ({
  page
}) => {
  await page.goto("/demo-json/proposal");

  const proposal = page.getByRole("region", { name: "Proposal" });
  await expect(proposal.getByRole("heading", { name: "Rationale" })).toBeVisible();
  await expect(proposal.getByRole("heading", { name: "Proposed prompt" })).toBeVisible();
  await expect(proposal.getByRole("heading", { name: "Proposed model" })).toBeVisible();
  await expect(proposal.getByText("set launch_ready to false")).toBeVisible();
  await expect(proposal.getByText("max_length=3")).toBeVisible();

  await proposal.getByRole("tab", { name: "Diff" }).click();

  await expect(proposal.getByRole("heading", { name: "Prompt diff" })).toBeVisible();
  await expect(proposal.getByRole("heading", { name: "Model diff" })).toBeVisible();
  await expect(proposal.getByText("set launch_ready based on the risks")).toBeVisible();
  await expect(proposal.getByText("set launch_ready to false")).toBeVisible();
});
```

- [ ] **Step 2: Run e2e tests**

Run:

```bash
cd frontend && pnpm test:e2e
```

Expected: PASS. If shell networking or browser launch is blocked by the sandbox, rerun with escalated approval rather than treating it as an app failure.

- [ ] **Step 3: Commit e2e coverage**

```bash
git add frontend/e2e/demo-overview.spec.ts
git commit -m "Cover CodeMirror proposal views in e2e"
```

## Task 7: Full Validation And Browser QA

**Files:**
- No planned source edits unless validation reveals a defect.

- [ ] **Step 1: Run backend validation**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_chat.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_chat_get_structured_lite.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_structured_lite_units.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_format_validation_errors.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_api.py
.venv/bin/pyright --project pyrightconfig.json --pythonpath .venv/bin/python
```

Expected: PASS.

- [ ] **Step 2: Run frontend validation**

Run:

```bash
cd frontend && pnpm lint && pnpm test && pnpm build && pnpm test:e2e
```

Expected: PASS.

- [ ] **Step 3: Inspect the running app in the in-app browser**

Use the Browser plugin through `node_repl`, then inspect these routes:

```text
http://127.0.0.1:5173/demo-string/proposal
http://127.0.0.1:5173/demo-json/overview
http://127.0.0.1:5173/demo-json/proposal
```

Required checks:

- `demo-string/proposal` shows rationale and prompt, with no model panel.
- `demo-json/overview` shows prompt left and model right on desktop.
- `demo-json/proposal` shows rationale full width and prompt/model artifact panels.
- The `Diff` tab on `demo-json/proposal` changes headings to `Prompt diff` and `Model diff`.
- Browser console has no relevant app errors or warnings.
- A desktop screenshot and one mobile-width screenshot show no overlapping text or clipped controls.

- [ ] **Step 4: Confirm no uncommitted validation drift**

Run:

```bash
git status --short
```

Expected: no output. If validation required a fix, finish that fix in a separate targeted commit after rerunning the failed command.

## Self-Review Notes

- Spec coverage: backend model source, CodeMirror viewers, Markdown/Jinja highlighting, Python model display, overview model panel, proposal new/diff modes, text-output no-model behavior, and e2e coverage all map to tasks in this plan.
- Type consistency: `VersionOverview.model_py`, `VersionOverview.model_file`, `ProposalView.currentPrompt`, `ProposalView.currentModel`, and `ProposalView.currentModelFile` are introduced before use.
- Diff layout: Task 5 keeps two artifact panels only at the prompt/model level. Each artifact panel uses `DiffViewer`, which wraps CodeMirror `unifiedMergeView`.
