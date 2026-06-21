# Prompt Lab MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Prompt Lab MVP: a standalone local web app for running prompt experiments, reviewing repeated outputs, judging results with a stronger model, adding human decisions/notes, generating proposals, and comparing versions.

**Architecture:** Python backend owns filesystem experiment storage, prompt rendering, Pydantic model loading, LLM calls, run artifacts, job progress, judgments, proposals, and comparisons. React/Vite frontend is a local tool UI over backend REST endpoints and SSE job events. Experiments are plain files; `backend/shared/llm` provides the local LLM routing layer and should be accessed through a thin Prompt Lab wrapper.

**Tech Stack:** Python 3.14, FastAPI, Pydantic v2, Jinja2, `shared.llm`, React, Vite, TypeScript, filesystem artifacts, SSE.

---

## Starting Context

Prompt Lab is a standalone local application for improving prompts through repeated model runs, qualitative LLM judgment, human review, proposal generation, and version comparison.

Carmilla is a separate local storytelling/workflow project. It is relevant here only as an external producer of neutral Prompt Lab experiment bundles and as the original reference for the bundled `shared.llm` model-routing layer. Prompt Lab must remain independent: it should import neutral experiment files, not Carmilla workflow state or workflow code.

This repository already contains the seed files needed to start implementing Prompt Lab.

Important files already present:

- `DESIGN.md` - full product design.
- `FORMAT.md` - artifact format summary.
- `TRANSFER.md` - bootstrap checklist for setting up a fresh repository.
- `AGENTS.md` - project rules.
- `backend/shared/llm/` - local LLM backend used for OpenAI and OpenAI-compatible model routing.
- `backend/tests/` - LLM and structured-output tests.
- `examples/split-scenes/` - Pydantic example experiment.
- `examples/summarize-chapter/` - text example experiment.

Do not import Carmilla workflow runtime, Story Parser workflow classes, `WorkflowState`, or `FlatFileSystem`. If Carmilla integration is needed later, implement it as an exporter on the Carmilla side that writes neutral Prompt Lab bundles.

## Target File Structure

Create or evolve the standalone repo toward this structure:

```text
prompt-lab/
  backend/
    prompt_lab/
      __init__.py
      app.py
      api.py
      config.py
      errors.py
      template_renderer.py
      pydantic_loader.py
      llm_client.py
      storage.py
      runner.py
      jobs.py
      judge.py
      compare.py
      proposal.py
      models/
        __init__.py
        artifacts.py
        api.py
        judgments.py
    shared/
      llm/
    tests/
      test_artifacts.py
      test_storage.py
      test_template_renderer.py
      test_pydantic_loader.py
      test_runner.py
      test_jobs.py
      test_judge.py
      test_reviews.py
      test_proposal.py
      test_compare.py
      test_api.py
      test_chat.py
      test_chat_get_structured_lite.py
      test_structured_lite_units.py
      test_format_validation_errors.py
      test_chat_env.py
    requirements.txt
    requirements-dev.txt
  frontend/
    package.json
    index.html
    src/
      api.ts
      main.tsx
      App.tsx
      types.ts
      components/
        ExperimentsList.tsx
        PromptView.tsx
        ValidatorsView.tsx
        RunsView.tsx
        RunDetail.tsx
        ReviewView.tsx
        ProposalView.tsx
        ComparisonView.tsx
      styles.css
  examples/
  experiments/
  config/
  .agents/
  .gitignore
  AGENTS.md
  DESIGN.md
  FORMAT.md
  TRANSFER.md
  IMPLEMENTATION_PLAN.md
  pyrightconfig.json
```

## Global Validation Commands

Run these after each backend task:

```bash
PYTHONPATH=backend python backend/tests/test_chat.py
PYTHONPATH=backend python backend/tests/test_chat_get_structured_lite.py
PYTHONPATH=backend python backend/tests/test_structured_lite_units.py
PYTHONPATH=backend python backend/tests/test_format_validation_errors.py
pyright --project pyrightconfig.json --pythonpath .venv/bin/python
```

Run these after each frontend task:

```bash
cd frontend
pnpm lint
pnpm build
```

If `pnpm` or frontend dependencies are not installed yet, document that explicitly and run backend checks.

---

### Task 1: Repository Bootstrap

**Files:**
- Create: `backend/prompt_lab/__init__.py`
- Create: `backend/prompt_lab/config.py`
- Create: `backend/prompt_lab/errors.py`
- Create: `backend/tests/test_config.py`
- Modify: `pyrightconfig.json`
- Modify: `backend/README.md`

- [ ] **Step 1: Write config tests**

Create `backend/tests/test_config.py`:

```python
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from prompt_lab.config import PromptLabConfig


def test_default_config_uses_repo_local_paths() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        config = PromptLabConfig.from_env(project_root=root)

        assert config.project_root == root
        assert config.experiments_root == root / "experiments"
        assert config.examples_root == root / "examples"


def test_config_accepts_experiments_root_override() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiments = root / "custom-experiments"
        previous = os.environ.get("PROMPT_LAB_EXPERIMENTS_ROOT")
        os.environ["PROMPT_LAB_EXPERIMENTS_ROOT"] = str(experiments)
        try:
            config = PromptLabConfig.from_env(project_root=root)
        finally:
            if previous is None:
                os.environ.pop("PROMPT_LAB_EXPERIMENTS_ROOT", None)
            else:
                os.environ["PROMPT_LAB_EXPERIMENTS_ROOT"] = previous

        assert config.experiments_root == experiments
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
PYTHONPATH=backend python backend/tests/test_config.py
```

Expected: fails because `prompt_lab.config` does not exist.

- [ ] **Step 3: Implement config and errors**

Create `backend/prompt_lab/__init__.py`:

```python
"""Prompt Lab backend package."""
```

Create `backend/prompt_lab/errors.py`:

```python
from __future__ import annotations


class PromptLabError(Exception):
    """Base class for Prompt Lab domain errors."""


class NotFoundError(PromptLabError):
    """Raised when an experiment artifact does not exist."""


class InvalidArtifactError(PromptLabError):
    """Raised when a stored artifact has invalid shape or content."""
```

Create `backend/prompt_lab/config.py`:

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PromptLabConfig:
    """Runtime paths for a local Prompt Lab backend."""

    project_root: Path
    experiments_root: Path
    examples_root: Path

    @classmethod
    def from_env(cls, *, project_root: Path | None = None) -> "PromptLabConfig":
        root = (project_root or Path.cwd()).resolve()
        experiments_override = os.getenv("PROMPT_LAB_EXPERIMENTS_ROOT")
        examples_override = os.getenv("PROMPT_LAB_EXAMPLES_ROOT")
        return cls(
            project_root=root,
            experiments_root=Path(experiments_override).resolve() if experiments_override else root / "experiments",
            examples_root=Path(examples_override).resolve() if examples_override else root / "examples",
        )
