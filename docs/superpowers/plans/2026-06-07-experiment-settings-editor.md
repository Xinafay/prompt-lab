# Experiment Settings Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Settings tab that edits and saves the selected experiment's `experiment.json` manifest from the GUI.

**Architecture:** Backend owns manifest persistence through `PromptLabStore.save_experiment()` and a single `PUT /api/experiments/{experiment_id}` route that validates the full `ExperimentArtifact`. Frontend adds a typed API helper and a focused `ExperimentSettings` form component; `App` coordinates save, refreshes experiment data, and keeps the user on Settings. Runtime writes stay under `experiments/`; `examples/` is never modified.

**Tech Stack:** Python 3.14, FastAPI, Pydantic, filesystem artifacts with `pathlib`, React/Vite/TypeScript, direct script-style backend tests, `pnpm` frontend validation.

---

## File Structure

Backend:

- Modify: `backend/prompt_lab/storage.py` - add `save_experiment()` and centralize manifest write validation.
- Modify: `backend/prompt_lab/api.py` - add `PUT /api/experiments/{experiment_id}`.
- Test: `backend/tests/test_storage.py` - add storage tests for manifest save, ID mismatch, missing active version, and examples isolation.
- Test: `backend/tests/test_api.py` - add route tests for save, ID mismatch, missing active version, and no examples write.

Frontend:

- Modify: `frontend/src/api.ts` - add `updateExperiment()`.
- Modify: `frontend/src/components/WorkbenchTabs.tsx` - add `settings` tab.
- Create: `frontend/src/components/ExperimentSettings.tsx` - form component for editable manifest fields.
- Modify: `frontend/src/App.tsx` - wire Settings tab, save/reset state, and refresh after save.
- Modify: `frontend/src/styles.css` - add compact form styles.

Validation:

- Run backend feature tests, pyright, frontend lint, and frontend build.
- Use the in-app browser for one manual smoke check if a dev server is available or started during implementation.

---

### Task 1: Add Storage Manifest Save

**Files:**
- Modify: `backend/prompt_lab/storage.py`
- Test: `backend/tests/test_storage.py`

- [ ] **Step 1: Add failing storage tests**

Add this import to `backend/tests/test_storage.py`:

```python
from prompt_lab.models.artifacts import ExperimentArtifact
```

Append these helpers and tests to `backend/tests/test_storage.py` before `main()`:

```python
def write_experiment_manifest(path: Path, *, experiment_id: str = "demo", active_version: str = "v001") -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "prompt_lab.experiment/v1",
                "id": experiment_id,
                "title": "Demo",
                "description": "",
                "active_version": active_version,
                "output": {"type": "text"},
                "template": {"engine": "jinja2", "path": "prompt.md"},
                "models": {
                    "generator_model": "local/a",
                    "judge_model": "openai/b",
                },
                "run_defaults": {
                    "repeat_count": 3,
                    "llm_cache": "disabled",
                    "case_order": "case-major",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_store_saves_experiment_manifest_under_experiments_root() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        (experiment / "versions" / "v001").mkdir(parents=True)
        write_experiment_manifest(experiment / "experiment.json")
        example = root / "examples" / "demo"
        (example / "versions" / "v001").mkdir(parents=True)
        write_experiment_manifest(example / "experiment.json")
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )
        payload = store.load_experiment("demo").model_dump(mode="json")
        payload["title"] = "Updated Demo"
        payload["description"] = "Edited from settings"
        payload["models"] = {
            "generator_model": "local/new",
            "judge_model": "openai/new",
        }
        payload["run_defaults"] = {
            "repeat_count": 5,
            "llm_cache": "disabled",
            "case_order": "case-major",
        }
        artifact = ExperimentArtifact.model_validate(payload)

        path = store.save_experiment("demo", artifact)

        assert path == (experiment / "experiment.json").resolve()
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["title"] == "Updated Demo"
        assert saved["description"] == "Edited from settings"
        assert saved["models"]["generator_model"] == "local/new"
        assert saved["run_defaults"]["repeat_count"] == 5
        example_saved = json.loads(
            (example / "experiment.json").read_text(encoding="utf-8")
        )
        assert example_saved["title"] == "Demo"


def test_store_rejects_save_experiment_id_mismatch() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        (experiment / "versions" / "v001").mkdir(parents=True)
        write_experiment_manifest(experiment / "experiment.json")
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )
        artifact = store.load_experiment("demo").model_copy(update={"id": "other"})

        try:
            store.save_experiment("demo", artifact)
        except NotFoundError as exc:
            assert str(root) not in str(exc)
        else:
            raise AssertionError("Expected id mismatch to be rejected")


def test_store_rejects_save_missing_active_version() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        (experiment / "versions" / "v001").mkdir(parents=True)
        write_experiment_manifest(experiment / "experiment.json")
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )
        artifact = store.load_experiment("demo").model_copy(
            update={"active_version": "v999"}
        )

        try:
            store.save_experiment("demo", artifact)
        except NotFoundError as exc:
            assert str(root) not in str(exc)
        else:
            raise AssertionError("Expected missing active version to be rejected")
```

