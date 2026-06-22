# Validator Editing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build comprehensive version-level validator editing in the `Validators` tab, including add, edit, duplicate, delete, overwrite current version, and save as next version.

**Architecture:** Validators are already version source files under `versions/<version>/validators/`. The backend will add a validator-source update endpoint that writes the submitted validator list and invalidates only the artifacts affected by validator changes. The frontend will replace the read-only `ValidatorsView` with a structured editor controlled by `App`, using the same dirty-navigation and version-switching patterns as Prompt and Settings.

**Tech Stack:** FastAPI, Pydantic v2, filesystem artifacts, React/Vite, TypeScript, node:test SSR tests, Playwright e2e.

---

## Current State

- Version-level validator storage is already in place.
- `PromptLabStore.load_validators(experiment_id, version)` reads `versions/<version>/validators/*.json`.
- `VersionOverview.validators` returns validators for the selected version.
- `ValidatorsView` is currently read-only and wraps `ValidatorsPreview`.
- `App` already has source-edit dirty navigation and source overwrite confirmation patterns to mirror.

## File Structure

- `backend/prompt_lab/api.py`
  - Add request model for validator source updates.
  - Add validation helpers for duplicate and unsafe validator IDs.
  - Add writer helper for `validators/*.json`.
  - Add `POST /api/experiments/{experiment_id}/versions/{version}/validators`.
- `backend/tests/test_validator_source.py`
  - New backend endpoint tests for create-next, overwrite, malformed payloads, and artifact invalidation.
- `frontend/src/types.ts`
  - Add validator-source request/response and draft types.
- `frontend/src/api.ts`
  - Add `updateVersionValidators`.
- `frontend/src/components/ValidatorEditor.tsx`
  - New focused editor for one selected validator and its checks.
- `frontend/src/components/ValidatorsView.tsx`
  - Replace read-only panel with editor shell: list, actions, JSON mode, save controls, validation errors.
- `frontend/src/App.tsx`
  - Own validator draft state, dirty state, save handlers, overwrite confirmation, and unsaved navigation.
- `frontend/tests/validatorEditor.test.ts`
  - SSR/unit coverage for validator editing helpers and UI states.
- `frontend/tests/promptView.test.ts`
  - Update production delegation assertions.
- `frontend/e2e/demo-prompt.spec.ts`
  - Add browser coverage for save-as-next and overwrite flows.
- `frontend/src/styles.css`
  - Add styles for validator editor layout using existing settings/source editor patterns.

---

### Task 1: Backend Validator Source Endpoint

**Files:**
- Create: `backend/tests/test_validator_source.py`
- Modify: `backend/prompt_lab/api.py`

- [ ] **Step 1: Write failing backend tests**

Create `backend/tests/test_validator_source.py` with this content:

```python
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from prompt_lab.api import create_app
from prompt_lab.config import PromptLabConfig


def write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validator_payload(
    validator_id: str = "quality",
    *,
    title: str = "Quality",
) -> dict[str, object]:
    return {
        "schema_version": "prompt_lab.validator/v1",
        "validator_id": validator_id,
        "type": "llm_questionnaire",
        "title": title,
        "description": "",
        "enabled": True,
        "input_scope": "output_only",
        "checks": [
            {
                "check_id": "complete",
                "title": "Complete",
                "question": "Is the output complete?",
                "description": "",
            }
        ],
    }


def automatic_validator_payload() -> dict[str, object]:
    return {
        "schema_version": "prompt_lab.validator/v1",
        "validator_id": "length",
        "type": "automatic",
        "title": "Length",
        "description": "",
        "enabled": True,
        "input_scope": "output_only",
        "checks": [
            {
                "check_id": "short",
                "title": "Short",
                "description": "",
                "rule": {
                    "kind": "word_count",
                    "source": "output_text",
                    "comparison": {"op": "gte", "value": 1},
                },
            }
        ],
    }


def write_experiment(root: Path) -> Path:
    experiment_dir = root / "experiments" / "demo"
    version_dir = experiment_dir / "versions" / "v001"
    version_dir.mkdir(parents=True)
    write_json(
        experiment_dir / "experiment.json",
        {
            "schema_version": "prompt_lab.experiment/v1",
            "id": "demo",
            "title": "Demo",
            "description": "",
            "active_version": "v001",
            "output": {"type": "text"},
            "template": {"engine": "jinja2", "path": "prompt.md"},
            "models": {
                "generator_model": "local/generator",
                "validator_model": "openai/validator",
                "judge_model": "openai/judge",
            },
            "run_defaults": {
                "repeat_count": 1,
                "llm_cache": "disabled",
                "case_order": "case-major",
            },
        },
    )
    (version_dir / "prompt.md").write_text("Say hello", encoding="utf-8")
    write_json(version_dir / "validators" / "quality.json", validator_payload())
    return version_dir


def test_api_validator_create_next_writes_clean_version() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        version_dir = write_experiment(root)
        (version_dir / "runs" / "run-001").mkdir(parents=True)
        (version_dir / "validations" / "validation-001").mkdir(parents=True)
        (version_dir / "reviews" / "review-001").mkdir(parents=True)
        (version_dir / "comparisons" / "comparison-001").mkdir(parents=True)
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app).post(
            "/api/experiments/demo/versions/v001/validators",
            json={
                "mode": "create_next",
                "validators": [
                    validator_payload(title="Updated quality"),
                    automatic_validator_payload(),
                ],
            },
        )

        assert response.status_code == 200
        assert response.json()["version"] == "v002"
        new_version_dir = root / "experiments" / "demo" / "versions" / "v002"
        assert (new_version_dir / "prompt.md").read_text(encoding="utf-8") == "Say hello"
        assert sorted(path.name for path in (new_version_dir / "validators").glob("*.json")) == [
            "length.json",
            "quality.json",
        ]
        updated = json.loads((new_version_dir / "validators" / "quality.json").read_text(encoding="utf-8"))
        assert updated["title"] == "Updated quality"
        assert not (new_version_dir / "runs").exists()
        assert not (new_version_dir / "validations").exists()
        assert not (new_version_dir / "reviews").exists()
        assert not (new_version_dir / "comparisons").exists()
        manifest = json.loads((root / "experiments" / "demo" / "experiment.json").read_text(encoding="utf-8"))
        assert manifest["active_version"] == "v001"


def test_api_validator_overwrite_keeps_runs_and_clears_downstream_artifacts() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        version_dir = write_experiment(root)
        (version_dir / "runs" / "run-001").mkdir(parents=True)
        (version_dir / "validations" / "validation-001").mkdir(parents=True)
        (version_dir / "reviews" / "review-001" / "proposal").mkdir(parents=True)
        (version_dir / "comparisons" / "comparison-001").mkdir(parents=True)
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app).post(
            "/api/experiments/demo/versions/v001/validators",
            json={
                "mode": "overwrite_current",
                "validators": [automatic_validator_payload()],
            },
        )

        assert response.status_code == 200
        assert response.json()["version"] == "v001"
        assert sorted(path.name for path in (version_dir / "validators").glob("*.json")) == ["length.json"]
        assert (version_dir / "runs").is_dir()
        assert not (version_dir / "validations").exists()
        assert not (version_dir / "reviews").exists()
        assert not (version_dir / "comparisons").exists()


def test_api_validator_update_rejects_duplicate_validator_ids() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_experiment(root)
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app).post(
            "/api/experiments/demo/versions/v001/validators",
            json={
                "mode": "overwrite_current",
                "validators": [validator_payload("quality"), validator_payload("quality")],
            },
        )

        assert response.status_code == 400
        assert "duplicate validator_id: quality" in response.json()["detail"]


def test_api_validator_update_rejects_unsafe_validator_id() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_experiment(root)
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app).post(
            "/api/experiments/demo/versions/v001/validators",
            json={"mode": "overwrite_current", "validators": [validator_payload("../bad")]},
        )

        assert response.status_code == 400
        assert "Unsafe validator id" in response.json()["detail"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_validator_source.py
```