```

- [ ] **Step 4: Add test runner guard**

Append to `backend/tests/test_config.py`:

```python
def main() -> int:
    tests = [
        test_default_config_uses_repo_local_paths,
        test_config_accepts_experiments_root_override,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run test and verify it passes**

Run:

```bash
PYTHONPATH=backend python backend/tests/test_config.py
```

Expected: both tests print `OK`.

- [ ] **Step 6: Update docs**

Add to `backend/README.md`:

```markdown
## Runtime Paths

Prompt Lab defaults to repository-local `experiments/` and `examples/`.

Environment overrides:

- `PROMPT_LAB_EXPERIMENTS_ROOT`
- `PROMPT_LAB_EXAMPLES_ROOT`
```

- [ ] **Step 7: Commit**

```bash
git add backend/prompt_lab backend/tests/test_config.py backend/README.md pyrightconfig.json
git commit -m "chore: bootstrap prompt lab backend package"
```

---

### Task 2: Artifact Pydantic Models

**Files:**
- Create: `backend/prompt_lab/models/__init__.py`
- Create: `backend/prompt_lab/models/artifacts.py`
- Test: `backend/tests/test_artifacts.py`

- [ ] **Step 1: Write artifact tests**

Create `backend/tests/test_artifacts.py`:

```python
from __future__ import annotations

from prompt_lab.models.artifacts import (
    CaseArtifact,
    ExperimentArtifact,
    OutputConfig,
    RunDefaults,
)


def test_pydantic_experiment_artifact_validates() -> None:
    artifact = ExperimentArtifact.model_validate(
        {
            "schema_version": "prompt_lab.experiment/v1",
            "id": "split-scenes",
            "title": "Split scenes",
            "description": "Split scenes.",
            "active_version": "v001",
            "output": {
                "type": "pydantic",
                "model_file": "model.py",
                "model_entrypoint": "model.SceneList",
            },
            "template": {"engine": "jinja2", "path": "prompt.md"},
            "models": {
                "generator_model": "local/example-small-model",
                "judge_model": "openai/example-large-model",
            },
            "run_defaults": {
                "repeat_count": 3,
                "llm_cache": "disabled",
                "case_order": "case-major",
            },
        }
    )

    assert artifact.id == "split-scenes"
    assert artifact.output.type == "pydantic"
    assert artifact.run_defaults.repeat_count == 3


def test_text_experiment_artifact_validates() -> None:
    output = OutputConfig.model_validate({"type": "text"})
    defaults = RunDefaults()

    assert output.type == "text"
    assert defaults.repeat_count == 3
    assert defaults.llm_cache == "disabled"
    assert defaults.case_order == "case-major"


def test_case_artifact_validates_stores_and_bindings() -> None:
    case = CaseArtifact.model_validate(
        {
            "schema_version": "prompt_lab.case/v2",
            "id": "case-a",
            "title": "Case A",
            "stores": {
                "case": {
                    "kind": "flat_file_tree",
                    "values": {
                        "chapter_text": {
                            "__carmilla_flat_file_node__": "file",
                            "value": "Hello",
                        }
                    },
                }
            },
            "bindings": {
                "chapter_text": {
                    "kind": "store_scope",
                    "store": "case",
                    "path": "chapter_text",
                }
            },
        }
    )

    assert case.bindings["chapter_text"].path == "chapter_text"
```

- [ ] **Step 2: Run test and verify it fails**

```bash
PYTHONPATH=backend python backend/tests/test_artifacts.py
```

Expected: import failure.

- [ ] **Step 3: Implement artifact models**

Create `backend/prompt_lab/models/__init__.py`:

```python
"""Prompt Lab Pydantic contracts."""
```

Create `backend/prompt_lab/models/artifacts.py`:

```python
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


JsonObject = dict[str, Any]


class TemplateConfig(BaseModel):
    """Prompt template configuration for an experiment version."""

    model_config = ConfigDict(extra="forbid")

    engine: Literal["jinja2"] = "jinja2"
    path: str = "prompt.md"


class OutputConfig(BaseModel):
    """Output mode for an experiment."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["text", "pydantic"]
    model_file: str | None = None
    model_entrypoint: str | None = None


class ModelConfig(BaseModel):
    """Generator and judge model references."""

    model_config = ConfigDict(extra="forbid")

    generator_model: str
    judge_model: str


class RunDefaults(BaseModel):
    """Default repeated-run behavior."""

    model_config = ConfigDict(extra="forbid")

    repeat_count: int = Field(default=3, ge=1)
    llm_cache: Literal["disabled"] = "disabled"
    case_order: Literal["case-major"] = "case-major"


class ExperimentArtifact(BaseModel):
    """Experiment manifest stored as `experiment.json`."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["prompt_lab.experiment/v1"]
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = ""
    active_version: str = Field(min_length=1)
    output: OutputConfig
    template: TemplateConfig
    models: ModelConfig
    run_defaults: RunDefaults = Field(default_factory=RunDefaults)


class CaseSource(BaseModel):
    """Optional source metadata for imported cases."""

    model_config = ConfigDict(extra="allow")

    type: str | None = None


class FlatFileTreeStore(BaseModel):
    """A neutral serialized flat-file tree store produced by an external system."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["flat_file_tree"]
    values: JsonObject


class StoreScopeBinding(BaseModel):
    """Bind a prompt variable to a scope inside a named store."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["store_scope"]
    store: str = Field(min_length=1)
    path: str = ""


class ValueBinding(BaseModel):
    """Bind a prompt variable directly to a JSON-like value."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["value"]
    value: Any


PromptBinding = StoreScopeBinding | ValueBinding


class CaseArtifact(BaseModel):
    """One prompt input case."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["prompt_lab.case/v2"]
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source: CaseSource | None = None
    stores: dict[str, FlatFileTreeStore]
    bindings: dict[str, PromptBinding]


class RunBatchArtifact(BaseModel):
    """Metadata for a batch of repeated runs."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["prompt_lab.run_batch/v1"]
    run_batch_id: str
    version: str
    status: Literal["running", "completed", "failed", "cancelled", "interrupted"]
    repeat_count: int = Field(ge=1)
    case_order: Literal["case-major"]
    llm_cache: Literal["disabled"]
    started_at: str
    finished_at: str | None = None
    total_runs: int
    completed_runs: int


class RunArtifact(BaseModel):
    """One generator output for one case/repeat."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["prompt_lab.run/v1"]
    run_id: str
    run_batch_id: str
    version: str
    case_id: str
    repeat_index: int = Field(ge=1)
    generator_model: str
    status: Literal["ok", "validation_error", "execution_error"]
    rendered_prompt: str
    raw_output: str | None = None
    output_type: Literal["text", "pydantic"]
    output_json: Any = None
    output_text: str | None = None
    validation_error: str | None = None
    execution_error: str | None = None
    usage: JsonObject = Field(default_factory=dict)
```

- [ ] **Step 4: Add test runner guard**

Append:

```python
def main() -> int:
    tests = [
        test_pydantic_experiment_artifact_validates,
        test_text_experiment_artifact_validates,
        test_case_artifact_validates_variables,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run test and verify it passes**

```bash
PYTHONPATH=backend python backend/tests/test_artifacts.py
```

- [ ] **Step 6: Commit**

```bash
git add backend/prompt_lab/models backend/tests/test_artifacts.py
git commit -m "feat: define prompt lab artifact contracts"
```

---

### Task 3: Filesystem Storage

**Files:**
- Create: `backend/prompt_lab/storage.py`
- Test: `backend/tests/test_storage.py`

- [ ] **Step 1: Write storage tests**

Create `backend/tests/test_storage.py`:

```python
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from prompt_lab.storage import PromptLabStore


def test_store_lists_example_experiments() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        example = root / "examples" / "demo"
        version = example / "versions" / "v001"
        version.mkdir(parents=True)
        (example / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )

        store = PromptLabStore(experiments_root=root / "experiments", examples_root=root / "examples")

        assert [item.id for item in store.list_experiments()] == ["demo"]


def test_store_loads_cases_for_version() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "experiments" / "demo"
        cases = experiment / "cases"
        cases.mkdir(parents=True)
        (experiment / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )
        (cases / "case-a.json").write_text(
            '{"schema_version":"prompt_lab.case/v2","id":"case-a","title":"Case A","stores":{"case":{"kind":"flat_file_tree","values":{"text":{"__carmilla_flat_file_node__":"file","value":"hello"}}}},"bindings":{"text":{"kind":"store_scope","store":"case","path":"text"}}}',
            encoding="utf-8",
        )

        store = PromptLabStore(experiments_root=root / "experiments", examples_root=root / "examples")

        loaded = store.load_cases("demo")
        assert len(loaded) == 1
        assert loaded[0].id == "case-a"
```

- [ ] **Step 2: Run test and verify it fails**

```bash
PYTHONPATH=backend python backend/tests/test_storage.py
```

- [ ] **Step 3: Implement storage**

Create `backend/prompt_lab/storage.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from prompt_lab.errors import NotFoundError
from prompt_lab.models.artifacts import CaseArtifact, ExperimentArtifact


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class PromptLabStore:
    """Filesystem-backed Prompt Lab artifact store."""

    def __init__(self, *, experiments_root: Path, examples_root: Path) -> None:
        self.experiments_root = experiments_root
        self.examples_root = examples_root

    def list_experiments(self) -> list[ExperimentArtifact]:
        """Return experiments from `experiments/` and `examples/`, sorted by id."""
        manifests: dict[str, ExperimentArtifact] = {}
        for root in [self.examples_root, self.experiments_root]:
            if not root.exists():
                continue
            for manifest_path in sorted(root.glob("*/experiment.json")):
                artifact = ExperimentArtifact.model_validate(_read_json(manifest_path))
                manifests[artifact.id] = artifact
        return [manifests[key] for key in sorted(manifests)]

    def experiment_dir(self, experiment_id: str) -> Path:
        """Resolve an experiment directory, preferring editable experiments over examples."""
        for root in [self.experiments_root, self.examples_root]:
            candidate = root / experiment_id
            if (candidate / "experiment.json").is_file():
                return candidate
        raise NotFoundError(f"Experiment not found: {experiment_id}")

    def load_experiment(self, experiment_id: str) -> ExperimentArtifact:
        path = self.experiment_dir(experiment_id) / "experiment.json"
        return ExperimentArtifact.model_validate(_read_json(path))

    def version_dir(self, experiment_id: str, version: str) -> Path:
        path = self.experiment_dir(experiment_id) / "versions" / version
        if not path.is_dir():
            raise NotFoundError(f"Version not found: {experiment_id}/{version}")
        return path

    def read_text(self, experiment_id: str, version: str, relative_path: str) -> str:
        path = self.version_dir(experiment_id, version) / relative_path
        if not path.is_file():
            raise NotFoundError(f"File not found: {path}")
        return path.read_text(encoding="utf-8")

    def load_cases(self, experiment_id: str) -> list[CaseArtifact]:
        cases_dir = self.experiment_dir(experiment_id) / "cases"
        if not cases_dir.is_dir():
            return []
        return [
            CaseArtifact.model_validate(_read_json(path))
            for path in sorted(cases_dir.glob("*.json"))
        ]

    def write_run_artifact(self, experiment_id: str, version: str, relative_path: str, value: dict[str, Any]) -> Path:
        path = self.version_dir(experiment_id, version) / relative_path
        _write_json(path, value)
        return path
```

- [ ] **Step 4: Add test runner guard**

Append:

```python
def main() -> int:
    tests = [
        test_store_lists_example_experiments,
        test_store_loads_cases_for_version,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run test and verify it passes**

```bash
PYTHONPATH=backend python backend/tests/test_storage.py
```

- [ ] **Step 6: Commit**

```bash
git add backend/prompt_lab/storage.py backend/tests/test_storage.py
git commit -m "feat: add filesystem experiment store"
```

---

### Task 4: Prompt Rendering

**Files:**
- Create: `backend/prompt_lab/template_renderer.py`
- Test: `backend/tests/test_template_renderer.py`

- [ ] **Step 1: Write renderer tests**

Create `backend/tests/test_template_renderer.py`:

```python
from __future__ import annotations

from prompt_lab.models.artifacts import CaseArtifact
from prompt_lab.template_renderer import render_prompt


def test_render_prompt_uses_case_variables() -> None:
    case = CaseArtifact.model_validate(
        {
            "schema_version": "prompt_lab.case/v2",
            "id": "case-a",
            "title": "Case A",
            "stores": {"case": {"kind": "flat_file_tree", "values": {}}},
            "bindings": {"name": {"kind": "value", "value": "Ada"}},
        }
    )

    assert render_prompt("Hello {{ name }}.", case) == "Hello Ada."


def test_render_prompt_supports_lists() -> None:
    case = CaseArtifact.model_validate(
        {
            "schema_version": "prompt_lab.case/v2",
            "id": "case-a",
            "title": "Case A",
            "stores": {"case": {"kind": "flat_file_tree", "values": {}}},
            "bindings": {"items": {"kind": "value", "value": ["a", "b"]}},
        }
    )

    rendered = render_prompt("{% for item in items %}{{ item }}{% endfor %}", case)
    assert rendered == "ab"
```

- [ ] **Step 2: Run test and verify it fails**

```bash
PYTHONPATH=backend python backend/tests/test_template_renderer.py
```

- [ ] **Step 3: Implement renderer**

Create `backend/prompt_lab/template_renderer.py`:

```python
from __future__ import annotations

from typing import Any

from shared.jinjax import Template


def render_prompt(template_text: str, context: dict[str, Any]) -> str:
    """Render a prompt template with a materialized case context."""
    return Template(template_text).render(context)
```

- [ ] **Step 4: Add runner guard and pass**

Append:

```python
def main() -> int:
    tests = [
        test_render_prompt_uses_case_variables,
        test_render_prompt_supports_lists,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Run:

```bash
PYTHONPATH=backend python backend/tests/test_template_renderer.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/prompt_lab/template_renderer.py backend/tests/test_template_renderer.py
git commit -m "feat: render prompt templates from case context"
```

---

### Task 5: Pydantic Model Loader

**Files:**
- Create: `backend/prompt_lab/pydantic_loader.py`
- Test: `backend/tests/test_pydantic_loader.py`

- [ ] **Step 1: Write loader tests**

Create `backend/tests/test_pydantic_loader.py`:

```python
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import BaseModel

from prompt_lab.pydantic_loader import load_model_entrypoint


def test_load_model_entrypoint_loads_class() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        model_path = root / "model.py"
        model_path.write_text(
            "from pydantic import BaseModel\n\nclass Demo(BaseModel):\n    name: str\n",
            encoding="utf-8",
        )

        model = load_model_entrypoint(root, "model.py", "model.Demo")

        assert issubclass(model, BaseModel)
        assert model.model_validate({"name": "Ada"}).name == "Ada"
```

- [ ] **Step 2: Run test and verify it fails**

```bash
PYTHONPATH=backend python backend/tests/test_pydantic_loader.py
```

- [ ] **Step 3: Implement loader**

Create `backend/prompt_lab/pydantic_loader.py`:

```python
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import cast

from pydantic import BaseModel


def _load_module(path: Path) -> ModuleType:
    module_name = f"prompt_lab_dynamic_model_{abs(hash(path))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load model module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_model_entrypoint(version_dir: Path, model_file: str, model_entrypoint: str) -> type[BaseModel]:
    """Load a Pydantic model class from a version-local Python file."""
    module_name, _, class_name = model_entrypoint.partition(".")
    if module_name != Path(model_file).stem or not class_name:
        raise ValueError("model_entrypoint must look like '<model_file_stem>.<ClassName>'.")
    module = _load_module(version_dir / model_file)
    value = getattr(module, class_name)
    if not isinstance(value, type) or not issubclass(value, BaseModel):
        raise TypeError(f"Entrypoint is not a Pydantic BaseModel subclass: {model_entrypoint}")
    return cast(type[BaseModel], value)
```

- [ ] **Step 4: Add runner guard and pass**

Append:

```python
def main() -> int:
    tests = [test_load_model_entrypoint_loads_class]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Run:

```bash
PYTHONPATH=backend python backend/tests/test_pydantic_loader.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/prompt_lab/pydantic_loader.py backend/tests/test_pydantic_loader.py
git commit -m "feat: load version-local pydantic models"
```

---

### Task 6: LLM Client Wrapper

**Files:**
- Create: `backend/prompt_lab/llm_client.py`
- Test: `backend/tests/test_llm_client.py`

- [ ] **Step 1: Write wrapper tests with monkeypatchable functions**

Create `backend/tests/test_llm_client.py`:

```python
from __future__ import annotations

from pydantic import BaseModel

from prompt_lab import llm_client


class DemoModel(BaseModel):
    name: str


def test_text_wrapper_disables_cache(monkeypatch: object | None = None) -> None:
    calls: list[dict[str, object]] = []

    def fake_chat_get_text(chat: object, prompt: str, preset: dict[str, object], *, cache_enabled: bool, stream_callback: object | None = None) -> object:
        calls.append({"prompt": prompt, "preset": preset, "cache_enabled": cache_enabled})

        class Result:
            output = "hello"
            usage = {"total_tokens": 3}
            response = None

        return Result()

    original = llm_client.chat_get_text
    llm_client.chat_get_text = fake_chat_get_text  # type: ignore[assignment]
    try:
        result = llm_client.generate_text("local/model", "Prompt")
    finally:
        llm_client.chat_get_text = original

    assert result.output == "hello"
    assert calls[0]["cache_enabled"] is False


def test_structured_wrapper_disables_cache() -> None:
    calls: list[dict[str, object]] = []

    def fake_structured(chat: object, prompt: str, *, preset: dict[str, object], response_model: type[BaseModel], validation_context: object | None, cache_enabled: bool, stream_callback: object | None = None) -> object:
        calls.append({"prompt": prompt, "cache_enabled": cache_enabled, "validation_context": validation_context})

        class Result:
            output = DemoModel(name="Ada")
            usage = {"total_tokens": 4}
            response = None

        return Result()

    original = llm_client.chat_get_structured_lite
    llm_client.chat_get_structured_lite = fake_structured  # type: ignore[assignment]
    try:
        result = llm_client.generate_structured("local/model", "Prompt", DemoModel, {"x": 1})
    finally:
        llm_client.chat_get_structured_lite = original

    assert result.output.model_dump() == {"name": "Ada"}
    assert calls[0]["cache_enabled"] is False
```

- [ ] **Step 2: Run test and verify it fails**

```bash
PYTHONPATH=backend python backend/tests/test_llm_client.py
```

- [ ] **Step 3: Implement wrapper**

Create `backend/prompt_lab/llm_client.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from shared.llm.chat import Chat
from shared.llm.chat_get_structured_lite import chat_get_structured_lite
from shared.llm.chat_get_text import chat_get_text


@dataclass(frozen=True)
class GeneratedText:
    output: str
    usage: dict[str, Any]
    raw_response: Any


@dataclass(frozen=True)
class GeneratedStructured:
    output: BaseModel
    usage: dict[str, Any]
    raw_response: Any


def generate_text(model: str, prompt: str) -> GeneratedText:
    """Generate text with Prompt Lab cache policy."""
    result = chat_get_text(
        Chat(),
        prompt,
        {"model": model},
        cache_enabled=False,
    )
    return GeneratedText(output=result.output, usage=result.usage or {}, raw_response=result.response)


def generate_structured(
    model: str,
    prompt: str,
    response_model: type[BaseModel],
    validation_context: dict[str, Any] | None,
) -> GeneratedStructured:
    """Generate structured output with Prompt Lab cache policy."""
    result = chat_get_structured_lite(
        Chat(),
        prompt,
        preset={"model": model},
        response_model=response_model,
        validation_context=validation_context,
        cache_enabled=False,
    )
    return GeneratedStructured(output=result.output, usage=result.usage or {}, raw_response=result.response)
```

- [ ] **Step 4: Add runner guard and pass**

Append:

```python
def main() -> int:
    tests = [
        test_text_wrapper_disables_cache,
        test_structured_wrapper_disables_cache,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Run:

```bash
PYTHONPATH=backend python backend/tests/test_llm_client.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/prompt_lab/llm_client.py backend/tests/test_llm_client.py
git commit -m "feat: wrap llm generation for prompt lab"
```

---

### Task 7: Generator Runner

**Files:**
- Create: `backend/prompt_lab/runner.py`
- Test: `backend/tests/test_runner.py`

- [ ] **Step 1: Write runner tests**

Create `backend/tests/test_runner.py`:

```python
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from prompt_lab.runner import iter_case_major, run_text_case
from prompt_lab.models.artifacts import CaseArtifact


def test_iter_case_major_groups_repeats_per_case() -> None:
    cases = [
        CaseArtifact.model_validate({"schema_version": "prompt_lab.case/v2", "id": "a", "title": "A", "stores": {"case": {"kind": "flat_file_tree", "values": {}}}, "bindings": {}}),
        CaseArtifact.model_validate({"schema_version": "prompt_lab.case/v2", "id": "b", "title": "B", "stores": {"case": {"kind": "flat_file_tree", "values": {}}}, "bindings": {}}),
    ]

    pairs = [(case.id, repeat) for case, repeat in iter_case_major(cases, repeat_count=3)]

    assert pairs == [("a", 1), ("a", 2), ("a", 3), ("b", 1), ("b", 2), ("b", 3)]


def test_run_text_case_saves_text_output() -> None:
    case = CaseArtifact.model_validate(
        {"schema_version": "prompt_lab.case/v2", "id": "a", "title": "A", "stores": {"case": {"kind": "flat_file_tree", "values": {}}}, "bindings": {"name": {"kind": "value", "value": "Ada"}}}
    )

    def generate(model: str, prompt: str) -> object:
        class Result:
            output = f"out:{prompt}"
            usage = {"total_tokens": 2}

        return Result()

    run = run_text_case(
        version="v001",
        run_batch_id="batch-1",
        case=case,
        repeat_index=1,
        generator_model="local/model",
        template_text="Hello {{ name }}",
        generate_text=generate,
    )

    assert run.status == "ok"
    assert run.output_text == "out:Hello Ada"
    assert run.rendered_prompt == "Hello Ada"
```

- [ ] **Step 2: Run test and verify it fails**

```bash
PYTHONPATH=backend python backend/tests/test_runner.py
```

- [ ] **Step 3: Implement text runner**

Create `backend/prompt_lab/runner.py`:

```python
from __future__ import annotations

import traceback
from collections.abc import Callable, Iterable, Iterator
from typing import Any

from prompt_lab.models.artifacts import CaseArtifact, RunArtifact
from prompt_lab.template_renderer import render_prompt


def iter_case_major(cases: Iterable[CaseArtifact], *, repeat_count: int) -> Iterator[tuple[CaseArtifact, int]]:
    """Yield case/repeat pairs as A-A-A-B-B-B."""
    for case in cases:
        for repeat_index in range(1, repeat_count + 1):
            yield case, repeat_index


def run_text_case(
    *,
    version: str,
    run_batch_id: str,
    case: CaseArtifact,
    repeat_index: int,
    generator_model: str,
    template_text: str,
    generate_text: Callable[[str, str], Any],
) -> RunArtifact:
    rendered_prompt = render_prompt(template_text, case)
    run_id = f"{run_batch_id}-{case.id}-repeat-{repeat_index:03d}"
    try:
        result = generate_text(generator_model, rendered_prompt)
    except Exception:
        return RunArtifact(
            schema_version="prompt_lab.run/v1",
            run_id=run_id,
            run_batch_id=run_batch_id,
            version=version,
            case_id=case.id,
            repeat_index=repeat_index,
            generator_model=generator_model,
            status="execution_error",
            rendered_prompt=rendered_prompt,
            output_type="text",
            execution_error=traceback.format_exc(),
        )
    return RunArtifact(
        schema_version="prompt_lab.run/v1",
        run_id=run_id,
        run_batch_id=run_batch_id,
        version=version,
        case_id=case.id,
        repeat_index=repeat_index,
        generator_model=generator_model,
        status="ok",
        rendered_prompt=rendered_prompt,
        raw_output=getattr(result, "output", None),
        output_type="text",
        output_text=getattr(result, "output", None),
        usage=getattr(result, "usage", {}) or {},
    )
```

- [ ] **Step 4: Add runner guard and pass**

Append:

```python
def main() -> int:
    tests = [
        test_iter_case_major_groups_repeats_per_case,
        test_run_text_case_saves_text_output,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Run:

```bash
PYTHONPATH=backend python backend/tests/test_runner.py
```

- [ ] **Step 5: Add structured runner in a second test**

Extend `backend/tests/test_runner.py`:

```python
from pydantic import BaseModel
from prompt_lab.runner import run_structured_case


class DemoOutput(BaseModel):
    name: str


def test_run_structured_case_saves_json_output() -> None:
    case = CaseArtifact.model_validate(
        {
            "schema_version": "prompt_lab.case/v2",
            "id": "a",
            "title": "A",
            "stores": {"case": {"kind": "flat_file_tree", "values": {}}},
            "bindings": {
                "name": {"kind": "value", "value": "Ada"},
                "allowed": {"kind": "value", "value": ["Ada"]},
            },
        }
    )

    def generate(model: str, prompt: str, response_model: type[BaseModel], validation_context: dict[str, object] | None) -> object:
        class Result:
            output = DemoOutput(name="Ada")
            usage = {"total_tokens": 5}

        return Result()

    run = run_structured_case(
        version="v001",
        run_batch_id="batch-1",
        case=case,
        repeat_index=1,
        generator_model="local/model",
        template_text="Hello {{ name }}",
        response_model=DemoOutput,
        generate_structured=generate,
    )

    assert run.status == "ok"
    assert run.output_json == {"name": "Ada"}
    assert run.output_type == "pydantic"
```

Add it to `main()` and run. Expected: fails because `run_structured_case` does not exist.

- [ ] **Step 6: Implement structured runner**

Append to `backend/prompt_lab/runner.py`:

```python
from pydantic import BaseModel


def run_structured_case(
    *,
    version: str,
    run_batch_id: str,
    case: CaseArtifact,
    repeat_index: int,
    generator_model: str,
    template_text: str,
    response_model: type[BaseModel],
    generate_structured: Callable[[str, str, type[BaseModel], dict[str, Any] | None], Any],
) -> RunArtifact:
    context = materialize_case_context(case)
    rendered_prompt = render_prompt(template_text, context)
    run_id = f"{run_batch_id}-{case.id}-repeat-{repeat_index:03d}"
    try:
        result = generate_structured(
            generator_model,
            rendered_prompt,
            response_model,
            context,
        )
        output = getattr(result, "output")
    except Exception:
        return RunArtifact(
            schema_version="prompt_lab.run/v1",
            run_id=run_id,
            run_batch_id=run_batch_id,
            version=version,
            case_id=case.id,
            repeat_index=repeat_index,
            generator_model=generator_model,
            status="validation_error",
            rendered_prompt=rendered_prompt,
            output_type="pydantic",
            validation_error=traceback.format_exc(),
        )
    return RunArtifact(
        schema_version="prompt_lab.run/v1",
        run_id=run_id,
        run_batch_id=run_batch_id,
        version=version,
        case_id=case.id,
        repeat_index=repeat_index,
        generator_model=generator_model,
        status="ok",
        rendered_prompt=rendered_prompt,
        raw_output=output.model_dump_json(),
        output_type="pydantic",
        output_json=output.model_dump(mode="json"),
        usage=getattr(result, "usage", {}) or {},
    )
```

- [ ] **Step 7: Run tests**

```bash
PYTHONPATH=backend python backend/tests/test_runner.py
```

- [ ] **Step 8: Commit**

```bash
git add backend/prompt_lab/runner.py backend/tests/test_runner.py
git commit -m "feat: run text and structured prompt cases"
```

---

### Task 8: In-Process Jobs And SSE Events

**Files:**
- Create: `backend/prompt_lab/jobs.py`
- Test: `backend/tests/test_jobs.py`

- [ ] **Step 1: Write job manager tests**

Create `backend/tests/test_jobs.py`:

```python
from __future__ import annotations

from prompt_lab.jobs import JobManager


def test_job_manager_records_progress_events() -> None:
    jobs = JobManager()
    job = jobs.start_job(kind="run_version", experiment_id="demo", version="v001", total_units=2)

    jobs.update(job.job_id, completed_units=1, message="case a repeat 1")
    loaded = jobs.get(job.job_id)
    events = jobs.events(job.job_id)

    assert loaded.completed_units == 1
    assert events[-1].message == "case a repeat 1"


def test_job_manager_completes_job() -> None:
    jobs = JobManager()
    job = jobs.start_job(kind="judge", experiment_id="demo", version="v001", total_units=1)

    jobs.complete(job.job_id, message="done")

    assert jobs.get(job.job_id).status == "completed"
```

- [ ] **Step 2: Run test and verify it fails**

```bash
PYTHONPATH=backend python backend/tests/test_jobs.py
```

- [ ] **Step 3: Implement jobs**

Create `backend/prompt_lab/jobs.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from itertools import count
from threading import Lock


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_COUNTER = count(1)


@dataclass(frozen=True)
class JobEvent:
    event_id: int
    job_id: str
    status: str
    message: str
    completed_units: int
    total_units: int
    created_at: str


@dataclass(frozen=True)
class JobStatus:
    job_id: str
    kind: str
    experiment_id: str
    version: str
    status: str
    total_units: int
    completed_units: int = 0
    message: str = ""
    started_at: str = field(default_factory=_now)
    finished_at: str | None = None


class JobManager:
    """In-memory job status and event store for local Prompt Lab."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._jobs: dict[str, JobStatus] = {}
        self._events: dict[str, list[JobEvent]] = {}

    def start_job(self, *, kind: str, experiment_id: str, version: str, total_units: int) -> JobStatus:
        with self._lock:
            job_id = f"{kind}-{next(_COUNTER):06d}"
            job = JobStatus(
                job_id=job_id,
                kind=kind,
                experiment_id=experiment_id,
                version=version,
                status="running",
                total_units=total_units,
            )
            self._jobs[job_id] = job
            self._events[job_id] = []
            self._append_event(job, "started")
            return job

    def get(self, job_id: str) -> JobStatus:
        return self._jobs[job_id]

    def events(self, job_id: str) -> list[JobEvent]:
        return list(self._events[job_id])

    def update(self, job_id: str, *, completed_units: int, message: str) -> JobStatus:
        with self._lock:
            job = replace(self._jobs[job_id], completed_units=completed_units, message=message)
            self._jobs[job_id] = job
            self._append_event(job, message)
            return job

    def complete(self, job_id: str, *, message: str) -> JobStatus:
        with self._lock:
            old = self._jobs[job_id]
            job = replace(
                old,
                status="completed",
                completed_units=old.total_units,
                message=message,
                finished_at=_now(),
            )
            self._jobs[job_id] = job
            self._append_event(job, message)
            return job

    def fail(self, job_id: str, *, message: str) -> JobStatus:
        with self._lock:
            old = self._jobs[job_id]
            job = replace(old, status="failed", message=message, finished_at=_now())
            self._jobs[job_id] = job
            self._append_event(job, message)
            return job

    def _append_event(self, job: JobStatus, message: str) -> None:
        events = self._events[job.job_id]
        events.append(
            JobEvent(
                event_id=len(events) + 1,
                job_id=job.job_id,
                status=job.status,
                message=message,
                completed_units=job.completed_units,
                total_units=job.total_units,
                created_at=_now(),
            )
        )
```

- [ ] **Step 4: Add runner guard and pass**

Append:

```python
def main() -> int:
    tests = [
        test_job_manager_records_progress_events,
        test_job_manager_completes_job,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Run:

```bash
PYTHONPATH=backend python backend/tests/test_jobs.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/prompt_lab/jobs.py backend/tests/test_jobs.py
git commit -m "feat: track in-process job progress"
```

---

### Task 9: Backend API Skeleton

**Files:**
- Create: `backend/prompt_lab/api.py`
- Create: `backend/prompt_lab/app.py`
- Test: `backend/tests/test_api.py`
- Modify: `backend/requirements-dev.txt`

- [ ] **Step 1: Add test client dependency**

Add to `backend/requirements-dev.txt`:

```text
httpx
```

- [ ] **Step 2: Write API tests**

Create `backend/tests/test_api.py`:

```python
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from prompt_lab.api import create_app
from prompt_lab.config import PromptLabConfig


def test_api_lists_experiments() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        example = root / "examples" / "demo"
        (example / "versions" / "v001").mkdir(parents=True)
        (example / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )
        app = create_app(PromptLabConfig.from_env(project_root=root))
        client = TestClient(app)

        response = client.get("/api/experiments")

        assert response.status_code == 200
        assert response.json()[0]["id"] == "demo"
```

- [ ] **Step 3: Run test and verify it fails**

```bash
PYTHONPATH=backend python backend/tests/test_api.py
```

- [ ] **Step 4: Implement API skeleton**

Create `backend/prompt_lab/api.py`:

```python
from __future__ import annotations

from fastapi import FastAPI

from prompt_lab.config import PromptLabConfig
from prompt_lab.storage import PromptLabStore


def create_app(config: PromptLabConfig | None = None) -> FastAPI:
    """Create the Prompt Lab FastAPI app."""
    resolved_config = config or PromptLabConfig.from_env()
    store = PromptLabStore(
        experiments_root=resolved_config.experiments_root,
        examples_root=resolved_config.examples_root,
    )
    app = FastAPI(title="Prompt Lab")

    @app.get("/api/experiments")
    def list_experiments() -> list[dict[str, object]]:
        return [item.model_dump(mode="json") for item in store.list_experiments()]

    return app
```

Create `backend/prompt_lab/app.py`:

```python
from __future__ import annotations

from prompt_lab.api import create_app


app = create_app()
```

- [ ] **Step 5: Add runner guard and pass**

Append:

```python
def main() -> int:
    tests = [test_api_lists_experiments]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Run:

```bash
PYTHONPATH=backend python backend/tests/test_api.py
```

- [ ] **Step 6: Commit**

```bash
git add backend/prompt_lab/api.py backend/prompt_lab/app.py backend/tests/test_api.py backend/requirements-dev.txt
git commit -m "feat: add prompt lab api skeleton"
```

---

### Task 10: Run Version Endpoint

**Files:**
- Modify: `backend/prompt_lab/api.py`
- Modify: `backend/prompt_lab/storage.py`
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: Add API test for starting a run job**

Append to `backend/tests/test_api.py`:

```python
def test_api_starts_run_job() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = root / "examples" / "demo"
        version = experiment / "versions" / "v001"
        cases = experiment / "cases"
        cases.mkdir(parents=True)
        (experiment / "experiment.json").write_text(
            '{"schema_version":"prompt_lab.experiment/v1","id":"demo","title":"Demo","description":"","active_version":"v001","output":{"type":"text"},"template":{"engine":"jinja2","path":"prompt.md"},"models":{"generator_model":"local/a","judge_model":"openai/b"},"run_defaults":{"repeat_count":3,"llm_cache":"disabled","case_order":"case-major"}}',
            encoding="utf-8",
        )
        (version / "prompt.md").write_text("Hello {{ name }}", encoding="utf-8")
        (cases / "a.json").write_text(
            '{"schema_version":"prompt_lab.case/v2","id":"a","title":"A","stores":{"case":{"kind":"flat_file_tree","values":{}}},"bindings":{"name":{"kind":"value","value":"Ada"}}}',
            encoding="utf-8",
        )
        app = create_app(PromptLabConfig.from_env(project_root=root))
        client = TestClient(app)

        response = client.post("/api/experiments/demo/versions/v001/runs")

        assert response.status_code == 200
        payload = response.json()
        assert payload["kind"] == "run_version"
        assert payload["status"] in {"running", "completed"}
```

Add test to `main()` and run. Expected: 404.

- [ ] **Step 2: Implement synchronous MVP run endpoint with fakeable runner boundary**

In `backend/prompt_lab/api.py`, add a `JobManager` and endpoint. For MVP, run synchronously; later tasks can move execution to a background thread.

```python
from prompt_lab import llm_client
from prompt_lab.jobs import JobManager
from prompt_lab.runner import iter_case_major, run_text_case
```

Inside `create_app`:

```python
    jobs = JobManager()

    @app.post("/api/experiments/{experiment_id}/versions/{version}/runs")
    def run_version(experiment_id: str, version: str) -> dict[str, object]:
        experiment = store.load_experiment(experiment_id)
        cases = store.load_cases(experiment_id)
        job = jobs.start_job(
            kind="run_version",
            experiment_id=experiment_id,
            version=version,
            total_units=len(cases) * experiment.run_defaults.repeat_count,
        )
        template_text = store.read_text(experiment_id, version, experiment.template.path)
        completed = 0
        for case, repeat_index in iter_case_major(cases, repeat_count=experiment.run_defaults.repeat_count):
            completed += 1
            if experiment.output.type == "text":
                run = run_text_case(
                    version=version,
                    run_batch_id=job.job_id,
                    case=case,
                    repeat_index=repeat_index,
                    generator_model=experiment.models.generator_model,
                    template_text=template_text,
                    generate_text=llm_client.generate_text,
                )
            else:
                raise NotImplementedError("Pydantic run endpoint is implemented in a later task.")
            store.write_run_artifact(
                experiment_id,
                version,
                f"runs/{job.job_id}/{case.id}/repeat-{repeat_index:03d}.json",
                run.model_dump(mode="json"),
            )
            jobs.update(job.job_id, completed_units=completed, message=f"{case.id} repeat {repeat_index}")
        return jobs.complete(job.job_id, message="completed").__dict__
```

- [ ] **Step 3: Run API tests**

```bash
PYTHONPATH=backend python backend/tests/test_api.py
```

If this attempts a real LLM call, replace `llm_client.generate_text` in the test with a fake before creating the client:

```python
from prompt_lab import llm_client

original = llm_client.generate_text
llm_client.generate_text = lambda model, prompt: type("Result", (), {"output": "ok", "usage": {}})()
try:
    app = create_app(...)
finally:
    llm_client.generate_text = original
```

- [ ] **Step 4: Commit**

```bash
git add backend/prompt_lab/api.py backend/prompt_lab/storage.py backend/tests/test_api.py
git commit -m "feat: run text experiment versions from api"
```

---

### Task 11: Structured Run Endpoint

**Files:**
- Modify: `backend/prompt_lab/api.py`
- Modify: `backend/prompt_lab/runner.py`
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: Add API test for Pydantic example run**

Use `examples/split-scenes` as a fixture. The test should copy the example into a temp `examples/` root, monkeypatch `llm_client.generate_structured`, call `/runs`, and assert that a run artifact contains `output_json`.

Test code skeleton:

```python
def test_api_runs_pydantic_version() -> None:
    # copy examples/split-scenes to temp examples
    # monkeypatch llm_client.generate_structured to return a valid instance of loaded response model
    # POST /api/experiments/split-scenes/versions/v001/runs
    # assert status 200 and at least one run artifact exists
```

Make this test concrete during implementation using `shutil.copytree`.

- [ ] **Step 2: Run and verify failure**

Expected: endpoint raises `NotImplementedError`.

- [ ] **Step 3: Implement Pydantic branch**

In `api.py`, when `experiment.output.type == "pydantic"`:

1. Resolve `version_dir = store.version_dir(experiment_id, version)`.
2. Load model with `load_model_entrypoint`.
3. Call `run_structured_case`.
4. Save artifacts exactly like text runs.

- [ ] **Step 4: Run API tests**

```bash
PYTHONPATH=backend python backend/tests/test_api.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/prompt_lab/api.py backend/tests/test_api.py
git commit -m "feat: run pydantic experiment versions from api"
```

---

### Task 12: Judgment Models

**Files:**
- Create: `backend/prompt_lab/models/judgments.py`
- Test: `backend/tests/test_judge.py`

- [ ] **Step 1: Write judgment model tests**

Create `backend/tests/test_judge.py`:

```python
from __future__ import annotations

from prompt_lab.models.judgments import JudgmentArtifact, FindingDecisionSet


def test_judgment_artifact_validates() -> None:
    judgment = JudgmentArtifact.model_validate(
        {
            "schema_version": "prompt_lab.judgment/v1",
            "judgment_id": "j001",
            "version": "v001",
            "run_batch_ids": ["run-1"],
            "judge_model": "openai/large",
            "summary": "Good.",
            "what_looks_correct": [],
            "findings": [
                {
                    "finding_id": "f001",
                    "severity": "recommended",
                    "area": "prompt",
                    "category": "recurring_problem",
                    "description": "Too verbose.",
                    "evidence": ["case a"],
                    "suggested_change": "Ask for concise output.",
                }
            ],
            "decision_points": [],
        }
    )

    assert judgment.findings[0].finding_id == "f001"


def test_decisions_default_to_accepted() -> None:
    decisions = FindingDecisionSet.from_finding_ids(["f001", "f002"])

    assert decisions.finding_decisions["f001"].decision == "accepted"
    assert decisions.finding_decisions["f002"].decision == "accepted"
```

- [ ] **Step 2: Run and verify failure**

```bash
PYTHONPATH=backend python backend/tests/test_judge.py
```

- [ ] **Step 3: Implement judgment models**

Create `backend/prompt_lab/models/judgments.py` with models matching `DESIGN.md`: `EvidenceFinding`, `JudgmentFinding`, `DecisionPoint`, `JudgmentArtifact`, `FindingDecision`, `FindingDecisionSet`.

Ensure:

- severities are `recommended | optional | do_not_change_yet | regression_risk`;
- finding decisions are `accepted | rejected | deferred`;
- `FindingDecisionSet.from_finding_ids()` creates accepted defaults.

- [ ] **Step 4: Add runner guard and pass**

Run:

```bash
PYTHONPATH=backend python backend/tests/test_judge.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/prompt_lab/models/judgments.py backend/tests/test_judge.py
git commit -m "feat: define judgment and decision contracts"
```

---

### Task 13: Single-Version Judge

**Files:**
- Create: `backend/prompt_lab/judge.py`
- Modify: `backend/prompt_lab/api.py`
- Test: `backend/tests/test_judge.py`

- [ ] **Step 1: Add test for judge prompt input**

Add a test that builds a judge input from rubric, prompt, cases, and run artifacts, and asserts it includes validation errors and repeated outputs.

- [ ] **Step 2: Implement `build_judge_prompt`**

Create `backend/prompt_lab/judge.py` with:

```python
def build_judge_prompt(...args...) -> str:
    """Build the judge prompt from rubric, prompt, cases, and runs."""
```

The prompt must instruct the judge to:

- distinguish recurring problems from one-off deviations;
- cite case/repeat evidence;
- produce JSON matching `JudgmentArtifact`;
- avoid numeric scorecards as primary output.

- [ ] **Step 3: Add test for default decisions after judgment**

Assert that after creating a judgment, `decisions.json` defaults all findings to accepted.

- [ ] **Step 4: Implement `/judgments` endpoint**

Endpoint:

```text
POST /api/experiments/{experiment_id}/versions/{version}/judgments
```

It should:

1. Load latest or selected run batch.
2. Load rubric snapshot.
3. Build judge prompt.
4. Call `llm_client.generate_structured` with `JudgmentArtifact`.
5. Save:
   - `reviews/review-001/judgment.json`
   - `reviews/review-001/judgment.md`
   - `reviews/review-001/rubric_snapshot.md`
   - `reviews/review-001/decisions.json`

- [ ] **Step 5: Test with monkeypatched LLM**

Use fake `generate_structured` returning a `JudgmentArtifact`.

- [ ] **Step 6: Commit**

```bash
git add backend/prompt_lab/judge.py backend/prompt_lab/api.py backend/tests/test_judge.py
git commit -m "feat: judge experiment runs"
```

---

### Task 14: Review Decisions And Human Notes

**Files:**
- Modify: `backend/prompt_lab/api.py`
- Modify: `backend/prompt_lab/storage.py`
- Test: `backend/tests/test_reviews.py`

- [ ] **Step 1: Write tests**

Create tests for:

- updating one finding decision to `rejected`;
- saving `human_notes.md`;
- reading review state.

- [ ] **Step 2: Implement endpoints**

Add:

```text
PUT /api/experiments/{experiment_id}/versions/{version}/reviews/{review_id}/decisions
PUT /api/experiments/{experiment_id}/versions/{version}/reviews/{review_id}/human-notes
GET /api/experiments/{experiment_id}/versions/{version}/reviews/{review_id}
```

Rules:

- accepted findings feed proposals;
- rejected findings are constraints;
- deferred findings are ignored;
- human notes override judge findings.

- [ ] **Step 3: Run tests**

```bash
PYTHONPATH=backend python backend/tests/test_reviews.py
```

- [ ] **Step 4: Commit**

```bash
git add backend/prompt_lab/api.py backend/prompt_lab/storage.py backend/tests/test_reviews.py
git commit -m "feat: save review decisions and human notes"
```

---

### Task 15: Proposal Generation

**Files:**
- Create: `backend/prompt_lab/proposal.py`
- Modify: `backend/prompt_lab/api.py`
- Test: `backend/tests/test_proposal.py`

- [ ] **Step 1: Write proposal input test**

Test that proposal input includes:

- current prompt;
- current model if present;
- accepted findings;
- rejected findings as constraints;
- human notes;
- rubric snapshot.

- [ ] **Step 2: Implement proposal prompt builder**

Create `build_proposal_prompt`.

Rules inside prompt:

- human notes override all judge findings;
- accepted findings are requested changes;
- rejected findings are constraints;
- deferred findings are ignored;
- preserve task scope;
- change `model.py` only when contract changes are clearly needed.

- [ ] **Step 3: Add proposal endpoint**

```text
POST /api/experiments/{experiment_id}/versions/{version}/reviews/{review_id}/proposal
```

Save:

```text
reviews/<review_id>/proposal/prompt.md
reviews/<review_id>/proposal/model.py      # optional
reviews/<review_id>/proposal/rationale.md
reviews/<review_id>/proposal/source.json
```

- [ ] **Step 4: Add create-next-version endpoint**

```text
POST /api/experiments/{experiment_id}/versions/{version}/reviews/{review_id}/proposal/create-version
```

It creates `versions/vNNN` by copying current version and replacing prompt/model from proposal. It must not mutate old versions.

- [ ] **Step 5: Run tests**

```bash
PYTHONPATH=backend python backend/tests/test_proposal.py
```

- [ ] **Step 6: Commit**

```bash
git add backend/prompt_lab/proposal.py backend/prompt_lab/api.py backend/tests/test_proposal.py
git commit -m "feat: generate proposals and create next versions"
```

---

### Task 16: Comparison Judgment

**Files:**
- Create: `backend/prompt_lab/compare.py`
- Modify: `backend/prompt_lab/models/judgments.py`
- Modify: `backend/prompt_lab/api.py`
- Test: `backend/tests/test_compare.py`

- [ ] **Step 1: Add comparison artifact model**

Model should match `DESIGN.md`:

- improvements;
- regressions;
- unchanged_problems;
- new_problems;
- stability_changes;
- recommendation: `keep_new_version | revise_new_version | revert_to_baseline | inconclusive`;
- decision_points.

- [ ] **Step 2: Write comparison prompt test**

Assert comparison prompt includes baseline and candidate prompts, run summaries, rubric, and says not to require identical ids unless rubric requires it.

- [ ] **Step 3: Implement comparison endpoint**

```text
POST /api/experiments/{experiment_id}/comparisons
```

Request:

```json
{
  "baseline_version": "v001",
  "candidate_version": "v002"
}
```

Save under:

```text
versions/<candidate>/comparisons/comparison-001/
```

- [ ] **Step 4: Run tests**

```bash
PYTHONPATH=backend python backend/tests/test_compare.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/prompt_lab/compare.py backend/prompt_lab/models/judgments.py backend/prompt_lab/api.py backend/tests/test_compare.py
git commit -m "feat: compare prompt experiment versions"
```

---

### Task 17: Frontend Scaffold

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/api.ts`
- Create: `frontend/src/types.ts`
- Create: `frontend/src/styles.css`

- [ ] **Step 1: Initialize Vite React TypeScript app**

Use:

```bash
pnpm create vite frontend --template react-ts
```

If files already exist, merge without deleting backend files.

- [ ] **Step 2: Install dependencies**

Use minimal dependencies first:

```bash
cd frontend
pnpm install
```

- [ ] **Step 3: Implement API client**

`frontend/src/api.ts`:

```ts
export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: body === undefined ? undefined : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<T>;
}
```

- [ ] **Step 4: Implement basic App**

App loads `/api/experiments` and shows title/id/active version.

- [ ] **Step 5: Verify**

```bash
cd frontend
pnpm lint
pnpm build
```

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "feat: scaffold prompt lab frontend"
```

---

### Task 18: Frontend Prompt, Validators, And Runs

**Files:**
- Create: `frontend/src/components/ExperimentsList.tsx`
- Create: `frontend/src/components/PromptView.tsx`
- Create: `frontend/src/components/ValidatorsView.tsx`
- Create: `frontend/src/components/RunsView.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Define frontend types**

Include `Experiment`, `Case`, `RunArtifact`, and `JobStatus`.

- [ ] **Step 2: Build experiments list**

Show:

- title;
- output type;
- active version;
- generator model;
- judge model.

- [ ] **Step 3: Build overview**

Show:

- prompt text;
- rubric text;
- cases;
- `Run version` button.

- [ ] **Step 4: Build runs table**

Show:

- case;
- repeat;
- status;
- validation status;
- output preview.

- [ ] **Step 5: Verify**

```bash
cd frontend
pnpm lint
pnpm build
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "feat: show experiments and run results"
```

---

### Task 19: Frontend Review, Proposal, And Comparison Views

**Files:**
- Create: `frontend/src/components/ReviewView.tsx`
- Create: `frontend/src/components/ProposalView.tsx`
- Create: `frontend/src/components/ComparisonView.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Review view**

Show judgment sections, findings, evidence, and decision controls:

```text
Accepted | Rejected | Deferred
```

Rejected/deferred findings have an optional reason field.

- [ ] **Step 2: Human notes**

Add textarea saving to `human_notes.md`.

- [ ] **Step 3: Proposal view**

Show proposed prompt, optional proposed model, rationale, and `Create next version`.

- [ ] **Step 4: Comparison view**

Show baseline/candidate selectors and comparison report.

- [ ] **Step 5: Verify**

```bash
cd frontend
pnpm lint
pnpm build
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "feat: review judgments and proposals in ui"
```

---

### Task 20: End-To-End Local Smoke

**Files:**
- Modify: `README.md`
- Modify: `backend/README.md`
- Modify: `frontend/README.md`

- [ ] **Step 1: Start backend**

```bash
PYTHONPATH=backend uvicorn prompt_lab.app:app --reload
```

Expected: backend starts on `http://127.0.0.1:8000`.

- [ ] **Step 2: Start frontend**

```bash
cd frontend
pnpm dev
```

Expected: frontend starts on Vite dev URL.

- [ ] **Step 3: Manual smoke**

In browser:

1. Open Prompt Lab.
2. Confirm `split-scenes` and `summarize-chapter` examples are listed.
3. Open `summarize-chapter`.
4. Run version with a monkeypatched/mock LLM mode if real models are not configured.
5. Confirm progress shows current case/repeat.
6. Confirm run artifacts appear.
7. Judge with fake or live judge model.
8. Reject one finding, add human notes.
9. Generate proposal.
10. Create `v002`.
11. Compare `v002` with `v001`.

- [ ] **Step 4: Document setup**

Root `README.md` should include:

- install backend dependencies;
- copy config templates;
- run backend;
- run frontend;
- run local tests;
- run live smoke.

- [ ] **Step 5: Final verification**

```bash
PYTHONPATH=backend python backend/tests/test_chat.py
PYTHONPATH=backend python backend/tests/test_chat_get_structured_lite.py
PYTHONPATH=backend python backend/tests/test_structured_lite_units.py
PYTHONPATH=backend python backend/tests/test_format_validation_errors.py
pyright --project pyrightconfig.json --pythonpath .venv/bin/python
cd frontend && pnpm lint && pnpm build
```

- [ ] **Step 6: Commit**

```bash
git add README.md backend/README.md frontend/README.md
git commit -m "docs: document prompt lab mvp workflow"
```

---

## Implementation Notes

- Keep generator-run cache disabled. This is required for variance testing.
- Validation errors are useful outputs and must be visible in UI and judge input.
- Store raw output and rendered prompt for each run.
- Prompt Lab owns neutral experiments only; Carmilla integration is a separate exporter concern.
- Do not implement automatic rubric editing in MVP.
- Do not mutate a version that already has run artifacts; create a new version.
- Human notes override judge findings.
- Rejected judge findings must be passed to proposal generation as constraints.
- Comparison should evaluate semantic quality and stability, not literal equality.

## Coverage Checklist

- [ ] Backend loads examples and experiments from filesystem.
- [ ] Text prompt versions run with case-major repeats.
- [ ] Pydantic prompt versions run with case-major repeats.
- [ ] Generator cache is disabled.
- [ ] Run artifacts include rendered prompt, raw output, parsed output/text, validation errors, execution errors, and usage.
- [ ] Job progress exposes current case/repeat.
- [ ] Judge creates structured judgment and default accepted decisions.
- [ ] User can reject/defer findings and write human notes.
- [ ] Proposal creates prompt/model/rationale without mutating current version.
- [ ] User can create next version from proposal.
- [ ] Comparison detects improvements/regressions between versions.
- [ ] Frontend exposes the full MVP workflow.