Add these tests to the `tests = [...]` list in `main()`:

```python
        test_store_saves_experiment_manifest_under_experiments_root,
        test_store_rejects_save_experiment_id_mismatch,
        test_store_rejects_save_missing_active_version,
```

- [ ] **Step 2: Run storage tests and verify they fail**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_storage.py
```

Expected: fail with `AttributeError: 'PromptLabStore' object has no attribute 'save_experiment'`.

- [ ] **Step 3: Implement `save_experiment()`**

In `backend/prompt_lab/storage.py`, add this method inside `PromptLabStore` after `load_experiment()`:

```python
    def save_experiment(
        self, experiment_id: str, artifact: ExperimentArtifact
    ) -> Path:
        """Persist an experiment manifest under the runtime experiments root."""
        if artifact.id != experiment_id:
            raise NotFoundError("Experiment not found")
        experiment_dir = self.experiment_dir(experiment_id)
        active_version_dir = experiment_dir / "versions" / artifact.active_version
        if not active_version_dir.is_dir():
            raise NotFoundError("Version not found")
        path = experiment_dir / "experiment.json"
        _write_json(path, artifact.model_dump(mode="json"))
        return path.resolve()
```

- [ ] **Step 4: Run storage tests and verify they pass**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_storage.py
```

Expected: all storage tests print `OK`.

- [ ] **Step 5: Commit storage save**

Run:

```bash
git add backend/prompt_lab/storage.py backend/tests/test_storage.py
git commit -m "feat: save experiment manifests"
```

---

### Task 2: Add Experiment Update API

**Files:**
- Modify: `backend/prompt_lab/api.py`
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: Add failing API tests**

Add this helper near the top of `backend/tests/test_api.py`:

```python
def demo_experiment_payload(
    *, experiment_id: str = "demo", active_version: str = "v001"
) -> dict[str, object]:
    return {
        "schema_version": "prompt_lab.experiment/v1",
        "id": experiment_id,
        "title": "Demo",
        "description": "",
        "active_version": active_version,
        "output": {"type": "text"},
        "template": {"engine": "jinja2", "path": "prompt.md"},
        "models": {
            "generator_model": "local/a",
            "judge_model": "openai/b",
        },
        "run_defaults": {
            "repeat_count": 1,
            "llm_cache": "disabled",
            "case_order": "case-major",
        },
    }


def write_demo_experiment_manifest(root: Path) -> None:
    example = root / "examples" / "demo"
    (example / "versions" / "v001").mkdir(parents=True)
    (example / "experiment.json").write_text(
        json.dumps(demo_experiment_payload(), ensure_ascii=False),
        encoding="utf-8",
    )
```

Append these tests near the existing API experiment tests:

```python
def test_api_updates_experiment_manifest_under_experiments() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_demo_experiment_manifest(root)
        app = create_app(PromptLabConfig.from_env(project_root=root))
        payload = demo_experiment_payload()
        payload["title"] = "Updated"
        payload["description"] = "Saved from Settings"
        payload["models"] = {
            "generator_model": "local/updated",
            "judge_model": "openai/updated",
        }
        payload["run_defaults"] = {
            "repeat_count": 4,
            "llm_cache": "disabled",
            "case_order": "case-major",
        }

        response = TestClient(app).put("/api/experiments/demo", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body["title"] == "Updated"
        saved = json.loads(
            (root / "experiments" / "demo" / "experiment.json").read_text(
                encoding="utf-8"
            )
        )
        assert saved["description"] == "Saved from Settings"
        assert saved["models"]["generator_model"] == "local/updated"
        assert saved["run_defaults"]["repeat_count"] == 4
        example_saved = json.loads(
            (root / "examples" / "demo" / "experiment.json").read_text(
                encoding="utf-8"
            )
        )
        assert example_saved["title"] == "Demo"


def test_api_rejects_experiment_update_id_mismatch() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_demo_experiment_manifest(root)
        app = create_app(PromptLabConfig.from_env(project_root=root))
        payload = demo_experiment_payload(experiment_id="other")

        response = TestClient(app, raise_server_exceptions=False).put(
            "/api/experiments/demo",
            json=payload,
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Experiment id mismatch"


def test_api_rejects_experiment_update_missing_active_version() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_demo_experiment_manifest(root)
        app = create_app(PromptLabConfig.from_env(project_root=root))
        payload = demo_experiment_payload(active_version="v999")

        response = TestClient(app, raise_server_exceptions=False).put(
            "/api/experiments/demo",
            json=payload,
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Version not found"
```

Add the three tests to the `tests = [...]` list in `main()`.

- [ ] **Step 2: Run API tests and verify they fail**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_api.py
```

Expected: new tests fail with HTTP 405 or 404 because the `PUT` route does not exist.

- [ ] **Step 3: Add API route**

In `backend/prompt_lab/api.py`, add `ExperimentArtifact` to the artifacts import:

```python
from prompt_lab.models.artifacts import ExperimentArtifact, RunArtifact
```

Add this route after `list_experiments()`:

```python
    @app.put("/api/experiments/{experiment_id}")
    def update_experiment(
        experiment_id: str, experiment: ExperimentArtifact
    ) -> dict[str, object]:
        if experiment.id != experiment_id:
            raise HTTPException(status_code=400, detail="Experiment id mismatch")
        try:
            store.save_experiment(experiment_id, experiment)
        except NotFoundError as exc:
            if str(exc) == "Version not found":
                raise HTTPException(status_code=400, detail="Version not found") from exc
            raise
        return experiment.model_dump(mode="json")
```

- [ ] **Step 4: Run API tests and verify they pass**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_api.py
```

Expected: all API tests print `OK`.

- [ ] **Step 5: Commit API update route**

Run:

```bash
git add backend/prompt_lab/api.py backend/tests/test_api.py
git commit -m "feat: update experiment manifests through api"
```

---

### Task 3: Add Frontend API Helper And Settings Tab

**Files:**
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/components/WorkbenchTabs.tsx`

- [ ] **Step 1: Add `updateExperiment()` API helper**

In `frontend/src/api.ts`, add `Experiment` to the type import:

```ts
  Experiment,
```

Then add this helper after `getVersionOverview()`:

```ts
export function updateExperiment(
  experimentId: string,
  experiment: Experiment
): Promise<Experiment> {
  return apiPut<Experiment>(
    `/api/experiments/${encodeURIComponent(experimentId)}`,
    experiment
  );
}
```

- [ ] **Step 2: Add the Settings tab type and label**

In `frontend/src/components/WorkbenchTabs.tsx`, update the union:

```ts
export type WorkbenchTab =
  | "overview"
  | "settings"
  | "cases"
  | "runs"
  | "review"
  | "proposal"
  | "compare";
