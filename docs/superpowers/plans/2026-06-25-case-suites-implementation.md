# Case Suites Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Prompt Lab case payloads into reusable Case Suites, keep experiment case tabs focused on preview and run inclusion, and add a separate UI for managing suites and suite cases.

**Architecture:** Add `case_suite_id` to experiment manifests and introduce `CaseSuiteArtifact` plus a gitignored runtime `case_suites/` root seeded from `examples/case_suites/`. Keep existing workflow call sites mostly stable by preserving `PromptLabStore.load_cases(experiment_id)` and changing it to resolve cases through the assigned suite. Frontend state gets a new Case Suites app view, while the experiment Cases tab becomes read-only for payloads and writable only for per-experiment inclusion.

**Tech Stack:** FastAPI, Pydantic v2, filesystem artifacts, React/Vite, TypeScript, node:test SSR tests, Playwright e2e, Prompt Lab demo fixtures.

---

## Current State

- Runtime experiments live under `experiments/<id>/` and committed templates live directly under `examples/<id>/`.
- Cases currently live under each experiment directory at `cases/*.json`.
- `ExperimentArtifact` has no `case_suite_id`.
- `PromptLabStore.load_cases(experiment_id)` reads `experiments/<id>/cases/*.json`.
- `CaseBrowser` currently combines payload preview, upload, delete, and run inclusion controls.
- `demo-string` and `demo-json` are stable demo fixtures used by frontend tests and e2e.

## File Structure

- `backend/prompt_lab/models/artifacts.py`
  - Add `CaseSuiteArtifact`.
  - Add optional `case_suite_id` to `ExperimentArtifact`.
- `backend/prompt_lab/config.py`
  - Add `case_suites_root` and `PROMPT_LAB_CASE_SUITES_ROOT`.
- `backend/prompt_lab/experiment_seed.py`
  - Seed `examples/experiments/` into `experiments/`.
  - Seed `examples/case_suites/` into `case_suites/`.
- `backend/prompt_lab/storage.py`
  - Add Case Suite path resolution, CRUD, case loading, inclusion save, and invalidation helpers.
  - Preserve `load_cases(experiment_id)` as the workflow-facing helper.
- `backend/prompt_lab/api.py`
  - Add Case Suite API endpoints.
  - Replace experiment case payload write endpoints with inclusion-only behavior.
  - Pass `case_suites_root` into seeding and storage.
- `examples/`
  - Move experiment templates under `examples/experiments/`.
  - Move committed case files under `examples/case_suites/`.
- `.gitignore`
  - Add runtime `case_suites/`.
- `README.md`, `FORMAT.md`, `backend/README.md`
  - Document Case Suite format, runtime roots, and reset instructions.
- `frontend/src/types.ts`
  - Add Case Suite and response types.
  - Add `case_suite_id` to `Experiment`.
  - Add optional `case_suite` metadata to `VersionOverview`.
- `frontend/src/api.ts`
  - Add Case Suite helpers and inclusion helper.
  - Remove frontend use of experiment payload mutation helpers.
- `frontend/src/components/CaseBrowser.tsx`
  - Convert to experiment case preview plus inclusion controls.
- `frontend/src/components/CaseSuiteManager.tsx`
  - New suite management UI for listing suites, editing metadata, and managing case payloads.
- `frontend/src/components/ExperimentSettings.tsx`
  - Add Case Suite selector.
- `frontend/src/App.tsx`
  - Load suites, route to the new Case Suites view, save inclusion, and refresh invalidated views.
- `frontend/src/styles.css`
  - Add restrained styles for suite management using existing forms, buttons, and light surfaces.
- Backend tests
  - `backend/tests/test_config.py`
  - `backend/tests/test_artifacts.py`
  - `backend/tests/test_experiment_seed.py`
  - `backend/tests/test_storage.py`
  - `backend/tests/test_api.py`
- Frontend tests
  - `frontend/tests/caseBrowser.test.ts`
  - `frontend/tests/experimentSettings.test.ts`
  - `frontend/tests/caseSuitesView.test.ts`
  - `frontend/tests/experimentManagementModals.test.ts`
  - `frontend/e2e/demo-prompt.spec.ts`

---

### Task 1: Backend Models And Runtime Roots

**Files:**
- Modify: `backend/prompt_lab/models/artifacts.py`
- Modify: `backend/prompt_lab/config.py`
- Modify: `backend/tests/test_artifacts.py`
- Modify: `backend/tests/test_config.py`
- Modify: `.gitignore`

- [ ] **Step 1: Write failing artifact tests**

Add these tests to `backend/tests/test_artifacts.py`:

```python
from prompt_lab.models.artifacts import CaseSuiteArtifact, ExperimentArtifact


def test_case_suite_artifact_accepts_minimal_manifest() -> None:
    artifact = CaseSuiteArtifact.model_validate(
        {
            "schema_version": "prompt_lab.case_suite/v1",
            "id": "story-chapters",
            "title": "Story chapters",
            "description": "Shared story input cases.",
        }
    )

    assert artifact.id == "story-chapters"
    assert artifact.title == "Story chapters"
    assert artifact.description == "Shared story input cases."


def test_experiment_artifact_accepts_case_suite_id() -> None:
    artifact = ExperimentArtifact.model_validate(
        {
            "schema_version": "prompt_lab.experiment/v1",
            "id": "demo",
            "title": "Demo",
            "description": "",
            "case_suite_id": "demo-suite",
            "active_version": "v001",
            "output": {"type": "text"},
            "template": {"engine": "jinjax", "path": "prompt.md"},
            "models": {
                "generator_model": "local/a",
                "validator_model": "openai/b",
                "judge_model": "openai/b",
            },
            "run_defaults": {
                "repeat_count": 1,
                "llm_cache": "disabled",
                "case_order": "case-major",
            },
        }
    )

    assert artifact.case_suite_id == "demo-suite"
```

