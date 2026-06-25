# Experiment Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add UI and API support for creating, cloning, and deleting Prompt Lab experiments from the local-first workbench.

**Architecture:** Filesystem mutations stay in `PromptLabStore`, with FastAPI exposing small create, clone, and delete endpoints. React keeps the experiment management dialogs controlled by `App`, while `ExperimentsList` remains a presentational sidebar and Settings treats creation-time structural fields as read-only.

**Tech Stack:** FastAPI, Pydantic v2, filesystem artifacts, React/Vite, TypeScript, node:test SSR tests, Playwright e2e, Codex in-app Browser QA.

---

## Current State

- Runtime experiments live under `experiments/<id>/`.
- `PromptLabStore` already centralizes safe path resolution for experiment, version, case, validator, run, and validation artifacts.
- `GET /api/experiments` lists runtime experiments and `PUT /api/experiments/{id}` updates an existing manifest.
- `ExperimentsList` is currently a navigation-only sidebar.
- `App` already owns selection, routing, dirty navigation protection, modal overlays, and refresh-after-save behavior.
- `ExperimentSettings` currently renders some structural fields as editable; this plan makes output and source-file structure read-only after creation.

## File Structure

- `backend/prompt_lab/storage.py`
  - Add slug generation and experiment directory mutation methods.
  - Keep filesystem path validation in the store.
- `backend/prompt_lab/api.py`
  - Add request models and endpoints for create, clone, and delete.
  - Translate expected storage conflicts into clear HTTP responses.
- `backend/tests/test_storage.py`
  - Add storage-level tests for create, clone, delete, slug conflicts, and path safety.
  - Add new tests to the file's manual `main()` list.
- `backend/tests/test_api.py`
  - Add endpoint tests for create, clone, delete, and invalid input.
- `frontend/src/types.ts`
  - Add request and response types for experiment management.
- `frontend/src/api.ts`
  - Add API helper functions.
- `frontend/src/components/ExperimentManagementModals.tsx`
  - New focused dialog component file for create, clone, and delete.
- `frontend/src/components/ExperimentsList.tsx`
  - Add sidebar action controls while keeping selection behavior presentational.
- `frontend/src/components/ExperimentSettings.tsx`
  - Make creation-time structural fields read-only.
- `frontend/src/App.tsx`
  - Own modal state, API calls, refresh, selection, routing, and operation messages.
- `frontend/src/styles.css`
  - Add small sidebar action and modal form styles using existing colors, radii, and button classes.
- `frontend/tests/experimentManagementModals.test.ts`
  - SSR tests for modal fields and delete warning copy.
- `frontend/tests/experimentsList.test.ts`
  - SSR tests for sidebar controls and selected-item actions.
- `frontend/tests/experimentSettings.test.ts`
  - SSR tests proving structural fields are read-only.
- `frontend/e2e/demo-prompt.spec.ts`
  - Add a serial browser flow for create, clone, and delete.

---

### Task 1: Storage Create Experiment

**Files:**
- Modify: `backend/tests/test_storage.py`
- Modify: `backend/prompt_lab/storage.py`

- [ ] **Step 1: Write failing storage tests for creation**

Add this import to the import block in `backend/tests/test_storage.py`:

```python
from prompt_lab.settings import PromptLabSettings
```

Append these tests before `main()` in `backend/tests/test_storage.py`:

```python
def test_store_creates_text_experiment_with_unique_slug() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        existing = root / "experiments" / "demo-title"
        (existing / "versions" / "v001").mkdir(parents=True)
        write_experiment_manifest(
            existing / "experiment.json",
            experiment_id="demo-title",
        )
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )
        settings = PromptLabSettings(
            schema_version="prompt_lab.settings/v1",
            default_generator_model="openai/generator",
            default_validator_model="openai/validator",
            default_judge_model="openai/judge",
            default_repeat_count=4,
        )

        created = store.create_experiment(
            title="Demo Title",
            output_type="text",
            model_entrypoint=None,
            settings=settings,
        )

        created_dir = root / "experiments" / "demo-title-2"
        assert created.id == "demo-title-2"
        assert created.title == "Demo Title"
        assert created.active_version == "v001"
        assert created.output.type == "text"
        assert created.models.generator_model == "openai/generator"
        assert created.models.validator_model == "openai/validator"
        assert created.models.judge_model == "openai/judge"
        assert created.run_defaults.repeat_count == 4
        assert (created_dir / "experiment.json").is_file()
        assert (created_dir / "versions" / "v001" / "prompt.md").read_text(
            encoding="utf-8"
        ) == ""
        assert not (created_dir / "versions" / "v001" / "model.py").exists()


def test_store_creates_pydantic_experiment_with_empty_model_file() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )
        settings = PromptLabSettings(
            schema_version="prompt_lab.settings/v1",
            default_generator_model="local/generator",
            default_validator_model="local/validator",
            default_judge_model="local/judge",
            default_repeat_count=1,
        )

        created = store.create_experiment(
            title="Structured Output",
            output_type="pydantic",
            model_entrypoint="model.Output",
            settings=settings,
        )

        version_dir = root / "experiments" / "structured-output" / "versions" / "v001"
        assert created.id == "structured-output"
        assert created.output.type == "pydantic"
        assert created.output.model_file == "model.py"
        assert created.output.model_entrypoint == "model.Output"
        assert (version_dir / "prompt.md").read_text(encoding="utf-8") == ""
        assert (version_dir / "model.py").read_text(encoding="utf-8") == ""


def test_store_create_experiment_slug_falls_back_for_symbol_title() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )
        settings = PromptLabSettings(
            schema_version="prompt_lab.settings/v1",
            default_generator_model="local/generator",
            default_validator_model="local/validator",
            default_judge_model="local/judge",
            default_repeat_count=1,
        )

        created = store.create_experiment(
            title="!!!",
            output_type="text",
            model_entrypoint=None,
            settings=settings,
        )

        assert created.id == "experiment"
        assert (root / "experiments" / "experiment" / "experiment.json").is_file()
```

Add these functions to the `tests = [...]` list in `main()`:

```python
        test_store_creates_text_experiment_with_unique_slug,
        test_store_creates_pydantic_experiment_with_empty_model_file,
        test_store_create_experiment_slug_falls_back_for_symbol_title,
```

- [ ] **Step 2: Run storage tests and verify failure**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_storage.py
```

Expected: FAIL with `AttributeError: 'PromptLabStore' object has no attribute 'create_experiment'`.

- [ ] **Step 3: Implement slug generation and `create_experiment`**

Modify imports at the top of `backend/prompt_lab/storage.py`:

```python
import re
import shutil
from typing import Any, Literal