```

Update `tabs`:

```ts
const tabs: Array<{ id: WorkbenchTab; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "settings", label: "Settings" },
  { id: "cases", label: "Cases" },
  { id: "runs", label: "Runs" },
  { id: "review", label: "Review" },
  { id: "proposal", label: "Proposal" },
  { id: "compare", label: "Compare" }
];
```

- [ ] **Step 3: Run frontend typecheck and verify it passes**

Run:

```bash
cd frontend
pnpm lint
```

Expected: `tsc --noEmit` succeeds.

- [ ] **Step 4: Commit API helper and tab**

Run:

```bash
git add frontend/src/api.ts frontend/src/components/WorkbenchTabs.tsx
git commit -m "feat: add settings tab entrypoint"
```

---

### Task 4: Build Experiment Settings Form Component

**Files:**
- Create: `frontend/src/components/ExperimentSettings.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Create `ExperimentSettings` component**

Create `frontend/src/components/ExperimentSettings.tsx`:

```tsx
import { useEffect, useMemo, useState } from "react";

import type { Experiment, OutputType } from "../types";

interface ExperimentSettingsProps {
  experiment: Experiment;
  isBusy: boolean;
  message: string | null;
  onReset: () => void;
  onSave: (experiment: Experiment) => Promise<void>;
}

function cloneExperiment(experiment: Experiment): Experiment {
  return JSON.parse(JSON.stringify(experiment)) as Experiment;
}

function prepareForSave(draft: Experiment): Experiment {
  if (draft.output.type === "text") {
    return {
      ...draft,
      output: { type: "text" }
    };
  }
  return draft;
}

export function ExperimentSettings({
  experiment,
  isBusy,
  message,
  onReset,
  onSave
}: ExperimentSettingsProps) {
  const [draft, setDraft] = useState<Experiment>(() => cloneExperiment(experiment));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDraft(cloneExperiment(experiment));
    setError(null);
  }, [experiment]);

  const preparedDraft = useMemo(() => prepareForSave(draft), [draft]);
  const preparedExperiment = useMemo(
    () => prepareForSave(experiment),
    [experiment]
  );
  const isDirty = useMemo(
    () => JSON.stringify(preparedDraft) !== JSON.stringify(preparedExperiment),
    [preparedDraft, preparedExperiment]
  );

  function updateDraft(updater: (current: Experiment) => Experiment) {
    setDraft((current) => updater(current));
    setError(null);
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      await onSave(preparedDraft);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unknown error");
    }
  }

  function handleOutputTypeChange(type: OutputType) {
    updateDraft((current) => {
      if (type === "text") {
        return { ...current, output: { type: "text" } };
      }
      return {
        ...current,
        output: {
          type: "pydantic",
          model_file: current.output.model_file ?? "model.py",
          model_entrypoint: current.output.model_entrypoint ?? ""
        }
      };
    });
  }

  return (
    <form className="settings-form" onSubmit={handleSubmit}>
      <div className="settings-header">
        <div>
          <h2>Experiment settings</h2>
          <p>Edit the manifest stored in the runtime experiments workspace.</p>
        </div>
        <div className="settings-actions">
          <button
            className="secondary-action"
            disabled={isBusy || !isDirty}
            onClick={() => {
              setDraft(cloneExperiment(experiment));
              setError(null);
              onReset();
            }}
            type="button"
          >
            Reset
          </button>
          <button className="primary-action" disabled={isBusy || !isDirty} type="submit">
            {isBusy ? "Saving..." : "Save"}
          </button>
        </div>
      </div>

      {message !== null ? <div className="settings-message">{message}</div> : null}
      {error !== null ? <div className="settings-error">{error}</div> : null}

      <section className="settings-section">
        <h3>Identity</h3>
        <label className="settings-field">
          <span>ID</span>
          <input readOnly value={draft.id} />
        </label>
        <label className="settings-field">
          <span>Title</span>
          <input
            required
            value={draft.title}
            onChange={(event) =>
              updateDraft((current) => ({ ...current, title: event.target.value }))
            }
          />
        </label>
        <label className="settings-field settings-field-wide">
          <span>Description</span>
          <textarea
            rows={3}
            value={draft.description}
            onChange={(event) =>
              updateDraft((current) => ({
                ...current,
                description: event.target.value
              }))
            }
          />
        </label>
      </section>

      <section className="settings-section">
        <h3>Version</h3>
        <label className="settings-field">
          <span>Active version</span>
          <input
            required
            value={draft.active_version}
            onChange={(event) =>
              updateDraft((current) => ({
                ...current,
                active_version: event.target.value
              }))
            }
          />
        </label>
      </section>

      <section className="settings-section">
        <h3>Models</h3>
        <label className="settings-field">
          <span>Generator model</span>
          <input
            required
            value={draft.models.generator_model}
            onChange={(event) =>
              updateDraft((current) => ({
                ...current,
                models: {
                  ...current.models,
                  generator_model: event.target.value
                }
              }))
            }
          />
        </label>
        <label className="settings-field">
          <span>Judge model</span>
          <input
            required
            value={draft.models.judge_model}
            onChange={(event) =>
              updateDraft((current) => ({
                ...current,
                models: {
                  ...current.models,
                  judge_model: event.target.value
                }
              }))
            }
          />
        </label>
      </section>

      <section className="settings-section">
        <h3>Output</h3>
        <label className="settings-field">
          <span>Type</span>
          <select
            value={draft.output.type}
            onChange={(event) => handleOutputTypeChange(event.target.value as OutputType)}
          >
            <option value="text">text</option>
            <option value="pydantic">pydantic</option>
          </select>
        </label>
        {draft.output.type === "pydantic" ? (
          <>
            <label className="settings-field">
              <span>Model file</span>
              <input
                required
                value={draft.output.model_file ?? ""}
                onChange={(event) =>
                  updateDraft((current) => ({
                    ...current,
                    output: { ...current.output, model_file: event.target.value }
                  }))
                }
              />
            </label>
            <label className="settings-field">
              <span>Model entrypoint</span>
              <input
                required
                value={draft.output.model_entrypoint ?? ""}
                onChange={(event) =>
                  updateDraft((current) => ({
                    ...current,
                    output: {
                      ...current.output,
                      model_entrypoint: event.target.value
                    }
                  }))
                }
              />
            </label>
          </>
        ) : null}
      </section>

      <section className="settings-section">
        <h3>Template</h3>
        <label className="settings-field">
          <span>Engine</span>
          <input readOnly value={draft.template.engine} />
        </label>
        <label className="settings-field">
          <span>Path</span>
          <input
            required
            value={draft.template.path}
            onChange={(event) =>
              updateDraft((current) => ({
                ...current,
                template: { ...current.template, path: event.target.value }
              }))
            }
          />
        </label>
      </section>

      <section className="settings-section">
        <h3>Run defaults</h3>
        <label className="settings-field">
          <span>Repeat count</span>
          <input
            min={1}
            required
            type="number"
            value={draft.run_defaults.repeat_count}
            onChange={(event) =>
              updateDraft((current) => ({
                ...current,
                run_defaults: {
                  ...current.run_defaults,
                  repeat_count: Number(event.target.value)
                }
              }))
            }
          />
        </label>
        <label className="settings-field">
          <span>LLM cache</span>
          <input readOnly value={draft.run_defaults.llm_cache} />
        </label>
        <label className="settings-field">
          <span>Case order</span>
          <input readOnly value={draft.run_defaults.case_order} />
        </label>
      </section>
    </form>
  );
}
```

