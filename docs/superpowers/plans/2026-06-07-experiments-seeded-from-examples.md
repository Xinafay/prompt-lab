# Experiments Seeded From Examples Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `examples/` a committed golden template and make `experiments/` the only runtime workspace seeded from examples on first backend startup.

**Architecture:** Add an explicit seeding helper that copies top-level example experiment directories into `experiments/` only when no runtime experiment manifests exist. After seeding, `PromptLabStore` reads and writes only `experiments_root`; `examples_root` remains only an initialization source. Tests should prove examples are not a runtime fallback and generated artifacts are written under `experiments/`.

**Tech Stack:** Python 3.14, FastAPI startup/app factory, filesystem storage with `pathlib`/`shutil`, Pydantic artifact validation, direct script-style backend tests, gitignored local runtime artifacts.

---

## File Structure

Backend:

- Create: `backend/prompt_lab/experiment_seed.py` - owns seed-once logic from `examples_root` to `experiments_root`.
- Modify: `backend/prompt_lab/api.py` - calls seeding before constructing `PromptLabStore`.
- Modify: `backend/prompt_lab/storage.py` - removes runtime fallback to `examples_root`; lists and resolves only `experiments_root`.
- Test: `backend/tests/test_experiment_seed.py` - focused seeding unit tests.
- Test: `backend/tests/test_storage.py` - updates storage expectations for experiments-only runtime.
- Test: `backend/tests/test_api.py` - proves app factory seeds examples and writes run artifacts under `experiments/`.

Docs/config:

- Modify: `.gitignore` - add `experiments/`.
- Modify: `README.md` - explain examples as templates and experiments as runtime workspace.
- Modify: `backend/README.md` - document seed-once behavior and runtime path ownership.
- Modify: `examples/README.md` - clarify examples are copied into experiments and are not modified by the app.

---

### Task 1: Add Seed-On-Empty Helper

**Files:**
- Create: `backend/prompt_lab/experiment_seed.py`
- Test: `backend/tests/test_experiment_seed.py`

- [ ] **Step 1: Add failing tests for missing, empty, existing, missing examples, and conflict roots**

Create `backend/tests/test_experiment_seed.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from prompt_lab.experiment_seed import seed_experiments_from_examples


MANIFEST = {
    "schema_version": "prompt_lab.experiment/v1",
    "id": "demo",
    "title": "Demo",
    "description": "",
    "active_version": "v001",
    "output": {"type": "text"},
    "template": {"engine": "jinja2", "path": "prompt.md"},
    "models": {"generator_model": "local/a", "judge_model": "openai/b"},
    "run_defaults": {
        "repeat_count": 1,
        "llm_cache": "disabled",
        "case_order": "case-major",
    },
}


def write_example(root: Path, experiment_id: str = "demo") -> Path:
    example_dir = root / "examples" / experiment_id
    version_dir = example_dir / "versions" / "v001"
    version_dir.mkdir(parents=True)
    manifest = {**MANIFEST, "id": experiment_id, "title": experiment_id.title()}
    (example_dir / "experiment.json").write_text(
        json.dumps(manifest, ensure_ascii=False),
        encoding="utf-8",
    )
    (version_dir / "prompt.md").write_text("Prompt", encoding="utf-8")
    return example_dir


def test_seed_creates_experiments_root_when_missing() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_example(root)

        result = seed_experiments_from_examples(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        assert result.seeded is True
        assert result.copied_experiment_ids == ["demo"]
        assert (root / "experiments" / "demo" / "experiment.json").is_file()
        assert (
            root / "experiments" / "demo" / "versions" / "v001" / "prompt.md"
        ).read_text(encoding="utf-8") == "Prompt"


def test_seed_copies_when_experiments_root_is_empty() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "experiments").mkdir()
        write_example(root)

        result = seed_experiments_from_examples(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        assert result.seeded is True
        assert result.copied_experiment_ids == ["demo"]
        assert (root / "experiments" / "demo" / "experiment.json").is_file()


def test_seed_does_nothing_when_any_runtime_manifest_exists() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_example(root, "template")
        runtime_dir = root / "experiments" / "existing"
        runtime_dir.mkdir(parents=True)
        (runtime_dir / "experiment.json").write_text(
            json.dumps({**MANIFEST, "id": "existing"}, ensure_ascii=False),
            encoding="utf-8",
        )

        result = seed_experiments_from_examples(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        assert result.seeded is False
        assert result.copied_experiment_ids == []
        assert not (root / "experiments" / "template").exists()


def test_seed_creates_empty_experiments_when_examples_missing() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)

        result = seed_experiments_from_examples(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        assert result.seeded is False
        assert result.copied_experiment_ids == []
        assert (root / "experiments").is_dir()


def test_seed_fails_on_conflicting_existing_directory_without_manifest() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_example(root, "demo")
        conflict_dir = root / "experiments" / "demo"
        conflict_dir.mkdir(parents=True)
        (conflict_dir / "notes.txt").write_text("local data", encoding="utf-8")

        try:
            seed_experiments_from_examples(
                experiments_root=root / "experiments",
                examples_root=root / "examples",
            )
        except FileExistsError:
            pass
        else:
            raise AssertionError("Expected conflicting seed destination to fail")

        assert (conflict_dir / "notes.txt").read_text(encoding="utf-8") == "local data"


def main() -> int:
    tests = [
        test_seed_creates_experiments_root_when_missing,
        test_seed_copies_when_experiments_root_is_empty,
        test_seed_does_nothing_when_any_runtime_manifest_exists,
        test_seed_creates_empty_experiments_when_examples_missing,
        test_seed_fails_on_conflicting_existing_directory_without_manifest,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run seed tests and verify they fail**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_experiment_seed.py
```