from prompt_lab.settings import PromptLabSettings
```

Add these helpers near `_validate_storage_id`:

```python
def _slugify_title(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "experiment"
```

Add these methods inside `PromptLabStore`, after `load_experiment`:

```python
    def _available_experiment_id(self, title: str) -> str:
        base = _slugify_title(title)
        resolved_root = self.experiments_root.resolve()
        self.experiments_root.mkdir(parents=True, exist_ok=True)
        candidate = base
        suffix = 2
        while True:
            _validate_storage_id(candidate, "Experiment")
            candidate_dir = (resolved_root / candidate).resolve()
            if candidate_dir != resolved_root and not candidate_dir.is_relative_to(
                resolved_root
            ):
                raise NotFoundError("Experiment not found")
            if not candidate_dir.exists():
                return candidate
            candidate = f"{base}-{suffix}"
            suffix += 1

    def create_experiment(
        self,
        *,
        title: str,
        output_type: Literal["text", "pydantic"],
        model_entrypoint: str | None,
        settings: PromptLabSettings,
    ) -> ExperimentArtifact:
        experiment_id = self._available_experiment_id(title)
        experiment_dir = self.experiments_root.resolve() / experiment_id
        version_dir = experiment_dir / "versions" / "v001"
        output: dict[str, Any]
        if output_type == "pydantic":
            if model_entrypoint is None or model_entrypoint.strip() == "":
                raise ValueError("pydantic output requires model_entrypoint")
            output = {
                "type": "pydantic",
                "model_file": "model.py",
                "model_entrypoint": model_entrypoint.strip(),
            }
        else:
            output = {"type": "text"}
        artifact = ExperimentArtifact.model_validate(
            {
                "schema_version": "prompt_lab.experiment/v1",
                "id": experiment_id,
                "title": title,
                "description": "",
                "active_version": "v001",
                "output": output,
                "template": {"engine": "jinjax", "path": "prompt.md"},
                "models": {
                    "generator_model": settings.default_generator_model,
                    "validator_model": settings.default_validator_model,
                    "judge_model": settings.default_judge_model,
                },
                "run_defaults": {
                    "repeat_count": settings.default_repeat_count,
                    "llm_cache": "disabled",
                    "case_order": "case-major",
                    "excluded_case_ids": [],
                },
            }
        )
        try:
            version_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            raise FileExistsError("Experiment already exists")
        _write_json(experiment_dir / "experiment.json", artifact.model_dump(mode="json"))
        (version_dir / "prompt.md").write_text("", encoding="utf-8")
        if output_type == "pydantic":
            (version_dir / "model.py").write_text("", encoding="utf-8")
        return artifact
```

- [ ] **Step 4: Run storage tests and verify pass**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_storage.py
```

Expected: all listed storage tests print `OK:` and exit 0.

- [ ] **Step 5: Commit storage create support**

Run:

```bash
git add backend/prompt_lab/storage.py backend/tests/test_storage.py
git commit -m "Add experiment creation storage"
```

---

### Task 2: Storage Clone And Delete

**Files:**
- Modify: `backend/tests/test_storage.py`
- Modify: `backend/prompt_lab/storage.py`

- [ ] **Step 1: Write failing storage tests for clone and delete**

Append these tests before `main()` in `backend/tests/test_storage.py`:

```python
def test_store_clones_experiment_directory_and_rewrites_manifest() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "experiments" / "demo"
        version_dir = source / "versions" / "v001"
        validators_dir = version_dir / "validators"
        cases_dir = source / "cases"
        validators_dir.mkdir(parents=True)
        cases_dir.mkdir(parents=True)
        write_experiment_manifest(source / "experiment.json")
        (version_dir / "prompt.md").write_text("Say {{ value }}", encoding="utf-8")
        (validators_dir / "quality.json").write_text(
            '{"schema_version":"prompt_lab.validator/v1","validator_id":"quality","type":"llm_questionnaire","title":"Quality","checks":[{"check_id":"ok","title":"OK","question":"OK?"}]}',
            encoding="utf-8",
        )
        (cases_dir / "case-a.json").write_text('{"value":"alpha"}', encoding="utf-8")
        (version_dir / "runs" / "run-001").mkdir(parents=True)
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        cloned = store.clone_experiment(
            source_experiment_id="demo",
            title="Demo Clone",
        )

        clone_dir = root / "experiments" / "demo-clone"
        assert cloned.id == "demo-clone"
        assert cloned.title == "Demo Clone"
        assert (clone_dir / "cases" / "case-a.json").is_file()
        assert (clone_dir / "versions" / "v001" / "prompt.md").read_text(
            encoding="utf-8"
        ) == "Say {{ value }}"
        assert (clone_dir / "versions" / "v001" / "validators" / "quality.json").is_file()
        assert (clone_dir / "versions" / "v001" / "runs" / "run-001").is_dir()
        saved = json.loads((clone_dir / "experiment.json").read_text(encoding="utf-8"))
        assert saved["id"] == "demo-clone"
        assert saved["title"] == "Demo Clone"


def test_store_delete_experiment_removes_directory() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        (experiment / "versions" / "v001").mkdir(parents=True)
        write_experiment_manifest(experiment / "experiment.json")
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        store.delete_experiment("demo")

        assert not experiment.exists()


def test_store_delete_experiment_rejects_path_escape() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        (experiment / "versions" / "v001").mkdir(parents=True)
        write_experiment_manifest(experiment / "experiment.json")
        outside = root / "secret"
        outside.mkdir()
        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        try:
            store.delete_experiment("../secret")
        except NotFoundError as exc:
            assert str(root) not in str(exc)
        else:
            raise AssertionError("Expected escaped delete to be rejected")
        assert outside.is_dir()
```

Add these functions to `main()`:

```python
        test_store_clones_experiment_directory_and_rewrites_manifest,
        test_store_delete_experiment_removes_directory,
        test_store_delete_experiment_rejects_path_escape,
```

- [ ] **Step 2: Run storage tests and verify failure**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_storage.py
```

Expected: FAIL with `AttributeError` for `clone_experiment` or `delete_experiment`.

- [ ] **Step 3: Implement clone and delete methods**

Add these methods inside `PromptLabStore`, after `create_experiment`:

```python
    def clone_experiment(
        self,
        *,
        source_experiment_id: str,
        title: str,
    ) -> ExperimentArtifact:
        source_dir = self.experiment_dir(source_experiment_id)
        experiment_id = self._available_experiment_id(title)
        destination = self.experiments_root.resolve() / experiment_id
        try:
            shutil.copytree(source_dir, destination)
        except FileExistsError:
            raise FileExistsError("Experiment already exists")
        source_artifact = ExperimentArtifact.model_validate(
            _read_json(destination / "experiment.json")
        )
        cloned = source_artifact.model_copy(
            update={
                "id": experiment_id,
                "title": title,
            }
        )
        _write_json(destination / "experiment.json", cloned.model_dump(mode="json"))
        return cloned

    def delete_experiment(self, experiment_id: str) -> None:
        experiment_dir = self.experiment_dir(experiment_id)
        shutil.rmtree(experiment_dir)
```

- [ ] **Step 4: Run storage tests and verify pass**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_storage.py
```

Expected: all storage tests print `OK:` and exit 0.

- [ ] **Step 5: Commit storage clone/delete support**

Run:

```bash
git add backend/prompt_lab/storage.py backend/tests/test_storage.py
git commit -m "Add experiment clone and delete storage"
```

---

### Task 3: Backend Experiment Management API

**Files:**
- Modify: `backend/tests/test_api.py`
- Modify: `backend/prompt_lab/api.py`

- [ ] **Step 1: Write failing API tests**

Append these tests near the existing experiment settings tests in `backend/tests/test_api.py`:

```python
def test_api_creates_text_experiment_from_title() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        save_settings(
            root / "config" / "settings.json",
            PromptLabSettings(
                schema_version="prompt_lab.settings/v1",
                default_generator_model="local/generator",
                default_validator_model="local/validator",
                default_judge_model="local/judge",
                default_repeat_count=2,
            ),
        )
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app).post(
            "/api/experiments",
            json={"title": "API Created", "output_type": "text"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == "api-created"
        assert payload["title"] == "API Created"
        assert payload["output"] == {"type": "text"}
        assert payload["models"]["generator_model"] == "local/generator"
        assert (root / "experiments" / "api-created" / "versions" / "v001" / "prompt.md").is_file()


def test_api_creates_pydantic_experiment() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        save_settings(root / "config" / "settings.json", PromptLabSettings())
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app).post(
            "/api/experiments",
            json={
                "title": "API Structured",
                "output_type": "pydantic",
                "model_entrypoint": "model.Output",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == "api-structured"
        assert payload["output"]["type"] == "pydantic"
        assert payload["output"]["model_file"] == "model.py"
        assert payload["output"]["model_entrypoint"] == "model.Output"
        assert (root / "experiments" / "api-structured" / "versions" / "v001" / "model.py").is_file()


def test_api_rejects_empty_experiment_title() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        save_settings(root / "config" / "settings.json", PromptLabSettings())
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app).post(
            "/api/experiments",
            json={"title": "   ", "output_type": "text"},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Experiment title is required"


def test_api_clones_experiment() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        version_dir = write_runtime_preview_experiment(root)
        (version_dir / "validators").mkdir()
        write_json(
            version_dir / "validators" / "quality.json",
            {
                "schema_version": "prompt_lab.validator/v1",
                "validator_id": "quality",
                "type": "llm_questionnaire",
                "title": "Quality",
                "checks": [
                    {
                        "check_id": "ok",
                        "title": "OK",
                        "question": "OK?",
                    }
                ],
            },
        )
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app).post(
            "/api/experiments/demo/clone",
            json={"title": "Demo Copy"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == "demo-copy"
        assert payload["title"] == "Demo Copy"
        assert (root / "experiments" / "demo-copy" / "cases" / "case-a.json").is_file()
        assert (root / "experiments" / "demo-copy" / "versions" / "v001" / "validators" / "quality.json").is_file()


def test_api_deletes_experiment() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_runtime_preview_experiment(root)
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app).delete("/api/experiments/demo")

        assert response.status_code == 200
        assert response.json() == {"experiment_id": "demo"}
        assert not (root / "experiments" / "demo").exists()
```

- [ ] **Step 2: Run API tests and verify failure**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_api.py
```

Expected: FAIL with 405 or 404 for the new endpoints.

- [ ] **Step 3: Add request models**

In `backend/prompt_lab/api.py`, add these classes after `RunVersionRequest`:

```python
class ExperimentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    output_type: Literal["text", "pydantic"]
    model_entrypoint: str | None = Field(default=None, min_length=1)


class ExperimentCloneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
```

- [ ] **Step 4: Add API routes**

In `backend/prompt_lab/api.py`, add these routes after `list_experiments()` and before `/api/settings`:

```python
    @app.post("/api/experiments")
    def create_experiment(request: ExperimentCreateRequest) -> dict[str, object]:
        title = request.title.strip()
        if title == "":
            raise HTTPException(status_code=400, detail="Experiment title is required")
        if request.output_type == "pydantic" and (
            request.model_entrypoint is None or request.model_entrypoint.strip() == ""
        ):
            raise HTTPException(
                status_code=400,
                detail="Model entrypoint is required for pydantic experiments",
            )
        settings = load_settings(resolved_config.settings_path)
        try:
            experiment = store.create_experiment(
                title=title,
                output_type=request.output_type,
                model_entrypoint=request.model_entrypoint,
                settings=settings,
            )
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return experiment.model_dump(mode="json")

    @app.post("/api/experiments/{experiment_id}/clone")
    def clone_experiment(
        experiment_id: str,
        request: ExperimentCloneRequest,
    ) -> dict[str, object]:
        title = request.title.strip()
        if title == "":
            raise HTTPException(status_code=400, detail="Experiment title is required")
        try:
            experiment = store.clone_experiment(
                source_experiment_id=experiment_id,
                title=title,
            )
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return experiment.model_dump(mode="json")

    @app.delete("/api/experiments/{experiment_id}")
    def delete_experiment(experiment_id: str) -> dict[str, object]:
        store.delete_experiment(experiment_id)
        return {"experiment_id": experiment_id}
```

- [ ] **Step 5: Run API tests and targeted storage tests**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_api.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_storage.py
```

Expected: both commands exit 0.

- [ ] **Step 6: Commit backend API support**

Run:

```bash
git add backend/prompt_lab/api.py backend/tests/test_api.py
git commit -m "Add experiment management API"
```

---

### Task 4: Frontend Types, API Helpers, And Dialogs

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api.ts`
- Create: `frontend/src/components/ExperimentManagementModals.tsx`
- Create: `frontend/tests/experimentManagementModals.test.ts`

- [ ] **Step 1: Write failing modal tests**

Create `frontend/tests/experimentManagementModals.test.ts`:

```typescript
import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import {
  CloneExperimentModal,
  DeleteExperimentModal,
  NewExperimentModal
} from "../src/components/ExperimentManagementModals.tsx";

const noop = () => undefined;
const noopAsync = async () => undefined;

test("new experiment modal renders title and output fields", () => {
  const html = renderToStaticMarkup(
    React.createElement(NewExperimentModal, {
      error: null,
      isBusy: false,
      onCancel: noop,
      onSubmit: noopAsync
    })
  );

  assert.match(html, /New experiment/);
  assert.match(html, /Title/);
  assert.match(html, /Output type/);
  assert.match(html, /text/);
  assert.match(html, /pydantic/);
  assert.doesNotMatch(html, /window.confirm/);
});

test("clone experiment modal explains full local copy", () => {
  const html = renderToStaticMarkup(
    React.createElement(CloneExperimentModal, {
      error: null,
      isBusy: false,
      onCancel: noop,
      onSubmit: noopAsync,
      sourceTitle: "Demo JSON"
    })
  );

  assert.match(html, /Clone experiment/);
  assert.match(html, /Copy of Demo JSON/);
  assert.match(html, /copies cases, versions, prompts, models, validators, and artifacts/);
});

test("delete experiment modal uses custom destructive copy", () => {
  const html = renderToStaticMarkup(
    React.createElement(DeleteExperimentModal, {
      error: null,
      experimentTitle: "Demo JSON",
      isBusy: false,
      onCancel: noop,
      onConfirm: noopAsync
    })
  );

  assert.match(html, /Delete experiment/);
  assert.match(html, /Demo JSON/);
  assert.match(html, /runs, validations, reviews, proposals, and comparisons/);
  assert.match(html, /Delete experiment/);
  assert.doesNotMatch(html, /window.confirm/);
});
```

- [ ] **Step 2: Run modal tests and verify failure**

Run:

```bash
cd frontend && pnpm test experimentManagementModals.test.ts
```

Expected: FAIL because `ExperimentManagementModals.tsx` does not exist.

- [ ] **Step 3: Add frontend types**

Append these interfaces near `Experiment` in `frontend/src/types.ts`:

```typescript
export interface ExperimentCreateRequest {
  title: string;
  output_type: OutputType;
  model_entrypoint?: string | null;
}

export interface ExperimentCloneRequest {
  title: string;
}

export interface ExperimentDeleteResponse {
  experiment_id: string;
}
```

- [ ] **Step 4: Add API helper functions**

Update imports in `frontend/src/api.ts` to include the new types:

```typescript
  ExperimentCreateRequest,
  ExperimentCloneRequest,
  ExperimentDeleteResponse,
```

Add these helpers after `updateExperiment`:

```typescript
export function createExperiment(
  request: ExperimentCreateRequest
): Promise<Experiment> {
  return apiPost<Experiment>("/api/experiments", request);
}

export function cloneExperiment(
  experimentId: string,
  request: ExperimentCloneRequest
): Promise<Experiment> {
  return apiPost<Experiment>(
    `/api/experiments/${encodeURIComponent(experimentId)}/clone`,
    request
  );
}

export function deleteExperiment(
  experimentId: string
): Promise<ExperimentDeleteResponse> {
  return apiDelete<ExperimentDeleteResponse>(
    `/api/experiments/${encodeURIComponent(experimentId)}`
  );
}
```

- [ ] **Step 5: Add modal components**

Create `frontend/src/components/ExperimentManagementModals.tsx`:

```tsx
import { useEffect, useState, type FormEvent } from "react";

import type { OutputType } from "../types";

interface NewExperimentModalProps {
  error: string | null;
  isBusy: boolean;
  onCancel: () => void;
  onSubmit: (request: {
    title: string;
    output_type: OutputType;
    model_entrypoint?: string | null;
  }) => Promise<void>;
}

interface CloneExperimentModalProps {
  error: string | null;
  isBusy: boolean;
  onCancel: () => void;
  onSubmit: (request: { title: string }) => Promise<void>;
  sourceTitle: string;
}

interface DeleteExperimentModalProps {
  error: string | null;
  experimentTitle: string;
  isBusy: boolean;
  onCancel: () => void;
  onConfirm: () => Promise<void>;
}

export function NewExperimentModal({
  error,
  isBusy,
  onCancel,
  onSubmit
}: NewExperimentModalProps) {
  const [title, setTitle] = useState("");
  const [outputType, setOutputType] = useState<OutputType>("text");
  const [modelEntrypoint, setModelEntrypoint] = useState("model.Output");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit({
      title,
      output_type: outputType,
      model_entrypoint: outputType === "pydantic" ? modelEntrypoint : null
    });
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section
        aria-labelledby="new-experiment-title"
        aria-modal="true"
        className="settings-navigation-modal experiment-management-modal"
        role="dialog"
      >
        <div>
          <h2 id="new-experiment-title">New experiment</h2>
          <p>Create a local experiment with an initial v001 source file.</p>
        </div>
        <form className="experiment-management-form" onSubmit={handleSubmit}>
          <label className="settings-field settings-field-wide">
            <span>Title</span>
            <input
              autoFocus
              required
              value={title}
              onChange={(event) => setTitle(event.currentTarget.value)}
            />
          </label>
          <label className="settings-field">
            <span>Output type</span>
            <select
              value={outputType}
              onChange={(event) => setOutputType(event.currentTarget.value as OutputType)}
            >
              <option value="text">text</option>
              <option value="pydantic">pydantic</option>
            </select>
          </label>
          {outputType === "pydantic" ? (
            <label className="settings-field">
              <span>Model entrypoint</span>
              <input
                required
                value={modelEntrypoint}
                onChange={(event) => setModelEntrypoint(event.currentTarget.value)}
              />
            </label>
          ) : null}
          {error === null ? null : <p className="settings-error">{error}</p>}
          <div className="modal-actions">
            <button
              className="secondary-action"
              disabled={isBusy}
              onClick={onCancel}
              type="button"
            >
              Cancel
            </button>
            <button className="primary-action" disabled={isBusy} type="submit">
              {isBusy ? "Creating..." : "Create experiment"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

export function CloneExperimentModal({
  error,
  isBusy,
  onCancel,
  onSubmit,
  sourceTitle
}: CloneExperimentModalProps) {
  const [title, setTitle] = useState(() => `Copy of ${sourceTitle}`);

  useEffect(() => {
    setTitle(`Copy of ${sourceTitle}`);
  }, [sourceTitle]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit({ title });
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section
        aria-labelledby="clone-experiment-title"
        aria-modal="true"
        className="settings-navigation-modal experiment-management-modal"
        role="dialog"
      >
        <div>
          <h2 id="clone-experiment-title">Clone experiment</h2>
          <p>
            This copies cases, versions, prompts, models, validators, and artifacts
            into an independent local experiment.
          </p>
        </div>
        <form className="experiment-management-form" onSubmit={handleSubmit}>
          <label className="settings-field settings-field-wide">
            <span>Title</span>
            <input
              autoFocus
              required
              value={title}
              onChange={(event) => setTitle(event.currentTarget.value)}
            />
          </label>
          {error === null ? null : <p className="settings-error">{error}</p>}
          <div className="modal-actions">
            <button
              className="secondary-action"
              disabled={isBusy}
              onClick={onCancel}
              type="button"
            >
              Cancel
            </button>
            <button className="primary-action" disabled={isBusy} type="submit">
              {isBusy ? "Cloning..." : "Clone experiment"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

export function DeleteExperimentModal({
  error,
  experimentTitle,
  isBusy,
  onCancel,
  onConfirm
}: DeleteExperimentModalProps) {
  return (
    <div className="modal-backdrop" role="presentation">
      <section
        aria-labelledby="delete-experiment-title"
        aria-modal="true"
        className="settings-navigation-modal experiment-management-modal"
        role="dialog"
      >
        <div>
          <h2 id="delete-experiment-title">Delete experiment</h2>
          <p>
            Delete {experimentTitle}? This removes the manifest, versions, prompts,
            models, cases, runs, validations, reviews, proposals, and comparisons
            from the local experiments workspace.
          </p>
        </div>
        {error === null ? null : <p className="settings-error">{error}</p>}
        <div className="modal-actions">
          <button
            className="secondary-action"
            disabled={isBusy}
            onClick={onCancel}
            type="button"
          >
            Cancel
          </button>
          <button
            className="secondary-action danger-action"
            disabled={isBusy}
            onClick={() => void onConfirm()}
            type="button"
          >
            {isBusy ? "Deleting..." : "Delete experiment"}
          </button>
        </div>
      </section>
    </div>
  );
}
```

- [ ] **Step 6: Run frontend modal tests**

Run:

```bash
cd frontend && pnpm test experimentManagementModals.test.ts
```

Expected: tests pass.

- [ ] **Step 7: Commit frontend contracts and modals**

Run:

```bash
git add frontend/src/types.ts frontend/src/api.ts frontend/src/components/ExperimentManagementModals.tsx frontend/tests/experimentManagementModals.test.ts
git commit -m "Add experiment management dialogs"
```

---

### Task 5: Sidebar Actions And Styles

**Files:**
- Modify: `frontend/src/components/ExperimentsList.tsx`
- Modify: `frontend/src/styles.css`
- Create: `frontend/tests/experimentsList.test.ts`

- [ ] **Step 1: Write failing sidebar tests**

Create `frontend/tests/experimentsList.test.ts`:

```typescript
import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { ExperimentsList } from "../src/components/ExperimentsList.tsx";
import type { Experiment } from "../src/types.ts";

const experiment: Experiment = {
  schema_version: "prompt_lab.experiment/v1",
  id: "demo-json",
  title: "Demo JSON",
  description: "",
  active_version: "v001",
  output: {
    type: "pydantic",
    model_file: "model.py",
    model_entrypoint: "model.Output"
  },
  template: {
    engine: "jinjax",
    path: "prompt.md"
  },
  models: {
    generator_model: "local/generator",
    validator_model: "local/validator",
    judge_model: "local/judge"
  },
  run_defaults: {
    repeat_count: 1,
    llm_cache: "disabled",
    case_order: "case-major",
    excluded_case_ids: []
  }
};

test("experiments list renders management actions", () => {
  const html = renderToStaticMarkup(
    React.createElement(ExperimentsList, {
      experiments: [experiment],
      onClone: () => undefined,
      onCreate: () => undefined,
      onDelete: () => undefined,
      onSelect: () => undefined,
      selectedExperimentId: "demo-json"
    })
  );

  assert.match(html, /New/);
  assert.match(html, /Clone/);
  assert.match(html, /Delete/);
  assert.match(html, /danger-action/);
});

test("experiments list only shows clone and delete for selected experiment", () => {
  const html = renderToStaticMarkup(
    React.createElement(ExperimentsList, {
      experiments: [experiment],
      onClone: () => undefined,
      onCreate: () => undefined,
      onDelete: () => undefined,
      onSelect: () => undefined,
      selectedExperimentId: null
    })
  );

  assert.match(html, /New/);
  assert.doesNotMatch(html, /Clone/);
  assert.doesNotMatch(html, /Delete/);
});
```

- [ ] **Step 2: Run sidebar tests and verify failure**

Run:

```bash
cd frontend && pnpm test experimentsList.test.ts
```

Expected: FAIL because `onCreate`, `onClone`, and `onDelete` props do not exist.

- [ ] **Step 3: Update `ExperimentsList` props and markup**

Replace `frontend/src/components/ExperimentsList.tsx` with:

```tsx
import type { Experiment } from "../types";

interface ExperimentsListProps {
  experiments: Experiment[];
  selectedExperimentId: string | null;
  onClone: (experiment: Experiment) => void;
  onCreate: () => void;
  onDelete: (experiment: Experiment) => void;
  onSelect: (experiment: Experiment) => void;
}

export function ExperimentsList({
  experiments,
  selectedExperimentId,
  onClone,
  onCreate,
  onDelete,
  onSelect
}: ExperimentsListProps) {
  return (
    <nav className="experiments-panel" aria-label="Experiments">
      <div className="panel-heading experiments-panel-heading">
        <h2>Experiments</h2>
        <button className="secondary-action experiment-panel-action" onClick={onCreate} type="button">
          New
        </button>
      </div>
      <div className="experiment-nav-list">
        {experiments.map((experiment) => {
          const isSelected = experiment.id === selectedExperimentId;
          return (
            <div
              className={isSelected ? "experiment-nav-row is-selected" : "experiment-nav-row"}
              key={experiment.id}
            >
              <button
                className={
                  isSelected
                    ? "experiment-nav-item is-selected"
                    : "experiment-nav-item"
                }
                onClick={() => onSelect(experiment)}
                type="button"
              >
                <span className="experiment-nav-title">{experiment.title}</span>
                <span className="experiment-nav-meta">
                  {experiment.output.type} · {experiment.active_version}
                </span>
                <span className="experiment-nav-model">
                  Generator: {experiment.models.generator_model}
                </span>
                <span className="experiment-nav-model">
                  Judge: {experiment.models.judge_model}
                </span>
                <span className="experiment-nav-model">
                  Validator: {experiment.models.validator_model}
                </span>
              </button>
              {isSelected ? (
                <div className="experiment-nav-actions">
                  <button
                    className="secondary-action"
                    onClick={() => onClone(experiment)}
                    type="button"
                  >
                    Clone
                  </button>
                  <button
                    className="secondary-action danger-action"
                    onClick={() => onDelete(experiment)}
                    type="button"
                  >
                    Delete
                  </button>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </nav>
  );
}
```

- [ ] **Step 4: Add sidebar styles**

In `frontend/src/styles.css`, update the focus selector by adding:

```css
.experiment-panel-action:focus-visible,
.experiment-nav-actions .secondary-action:focus-visible,
```

Add these styles after `.panel-heading`:

```css
.experiments-panel-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.experiment-panel-action {
  min-height: 30px;
  padding: 0 10px;
}

.experiment-nav-row {
  border-bottom: 1px solid #eef1f5;
}

.experiment-nav-row .experiment-nav-item {
  border-bottom: 0;
}

.experiment-nav-row.is-selected {
  background: #eaf2ff;
  box-shadow:
    inset 4px 0 0 #2563eb,
    inset 0 0 0 1px #bfdbfe;
}

.experiment-nav-row.is-selected .experiment-nav-item.is-selected {
  background: transparent;
  box-shadow: none;
}

.experiment-nav-actions {
  display: flex;
  gap: 8px;
  padding: 0 18px 14px 18px;
}

.experiment-nav-actions .secondary-action {
  min-height: 30px;
  padding: 0 10px;
  font-size: 12px;
}
```

- [ ] **Step 5: Run sidebar tests**

Run:

```bash
cd frontend && pnpm test experimentsList.test.ts
```

Expected: tests pass.

- [ ] **Step 6: Commit sidebar actions**

Run:

```bash
git add frontend/src/components/ExperimentsList.tsx frontend/src/styles.css frontend/tests/experimentsList.test.ts
git commit -m "Add experiment sidebar actions"
```

---

### Task 6: Settings Structural Fields Read-Only

**Files:**
- Modify: `frontend/src/components/ExperimentSettings.tsx`
- Create: `frontend/tests/experimentSettings.test.ts`

- [ ] **Step 1: Write failing settings tests**

Create `frontend/tests/experimentSettings.test.ts`:

```typescript
import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { ExperimentSettings } from "../src/components/ExperimentSettings.tsx";
import type { Experiment } from "../src/types.ts";

const experiment: Experiment = {
  schema_version: "prompt_lab.experiment/v1",
  id: "demo-json",
  title: "Demo JSON",
  description: "",
  active_version: "v001",
  output: {
    type: "pydantic",
    model_file: "model.py",
    model_entrypoint: "model.Output"
  },
  template: {
    engine: "jinjax",
    path: "prompt.md"
  },
  models: {
    generator_model: "local/generator",
    validator_model: "local/validator",
    judge_model: "local/judge"
  },
  run_defaults: {
    repeat_count: 1,
    llm_cache: "disabled",
    case_order: "case-major",
    excluded_case_ids: []
  }
};

test("experiment settings renders creation-time structural fields read-only", () => {
  const html = renderToStaticMarkup(
    React.createElement(ExperimentSettings, {
      experiment,
      isBusy: false,
      message: null,
      onDirtyChange: () => undefined,
      onDraftChange: () => undefined,
      onReset: () => undefined,
      onSave: async () => undefined
    })
  );

  assert.match(html, /value="pydantic" readOnly=""/);
  assert.match(html, /value="model.py" readOnly=""/);
  assert.match(html, /value="model.Output" readOnly=""/);
  assert.match(html, /value="prompt.md" readOnly=""/);
  assert.doesNotMatch(html, /<select[^>]*><option value="text"/);
});
```

- [ ] **Step 2: Run settings tests and verify failure**

Run:

```bash
cd frontend && pnpm test experimentSettings.test.ts
```

Expected: FAIL because output type and path fields are still editable controls.

- [ ] **Step 3: Make structural fields read-only**

In `frontend/src/components/ExperimentSettings.tsx`, remove `OutputType` from the import:

```tsx
import type { Experiment } from "../types";
```

Delete `handleOutputTypeChange`.

In the `Output` section, replace the `<select>` and editable pydantic inputs with:

```tsx
        <label className="settings-field">
          <span>Type</span>
          <input readOnly value={draft.output.type} />
        </label>
        {draft.output.type === "pydantic" ? (
          <>
            <label className="settings-field">
              <span>Model file</span>
              <input readOnly value={draft.output.model_file ?? ""} />
            </label>
            <label className="settings-field">
              <span>Model entrypoint</span>
              <input readOnly value={draft.output.model_entrypoint ?? ""} />
            </label>
          </>
        ) : null}
```

In the `Template` section, replace the editable path input with:

```tsx
        <label className="settings-field">
          <span>Path</span>
          <input readOnly value={draft.template.path} />
        </label>
```

- [ ] **Step 4: Run settings tests**

Run:

```bash
cd frontend && pnpm test experimentSettings.test.ts
```

Expected: tests pass.

- [ ] **Step 5: Commit read-only settings fields**

Run:

```bash
git add frontend/src/components/ExperimentSettings.tsx frontend/tests/experimentSettings.test.ts
git commit -m "Lock experiment structural settings"
```

---

### Task 7: App Integration For Create, Clone, Delete

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/experimentsList.test.ts`

- [ ] **Step 1: Write failing production integration test**

Append this test to `frontend/tests/experimentsList.test.ts`:

```typescript
import { readFileSync } from "node:fs";

test("app wires experiment management API calls and modals", () => {
  const source = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");

  assert.match(source, /createExperiment/);
  assert.match(source, /cloneExperiment/);
  assert.match(source, /deleteExperiment/);
  assert.match(source, /NewExperimentModal/);
  assert.match(source, /CloneExperimentModal/);
  assert.match(source, /DeleteExperimentModal/);
  assert.match(source, /routeAfterExperimentMutation/);
});
```

- [ ] **Step 2: Run integration test and verify failure**

Run:

```bash
cd frontend && pnpm test experimentsList.test.ts
```

Expected: FAIL because `App.tsx` does not import or wire these APIs and modals yet.

- [ ] **Step 3: Import APIs and modals in `App.tsx`**

Update the API import in `frontend/src/App.tsx`:

```tsx
  cloneExperiment,
  createExperiment,
  deleteExperiment,
```

Add modal imports:

```tsx
import {
  CloneExperimentModal,
  DeleteExperimentModal,
  NewExperimentModal
} from "./components/ExperimentManagementModals";
```

- [ ] **Step 4: Add modal state types and state**

Add before `PendingNavigationTarget`:

```tsx
type ExperimentManagementDialog =
  | { kind: "new" }
  | { kind: "clone"; experiment: Experiment }
  | { kind: "delete"; experiment: Experiment };
```

Extend `PendingNavigationTarget` with an experiment-management branch:

```tsx
  | { kind: "experimentDialog"; dialog: ExperimentManagementDialog }
```

Add near other `useState` calls:

```tsx
  const [experimentDialog, setExperimentDialog] =
    useState<ExperimentManagementDialog | null>(null);
  const [experimentActionBusy, setExperimentActionBusy] = useState(false);
  const [experimentActionError, setExperimentActionError] = useState<string | null>(
    null
  );
```

- [ ] **Step 5: Add pending-navigation, refresh, and route helpers**

Add this branch to `performPendingNavigation` before the version branch:

```tsx
    if (navigation.kind === "experimentDialog") {
      openExperimentDialog(navigation.dialog);
      return;
    }
```

Add after `requestTabChange`:

```tsx
  function openExperimentDialog(dialog: ExperimentManagementDialog) {
    setExperimentActionError(null);
    setExperimentDialog(dialog);
  }

  function requestExperimentDialog(dialog: ExperimentManagementDialog) {
    const navigation = buildPendingNavigation({
      kind: "experimentDialog",
      dialog
    });
    if (navigation !== null) {
      setNavigationError(null);
      setPendingNavigation(navigation);
      return;
    }
    openExperimentDialog(dialog);
  }
```

Add after `requestExperimentDialog`:

```tsx
  async function routeAfterExperimentMutation(
    experiment: Experiment,
    tab: WorkbenchTab
  ) {
    const experiments = await apiGet<Experiment[]>("/api/experiments");
    setState({ status: "loaded", experiments });
    selectExperiment(experiment, {
      historyMode: "replace",
      tab
    });
  }

  async function refreshAfterExperimentDelete(deletedExperimentId: string) {
    const experiments = await apiGet<Experiment[]>("/api/experiments");
    setState({ status: "loaded", experiments });
    const deletedIndex =
      state.status === "loaded"
        ? state.experiments.findIndex(
            (experiment) => experiment.id === deletedExperimentId
          )
        : -1;
    const nextExperiment =
      experiments[deletedIndex] ?? experiments[deletedIndex - 1] ?? experiments[0] ?? null;
    selectExperiment(nextExperiment, {
      historyMode: "replace",
      tab: "prompt"
    });
  }
```

- [ ] **Step 6: Add request handlers**

Add after `requestTabChange`:

```tsx
  function requestNewExperiment() {
    requestExperimentDialog({ kind: "new" });
  }

  function requestCloneExperiment(experiment: Experiment) {
    requestExperimentDialog({ kind: "clone", experiment });
  }

  function requestDeleteExperiment(experiment: Experiment) {
    requestExperimentDialog({ kind: "delete", experiment });
  }

  function closeExperimentDialog() {
    if (experimentActionBusy) return;
    setExperimentDialog(null);
    setExperimentActionError(null);
  }
```

- [ ] **Step 7: Add submit handlers**

Add near the settings save handlers:

```tsx
  async function handleCreateExperiment(request: {
    title: string;
    output_type: Experiment["output"]["type"];
    model_entrypoint?: string | null;
  }) {
    setExperimentActionBusy(true);
    setExperimentActionError(null);
    try {
      const created = await createExperiment(request);
      setExperimentDialog(null);
      await routeAfterExperimentMutation(created, "prompt");
      setWorkflowMessage(`Created ${created.title}.`);
    } catch (error) {
      setExperimentActionError(
        error instanceof Error ? error.message : "Unknown error"
      );
    } finally {
      setExperimentActionBusy(false);
    }
  }

  async function handleCloneExperiment(request: { title: string }) {
    if (experimentDialog?.kind !== "clone") return;
    setExperimentActionBusy(true);
    setExperimentActionError(null);
    try {
      const cloned = await cloneExperiment(experimentDialog.experiment.id, request);
      setExperimentDialog(null);
      await routeAfterExperimentMutation(cloned, "settings");
      setSettingsMessage(`Cloned ${experimentDialog.experiment.title}.`);
    } catch (error) {
      setExperimentActionError(
        error instanceof Error ? error.message : "Unknown error"
      );
    } finally {
      setExperimentActionBusy(false);
    }
  }

  async function handleDeleteExperiment() {
    if (experimentDialog?.kind !== "delete") return;
    const deletedExperiment = experimentDialog.experiment;
    setExperimentActionBusy(true);
    setExperimentActionError(null);
    try {
      await deleteExperiment(deletedExperiment.id);
      setExperimentDialog(null);
      await refreshAfterExperimentDelete(deletedExperiment.id);
      setWorkflowMessage(`Deleted ${deletedExperiment.title}.`);
    } catch (error) {
      setExperimentActionError(
        error instanceof Error ? error.message : "Unknown error"
      );
    } finally {
      setExperimentActionBusy(false);
    }
  }
```

- [ ] **Step 8: Pass action props to `ExperimentsList`**

Update the `ExperimentsList` JSX in `App.tsx`:

```tsx
            <ExperimentsList
              experiments={state.experiments}
              onClone={requestCloneExperiment}
              onCreate={requestNewExperiment}
              onDelete={requestDeleteExperiment}
              onSelect={requestExperimentSelection}
              selectedExperimentId={
                appView === "experiment" ? selectedExperiment?.id ?? null : null
              }
            />
```

- [ ] **Step 9: Render modal components**

Add before the existing pending-navigation modal render:

```tsx
      {experimentDialog?.kind === "new" ? (
        <NewExperimentModal
          error={experimentActionError}
          isBusy={experimentActionBusy}
          onCancel={closeExperimentDialog}
          onSubmit={handleCreateExperiment}
        />
      ) : null}

      {experimentDialog?.kind === "clone" ? (
        <CloneExperimentModal
          error={experimentActionError}
          isBusy={experimentActionBusy}
          onCancel={closeExperimentDialog}
          onSubmit={handleCloneExperiment}
          sourceTitle={experimentDialog.experiment.title}
        />
      ) : null}

      {experimentDialog?.kind === "delete" ? (
        <DeleteExperimentModal
          error={experimentActionError}
          experimentTitle={experimentDialog.experiment.title}
          isBusy={experimentActionBusy}
          onCancel={closeExperimentDialog}
          onConfirm={handleDeleteExperiment}
        />
      ) : null}
```

- [ ] **Step 10: Add modal form styles**

Add to `frontend/src/styles.css` near the existing modal styles:

```css
.experiment-management-modal {
  width: min(560px, 100%);
}

.experiment-management-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.experiment-management-form .settings-error,
.experiment-management-form .modal-actions {
  grid-column: 1 / -1;
}
```

Add inside the existing `@media (max-width: 760px)` block:

```css
  .experiment-management-form {
    grid-template-columns: 1fr;
  }
```

- [ ] **Step 11: Run frontend targeted tests**

Run:

```bash
cd frontend && pnpm test experimentsList.test.ts experimentManagementModals.test.ts experimentSettings.test.ts
```

Expected: tests pass.

- [ ] **Step 12: Commit App integration**

Run:

```bash
git add frontend/src/App.tsx frontend/src/styles.css frontend/tests/experimentsList.test.ts
git commit -m "Wire experiment management in app"
```

---

### Task 8: E2E And Full Verification

**Files:**
- Modify: `frontend/e2e/demo-prompt.spec.ts`

- [ ] **Step 1: Add Playwright e2e flow**

Append this test to `frontend/e2e/demo-prompt.spec.ts`:

```typescript
test("experiment management creates clones and deletes experiments", async ({
  page
}) => {
  await page.goto("/demo-json/settings");

  const unique = Date.now();
  await page.getByRole("button", { name: "New" }).click();
  const newDialog = page.getByRole("dialog", { name: "New experiment" });
  await expect(newDialog).toBeVisible();
  await newDialog.getByLabel("Title").fill(`Managed Text ${unique}`);
  await newDialog.getByRole("button", { name: "Create experiment" }).click();

  await expect(page).toHaveURL(new RegExp(`/managed-text-${unique}/prompt$`));
  await expect(page.getByRole("navigation", { name: "Experiments" })).toContainText(
    `Managed Text ${unique}`
  );

  await page.getByRole("button", { name: "New" }).click();
  const pydanticDialog = page.getByRole("dialog", { name: "New experiment" });
  await pydanticDialog.getByLabel("Title").fill(`Managed JSON ${unique}`);
  await pydanticDialog.getByLabel("Output type").selectOption("pydantic");
  await pydanticDialog.getByLabel("Model entrypoint").fill("model.Output");
  await pydanticDialog.getByRole("button", { name: "Create experiment" }).click();
  await expect(page).toHaveURL(new RegExp(`/managed-json-${unique}/prompt$`));
  await expect(page.getByRole("region", { name: "Prompt source" })).toContainText(
    "model.py"
  );

  await page.goto("/demo-json/settings");
  await page.getByRole("button", { name: "Clone" }).click();
  const cloneDialog = page.getByRole("dialog", { name: "Clone experiment" });
  await cloneDialog.getByLabel("Title").fill(`Managed Clone ${unique}`);
  await cloneDialog.getByRole("button", { name: "Clone experiment" }).click();

  await expect(page).toHaveURL(new RegExp(`/managed-clone-${unique}/settings$`));
  await page.getByRole("tab", { name: "Cases" }).click();
  await expect(page.getByRole("region", { name: "Cases" })).toContainText(
    "product-brief"
  );
  await page.getByRole("tab", { name: "Validators" }).click();
  await expect(page.getByRole("region", { name: "Validators" })).toContainText(
    "Report"
  );

  await page.getByRole("button", { name: "Delete" }).click();
  const deleteDialog = page.getByRole("dialog", { name: "Delete experiment" });
  await expect(deleteDialog).toContainText(
    "runs, validations, reviews, proposals, and comparisons"
  );
  await deleteDialog.getByRole("button", { name: "Delete experiment" }).click();

  await expect(page.getByRole("navigation", { name: "Experiments" })).not.toContainText(
    `Managed Clone ${unique}`
  );
});
```

- [ ] **Step 2: Run e2e and verify**

Run:

```bash
cd frontend && pnpm test:e2e
```

Expected: Playwright exits 0. If sandbox networking blocks browser startup, request escalation for the same command with the justification "Do you want to run the frontend Playwright e2e suite outside the sandbox so it can start/reuse local dev servers and browser processes?"

- [ ] **Step 3: Run backend validation**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_storage.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_api.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_config.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_settings.py
.venv/bin/pyright --project pyrightconfig.json --pythonpath .venv/bin/python
```

Expected: each command exits 0.

- [ ] **Step 4: Run frontend validation**

Run:

```bash
cd frontend && pnpm test && pnpm lint && pnpm build
```

Expected: each command exits 0.

- [ ] **Step 5: Run in-app Browser QA**

Use the Browser plugin on `http://127.0.0.1:5173/demo-json/settings` and verify:

```text
Flow under test: demo-json/settings -> New, Clone, Delete experiment actions -> sidebar, route, modal, and detail state update without console errors.
```

Collect:

- page URL and title,
- DOM snapshot showing `New`, `Clone`, `Delete`,
- console warnings/errors,
- screenshot of the sidebar with selected experiment actions,
- interaction proof for delete modal opening and closing.

- [ ] **Step 6: Commit e2e coverage**

Run:

```bash
git add frontend/e2e/demo-prompt.spec.ts
git commit -m "Add experiment management e2e coverage"
```

- [ ] **Step 7: Final status check**

Run:

```bash
git status --short
```

Expected: no uncommitted changes, except ignored Playwright reports or user-created local files that are outside this task.

---

## Self-Review Checklist

- Spec coverage:
  - Create: Tasks 1, 3, 4, 5, 7, 8.
  - Clone: Tasks 2, 3, 4, 5, 7, 8.
  - Delete: Tasks 2, 3, 4, 5, 7, 8.
  - Read-only structural Settings fields: Task 6.
  - Custom modal instead of JavaScript alert: Tasks 4 and 8.
  - Full validation and browser QA: Task 8.
- Type consistency:
  - Backend request fields use `title`, `output_type`, and `model_entrypoint`.
  - Frontend request types use the same snake_case fields because they are sent directly to FastAPI.
  - Delete response is consistently `{ experiment_id: string }`.
- Commit cadence:
  - Each task ends with a focused commit.