- [ ] **Step 2: Add Settings form styles**

Append this CSS to `frontend/src/styles.css` near other workbench component styles:

```css
.settings-form {
  display: grid;
  gap: 14px;
}

.settings-header,
.settings-actions {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.settings-header h2 {
  margin: 0;
  color: #111827;
  font-size: 18px;
  font-weight: 760;
  line-height: 1.25;
}

.settings-header p {
  margin: 4px 0 0;
  color: #667085;
  font-size: 13px;
  line-height: 1.4;
}

.settings-message,
.settings-error {
  padding: 10px 12px;
  border-radius: 6px;
  font-size: 13px;
  line-height: 1.4;
}

.settings-message {
  border: 1px solid #bbf7d0;
  background: #f0fdf4;
  color: #166534;
}

.settings-error {
  border: 1px solid #fecaca;
  background: #fef2f2;
  color: #991b1b;
}

.settings-section {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  padding: 14px;
  border: 1px solid #e4e7ec;
  border-radius: 8px;
  background: #ffffff;
}

.settings-section h3 {
  grid-column: 1 / -1;
  margin: 0;
  color: #111827;
  font-size: 14px;
  font-weight: 750;
  line-height: 1.3;
}

.settings-field {
  display: grid;
  gap: 5px;
  min-width: 0;
}

.settings-field-wide {
  grid-column: 1 / -1;
}

.settings-field span {
  color: #475467;
  font-size: 12px;
  font-weight: 750;
  line-height: 1.3;
}

.settings-field input,
.settings-field textarea,
.settings-field select {
  width: 100%;
  min-height: 36px;
  border: 1px solid #d0d5dd;
  border-radius: 6px;
  padding: 7px 9px;
  background: #ffffff;
  color: #111827;
  font-size: 13px;
  line-height: 1.35;
}

.settings-field textarea {
  resize: vertical;
}

.settings-field input[readonly] {
  background: #f8fafc;
  color: #667085;
}

.settings-field input:focus-visible,
.settings-field textarea:focus-visible,
.settings-field select:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: -1px;
}
```