Expected: fails with `404 Not Found` for `/validators` endpoint.

- [ ] **Step 3: Add backend request model and helpers**

In `backend/prompt_lab/api.py`, update imports from `prompt_lab.models.validators` to include `ValidatorDefinition` if it is not already imported, then add this request class near `VersionSourceUpdateRequest`:

```python
class VersionValidatorsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["create_next", "overwrite_current"]
    validators: list[ValidatorDefinition]
```

Add these helper functions near `_write_version_source_files`:

```python
def _validate_version_validators_update(
    request: VersionValidatorsUpdateRequest,
) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for validator in request.validators:
        if validator.validator_id in seen and validator.validator_id not in duplicates:
            duplicates.append(validator.validator_id)
        seen.add(validator.validator_id)
        _validate_validator_id_path_segment(validator.validator_id)
    if duplicates:
        raise HTTPException(
            status_code=400,
            detail=f"duplicate validator_id: {', '.join(sorted(duplicates))}",
        )


def _write_version_validator_files(
    *,
    version_dir: Path,
    validators: list[ValidatorDefinition],
) -> None:
    validators_dir = _resolve_version_local_write_path(version_dir, "validators")
    if validators_dir.exists():
        shutil.rmtree(validators_dir)
    validators_dir.mkdir(parents=True, exist_ok=True)
    for validator in validators:
        target = _resolve_version_local_write_path(
            version_dir,
            f"validators/{validator.validator_id}.json",
        )
        _write_json(target, validator.model_dump(mode="json"))
```

- [ ] **Step 4: Add endpoint implementation**

Add the endpoint immediately after `update_version_source`:

```python
    @app.post("/api/experiments/{experiment_id}/versions/{version}/validators")
    def update_version_validators(
        experiment_id: str,
        version: str,
        request: VersionValidatorsUpdateRequest,
    ) -> dict[str, object]:
        store.load_experiment(experiment_id)
        source_version_dir = store.version_dir(experiment_id, version)
        _validate_version_validators_update(request)

        if request.mode == "create_next":
            versions_root = source_version_dir.parent
            new_version, new_version_dir = _next_numeric_version_dir(versions_root)
            staging_dir = versions_root / f".{new_version}.tmp"
            if staging_dir.exists():
                shutil.rmtree(staging_dir)
            try:
                shutil.copytree(source_version_dir, staging_dir)
                _remove_generated_version_dirs(staging_dir)
                legacy_cases_dir = staging_dir / "cases"
                if legacy_cases_dir.exists():
                    shutil.rmtree(legacy_cases_dir)
                _write_version_validator_files(
                    version_dir=staging_dir,
                    validators=request.validators,
                )
                staging_dir.rename(new_version_dir)
            except Exception:
                if staging_dir.exists():
                    shutil.rmtree(staging_dir)
                if new_version_dir.exists():
                    shutil.rmtree(new_version_dir)
                raise
            return {
                "version": new_version,
                "source_version": version,
                "mode": request.mode,
                "version_dir": str(new_version_dir),
            }

        _write_version_validator_files(
            version_dir=source_version_dir,
            validators=request.validators,
        )
        _remove_runtime_children(
            source_version_dir,
            ["validations", "reviews", "comparisons"],
        )
        return {
            "version": version,
            "source_version": version,
            "mode": request.mode,
            "version_dir": str(source_version_dir),
        }
```

- [ ] **Step 5: Run backend endpoint tests**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_validator_source.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_api.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_storage.py
```

Expected: all tests print `OK:`.

- [ ] **Step 6: Commit backend endpoint**

```bash
git add backend/prompt_lab/api.py backend/tests/test_validator_source.py
git commit -m "Add validator source update endpoint"
```

---

### Task 2: Frontend API Types

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api.ts`
- Test: `frontend/tests/promptView.test.ts`

- [ ] **Step 1: Write failing production assertion**