Expected: fail with `ModuleNotFoundError: No module named 'prompt_lab.experiment_seed'`.

- [ ] **Step 3: Implement seed helper**

Create `backend/prompt_lab/experiment_seed.py`:

```python
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SeedResult:
    seeded: bool
    copied_experiment_ids: list[str]


def _has_runtime_experiment_manifests(experiments_root: Path) -> bool:
    return experiments_root.is_dir() and any(
        path.is_file() for path in experiments_root.glob("*/experiment.json")
    )


def seed_experiments_from_examples(
    *, experiments_root: Path, examples_root: Path
) -> SeedResult:
    """Seed local runtime experiments from committed examples exactly once."""
    if _has_runtime_experiment_manifests(experiments_root):
        return SeedResult(seeded=False, copied_experiment_ids=[])

    experiments_root.mkdir(parents=True, exist_ok=True)
    if not examples_root.is_dir():
        return SeedResult(seeded=False, copied_experiment_ids=[])

    copied: list[str] = []
    for example_dir in sorted(path for path in examples_root.iterdir() if path.is_dir()):
        manifest_path = example_dir / "experiment.json"
        if not manifest_path.is_file():
            continue
        destination = experiments_root / example_dir.name
        shutil.copytree(example_dir, destination)
        copied.append(example_dir.name)

    return SeedResult(seeded=bool(copied), copied_experiment_ids=copied)
```

- [ ] **Step 4: Run seed tests and verify they pass**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_experiment_seed.py
```

Expected: all five tests print `OK`.

- [ ] **Step 5: Commit seed helper**

Run:

```bash
git add backend/prompt_lab/experiment_seed.py backend/tests/test_experiment_seed.py
git commit -m "feat: seed experiments from examples"
```

---

### Task 2: Make Storage Runtime-Only

**Files:**
- Modify: `backend/prompt_lab/storage.py`
- Test: `backend/tests/test_storage.py`

- [ ] **Step 1: Replace storage fallback tests with runtime-only expectations**

In `backend/tests/test_storage.py`, replace `test_store_lists_example_experiments` with:

```python
def test_store_does_not_list_examples_directly() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        example = root / "examples" / "demo"
        version = example / "versions" / "v001"
        version.mkdir(parents=True)
        (example / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )

        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        assert store.list_experiments() == []
```

Replace `test_store_prefers_experiments_root_over_examples_root` with:

```python
def test_store_resolves_only_experiments_root() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        example = root / "examples" / "demo"
        experiment = root / "experiments" / "demo"
        (example / "versions" / "v001").mkdir(parents=True)
        (experiment / "versions" / "v002").mkdir(parents=True)
        (example / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Example Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )
        (experiment / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Editable Demo","description":"","active_version":"v002","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )

        store = PromptLabStore(
            experiments_root=root / "experiments",
            examples_root=root / "examples",
        )

        experiments = store.list_experiments()

        assert len(experiments) == 1
        assert experiments[0].id == "demo"
        assert experiments[0].title == "Editable Demo"
        assert store.experiment_dir("demo") == experiment.resolve()