- [ ] **Step 3: Run frontend typecheck and verify component compiles in isolation**

Run:

```bash
cd frontend
pnpm lint
```

Expected: `tsc --noEmit` succeeds.

- [ ] **Step 4: Commit form component**

Run:

```bash
git add frontend/src/components/ExperimentSettings.tsx frontend/src/styles.css
git commit -m "feat: add experiment settings form"
```

---

### Task 5: Wire Settings Save Flow In App

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/api.ts`

- [ ] **Step 1: Import Settings component and API helper**

In `frontend/src/App.tsx`, add `updateExperiment` to the API import:

```ts
  updateExperiment,
```

Add the component import:

```ts
import { ExperimentSettings } from "./components/ExperimentSettings";
```

- [ ] **Step 2: Add settings save state**

Inside `App()`, near other state declarations, add:

```ts
  const [settingsBusy, setSettingsBusy] = useState(false);
  const [settingsMessage, setSettingsMessage] = useState<string | null>(null);
```

In `selectExperiment()`, clear the message:

```ts
    setSettingsMessage(null);
    setSettingsBusy(false);
```

- [ ] **Step 3: Add `refreshExperimentsAfterSettingsSave()` and save handler**

Add these functions before `knownVersions`:

```ts
  async function refreshExperimentsAfterSettingsSave(savedExperiment: Experiment) {
    const [experiments, overview, runs] = await Promise.all([
      apiGet<Experiment[]>("/api/experiments"),
      getVersionOverview(savedExperiment.id, savedExperiment.active_version),
      getVersionRuns(savedExperiment.id, savedExperiment.active_version)
    ]);
    setState({ status: "loaded", experiments });
    setSelectedExperiment(savedExperiment);
    selectedKeyRef.current = `${savedExperiment.id}:${savedExperiment.active_version}`;
    setDetailState({ status: "loaded", overview, runs });
    setCandidateVersion(savedExperiment.active_version);
    candidateVersionRef.current = savedExperiment.active_version;
    if (!experiments.some((experiment) => experiment.id === savedExperiment.id)) {
      setWorkflowMessage("Saved experiment is no longer listed.");
    }
  }

  async function handleSaveExperimentSettings(experiment: Experiment) {
    if (selectedExperiment === null) return;
    setSettingsBusy(true);
    setSettingsMessage(null);
    try {
      const savedExperiment = await updateExperiment(selectedExperiment.id, experiment);
      await refreshExperimentsAfterSettingsSave(savedExperiment);
      setSettingsMessage("Settings saved.");
      setActiveTab("settings");
    } catch (error) {
      setSettingsMessage(error instanceof Error ? error.message : "Unknown error");
      throw error;
    } finally {
      setSettingsBusy(false);
    }
  }

  function handleResetExperimentSettings() {
    setSettingsMessage(null);
  }