In `frontend/tests/promptView.test.ts`, add these assertions inside `production workbench delegates prompt and validators tabs`:

```ts
  assert.match(
    source,
    /updateVersionValidators/
  );
  assert.match(
    source,
    /VersionValidatorsUpdateRequest/
  );
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd frontend
pnpm test -- tests/promptView.test.ts
```

Expected: fails because `updateVersionValidators` and `VersionValidatorsUpdateRequest` do not exist.

- [ ] **Step 3: Add frontend types**

In `frontend/src/types.ts`, after `VersionSourceUpdateResponse`, add:

```ts
export type VersionValidatorsSaveMode = "create_next" | "overwrite_current";

export interface VersionValidatorsDraft {
  validators: ValidatorDefinition[];
}

export interface VersionValidatorsUpdateRequest extends VersionValidatorsDraft {
  mode: VersionValidatorsSaveMode;
}

export interface VersionValidatorsUpdateResponse {
  version: string;
  source_version: string;
  mode: VersionValidatorsSaveMode;
  version_dir: string;
}
```

- [ ] **Step 4: Add API helper**

In `frontend/src/api.ts`, include the new request/response types in the import and add:

```ts
export function updateVersionValidators(
  experimentId: string,
  version: string,
  request: VersionValidatorsUpdateRequest
): Promise<VersionValidatorsUpdateResponse> {
  return apiPost<VersionValidatorsUpdateResponse>(
    `/api/experiments/${encodeURIComponent(experimentId)}/versions/${encodeURIComponent(
      version
    )}/validators`,
    request
  );
}
```

- [ ] **Step 5: Run frontend unit tests**

Run:

```bash
cd frontend
pnpm test -- tests/promptView.test.ts
pnpm lint
```

Expected: tests and TypeScript pass.

- [ ] **Step 6: Commit frontend API types**

```bash
git add frontend/src/types.ts frontend/src/api.ts frontend/tests/promptView.test.ts
git commit -m "Add validator source API types"
```

---

### Task 3: Validator Draft Utilities And Editor Component

**Files:**
- Create: `frontend/src/components/ValidatorEditor.tsx`
- Create: `frontend/tests/validatorEditor.test.ts`
- Modify: `frontend/src/components/ValidatorsView.tsx`

- [ ] **Step 1: Write failing editor tests**

Create `frontend/tests/validatorEditor.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import type { ValidatorDefinition } from "../src/types.ts";

const {
  createDefaultValidator,
  duplicateValidator,
  validateValidatorDraft,
  ValidatorEditor
} = await import("../src/components/ValidatorEditor.tsx");

test("createDefaultValidator creates editable llm validator", () => {
  const validator = createDefaultValidator("llm_questionnaire", ["quality"]);

  assert.equal(validator.validator_id, "validator-1");
  assert.equal(validator.type, "llm_questionnaire");
  assert.equal(validator.checks[0].check_id, "check-1");
});

test("duplicateValidator creates unique validator and check ids", () => {
  const original: ValidatorDefinition = {
    schema_version: "prompt_lab.validator/v1",
    validator_id: "quality",
    type: "automatic",
    title: "Quality",
    description: "",
    enabled: true,
    input_scope: "output_only",
    checks: [
      {
        check_id: "length",
        title: "Length",
        description: "",
        rule: {
          kind: "word_count",
          source: "output_text",
          comparison: { op: "gte", value: 1 }
        }
      }
    ]
  };

  const duplicate = duplicateValidator(original, ["quality"]);

  assert.equal(duplicate.validator_id, "quality-copy");
  assert.equal(duplicate.checks[0].check_id, "length-copy");
});

test("validateValidatorDraft rejects duplicate ids", () => {
  const validators = [
    createDefaultValidator("llm_questionnaire", []),
    createDefaultValidator("automatic", [])
  ];
  validators[1].validator_id = validators[0].validator_id;

  assert.deepEqual(validateValidatorDraft(validators), [
    "Validator id validator-1 is duplicated."
  ]);
});

test("ValidatorEditor renders llm and automatic controls", () => {
  const llm = createDefaultValidator("llm_questionnaire", []);
  const automatic = createDefaultValidator("automatic", []);

  const llmHtml = renderToStaticMarkup(
    React.createElement(ValidatorEditor, {
      existingValidatorIds: [llm.validator_id],
      onChange: () => undefined,
      validator: llm
    })
  );
  const automaticHtml = renderToStaticMarkup(
    React.createElement(ValidatorEditor, {
      existingValidatorIds: [automatic.validator_id],
      onChange: () => undefined,
      validator: automatic
    })
  );

  assert.match(llmHtml, /Question/);
  assert.match(llmHtml, /Input scope/);
  assert.match(automaticHtml, /Rule kind/);
  assert.match(automaticHtml, /Comparison/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd frontend
pnpm test -- tests/validatorEditor.test.ts
```

Expected: fails because `ValidatorEditor.tsx` does not exist.

- [ ] **Step 3: Create validator editor utilities and shell**

Create `frontend/src/components/ValidatorEditor.tsx` with:

```tsx
import type {
  AutomaticRule,
  AutomaticValidatorDefinition,
  CountComparison,
  InputScope,
  LlmQuestionnaireValidatorDefinition,
  ValidatorDefinition,
  ValidatorType
} from "../types";

const inputScopes: InputScope[] = [
  "output_only",
  "output_and_prompt",
  "output_and_case",
  "output_prompt_and_case"
];

const validatorTypes: ValidatorType[] = ["llm_questionnaire", "automatic"];
const ruleKinds: AutomaticRule["kind"][] = [
  "word_count",
  "sentence_count",
  "character_count",
  "json_path_count",
  "json_path_exists"
];
const comparisonOps: CountComparison["op"][] = ["lt", "lte", "gt", "gte", "eq", "between"];

function nextId(base: string, existingIds: string[]): string {
  if (!existingIds.includes(base)) return base;
  let index = 1;
  while (existingIds.includes(`${base}-${index}`)) index += 1;
  return `${base}-${index}`;
}

function defaultRule(kind: AutomaticRule["kind"] = "word_count"): AutomaticRule {
  if (kind === "json_path_exists") {
    return { kind, source: "output_json", path: "$.field" };
  }
  if (kind === "json_path_count") {
    return {
      kind,
      source: "output_json",
      path: "$.items",
      comparison: { op: "gte", value: 1 }
    };
  }
  return {
    kind,
    source: "output_text",
    comparison: { op: "gte", value: 1 }
  };
}

export function createDefaultValidator(
  type: ValidatorType,
  existingValidatorIds: string[]
): ValidatorDefinition {
  const validator_id = nextId("validator-1", existingValidatorIds);
  if (type === "automatic") {
    return {
      schema_version: "prompt_lab.validator/v1",
      validator_id,
      type,
      title: "New automatic validator",
      description: "",
      enabled: true,
      input_scope: "output_only",
      checks: [
        {
          check_id: "check-1",
          title: "New check",
          description: "",
          rule: defaultRule()
        }
      ]
    };
  }
  return {
    schema_version: "prompt_lab.validator/v1",
    validator_id,
    type,
    title: "New questionnaire validator",
    description: "",
    enabled: true,
    input_scope: "output_only",
    checks: [
      {
        check_id: "check-1",
        title: "New check",
        question: "Does the output satisfy this check?",
        description: ""
      }
    ]
  };
}

export function duplicateValidator(
  validator: ValidatorDefinition,
  existingValidatorIds: string[]
): ValidatorDefinition {
  const copy = JSON.parse(JSON.stringify(validator)) as ValidatorDefinition;
  copy.validator_id = nextId(`${validator.validator_id}-copy`, existingValidatorIds);
  copy.title = `${validator.title} copy`;
  copy.checks = copy.checks.map((check) => ({
    ...check,
    check_id: `${check.check_id}-copy`
  })) as ValidatorDefinition["checks"];
  return copy;
}

export function validateValidatorDraft(validators: ValidatorDefinition[]): string[] {
  const errors: string[] = [];
  const seen = new Set<string>();
  for (const validator of validators) {
    if (seen.has(validator.validator_id)) {
      errors.push(`Validator id ${validator.validator_id} is duplicated.`);
    }
    seen.add(validator.validator_id);
    if (validator.validator_id.trim().length === 0) {
      errors.push("Validator id is required.");
    }
    if (validator.title.trim().length === 0) {
      errors.push(`Validator ${validator.validator_id || "(new)"} title is required.`);
    }
    if (validator.checks.length === 0) {
      errors.push(`Validator ${validator.validator_id} needs at least one check.`);
    }
    const checkIds = new Set<string>();
    for (const check of validator.checks) {
      if (checkIds.has(check.check_id)) {
        errors.push(`Check id ${check.check_id} is duplicated in ${validator.validator_id}.`);
      }
      checkIds.add(check.check_id);
      if (check.check_id.trim().length === 0) {
        errors.push(`Validator ${validator.validator_id} has a check without an id.`);
      }
      if (check.title.trim().length === 0) {
        errors.push(`Check ${check.check_id || "(new)"} needs a title.`);
      }
      if (validator.type === "llm_questionnaire" && check.question.trim().length === 0) {
        errors.push(`Check ${check.check_id} needs a question.`);
      }
    }
  }
  return errors;
}

interface ValidatorEditorProps {
  existingValidatorIds: string[];
  onChange: (validator: ValidatorDefinition) => void;
  validator: ValidatorDefinition;
}

export function ValidatorEditor({
  existingValidatorIds,
  onChange,
  validator
}: ValidatorEditorProps) {
  function updateBase(update: Partial<ValidatorDefinition>) {
    onChange({ ...validator, ...update } as ValidatorDefinition);
  }

  function changeType(type: ValidatorType) {
    onChange(createDefaultValidator(type, existingValidatorIds.filter((id) => id !== validator.validator_id)));
  }

  return (
    <section className="validator-editor" aria-label="Validator editor">
      <div className="settings-section">
        <h3>Validator</h3>
        <label className="settings-field">
          <span>Validator ID</span>
          <input
            required
            value={validator.validator_id}
            onChange={(event) => updateBase({ validator_id: event.target.value })}
          />
        </label>
        <label className="settings-field">
          <span>Type</span>
          <select
            value={validator.type}
            onChange={(event) => changeType(event.target.value as ValidatorType)}
          >
            {validatorTypes.map((type) => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
        </label>
        <label className="settings-field">
          <span>Title</span>
          <input
            required
            value={validator.title}
            onChange={(event) => updateBase({ title: event.target.value })}
          />
        </label>
        <label className="settings-field">
          <span>Input scope</span>
          <select
            value={validator.input_scope}
            onChange={(event) => updateBase({ input_scope: event.target.value as InputScope })}
          >
            {inputScopes.map((scope) => (
              <option key={scope} value={scope}>{scope}</option>
            ))}
          </select>
        </label>
        <label className="settings-field settings-field-wide">
          <span>Description</span>
          <textarea
            rows={3}
            value={validator.description}
            onChange={(event) => updateBase({ description: event.target.value })}
          />
        </label>
        <label className="settings-checkbox">
          <input
            checked={validator.enabled}
            onChange={(event) => updateBase({ enabled: event.target.checked })}
            type="checkbox"
          />
          <span>Enabled</span>
        </label>
      </div>
      {validator.type === "llm_questionnaire" ? (
        <LlmChecksEditor validator={validator} onChange={onChange} />
      ) : (
        <AutomaticChecksEditor validator={validator} onChange={onChange} />
      )}
    </section>
  );
}
```

Add minimal nested editors in the same file:

```tsx
function LlmChecksEditor({
  onChange,
  validator
}: {
  onChange: (validator: ValidatorDefinition) => void;
  validator: LlmQuestionnaireValidatorDefinition;
}) {
  return (
    <section className="settings-section">
      <h3>Checks</h3>
      {validator.checks.map((check, index) => (
        <div className="validator-check-editor" key={`${check.check_id}-${index}`}>
          <label className="settings-field">
            <span>Check ID</span>
            <input
              value={check.check_id}
              onChange={(event) => {
                const checks = validator.checks.map((item, itemIndex) =>
                  itemIndex === index ? { ...item, check_id: event.target.value } : item
                );
                onChange({ ...validator, checks });
              }}
            />
          </label>
          <label className="settings-field">
            <span>Title</span>
            <input
              value={check.title}
              onChange={(event) => {
                const checks = validator.checks.map((item, itemIndex) =>
                  itemIndex === index ? { ...item, title: event.target.value } : item
                );
                onChange({ ...validator, checks });
              }}
            />
          </label>
          <label className="settings-field settings-field-wide">
            <span>Question</span>
            <textarea
              rows={3}
              value={check.question}
              onChange={(event) => {
                const checks = validator.checks.map((item, itemIndex) =>
                  itemIndex === index ? { ...item, question: event.target.value } : item
                );
                onChange({ ...validator, checks });
              }}
            />
          </label>
        </div>
      ))}
    </section>
  );
}

function AutomaticChecksEditor({
  onChange,
  validator
}: {
  onChange: (validator: ValidatorDefinition) => void;
  validator: AutomaticValidatorDefinition;
}) {
  return (
    <section className="settings-section">
      <h3>Checks</h3>
      {validator.checks.map((check, index) => (
        <div className="validator-check-editor" key={`${check.check_id}-${index}`}>
          <label className="settings-field">
            <span>Check ID</span>
            <input
              value={check.check_id}
              onChange={(event) => {
                const checks = validator.checks.map((item, itemIndex) =>
                  itemIndex === index ? { ...item, check_id: event.target.value } : item
                );
                onChange({ ...validator, checks });
              }}
            />
          </label>
          <label className="settings-field">
            <span>Rule kind</span>
            <select
              value={check.rule.kind}
              onChange={(event) => {
                const checks = validator.checks.map((item, itemIndex) =>
                  itemIndex === index
                    ? { ...item, rule: defaultRule(event.target.value as AutomaticRule["kind"]) }
                    : item
                );
                onChange({ ...validator, checks });
              }}
            >
              {ruleKinds.map((kind) => (
                <option key={kind} value={kind}>{kind}</option>
              ))}
            </select>
          </label>
          {check.rule.kind !== "json_path_exists" ? (
            <label className="settings-field">
              <span>Comparison</span>
              <select
                value={check.rule.comparison?.op ?? "gte"}
                onChange={(event) => {
                  const op = event.target.value as CountComparison["op"];
                  const comparison: CountComparison =
                    op === "between"
                      ? { op, min_value: 1, max_value: 3 }
                      : { op, value: 1 };
                  const checks = validator.checks.map((item, itemIndex) =>
                    itemIndex === index
                      ? { ...item, rule: { ...item.rule, comparison } }
                      : item
                  );
                  onChange({ ...validator, checks });
                }}
              >
                {comparisonOps.map((op) => (
                  <option key={op} value={op}>{op}</option>
                ))}
              </select>
            </label>
          ) : null}
        </div>
      ))}
    </section>
  );
}
```

- [ ] **Step 4: Run editor tests**

Run:

```bash
cd frontend
pnpm test -- tests/validatorEditor.test.ts
pnpm lint
```

Expected: tests pass and TypeScript reports no errors.

- [ ] **Step 5: Commit editor utilities**

```bash
git add frontend/src/components/ValidatorEditor.tsx frontend/tests/validatorEditor.test.ts
git commit -m "Add validator editor utilities"
```

---

### Task 4: Editable Validators View

**Files:**
- Modify: `frontend/src/components/ValidatorsView.tsx`
- Modify: `frontend/tests/validatorEditor.test.ts`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Add failing view tests**

Append to `frontend/tests/validatorEditor.test.ts`:

```ts
const { ValidatorsView } = await import("../src/components/ValidatorsView.tsx");

test("ValidatorsView renders add duplicate delete and save actions", () => {
  const validator = createDefaultValidator("llm_questionnaire", []);
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
  assert.match(html, /Duplicate/);
  assert.match(html, /Delete/);
  assert.match(html, /Overwrite current version/);
  assert.match(html, /Save as next version/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd frontend
pnpm test -- tests/validatorEditor.test.ts
```

Expected: fails because `ValidatorsView` props are still read-only.

- [ ] **Step 3: Replace ValidatorsView shell**

Change `frontend/src/components/ValidatorsView.tsx` to own a local draft and selection:

```tsx
import { useEffect, useMemo, useState } from "react";

import type { ValidatorDefinition, VersionValidatorsDraft } from "../types";
import {
  createDefaultValidator,
  duplicateValidator,
  validateValidatorDraft,
  ValidatorEditor
} from "./ValidatorEditor";
import { ValidatorsPreview } from "./ValidatorsPreview";

interface ValidatorsViewProps {
  isBusy: boolean;
  message: string | null;
  onDraftChange: (draft: VersionValidatorsDraft | null) => void;
  onOverwriteCurrent: () => void;
  onReset: () => void;
  onSaveAsNext: () => void;
  validators: ValidatorDefinition[];
}

function cloneValidators(validators: ValidatorDefinition[]): ValidatorDefinition[] {
  return JSON.parse(JSON.stringify(validators)) as ValidatorDefinition[];
}

export function ValidatorsView({
  isBusy,
  message,
  onDraftChange,
  onOverwriteCurrent,
  onReset,
  onSaveAsNext,
  validators
}: ValidatorsViewProps) {
  const [draft, setDraft] = useState<ValidatorDefinition[]>(() => cloneValidators(validators));
  const [selectedId, setSelectedId] = useState<string | null>(validators[0]?.validator_id ?? null);
  const [showJson, setShowJson] = useState(false);

  useEffect(() => {
    setDraft(cloneValidators(validators));
    setSelectedId(validators[0]?.validator_id ?? null);
    setShowJson(false);
  }, [validators]);

  const isDirty = useMemo(
    () => JSON.stringify(draft) !== JSON.stringify(validators),
    [draft, validators]
  );
  const errors = useMemo(() => validateValidatorDraft(draft), [draft]);
  const selected = draft.find((validator) => validator.validator_id === selectedId) ?? draft[0] ?? null;

  useEffect(() => {
    onDraftChange(isDirty ? { validators: draft } : null);
  }, [draft, isDirty, onDraftChange]);

  function setDraftAndSelect(nextDraft: ValidatorDefinition[], nextSelectedId: string | null) {
    setDraft(nextDraft);
    setSelectedId(nextSelectedId);
  }

  function addValidator(type: "llm_questionnaire" | "automatic") {
    const next = createDefaultValidator(type, draft.map((validator) => validator.validator_id));
    setDraftAndSelect([...draft, next], next.validator_id);
  }

  function updateSelected(next: ValidatorDefinition) {
    setDraft((current) =>
      current.map((validator) =>
        validator.validator_id === selected?.validator_id ? next : validator
      )
    );
    setSelectedId(next.validator_id);
  }

  function duplicateSelected() {
    if (selected === null) return;
    const copy = duplicateValidator(selected, draft.map((validator) => validator.validator_id));
    setDraftAndSelect([...draft, copy], copy.validator_id);
  }

  function deleteSelected() {
    if (selected === null) return;
    const nextDraft = draft.filter((validator) => validator.validator_id !== selected.validator_id);
    setDraftAndSelect(nextDraft, nextDraft[0]?.validator_id ?? null);
  }

  return (
    <section className="validators-editor-panel" aria-label="Validators">
      <div className="settings-header">
        <div>
          <h2>Validators</h2>
          <p>Edit validators stored with this version.</p>
        </div>
        <div className="settings-actions">
          <button
            className="secondary-action"
            disabled={isBusy || !isDirty}
            onClick={() => {
              setDraft(cloneValidators(validators));
              setSelectedId(validators[0]?.validator_id ?? null);
              onReset();
            }}
            type="button"
          >
            Reset
          </button>
          <button
            className="secondary-action danger-action"
            disabled={isBusy || !isDirty || errors.length > 0}
            onClick={onOverwriteCurrent}
            type="button"
          >
            Overwrite current version
          </button>
          <button
            className="primary-action"
            disabled={isBusy || !isDirty || errors.length > 0}
            onClick={onSaveAsNext}
            type="button"
          >
            {isBusy ? "Saving..." : "Save as next version"}
          </button>
        </div>
      </div>

      {message !== null ? <div className="settings-message">{message}</div> : null}
      {errors.length > 0 ? (
        <div className="settings-error">{errors.join(" ")}</div>
      ) : null}

      <div className="validators-editor-layout">
        <aside className="validators-editor-list" aria-label="Validator list">
          <div className="source-editor-actions">
            <button className="secondary-action" onClick={() => addValidator("llm_questionnaire")} type="button">
              Add questionnaire
            </button>
            <button className="secondary-action" onClick={() => addValidator("automatic")} type="button">
              Add automatic
            </button>
          </div>
          {draft.length === 0 ? (
            <div className="empty-state compact-empty-state">
              <h2>No validators configured</h2>
              <p>Add validator definitions before running validation.</p>
            </div>
          ) : (
            draft.map((validator) => (
              <button
                aria-pressed={selected?.validator_id === validator.validator_id}
                className={
                  selected?.validator_id === validator.validator_id
                    ? "validator-list-item is-active"
                    : "validator-list-item"
                }
                key={validator.validator_id}
                onClick={() => setSelectedId(validator.validator_id)}
                type="button"
              >
                <strong>{validator.title}</strong>
                <span>{validator.validator_id}</span>
                <span>{validator.type} · {validator.checks.length} checks</span>
              </button>
            ))
          )}
        </aside>

        <div className="validators-editor-detail">
          {selected === null ? (
            <ValidatorsPreview validators={[]} />
          ) : (
            <>
              <div className="source-editor-actions">
                <button className="secondary-action" onClick={duplicateSelected} type="button">
                  Duplicate
                </button>
                <button className="secondary-action danger-action" onClick={deleteSelected} type="button">
                  Delete
                </button>
                <button className="secondary-action" onClick={() => setShowJson((current) => !current)} type="button">
                  {showJson ? "Structured" : "JSON"}
                </button>
              </div>
              {showJson ? (
                <textarea
                  aria-label="Validator JSON"
                  className="validator-json-editor"
                  rows={18}
                  value={JSON.stringify(selected, null, 2)}
                  onChange={(event) => {
                    try {
                      updateSelected(JSON.parse(event.target.value) as ValidatorDefinition);
                    } catch {
                      return;
                    }
                  }}
                />
              ) : (
                <ValidatorEditor
                  existingValidatorIds={draft.map((validator) => validator.validator_id)}
                  onChange={updateSelected}
                  validator={selected}
                />
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Add minimal CSS**

Append to `frontend/src/styles.css`:

```css
.validators-editor-panel {
  display: grid;
  gap: 16px;
}

.validators-editor-layout {
  display: grid;
  grid-template-columns: minmax(220px, 300px) minmax(0, 1fr);
  gap: 16px;
}

.validators-editor-list,
.validators-editor-detail,
.validator-editor {
  display: grid;
  gap: 12px;
}

.validator-list-item {
  width: 100%;
  border: 1px solid #d7deea;
  background: #ffffff;
  border-radius: 8px;
  padding: 10px 12px;
  text-align: left;
  display: grid;
  gap: 4px;
}

.validator-list-item.is-active {
  border-color: #2563eb;
  box-shadow: inset 3px 0 0 #2563eb;
}

.validator-list-item span {
  color: #65728a;
  font-size: 0.85rem;
}