```

Update the `tests = [...]` list in `main()` to use the new function names.

- [ ] **Step 2: Run storage tests and verify runtime-only tests fail**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_storage.py
```

Expected: `test_store_does_not_list_examples_directly` fails because examples are still listed.

- [ ] **Step 3: Update `PromptLabStore` to ignore examples at runtime**

In `backend/prompt_lab/storage.py`, change `list_experiments` and `experiment_dir` to:

```python
    def list_experiments(self) -> list[ExperimentArtifact]:
        """Return runtime experiments from `experiments/`, sorted by id."""
        if not self.experiments_root.exists():
            return []
        manifests: dict[str, ExperimentArtifact] = {}
        for manifest_path in sorted(self.experiments_root.glob("*/experiment.json")):
            artifact = ExperimentArtifact.model_validate(_read_json(manifest_path))
            manifests[artifact.id] = artifact
        return [manifests[key] for key in sorted(manifests)]

    def experiment_dir(self, experiment_id: str) -> Path:
        """Resolve an experiment directory under the runtime experiments root."""
        _validate_storage_id(experiment_id, "Experiment")
        resolved_root = self.experiments_root.resolve()
        candidate = (resolved_root / experiment_id).resolve()
        if candidate != resolved_root and not candidate.is_relative_to(resolved_root):
            raise NotFoundError("Experiment not found")
        if (candidate / "experiment.json").is_file():
            return candidate
        raise NotFoundError("Experiment not found")
```

Keep `examples_root` on `PromptLabStore.__init__` for constructor compatibility in this task.