```

- [ ] **Step 4: Render Settings tab**

Inside `.workbench-body`, after the overview block and before cases, add:

```tsx
                    {activeTab === "settings" ? (
                      <ExperimentSettings
                        experiment={detailState.overview.experiment}
                        isBusy={settingsBusy}
                        message={settingsMessage}
                        onReset={handleResetExperimentSettings}
                        onSave={handleSaveExperimentSettings}
                      />
                    ) : null}
```

- [ ] **Step 5: Run frontend lint**

Run:

```bash
cd frontend
pnpm lint
```

Expected: `tsc --noEmit` succeeds.

- [ ] **Step 6: Run frontend build**

Run:

```bash
cd frontend
pnpm build
```

Expected: Vite production build succeeds.

- [ ] **Step 7: Commit frontend Settings integration**

Run:

```bash
git add frontend/src/App.tsx frontend/src/api.ts frontend/src/components/WorkbenchTabs.tsx frontend/src/components/ExperimentSettings.tsx frontend/src/styles.css
git commit -m "feat: edit experiment settings in ui"
```

---

### Task 6: Final Validation And Browser Smoke

**Files:**
- No code edits expected.

- [ ] **Step 1: Run backend tests for changed API/storage behavior**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_storage.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_api.py
```

Expected: all tests print `OK`.

- [ ] **Step 2: Run broader backend checks**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_judge.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_proposal.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_compare.py
.venv/bin/pyright --project pyrightconfig.json --pythonpath .venv/bin/python
```

Expected: tests print `OK`; pyright reports `0 errors, 0 warnings, 0 informations`.

- [ ] **Step 3: Run frontend validation**

Run:

```bash
cd frontend
pnpm lint
pnpm build
```

Expected: TypeScript and production build succeed.

- [ ] **Step 4: Browser smoke**

If no frontend dev server is running, start one:

```bash
cd frontend
pnpm dev
```

Open the app in the in-app browser at the dev server URL, usually:

```text
http://127.0.0.1:5173/?experiment=split-scenes
```

Manual checks:

- Settings tab is visible.
- `id`, `template.engine`, `llm_cache`, and `case_order` are visible and read-only.
- Editing title, description, generator model, judge model, and repeat count enables Save.
- Save persists values.
- Browser refresh preserves saved values.
- Switching `output.type` between `text` and `pydantic` shows or hides pydantic fields.
- `examples/split-scenes/experiment.json` remains unchanged.

- [ ] **Step 5: Verify clean worktree**

Run:

```bash
git status --short
```

Expected: no uncommitted tracked changes. Any local `experiments/` runtime files should be ignored.

---

## Final Acceptance Checklist

- [ ] `PUT /api/experiments/{id}` validates and saves a full `ExperimentArtifact`.
- [ ] Backend rejects ID mismatches with HTTP 400.
- [ ] Backend rejects missing active versions with HTTP 400.
- [ ] Manifest writes go to `experiments/<id>/experiment.json`.
- [ ] `examples/` is not modified by Settings saves.
- [ ] Settings tab appears in the workbench.
- [ ] Settings form edits supported `experiment.json` fields.
- [ ] Read-only fields are visible but not editable.
- [ ] Save refreshes experiments list and active overview.
- [ ] Reset restores the last backend-loaded manifest.
- [ ] Backend tests, pyright, frontend lint, frontend build, and browser smoke pass.