- [ ] **Step 2: Run artifact tests and verify failure**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_artifacts.py
```

Expected: fail because `CaseSuiteArtifact` does not exist and `ExperimentArtifact` forbids `case_suite_id`.

- [ ] **Step 3: Add Pydantic fields**

In `backend/prompt_lab/models/artifacts.py`, add this model above `ExperimentArtifact`:

```python
class CaseSuiteArtifact(BaseModel):
    """Case Suite manifest stored as `suite.json`."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["prompt_lab.case_suite/v1"]
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = ""
```

Add this field to `ExperimentArtifact` after `description`:

```python
    case_suite_id: str | None = Field(default=None, min_length=1)
```

- [ ] **Step 4: Write failing config tests**

Add this test to `backend/tests/test_config.py`:

```python
def test_config_defaults_case_suites_root() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)

        config = PromptLabConfig.from_env(project_root=root)

        assert config.case_suites_root == root.resolve() / "case_suites"
```

Add this test near the existing override tests:

```python
def test_config_accepts_case_suites_root_override() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        case_suites = root / "custom-case-suites"
        previous = os.environ.get("PROMPT_LAB_CASE_SUITES_ROOT")
        os.environ["PROMPT_LAB_CASE_SUITES_ROOT"] = str(case_suites)
        try:
            config = PromptLabConfig.from_env(project_root=root)
        finally:
            if previous is None:
                os.environ.pop("PROMPT_LAB_CASE_SUITES_ROOT", None)
            else:
                os.environ["PROMPT_LAB_CASE_SUITES_ROOT"] = previous

        assert config.case_suites_root == case_suites.resolve()
```

- [ ] **Step 5: Run config tests and verify failure**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_config.py
```

Expected: fail because `PromptLabConfig` has no `case_suites_root`.

- [ ] **Step 6: Add `case_suites_root` to config**

In `backend/prompt_lab/config.py`, add a dataclass field:

```python
    case_suites_root: Path
```

In `from_env()`, read the override:

```python
        case_suites_override = os.getenv("PROMPT_LAB_CASE_SUITES_ROOT")
```

Return the new root between `experiments_root` and `examples_root`:

```python
            case_suites_root=Path(case_suites_override).resolve() if case_suites_override else root / "case_suites",
```

- [ ] **Step 7: Ignore runtime case suites**

Add this line to `.gitignore` below `experiments/`:

```gitignore
case_suites/
```

- [ ] **Step 8: Run focused checks**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_artifacts.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_config.py
```

Expected: both pass.

- [ ] **Step 9: Commit**

```bash
git add .gitignore backend/prompt_lab/models/artifacts.py backend/prompt_lab/config.py backend/tests/test_artifacts.py backend/tests/test_config.py
git commit -m "Add case suite artifact model"
```

---

### Task 2: Seed Experiments And Case Suites From Examples

**Files:**
- Modify: `backend/prompt_lab/experiment_seed.py`
- Modify: `backend/prompt_lab/api.py`
- Modify: `backend/tests/test_experiment_seed.py`
- Move: `examples/<experiment>/` to `examples/experiments/<experiment>/`
- Create: `examples/case_suites/story-chapters/suite.json`
- Create: `examples/case_suites/demo-string-replies/suite.json`
- Create: `examples/case_suites/demo-json-briefs/suite.json`
- Move: committed `cases/*.json` files into the matching suite case directories

- [ ] **Step 1: Write failing seed tests**

In `backend/tests/test_experiment_seed.py`, change `write_example()` so it writes to `root / "examples" / "experiments" / experiment_id` and includes `"case_suite_id": "demo-suite"` in the manifest.

Add this helper:

```python
def write_case_suite(root: Path, suite_id: str = "demo-suite") -> Path:
    suite_dir = root / "examples" / "case_suites" / suite_id
    cases_dir = suite_dir / "cases"
    cases_dir.mkdir(parents=True)
    (suite_dir / "suite.json").write_text(
        json.dumps(
            {
                "schema_version": "prompt_lab.case_suite/v1",
                "id": suite_id,
                "title": suite_id.replace("-", " ").title(),
                "description": "",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (cases_dir / "case-a.json").write_text(
        json.dumps({"value": "alpha"}, ensure_ascii=False),
        encoding="utf-8",
    )
    return suite_dir
```

Add this test:

```python
def test_seed_copies_case_suites_independently() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_case_suite(root)

        result = seed_experiments_from_examples(
            experiments_root=root / "experiments",
            case_suites_root=root / "case_suites",
            examples_root=root / "examples",
        )

        assert result.seeded_case_suites is True
        assert result.copied_case_suite_ids == ["demo-suite"]
        assert (root / "case_suites" / "demo-suite" / "suite.json").is_file()
        assert (
            root / "case_suites" / "demo-suite" / "cases" / "case-a.json"
        ).is_file()
```

Add this test:

```python
def test_seed_does_not_overwrite_existing_case_suites() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_case_suite(root, "template-suite")
        runtime_suite = root / "case_suites" / "local-suite"
        runtime_suite.mkdir(parents=True)
        (runtime_suite / "suite.json").write_text(
            json.dumps(
                {
                    "schema_version": "prompt_lab.case_suite/v1",
                    "id": "local-suite",
                    "title": "Local Suite",
                    "description": "",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = seed_experiments_from_examples(
            experiments_root=root / "experiments",
            case_suites_root=root / "case_suites",
            examples_root=root / "examples",
        )

        assert result.seeded_case_suites is False
        assert result.copied_case_suite_ids == []
        assert not (root / "case_suites" / "template-suite").exists()
```

- [ ] **Step 2: Run seed tests and verify failure**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_experiment_seed.py
```

Expected: fail because `seed_experiments_from_examples()` has no `case_suites_root` parameter and `SeedResult` has no suite fields.

- [ ] **Step 3: Update seed result and source paths**

In `backend/prompt_lab/experiment_seed.py`, change `SeedResult` to:

```python
@dataclass(frozen=True)
class SeedResult:
    seeded: bool
    copied_experiment_ids: list[str]
    seeded_case_suites: bool
    copied_case_suite_ids: list[str]
```

Add this helper:

```python
def _has_runtime_case_suite_manifests(case_suites_root: Path) -> bool:
    return case_suites_root.is_dir() and any(
        path.is_file() for path in case_suites_root.glob("*/suite.json")
    )
```

Change the function signature:

```python
def seed_experiments_from_examples(
    *,
    experiments_root: Path,
    case_suites_root: Path,
    examples_root: Path,
    settings: PromptLabSettings | None = None,
) -> SeedResult:
```

Inside the function, derive:

```python
    example_experiments_root = examples_root / "experiments"
    example_case_suites_root = examples_root / "case_suites"
```

Copy experiment templates from `example_experiments_root` and copy suites from `example_case_suites_root`. Return both copied id lists.

- [ ] **Step 4: Update app bootstrap**

In `backend/prompt_lab/api.py`, update startup seeding:

```python
    seed_experiments_from_examples(
        experiments_root=resolved_config.experiments_root,
        case_suites_root=resolved_config.case_suites_root,
        examples_root=resolved_config.examples_root,
        settings=settings,
    )
```

- [ ] **Step 5: Move committed examples**

Run these commands from repo root:

```bash
mkdir -p examples/experiments examples/case_suites/story-chapters/cases examples/case_suites/demo-string-replies/cases examples/case_suites/demo-json-briefs/cases
git mv examples/split-scenes examples/experiments/split-scenes
git mv examples/summarize-chapter examples/experiments/summarize-chapter
git mv examples/demo-string examples/experiments/demo-string
git mv examples/demo-json examples/experiments/demo-json
git mv examples/experiments/split-scenes/cases/*.json examples/case_suites/story-chapters/cases/
git rm -r examples/experiments/summarize-chapter/cases
git mv examples/experiments/demo-string/cases/*.json examples/case_suites/demo-string-replies/cases/
git mv examples/experiments/demo-json/cases/*.json examples/case_suites/demo-json-briefs/cases/
```

The `git rm -r examples/experiments/summarize-chapter/cases` command removes duplicated story chapter case files because `split-scenes` already moved the shared copies into `story-chapters`.

- [ ] **Step 6: Add suite manifests**

Create `examples/case_suites/story-chapters/suite.json`:

```json
{
  "schema_version": "prompt_lab.case_suite/v1",
  "id": "story-chapters",
  "title": "Story chapters",
  "description": "Shared chapter inputs for story prompt experiments."
}
```

Create `examples/case_suites/demo-string-replies/suite.json`:

```json
{
  "schema_version": "prompt_lab.case_suite/v1",
  "id": "demo-string-replies",
  "title": "Demo string replies",
  "description": "Stable reply-writing inputs for Prompt Lab UI tests."
}
```

Create `examples/case_suites/demo-json-briefs/suite.json`:

```json
{
  "schema_version": "prompt_lab.case_suite/v1",
  "id": "demo-json-briefs",
  "title": "Demo JSON briefs",
  "description": "Stable structured-output brief inputs for Prompt Lab UI tests."
}
```

- [ ] **Step 7: Add `case_suite_id` to example experiments**

In `examples/experiments/split-scenes/experiment.json` and `examples/experiments/summarize-chapter/experiment.json`, add:

```json
"case_suite_id": "story-chapters"
```

In `examples/experiments/demo-string/experiment.json`, add:

```json
"case_suite_id": "demo-string-replies"
```

In `examples/experiments/demo-json/experiment.json`, add:

```json
"case_suite_id": "demo-json-briefs"
```

- [ ] **Step 8: Run focused checks**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_experiment_seed.py
```

Expected: pass.

- [ ] **Step 9: Commit**

```bash
git add backend/prompt_lab/experiment_seed.py backend/prompt_lab/api.py backend/tests/test_experiment_seed.py examples
git commit -m "Seed case suites from examples"
```

---

### Task 3: Storage Case Suite Operations

**Files:**
- Modify: `backend/prompt_lab/storage.py`
- Modify: `backend/tests/test_storage.py`

- [ ] **Step 1: Write storage helper tests**

Add helper functions to `backend/tests/test_storage.py`:

```python
def write_case_suite_manifest(path: Path, *, suite_id: str = "demo-suite") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "prompt_lab.case_suite/v1",
                "id": suite_id,
                "title": suite_id.replace("-", " ").title(),
                "description": "",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def write_case_suite_case(
    root: Path,
    *,
    suite_id: str = "demo-suite",
    case_id: str = "case-a",
    payload: dict[str, object] | None = None,
) -> None:
    cases_dir = root / "case_suites" / suite_id / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    write_json(cases_dir / f"{case_id}.json", payload or {"value": "alpha"})
```

Add tests:

```python
def test_store_lists_case_suites() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_case_suite_manifest(root / "case_suites" / "beta" / "suite.json", suite_id="beta")
        write_case_suite_manifest(root / "case_suites" / "alpha" / "suite.json", suite_id="alpha")
        store = PromptLabStore(
            experiments_root=root / "experiments",
            case_suites_root=root / "case_suites",
            examples_root=root / "examples",
        )

        suites = store.list_case_suites()

        assert [suite.id for suite in suites] == ["alpha", "beta"]


def test_store_loads_cases_through_experiment_case_suite() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        (experiment / "versions" / "v001").mkdir(parents=True)
        write_experiment_manifest(experiment / "experiment.json")
        payload = json.loads((experiment / "experiment.json").read_text(encoding="utf-8"))
        payload["case_suite_id"] = "demo-suite"
        write_json(experiment / "experiment.json", payload)
        write_case_suite_manifest(root / "case_suites" / "demo-suite" / "suite.json")
        write_case_suite_case(root)
        store = PromptLabStore(
            experiments_root=root / "experiments",
            case_suites_root=root / "case_suites",
            examples_root=root / "examples",
        )

        cases = store.load_cases("demo")

        assert [case.id for case in cases] == ["case-a"]
        assert cases[0].payload == {"value": "alpha"}


def test_store_load_cases_rejects_missing_case_suite_assignment() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        (experiment / "versions" / "v001").mkdir(parents=True)
        write_experiment_manifest(experiment / "experiment.json")
        store = PromptLabStore(
            experiments_root=root / "experiments",
            case_suites_root=root / "case_suites",
            examples_root=root / "examples",
        )

        try:
            store.load_cases("demo")
        except NotFoundError as exc:
            assert str(exc) == "Case Suite not assigned"
        else:
            raise AssertionError("Expected missing case suite assignment")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_storage.py
```

Expected: fail because `PromptLabStore` has no `case_suites_root`, no suite list, and `load_cases()` still reads experiment-local cases.

- [ ] **Step 3: Update store constructor and suite resolution**

In `backend/prompt_lab/storage.py`, import `CaseSuiteArtifact` and update `__init__`:

```python
    def __init__(
        self,
        *,
        experiments_root: Path,
        examples_root: Path,
        case_suites_root: Path | None = None,
    ) -> None:
        self.experiments_root = experiments_root
        self.examples_root = examples_root
        self.case_suites_root = case_suites_root or experiments_root.parent / "case_suites"
```

Add methods:

```python
    def list_case_suites(self) -> list[CaseSuiteArtifact]:
        if not self.case_suites_root.exists():
            return []
        suites: dict[str, CaseSuiteArtifact] = {}
        for manifest_path in sorted(self.case_suites_root.glob("*/suite.json")):
            artifact = CaseSuiteArtifact.model_validate(_read_json(manifest_path))
            suites[artifact.id] = artifact
        return [suites[key] for key in sorted(suites)]

    def case_suite_dir(self, suite_id: str) -> Path:
        _validate_storage_id(suite_id, "Case Suite")
        resolved_root = self.case_suites_root.resolve()
        candidate = (resolved_root / suite_id).resolve()
        if candidate != resolved_root and not candidate.is_relative_to(resolved_root):
            raise NotFoundError("Case Suite not found")
        if (candidate / "suite.json").is_file():
            return candidate
        raise NotFoundError("Case Suite not found")

    def load_case_suite(self, suite_id: str) -> CaseSuiteArtifact:
        path = self.case_suite_dir(suite_id) / "suite.json"
        return CaseSuiteArtifact.model_validate(_read_json(path))
```

- [ ] **Step 4: Replace experiment-local case loading**

Replace `load_cases()` with:

```python
    def load_cases(self, experiment_id: str) -> list[CaseArtifact]:
        experiment = self.load_experiment(experiment_id)
        if experiment.case_suite_id is None:
            raise NotFoundError("Case Suite not assigned")
        return self.load_cases_for_suite(experiment.case_suite_id)

    def load_cases_for_suite(self, suite_id: str) -> list[CaseArtifact]:
        cases_dir = self.case_suite_dir(suite_id) / "cases"
        if not cases_dir.is_dir():
            return []
        cases: list[CaseArtifact] = []
        for path in sorted(cases_dir.glob("*.json")):
            cases.append(
                CaseArtifact.model_validate(
                    {
                        "id": path.stem,
                        "payload": _read_json(path),
                    }
                )
            )
        return cases
```

- [ ] **Step 5: Add suite case mutation and invalidation helpers**

Add:

```python
    def case_suite_case_path(self, suite_id: str, case_id: str) -> Path:
        _validate_storage_id(case_id, "Case")
        cases_dir = self.case_suite_dir(suite_id) / "cases"
        resolved_cases_dir = cases_dir.resolve()
        candidate = (resolved_cases_dir / f"{case_id}.json").resolve()
        if candidate != resolved_cases_dir and not candidate.is_relative_to(resolved_cases_dir):
            raise NotFoundError("Case not found")
        return candidate

    def write_case_to_suite(
        self,
        suite_id: str,
        case_id: str,
        payload: dict[str, Any],
        *,
        overwrite: bool = False,
    ) -> CaseArtifact:
        path = self.case_suite_case_path(suite_id, case_id)
        if path.exists() and not overwrite:
            raise FileExistsError("Case already exists")
        _write_json(path, payload)
        return CaseArtifact.model_validate({"id": case_id, "payload": payload})

    def delete_case_from_suite(self, suite_id: str, case_id: str) -> None:
        path = self.case_suite_case_path(suite_id, case_id)
        if not path.is_file():
            raise NotFoundError("Case not found")
        path.unlink()

    def replace_suite_cases(
        self, suite_id: str, cases: list[CaseArtifact]
    ) -> list[CaseArtifact]:
        cases_dir = self.case_suite_dir(suite_id) / "cases"
        cases_dir.mkdir(parents=True, exist_ok=True)
        case_ids = {artifact_case.id for artifact_case in cases}
        for path in cases_dir.glob("*.json"):
            if path.stem not in case_ids:
                path.unlink()
        for artifact_case in cases:
            _write_json(
                self.case_suite_case_path(suite_id, artifact_case.id),
                artifact_case.payload,
            )
        return self.load_cases_for_suite(suite_id)
```

Add:

```python
    def experiments_using_case_suite(self, suite_id: str) -> list[ExperimentArtifact]:
        _validate_storage_id(suite_id, "Case Suite")
        return [
            experiment
            for experiment in self.list_experiments()
            if experiment.case_suite_id == suite_id
        ]

    def invalidate_experiment_generated_artifacts(self, experiment_id: str) -> None:
        for version in self.list_versions(experiment_id):
            version_dir = self.version_dir(experiment_id, version)
            for name in ["runs", "validations", "reviews", "comparisons"]:
                path = version_dir / name
                if path.exists():
                    shutil.rmtree(path)

    def invalidate_case_suite_consumers(self, suite_id: str) -> list[str]:
        affected = self.experiments_using_case_suite(suite_id)
        for experiment in affected:
            self.invalidate_experiment_generated_artifacts(experiment.id)
        return [experiment.id for experiment in affected]
```

- [ ] **Step 6: Add suite metadata mutation methods**

Add:

```python
    def _available_case_suite_id(self, title: str) -> str:
        base = _slugify_title(title)
        resolved_root = self.case_suites_root.resolve()
        self.case_suites_root.mkdir(parents=True, exist_ok=True)
        candidate = base
        suffix = 2
        while True:
            _validate_storage_id(candidate, "Case Suite")
            candidate_dir = (resolved_root / candidate).resolve()
            if candidate_dir != resolved_root and not candidate_dir.is_relative_to(
                resolved_root
            ):
                raise NotFoundError("Case Suite not found")
            if not candidate_dir.exists():
                return candidate
            candidate = f"{base}-{suffix}"
            suffix += 1

    def create_case_suite(
        self, *, title: str, description: str = ""
    ) -> CaseSuiteArtifact:
        if title.strip() == "":
            raise ValueError("Case Suite title cannot be blank")
        suite_id = self._available_case_suite_id(title)
        suite_dir = self.case_suites_root.resolve() / suite_id
        artifact = CaseSuiteArtifact.model_validate(
            {
                "schema_version": "prompt_lab.case_suite/v1",
                "id": suite_id,
                "title": title,
                "description": description,
            }
        )
        suite_dir.mkdir(parents=True, exist_ok=False)
        (suite_dir / "cases").mkdir()
        _write_json(suite_dir / "suite.json", artifact.model_dump(mode="json"))
        return artifact

    def save_case_suite(
        self, suite_id: str, artifact: CaseSuiteArtifact
    ) -> CaseSuiteArtifact:
        if artifact.id != suite_id:
            raise NotFoundError("Case Suite not found")
        suite_dir = self.case_suite_dir(suite_id)
        _write_json(suite_dir / "suite.json", artifact.model_dump(mode="json"))
        return artifact

    def delete_case_suite(self, suite_id: str) -> None:
        if self.experiments_using_case_suite(suite_id):
            raise ValueError("Case Suite is used by one or more experiments")
        if (self.case_suites_root / suite_id).is_symlink():
            raise NotFoundError("Case Suite not found")
        suite_dir = self.case_suite_dir(suite_id)
        shutil.rmtree(suite_dir)
```

Add storage tests:

```python
def test_store_creates_case_suite_with_unique_slug() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_case_suite_manifest(
            root / "case_suites" / "demo-suite" / "suite.json",
            suite_id="demo-suite",
        )
        store = PromptLabStore(
            experiments_root=root / "experiments",
            case_suites_root=root / "case_suites",
            examples_root=root / "examples",
        )

        created = store.create_case_suite(
            title="Demo Suite",
            description="Reusable inputs",
        )

        assert created.id == "demo-suite-2"
        assert created.title == "Demo Suite"
        assert (root / "case_suites" / "demo-suite-2" / "suite.json").is_file()
        assert (root / "case_suites" / "demo-suite-2" / "cases").is_dir()


def test_store_delete_case_suite_rejects_referenced_suite() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        (experiment / "versions" / "v001").mkdir(parents=True)
        write_experiment_manifest(experiment / "experiment.json")
        payload = json.loads(
            (experiment / "experiment.json").read_text(encoding="utf-8")
        )
        payload["case_suite_id"] = "demo-suite"
        write_json(experiment / "experiment.json", payload)
        write_case_suite_manifest(root / "case_suites" / "demo-suite" / "suite.json")
        store = PromptLabStore(
            experiments_root=root / "experiments",
            case_suites_root=root / "case_suites",
            examples_root=root / "examples",
        )

        try:
            store.delete_case_suite("demo-suite")
        except ValueError as exc:
            assert str(exc) == "Case Suite is used by one or more experiments"
        else:
            raise AssertionError("Expected referenced Case Suite delete to fail")
```

- [ ] **Step 7: Run focused storage tests**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_storage.py
```

Expected: storage tests pass after updating any helper manifests that now need `case_suite_id` for case-loading tests.

- [ ] **Step 8: Commit**

```bash
git add backend/prompt_lab/storage.py backend/tests/test_storage.py
git commit -m "Add case suite storage"
```

---

### Task 4: Backend API And Workflow Behavior

**Files:**
- Modify: `backend/prompt_lab/api.py`
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Write API tests for suites and no-suite behavior**

Add helper setup to `backend/tests/test_api.py`:

```python
def write_runtime_case_suite(root: Path, suite_id: str = "demo-suite") -> None:
    suite_dir = root / "case_suites" / suite_id
    cases_dir = suite_dir / "cases"
    cases_dir.mkdir(parents=True)
    write_json(
        suite_dir / "suite.json",
        {
            "schema_version": "prompt_lab.case_suite/v1",
            "id": suite_id,
            "title": "Demo Suite",
            "description": "",
        },
    )
    write_json(cases_dir / "case-a.json", {"value": "alpha"})
```

Add tests:

```python
def test_api_lists_case_suites() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_runtime_case_suite(root)
        app = create_app(PromptLabConfig.from_env(project_root=root))
        client = TestClient(app)

        response = client.get("/api/case-suites")

        assert response.status_code == 200
        assert response.json()[0]["id"] == "demo-suite"


def test_api_run_requires_case_suite_assignment() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        version_dir = write_runtime_preview_experiment(root)
        del version_dir
        app = create_app(PromptLabConfig.from_env(project_root=root))
        client = TestClient(app)

        response = client.post("/api/experiments/demo/versions/v001/runs/preview-prompts")

        assert response.status_code == 400
        assert response.json()["detail"] == "Case Suite not assigned"
```

Add an inclusion test:

```python
def test_api_saves_case_inclusion_without_editing_suite_payloads() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        version_dir = write_runtime_preview_experiment(root)
        del version_dir
        manifest_path = root / "experiments" / "demo" / "experiment.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["case_suite_id"] = "demo-suite"
        write_json(manifest_path, manifest)
        write_runtime_case_suite(root)
        app = create_app(PromptLabConfig.from_env(project_root=root))
        client = TestClient(app)

        response = client.put(
            "/api/experiments/demo/case-inclusion",
            json={"excluded_case_ids": ["case-a"]},
        )

        assert response.status_code == 200
        assert response.json()["experiment"]["run_defaults"]["excluded_case_ids"] == ["case-a"]
        assert response.json()["cases"][0]["enabled"] is False
        saved_case = json.loads(
            (root / "case_suites" / "demo-suite" / "cases" / "case-a.json").read_text(
                encoding="utf-8"
            )
        )
        assert saved_case == {"value": "alpha"}
```

- [ ] **Step 2: Run API tests and verify failure**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_api.py
```

Expected: fail because Case Suite routes and inclusion route do not exist.

- [ ] **Step 3: Add API request and response models**

In `backend/prompt_lab/api.py`, import `CaseSuiteArtifact` and add models near existing request models:

```python
class CaseSuiteCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str = ""


class CaseSuiteUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str = ""


class CaseInclusionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    excluded_case_ids: list[str] = Field(default_factory=list)


class CaseSuiteCasesUpdateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cases: list[CaseArtifact]
    affected_experiment_ids: list[str]
```

Add helper for version overview responses:

```python
def _case_suite_response(
    store: PromptLabStore, suite_id: str | None
) -> dict[str, object] | None:
    if suite_id is None:
        return None
    return store.load_case_suite(suite_id).model_dump(mode="json")
```

- [ ] **Step 4: Pass `case_suites_root` into store**

In `create_app()`, instantiate:

```python
    store = PromptLabStore(
        experiments_root=resolved_config.experiments_root,
        case_suites_root=resolved_config.case_suites_root,
        examples_root=resolved_config.examples_root,
    )
```

- [ ] **Step 5: Add Case Suite read routes**

Add routes before experiment routes:

```python
    @app.get("/api/case-suites")
    def list_case_suites() -> list[dict[str, object]]:
        return [
            {
                **suite.model_dump(mode="json"),
                "case_count": len(store.load_cases_for_suite(suite.id)),
                "experiment_ids": [
                    experiment.id
                    for experiment in store.experiments_using_case_suite(suite.id)
                ],
            }
            for suite in store.list_case_suites()
        ]

    @app.get("/api/case-suites/{suite_id}")
    def get_case_suite(suite_id: str) -> dict[str, object]:
        suite = store.load_case_suite(suite_id)
        return suite.model_dump(mode="json")

    @app.get("/api/case-suites/{suite_id}/cases")
    def get_case_suite_cases(suite_id: str) -> list[dict[str, object]]:
        return [
            artifact_case.model_dump(mode="json")
            for artifact_case in store.load_cases_for_suite(suite_id)
        ]
```

Add mutation routes:

```python
    @app.post("/api/case-suites")
    def create_case_suite(request: CaseSuiteCreateRequest) -> dict[str, object]:
        try:
            suite = store.create_case_suite(
                title=request.title.strip(),
                description=request.description,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return suite.model_dump(mode="json")

    @app.patch("/api/case-suites/{suite_id}")
    def update_case_suite(
        suite_id: str, request: CaseSuiteUpdateRequest
    ) -> dict[str, object]:
        current = store.load_case_suite(suite_id)
        if request.title.strip() == "":
            raise HTTPException(
                status_code=400,
                detail="Case Suite title cannot be blank",
            )
        updated = current.model_copy(
            update={"title": request.title, "description": request.description}
        )
        return store.save_case_suite(suite_id, updated).model_dump(mode="json")

    @app.delete("/api/case-suites/{suite_id}")
    def delete_case_suite(suite_id: str) -> dict[str, object]:
        try:
            store.delete_case_suite(suite_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"suite_id": suite_id}
```

- [ ] **Step 6: Add experiment inclusion route**

Add helper:

```python
def _validate_case_inclusion_update(
    request: CaseInclusionUpdateRequest, cases: list[CaseArtifact]
) -> list[str]:
    case_ids = {artifact_case.id for artifact_case in cases}
    excluded_case_ids = set(request.excluded_case_ids)
    for case_id in excluded_case_ids:
        _validate_case_id_path_segment(case_id)
    unknown = sorted(excluded_case_ids - case_ids)
    if unknown:
        raise HTTPException(status_code=400, detail=f"Excluded case not found: {unknown[0]}")
    return sorted(excluded_case_ids)
```

Add route:

```python
    @app.put("/api/experiments/{experiment_id}/case-inclusion")
    def update_case_inclusion(
        experiment_id: str, request: CaseInclusionUpdateRequest
    ) -> dict[str, object]:
        experiment = store.load_experiment(experiment_id)
        try:
            cases = store.load_cases(experiment_id)
        except NotFoundError as exc:
            if str(exc) == "Case Suite not assigned":
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            raise
        experiment.run_defaults.excluded_case_ids = _validate_case_inclusion_update(
            request, cases
        )
        store.save_experiment(experiment_id, experiment)
        store.invalidate_experiment_generated_artifacts(experiment_id)
        refreshed = store.load_experiment(experiment_id)
        return {
            "experiment": refreshed.model_dump(mode="json"),
            "cases": _case_responses(cases, refreshed),
        }
```

Keep the existing `PATCH /cases/{case_id}/run-inclusion` route by rewriting it to call the same manifest save and invalidation path.

- [ ] **Step 7: Keep version overview usable without a suite**

In `get_experiment_version()`, replace direct `store.load_cases(experiment_id)` with:

```python
        case_suite: dict[str, object] | None = None
        try:
            cases = store.load_cases(experiment_id)
            case_suite = _case_suite_response(store, experiment.case_suite_id)
        except NotFoundError as exc:
            if str(exc) == "Case Suite not assigned":
                cases = []
            else:
                raise
```

Add this field to the returned dict:

```python
            "case_suite": case_suite,
```

Expected behavior: draft experiments without a suite still load Settings and the empty Cases state; run and prompt-preview endpoints still fail clearly through `_load_workflow_cases()`.

- [ ] **Step 8: Validate Case Suite assignment in settings saves**

In `update_experiment()`, before `store.save_experiment()`:

```python
        previous = store.load_experiment(experiment_id)
        if experiment.case_suite_id is not None:
            try:
                store.load_case_suite(experiment.case_suite_id)
            except NotFoundError as exc:
                raise HTTPException(status_code=400, detail="Case Suite not found") from exc
        case_suite_changed = previous.case_suite_id != experiment.case_suite_id
```

After save:

```python
        if case_suite_changed:
            store.invalidate_experiment_generated_artifacts(experiment_id)
```

- [ ] **Step 9: Convert missing suite errors to 400 for workflow actions**

Add helper:

```python
def _load_workflow_cases(experiment_id: str) -> list[CaseArtifact]:
    try:
        return store.load_cases(experiment_id)
    except NotFoundError as exc:
        if str(exc) == "Case Suite not assigned":
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        raise
```

Inside workflow endpoints that currently call `store.load_cases(experiment_id)`, replace the call with `_load_workflow_cases(experiment_id)`.

- [ ] **Step 10: Add suite case mutation routes**

Add routes for write case, replace cases, and delete case. Each route that changes suite case payloads must call:

```python
affected_experiment_ids = store.invalidate_case_suite_consumers(suite_id)
```

Return the changed cases and `affected_experiment_ids` so the frontend can report invalidation.

- [ ] **Step 11: Remove experiment payload mutation from frontend-facing API**

Delete or stop exposing payload-changing behavior from:

```http
POST /api/experiments/{experiment_id}/cases
PUT /api/experiments/{experiment_id}/cases
DELETE /api/experiments/{experiment_id}/cases/{case_id}
```

If keeping the routes temporarily for clearer errors, return status `410` with:

```python
raise HTTPException(
    status_code=410,
    detail="Case payloads are managed through Case Suites",
)
```

- [ ] **Step 12: Run focused API checks**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_api.py
```

Expected: pass.

- [ ] **Step 13: Commit**

```bash
git add backend/prompt_lab/api.py backend/tests/test_api.py
git commit -m "Add case suite API"
```

---

### Task 5: Frontend Types, API Helpers, And Settings Selector

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/components/ExperimentSettings.tsx`
- Modify: `frontend/tests/experimentSettings.test.ts`

- [ ] **Step 1: Write settings SSR test**

In `frontend/tests/experimentSettings.test.ts`, add a test that renders `ExperimentSettings` with `caseSuites` and asserts the selector:

```ts
test("experiment settings renders case suite selector", () => {
  const html = renderToStaticMarkup(
    React.createElement(ExperimentSettings, {
      experiment: {
        schema_version: "prompt_lab.experiment/v1",
        id: "demo",
        title: "Demo",
        description: "",
        case_suite_id: "demo-suite",
        active_version: "v001",
        output: { type: "text" },
        template: { engine: "jinjax", path: "prompt.md" },
        models: {
          generator_model: "local/a",
          validator_model: "openai/b",
          judge_model: "openai/b"
        },
        run_defaults: {
          repeat_count: 1,
          llm_cache: "disabled",
          case_order: "case-major",
          excluded_case_ids: []
        }
      },
      caseSuites: [
        {
          schema_version: "prompt_lab.case_suite/v1",
          id: "demo-suite",
          title: "Demo Suite",
          description: "",
          case_count: 2,
          experiment_ids: ["demo"]
        }
      ],
      isBusy: false,
      message: null,
      onDirtyChange: () => undefined,
      onDraftChange: () => undefined,
      onReset: () => undefined,
      onSave: async () => undefined
    })
  );

  assert.match(html, /Case Suite/);
  assert.match(html, /Demo Suite/);
});
```

- [ ] **Step 2: Run frontend settings test and verify failure**

Run:

```bash
cd frontend && pnpm test -- experimentSettings
```

Expected: fail because `ExperimentSettings` has no `caseSuites` prop.

- [ ] **Step 3: Add TypeScript types**

In `frontend/src/types.ts`, add:

```ts
export interface CaseSuite {
  schema_version: "prompt_lab.case_suite/v1";
  id: string;
  title: string;
  description: string;
  case_count?: number;
  experiment_ids?: string[];
}

export interface CaseSuiteCreateRequest {
  title: string;
  description?: string;
}

export interface CaseSuiteUpdateRequest {
  title: string;
  description: string;
}

export interface CaseInclusionUpdateRequest {
  excluded_case_ids: string[];
}

export interface CaseInclusionUpdateResponse {
  experiment: Experiment;
  cases: Case[];
}

export interface CaseSuiteCasesUpdateResponse {
  cases: Case[];
  affected_experiment_ids: string[];
}
```

Add to `Experiment`:

```ts
  case_suite_id?: string | null;
```

Add to `VersionOverview`:

```ts
  case_suite?: CaseSuite | null;
```

- [ ] **Step 4: Add API helpers**

In `frontend/src/api.ts`, import the new types and add:

```ts
export function getCaseSuites(): Promise<CaseSuite[]> {
  return apiGet<CaseSuite[]>("/api/case-suites");
}

export function createCaseSuite(
  request: CaseSuiteCreateRequest
): Promise<CaseSuite> {
  return apiPost<CaseSuite>("/api/case-suites", request);
}

export function updateCaseSuite(
  suiteId: string,
  request: CaseSuiteUpdateRequest
): Promise<CaseSuite> {
  return apiPatch<CaseSuite>(
    `/api/case-suites/${encodeURIComponent(suiteId)}`,
    request
  );
}

export function deleteCaseSuite(suiteId: string): Promise<{ suite_id: string }> {
  return apiDelete<{ suite_id: string }>(
    `/api/case-suites/${encodeURIComponent(suiteId)}`
  );
}

export function getCaseSuiteCases(suiteId: string): Promise<Case[]> {
  return apiGet<Case[]>(
    `/api/case-suites/${encodeURIComponent(suiteId)}/cases`
  );
}

export function saveCaseSuiteCases(
  suiteId: string,
  cases: CaseUploadRequest[]
): Promise<CaseSuiteCasesUpdateResponse> {
  return apiPut<CaseSuiteCasesUpdateResponse>(
    `/api/case-suites/${encodeURIComponent(suiteId)}/cases`,
    { cases }
  );
}

export function saveCaseInclusion(
  experimentId: string,
  request: CaseInclusionUpdateRequest
): Promise<CaseInclusionUpdateResponse> {
  return apiPut<CaseInclusionUpdateResponse>(
    `/api/experiments/${encodeURIComponent(experimentId)}/case-inclusion`,
    request
  );
}
```

Stop exporting `uploadCase`, `deleteCase`, and `saveCases` after frontend call sites are moved.

- [ ] **Step 5: Add selector prop to settings**

Update `ExperimentSettingsProps`:

```ts
  caseSuites: CaseSuite[];
```

Add a `Case Suite` section after Identity:

```tsx
      <section className="settings-section">
        <h3>Case Suite</h3>
        <label className="settings-field">
          <span>Assigned suite</span>
          <select
            value={draft.case_suite_id ?? ""}
            onChange={(event) =>
              updateDraft((current) => ({
                ...current,
                case_suite_id:
                  event.target.value.length === 0 ? null : event.target.value
              }))
            }
          >
            <option value="">No Case Suite assigned</option>
            {caseSuites.map((suite) => (
              <option key={suite.id} value={suite.id}>
                {suite.title} ({suite.id})
              </option>
            ))}
          </select>
        </label>
      </section>
```

- [ ] **Step 6: Run frontend test**

Run:

```bash
cd frontend && pnpm test -- experimentSettings
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/types.ts frontend/src/api.ts frontend/src/components/ExperimentSettings.tsx frontend/tests/experimentSettings.test.ts
git commit -m "Add case suite frontend contracts"
```

---

### Task 6: Experiment Case Preview And Inclusion UI

**Files:**
- Modify: `frontend/src/components/CaseBrowser.tsx`
- Modify: `frontend/tests/caseBrowser.test.ts`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Update CaseBrowser tests**

Replace the management-controls test in `frontend/tests/caseBrowser.test.ts` with:

```ts
test("experiment case browser renders inclusion controls without payload management", () => {
  const html = renderToStaticMarkup(
    React.createElement(CaseBrowser, {
      cases: [
        {
          id: "active-case",
          enabled: true,
          payload: { value: "alpha" }
        },
        {
          id: "disabled-case",
          enabled: false,
          payload: { value: "bravo" }
        }
      ],
      suiteTitle: "Demo Suite",
      onCasesChange: () => undefined
    })
  );

  assert.match(html, /Demo Suite/);
  assert.match(html, /Include in runs/);
  assert.match(html, /Excluded/);
  assert.doesNotMatch(html, /Upload case JSON/);
  assert.doesNotMatch(html, /Delete case/);
});
```

Replace the unsaved navigation test assertions:

```ts
  assert.match(source, /Unsaved case inclusion changes/);
  assert.match(source, /handleSaveCaseInclusion/);
```

- [ ] **Step 2: Run CaseBrowser tests and verify failure**

Run:

```bash
cd frontend && pnpm test -- caseBrowser
```

Expected: fail because the current browser still renders upload/delete controls.

- [ ] **Step 3: Remove payload mutation controls from CaseBrowser**

In `frontend/src/components/CaseBrowser.tsx`:

- remove `ChangeEvent` and `useRef` imports;
- remove `deriveCaseId()`, `isJsonObject()`, `handleFileInputChange()`, and `handleDeleteCase()`;
- remove file input markup;
- remove `Delete case` button.

Add prop:

```ts
  suiteTitle?: string | null;
```

Render suite context in the header:

```tsx
          <div>
            <h3>Cases</h3>
            <span>
              {filteredCases.length} of {cases.length}
              {suiteTitle ? ` from ${suiteTitle}` : ""}
            </span>
          </div>
```

Change inclusion message text to:

```ts
      enabled
        ? `Included ${caseId} in this experiment. Save inclusion to apply changes.`
        : `Excluded ${caseId} from this experiment. Save inclusion to apply changes.`
```

- [ ] **Step 4: Rename App save flow**

In `frontend/src/App.tsx`, rename state text and functions:

- `handleSaveCases` to `handleSaveCaseInclusion`;
- `"Saving cases..."` to `"Saving case inclusion..."`;
- `"Cases saved."` to `"Case inclusion saved."`;
- `"Unsaved case changes."` to `"Unsaved case inclusion changes."`;
- `"Save case changes before running."` to `"Save case inclusion before running."`;
- call `saveCaseInclusion(experiment.id, { excluded_case_ids })`.

The request body should be:

```ts
{
  excluded_case_ids: casesDraft
    .filter((artifactCase) => !artifactCase.enabled)
    .map((artifactCase) => artifactCase.id)
}
```

Pass suite title:

```tsx
suiteTitle={detailState.overview.case_suite?.title ?? null}
```

- [ ] **Step 5: Run frontend tests**

Run:

```bash
cd frontend && pnpm test -- caseBrowser
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/CaseBrowser.tsx frontend/tests/caseBrowser.test.ts frontend/src/App.tsx
git commit -m "Limit experiment cases to inclusion"
```

---

### Task 7: Case Suite Management UI

**Files:**
- Create: `frontend/src/components/CaseSuiteManager.tsx`
- Create: `frontend/tests/caseSuitesView.test.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Write CaseSuiteManager SSR tests**

Create `frontend/tests/caseSuitesView.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { CaseSuiteManager } from "../src/components/CaseSuiteManager.tsx";

test("case suite manager renders suite list and case payload management", () => {
  const html = renderToStaticMarkup(
    React.createElement(CaseSuiteManager, {
      suites: [
        {
          schema_version: "prompt_lab.case_suite/v1",
          id: "demo-suite",
          title: "Demo Suite",
          description: "",
          case_count: 1,
          experiment_ids: ["demo"]
        }
      ],
      selectedSuiteId: "demo-suite",
      cases: [{ id: "case-a", enabled: true, payload: { value: "alpha" } }],
      isBusy: false,
      message: null,
      onSelectSuite: () => undefined,
      onCreateSuite: async () => undefined,
      onUpdateSuite: async () => undefined,
      onDeleteSuite: async () => undefined,
      onCasesChange: () => undefined,
      onSaveCases: async () => undefined
    })
  );

  assert.match(html, /Case Suites/);
  assert.match(html, /Demo Suite/);
  assert.match(html, /Add case/);
  assert.match(html, /Delete case/);
  assert.match(html, /value/);
  assert.match(html, /Referenced by demo/);
});
```

- [ ] **Step 2: Run new frontend test and verify failure**

Run:

```bash
cd frontend && pnpm test -- caseSuitesView
```

Expected: fail because `CaseSuiteManager.tsx` does not exist.

- [ ] **Step 3: Create CaseSuiteManager component**

Create `frontend/src/components/CaseSuiteManager.tsx` with these responsibilities:

- render suite list with title, id, case count, and references;
- render create/update/delete controls for suite metadata;
- disable suite deletion when `experiment_ids.length > 0`;
- render selected suite cases;
- allow adding a case from JSON file or pasted JSON object;
- allow editing selected case payload JSON in a textarea;
- allow deleting selected case;
- call `onCasesChange(nextCases)` for local draft edits and `onSaveCases()` for persistence.

Use these prop types:

```ts
interface CaseSuiteManagerProps {
  suites: CaseSuite[];
  selectedSuiteId: string | null;
  cases: Case[];
  isBusy: boolean;
  message: string | null;
  onSelectSuite: (suiteId: string) => void;
  onCreateSuite: (request: CaseSuiteCreateRequest) => Promise<void>;
  onUpdateSuite: (suiteId: string, request: CaseSuiteUpdateRequest) => Promise<void>;
  onDeleteSuite: (suiteId: string) => Promise<void>;
  onCasesChange: (cases: Case[]) => void;
  onSaveCases: () => Promise<void>;
}
```

Use existing button classes: `primary-action`, `secondary-action`, and `danger-action`.

- [ ] **Step 4: Add App state and handlers**

In `frontend/src/App.tsx`:

- extend `AppView` to `"experiment" | "globalSettings" | "caseSuites"`;
- add `caseSuites`, `selectedCaseSuiteId`, `caseSuiteCases`, `caseSuiteCasesDraft`, `caseSuitesBusy`, and `caseSuitesMessage` state;
- load `getCaseSuites()` during app initialization and after suite mutations;
- load `getCaseSuiteCases(selectedSuiteId)` when selected suite changes;
- add header/sidebar control labelled `Case Suites`;
- render `CaseSuiteManager` when `appView === "caseSuites"`;
- wire create/update/delete/save cases to the API helpers from Task 5.

After saving suite cases, set a message:

```ts
const affected = response.affected_experiment_ids;
setCaseSuitesMessage(
  affected.length === 0
    ? "Case Suite cases saved."
    : `Case Suite cases saved. Invalidated generated artifacts for ${affected.join(", ")}.`
);
```

- [ ] **Step 5: Add styles**

In `frontend/src/styles.css`, add styles with existing surface tokens and 8px-or-less radii:

```css
.case-suite-layout {
  display: grid;
  grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
  gap: 16px;
}

.case-suite-list,
.case-suite-detail {
  min-width: 0;
}

.case-suite-item {
  width: 100%;
  text-align: left;
}

.case-suite-case-editor textarea {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  min-height: 260px;
}

@media (max-width: 980px) {
  .case-suite-layout {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 6: Run frontend suite tests**

Run:

```bash
cd frontend && pnpm test -- caseSuitesView
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/CaseSuiteManager.tsx frontend/tests/caseSuitesView.test.ts frontend/src/App.tsx frontend/src/styles.css
git commit -m "Add case suite management UI"
```

---

### Task 8: Update Docs And Full Test Fixtures

**Files:**
- Modify: `README.md`
- Modify: `FORMAT.md`
- Modify: `backend/README.md`
- Modify: `frontend/e2e/demo-prompt.spec.ts`
- Modify: remaining backend/frontend tests that reference `examples/<id>` or experiment-local `cases/`

- [ ] **Step 1: Update docs**

In `README.md`, replace the current case description with:

```markdown
Cases are plain JSON objects grouped into Case Suites. Runtime experiments point
to one Case Suite by `case_suite_id`; the suite owns payloads, and the
experiment owns per-experiment run inclusion through `run_defaults.excluded_case_ids`.
```

Update the seeding section:

```markdown
`examples/` contains committed golden templates under `examples/experiments/`
and `examples/case_suites/`. On backend startup, Prompt Lab seeds missing
runtime `experiments/` and `case_suites/` roots independently. Runtime reads,
generated artifacts, and GUI edits use the gitignored runtime roots only.
```

In `FORMAT.md`, add the `Case Suite` section from the accepted design and update the directory layout.

In `backend/README.md`, add `PROMPT_LAB_CASE_SUITES_ROOT` to the env override list.

- [ ] **Step 2: Update e2e expectations**

In `frontend/e2e/demo-prompt.spec.ts`, keep `demo-string` and `demo-json` as the demo fixtures, and add an assertion that the Cases tab still shows at least two cases through the assigned suite. Add a navigation assertion that a `Case Suites` control exists and opens the suite manager.

- [ ] **Step 3: Search and update stale paths**

Run:

```bash
rg -n 'examples/(demo|string|json|split|summarize)|/cases|case changes|saveCases|uploadCase|deleteCase|PROMPT_LAB_CASE_SUITES_ROOT' README.md FORMAT.md backend frontend docs
```

For each remaining stale reference:

- examples should point to `examples/experiments/<id>` or `examples/case_suites/<id>`;
- experiment-local `cases/` should only appear in historical docs or tests that explicitly assert it is not used;
- frontend copy should say `case inclusion` when it means experiment inclusion;
- payload creation/deletion should mention Case Suite management.

- [ ] **Step 4: Run full backend checks from AGENTS.md**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_chat.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_chat_get_structured_lite.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_structured_lite_units.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_format_validation_errors.py
.venv/bin/pyright --project pyrightconfig.json --pythonpath .venv/bin/python
```

Expected: all pass.

- [ ] **Step 5: Run frontend checks from AGENTS.md**

Run:

```bash
cd frontend && pnpm lint && pnpm test && pnpm build
```

Expected: all pass.

- [ ] **Step 6: Run e2e**

Run:

```bash
cd frontend && pnpm test:e2e
```

Expected: pass. If sandbox networking blocks local server startup, rerun the same command with escalation approval.

- [ ] **Step 7: Commit**

```bash
git add README.md FORMAT.md backend/README.md frontend/e2e/demo-prompt.spec.ts backend frontend docs examples .gitignore
git commit -m "Finish case suite migration"
```

---

## Self-Review Checklist For Implementer

- Every committed example experiment has `case_suite_id`.
- No committed example experiment contains `cases/`.
- Runtime `case_suites/` is gitignored.
- `demo-string` and `demo-json` still have stable precomputed artifacts and load cases through their suites.
- Experiment Cases tab cannot add, delete, or edit payloads.
- Case Suite manager can add, delete, and edit suite cases.
- Run and prompt preview fail clearly when an experiment has no Case Suite.
- Changing experiment inclusion invalidates only that experiment's generated artifacts.
- Changing suite payloads invalidates all experiments referencing the suite.
- `PromptLabStore` has no read path for `experiments/<id>/cases/`.
- All checks in the last task pass before handoff.