- [ ] **Step 4: Run storage tests and verify they pass**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_storage.py
```

Expected: all storage tests print `OK`.

- [ ] **Step 5: Commit runtime-only storage**

Run:

```bash
git add backend/prompt_lab/storage.py backend/tests/test_storage.py
git commit -m "refactor: read runtime experiments only"
```

---

### Task 3: Seed During App Factory Initialization

**Files:**
- Modify: `backend/prompt_lab/api.py`
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: Add API test that app factory seeds examples before listing experiments**

Append this test to `backend/tests/test_api.py` near `test_api_lists_experiments`:

```python
def test_api_seeds_examples_into_experiments_on_startup() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        example = root / "examples" / "demo"
        version = example / "versions" / "v001"
        version.mkdir(parents=True)
        (example / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":1,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )
        (version / "prompt.md").write_text("Hello {{ name }}", encoding="utf-8")
        cases = version / "cases"
        cases.mkdir()
        (cases / "case-a.json").write_text(
            '{"schema_version":"prompt_lab.case/v1","id":"case-a","title":"Case A","variables":{"name":"Ada"}}',
            encoding="utf-8",
        )

        app = create_app(PromptLabConfig.from_env(project_root=root))
        response = TestClient(app).get("/api/experiments")

        assert response.status_code == 200
        assert [item["id"] for item in response.json()] == ["demo"]
        assert (root / "experiments" / "demo" / "experiment.json").is_file()
        assert (
            root / "experiments" / "demo" / "versions" / "v001" / "prompt.md"
        ).is_file()
```

Add this function to the `tests = [...]` list in `main()`.

- [ ] **Step 2: Run API tests and verify new seed test fails**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_api.py
```

Expected: the new test fails because `create_app` does not seed before constructing the store.

- [ ] **Step 3: Call seeding in `create_app`**

In `backend/prompt_lab/api.py`, add the import:

```python
from prompt_lab.experiment_seed import seed_experiments_from_examples
```

Then update `create_app`:

```python
def create_app(config: PromptLabConfig | None = None) -> FastAPI:
    resolved_config = config or PromptLabConfig.from_env()
    seed_experiments_from_examples(
        experiments_root=resolved_config.experiments_root,
        examples_root=resolved_config.examples_root,
    )
    store = PromptLabStore(
        experiments_root=resolved_config.experiments_root,
        examples_root=resolved_config.examples_root,
    )
```

- [ ] **Step 4: Run API tests and verify they pass**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_api.py
```

Expected: all API tests print `OK`.

- [ ] **Step 5: Commit app factory seeding**

Run:

```bash
git add backend/prompt_lab/api.py backend/tests/test_api.py
git commit -m "feat: seed experiments during app startup"
```

---

### Task 4: Prove Generated Artifacts Stay Under Experiments

**Files:**
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Strengthen dry-run run test with experiments-root assertion**

In `backend/tests/test_api.py`, find `test_api_dry_run_text_version_avoids_live_llm`. After the POST assertion, add:

```python
            assert (
                root
                / "experiments"
                / "demo"
                / "versions"
                / "v001"
                / "runs"
                / body["job_id"]
            ).is_dir()
            assert not (
                root
                / "examples"
                / "demo"
                / "versions"
                / "v001"
                / "runs"
            ).exists()
```

If this test fixture currently writes the experiment only under `examples/`, leave it that way; app startup seeding should copy it into `experiments/` before the run writes artifacts.

- [ ] **Step 2: Run API tests**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_api.py
```

Expected: all API tests print `OK`, including the new artifact location assertions.

- [ ] **Step 3: Commit artifact location coverage**

Run:

```bash
git add backend/tests/test_api.py
git commit -m "test: keep generated runs under experiments"
```

---

### Task 5: Gitignore And Documentation

**Files:**
- Modify: `.gitignore`
- Modify: `README.md`
- Modify: `backend/README.md`
- Modify: `examples/README.md`

- [ ] **Step 1: Add `experiments/` to `.gitignore`**

Add this line to `.gitignore` near other local runtime paths:

```gitignore
experiments/
```

- [ ] **Step 2: Update top-level README runtime path explanation**

In `README.md`, after the setup/config section, add:

```markdown
`examples/` contains committed golden templates. On backend startup, if
`experiments/` does not exist or contains no `*/experiment.json` manifests, Prompt
Lab copies examples into `experiments/`. Runtime reads, generated artifacts, and
future GUI edits use `experiments/` only. The `experiments/` directory is ignored
by git.
```

- [ ] **Step 3: Update backend README runtime paths**

In `backend/README.md`, replace the runtime paths text with:

```markdown
Prompt Lab has two repository-local experiment roots:

- `examples/` - committed golden templates, used only to seed a new workspace.
- `experiments/` - local runtime workspace, ignored by git.

On backend startup, if `experiments/` does not exist or contains no
`*/experiment.json` manifests, Prompt Lab copies top-level example experiment
directories from `examples/` into `experiments/`. Once seeded, the backend lists,
loads, and writes only `experiments/`.
```

Keep the environment override list for `PROMPT_LAB_EXPERIMENTS_ROOT` and `PROMPT_LAB_EXAMPLES_ROOT`.

- [ ] **Step 4: Update examples README**

Add this paragraph to `examples/README.md`:

```markdown
The running app does not write into `examples/`. At backend startup, examples are
copied into `experiments/` only when the runtime workspace is missing or has no
experiment manifests. Edit and run experiments from `experiments/`; update
`examples/` only when changing the golden starter templates.
```

- [ ] **Step 5: Run docs diff check**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 6: Commit docs and gitignore**

Run:

```bash
git add .gitignore README.md backend/README.md examples/README.md
git commit -m "docs: describe experiments runtime workspace"
```

---

### Task 6: Final Validation

**Files:**
- No code edits expected.

- [ ] **Step 1: Run seed, storage, and API tests**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_experiment_seed.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_storage.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_api.py
```

Expected: all tests print `OK`.

- [ ] **Step 2: Run broader backend checks affected by storage resolution**

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

Expected: `tsc --noEmit` and `vite build` succeed.

- [ ] **Step 4: Verify no generated runtime experiments are staged**

Run:

```bash
git status --short
```

Expected: no uncommitted tracked changes. If an untracked `experiments/` directory exists after manual browser testing, it should be ignored by git because `.gitignore` contains `experiments/`.

---

## Final Acceptance Checklist

- [ ] Backend startup seeds `experiments/` from `examples/` when no runtime manifests exist.
- [ ] Backend startup does not copy examples when `experiments/` already has an experiment manifest.
- [ ] `PromptLabStore` no longer lists or resolves `examples/` directly.
- [ ] API list/version/run workflows operate from `experiments/` after seeding.
- [ ] Generated run artifacts are not written under `examples/`.
- [ ] `experiments/` is ignored by git.
- [ ] Docs explain examples as golden templates and experiments as runtime workspace.
- [ ] Seed/storage/API/judge/proposal/compare tests pass.
- [ ] Pyright and frontend build pass.