.validator-check-editor {
  border: 1px solid #d7deea;
  border-radius: 8px;
  display: grid;
  gap: 12px;
  padding: 12px;
}

.validator-json-editor {
  border: 1px solid #d7deea;
  border-radius: 8px;
  font-family: "SFMono-Regular", Consolas, monospace;
  min-height: 360px;
  padding: 12px;
  resize: vertical;
}

@media (max-width: 900px) {
  .validators-editor-layout {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 5: Run view tests**

Run:

```bash
cd frontend
pnpm test -- tests/validatorEditor.test.ts
pnpm lint
```

Expected: tests pass and TypeScript reports no errors.

- [ ] **Step 6: Commit editable view**

```bash
git add frontend/src/components/ValidatorsView.tsx frontend/src/components/ValidatorEditor.tsx frontend/src/styles.css frontend/tests/validatorEditor.test.ts
git commit -m "Build editable validators view"
```

---

### Task 5: App State, Save Flow, And Dirty Navigation

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/tests/promptView.test.ts`

- [ ] **Step 1: Add failing App integration assertions**

In `frontend/tests/promptView.test.ts`, add assertions to `production workbench delegates prompt and validators tabs`:

```ts
  assert.match(source, /validatorsDirty/);
  assert.match(source, /requestValidatorsOverwrite/);
  assert.match(source, /handleSaveVersionValidators/);
  assert.match(source, /activeTab === "validators"/);
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd frontend
pnpm test -- tests/promptView.test.ts
```

Expected: fails until `App.tsx` owns validator draft state.

- [ ] **Step 3: Add App imports and state**

In `frontend/src/App.tsx`, import `updateVersionValidators` and the new types:

```ts
  updateVersionSource,
  updateVersionValidators
```

```ts
  VersionValidatorsDraft,
  VersionValidatorsSaveMode,
```

Add pending overwrite type:

```ts
type PendingValidatorsOverwrite = {
  navigation: PendingNavigation | null;
};
```

Add state near source state:

```ts
  const [validatorsDraft, setValidatorsDraft] =
    useState<VersionValidatorsDraft | null>(null);
  const [pendingValidatorsOverwrite, setPendingValidatorsOverwrite] =
    useState<PendingValidatorsOverwrite | null>(null);
```

Add dirty memo:

```ts
  const validatorsDirty = useMemo(() => {
    if (detailState.status !== "loaded" || validatorsDraft === null) {
      return false;
    }
    return (
      JSON.stringify(validatorsDraft.validators) !==
      JSON.stringify(detailState.overview.validators ?? [])
    );
  }, [detailState, validatorsDraft]);
```

- [ ] **Step 4: Add clear/reset/overwrite helpers**

Add near source helper functions:

```ts
  function clearValidatorsEditor() {
    setValidatorsDraft(null);
    setPendingValidatorsOverwrite(null);
  }

  function handleValidatorsDraftChange(draft: VersionValidatorsDraft | null) {
    setValidatorsDraft(draft);
    setWorkflowMessage(null);
  }

  function handleValidatorsReset() {
    clearValidatorsEditor();
    setWorkflowMessage(null);
  }

  function requestValidatorsOverwrite(navigation: PendingNavigation | null = null) {
    if (validatorsDraft === null || !validatorsDirty || workflowBusy) {
      return;
    }
    setPendingValidatorsOverwrite({ navigation });
  }

  function handleCancelValidatorsOverwrite() {
    setPendingValidatorsOverwrite(null);
  }
```

- [ ] **Step 5: Add save handler**

Add near `handleSaveVersionSource`:

```ts
  async function handleSaveVersionValidators(
    mode: VersionValidatorsSaveMode,
    options?: { navigation?: PendingNavigation | null; rethrow?: boolean }
  ) {
    if (
      selectedExperiment === null ||
      detailState.status !== "loaded" ||
      validatorsDraft === null
    ) {
      return;
    }
    const experiment = selectedExperiment;
    const version = experiment.active_version;
    const navigation = options?.navigation ?? null;
    setWorkflowBusy(true);
    setWorkflowMessage(
      mode === "create_next"
        ? "Saving validators as next version..."
        : "Overwriting current validators..."
    );
    try {
      const response = await updateVersionValidators(experiment.id, version, {
        mode,
        validators: validatorsDraft.validators
      });
      setVersionSummaries((current) => {
        if (current.some((summary) => summary.version === response.version)) {
          return current;
        }
        return [...current, { version: response.version, is_active: false }].sort(
          (left, right) => left.version.localeCompare(right.version)
        );
      });

      if (mode === "create_next") {
        const savedExperiment = await updateExperiment(experiment.id, {
          ...experiment,
          active_version: response.version
        });
        setCommittedReviewState(null);
        setProposalResponse(null);
        setCreatedVersion(null);
        setComparison(null);
        setCompareValidationByVersion({});
        await refreshExperimentsAfterSettingsSave(savedExperiment);
        clearValidatorsEditor();
        setWorkflowMessage(`Created ${response.version} and switched to it.`);
        activateTab("validators");
      } else {
        await refreshCurrentVersionAfterSourceOverwrite(experiment, version);
        clearValidatorsEditor();
        setWorkflowMessage(`Overwrote ${version} validators and cleared generated validation artifacts.`);
        activateTab("validators");
      }

      if (navigation !== null) {
        performPendingNavigation(navigation);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setWorkflowMessage(message);
      if (options?.rethrow) {
        throw error;
      }
    } finally {
      setWorkflowBusy(false);
    }
  }

  async function handleConfirmValidatorsOverwrite() {
    if (pendingValidatorsOverwrite === null) {
      return;
    }
    const navigation = pendingValidatorsOverwrite.navigation;
    setPendingValidatorsOverwrite(null);
    await handleSaveVersionValidators("overwrite_current", { navigation });
  }
```

- [ ] **Step 6: Wire dirty navigation**

In `unsavedNavigationKind`, add before validation/review checks:

```ts
    if (
      appView === "experiment" &&
      activeTab === "validators" &&
      validatorsDirty &&
      !workflowBusy
    ) {
      return "validators";
    }
```

Update the return type union to include `"validators"`.

In the navigation save handler that branches on unsaved kind, add:

```ts
    if (kind === "validators") {
      await handleSaveVersionValidators("create_next", {
        navigation,
        rethrow: true
      });
      return;
    }
```

In the discard path, call `clearValidatorsEditor()` when discarding validator changes.

- [ ] **Step 7: Render ValidatorsView with new props**

Replace the existing `ValidatorsView` render with:

```tsx
                    {activeTab === "validators" ? (
                      <ValidatorsView
                        isBusy={workflowLocked}
                        message={workflowMessage}
                        onDraftChange={handleValidatorsDraftChange}
                        onOverwriteCurrent={() => requestValidatorsOverwrite()}
                        onReset={handleValidatorsReset}
                        onSaveAsNext={() =>
                          void handleSaveVersionValidators("create_next")
                        }
                        validators={detailState.overview.validators ?? []}
                      />
                    ) : null}
```

Add an overwrite confirmation modal matching the source overwrite modal, with text:

```tsx
      {pendingValidatorsOverwrite !== null ? (
        <div className="modal-backdrop" role="presentation">
          <section className="confirm-dialog" role="dialog" aria-modal="true" aria-label="Overwrite validators">
            <h2>Overwrite current validators?</h2>
            <p>
              This replaces validators for the current version and clears validation,
              review, proposal, and comparison artifacts. Existing runs are kept.
            </p>
            <div className="dialog-actions">
              <button className="secondary-action" onClick={handleCancelValidatorsOverwrite} type="button">
                Cancel
              </button>
              <button className="secondary-action danger-action" onClick={() => void handleConfirmValidatorsOverwrite()} type="button">
                Overwrite current version
              </button>
            </div>
          </section>
        </div>
      ) : null}
```

- [ ] **Step 8: Run App tests**

Run:

```bash
cd frontend
pnpm test -- tests/promptView.test.ts tests/validatorEditor.test.ts
pnpm lint
```

Expected: pass.

- [ ] **Step 9: Commit App integration**

```bash
git add frontend/src/App.tsx frontend/src/components/ValidatorsView.tsx frontend/tests/promptView.test.ts
git commit -m "Wire validator editing into workbench"
```

---

### Task 6: Browser Workflow E2E

**Files:**
- Modify: `frontend/e2e/demo-prompt.spec.ts`

- [ ] **Step 1: Add failing e2e coverage**

Append:

```ts
test("demo json validators can save as next version", async ({ page }) => {
  await page.goto("/demo-json/validators");
  await page.getByLabel("Version").selectOption("v001");

  const validators = page.getByRole("region", { name: "Validators" });
  await validators.getByRole("button", { name: /Report quality/ }).click();
  await validators.getByLabel("Title").fill("Report quality edited");
  await validators.getByRole("button", { name: "Save as next version" }).click();

  await expect(page.getByText(/Created v/)).toBeVisible();
  await expect(page.getByRole("tab", { name: "Validators" })).toHaveAttribute("aria-selected", "true");
  await expect(validators.getByDisplayValue("Report quality edited")).toBeVisible();
});

test("demo json validators overwrite keeps runs and clears validation state", async ({ page }) => {
  await page.goto("/demo-json/validators");
  await page.getByLabel("Version").selectOption("v002");

  const validators = page.getByRole("region", { name: "Validators" });
  await validators.getByRole("button", { name: /Report quality/ }).click();
  await validators.getByLabel("Description").fill("Edited validator description.");
  await validators.getByRole("button", { name: "Overwrite current version" }).click();
  await page.getByRole("dialog", { name: "Overwrite validators" })
    .getByRole("button", { name: "Overwrite current version" })
    .click();

  await expect(page.getByText(/Overwrote v002 validators/)).toBeVisible();
  await page.getByRole("tab", { name: "Runs" }).click();
  await expect(page.getByRole("region", { name: "Runs" })).toContainText("product-brief");
  await page.getByRole("tab", { name: "Validation" }).click();
  await expect(page.getByRole("region", { name: "Validation" })).toContainText("Run validation");
});
```

- [ ] **Step 2: Run e2e workflow tests**

Run:

```bash
cd frontend
pnpm test:e2e
```

Expected after previous tasks: all e2e tests pass. If sandbox blocks port binding, rerun outside sandbox with the same command.

- [ ] **Step 3: Commit e2e coverage**

```bash
git add frontend/e2e/demo-prompt.spec.ts
git commit -m "Cover validator editing workflows"
```

---

### Task 7: Full Verification

**Files:**
- No code changes expected.

- [ ] **Step 1: Run backend verification**

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_storage.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_api.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_validator_source.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_validators.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_compare.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_judge.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_proposal.py
.venv/bin/pyright --project pyrightconfig.json --pythonpath .venv/bin/python
```

Expected: all Python tests print `OK:` and pyright reports `0 errors`.

- [ ] **Step 2: Run frontend verification**

```bash
cd frontend
pnpm test
pnpm lint
pnpm build
pnpm test:e2e
```

Expected: unit tests pass, TypeScript passes, Vite builds, and Playwright passes.

- [ ] **Step 3: Manual in-app browser check**

Open the current in-app browser tab at:

```text
http://127.0.0.1:5173/demo-json/validators
```

Verify:

- `Prompt`, `Settings`, `Validators`, `Cases`, `Runs`, `Validation`, `Review`, `Proposal`, `Compare` tabs render in order.
- The `Validators` tab shows list, editor, `Reset`, `Overwrite current version`, and `Save as next version`.
- Editing a title enables save actions.
- Switching tabs while dirty opens the shared unsaved-change dialog.
- `Overwrite current version` opens the explicit destructive confirmation.

- [ ] **Step 4: Final status**

```bash
git status --short
```

Expected: clean worktree after all commits.
