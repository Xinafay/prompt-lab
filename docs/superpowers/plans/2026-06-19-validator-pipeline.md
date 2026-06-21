# Validator Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Prompt Lab's rubric-centered review flow with explicit validator definitions, validation batches, judge synthesis from selected validation evidence, and deterministic validation-based comparison.

**Architecture:** Add validator definition/result contracts and focused backend modules for automatic validation, LLM questionnaire prompting, validation batch execution, and compare aggregation. Keep the existing filesystem artifact model and FastAPI app, but stop feeding rubric/raw outputs to judge and stop using LLM for compare. Add frontend types, API helpers, workflow actions, a Validation tab, updated settings fields, and a deterministic Compare matrix.

**Tech Stack:** Python 3.14, FastAPI, Pydantic, filesystem JSON artifacts, copied `backend/shared/llm` through `prompt_lab.llm_client`, React/Vite/TypeScript, direct Python test scripts, `pnpm` frontend tests/build.

---

## File Structure

Create:

- `backend/prompt_lab/models/validators.py` - Pydantic contracts for validator definitions, validation batches/results, LLM questionnaire responses, inclusion updates, and compare matrix responses.
- `backend/prompt_lab/automatic_validators.py` - deterministic automatic rule execution and JSON-path helpers.
- `backend/prompt_lab/validation.py` - validator loading, prompt building, validation result construction, batch aggregation, and inclusion mutation helpers.
- `backend/prompt_lab/system_prompts/validator.md.jinja` - LLM questionnaire prompt template.
- `frontend/src/components/ValidationView.tsx` - validation batch viewer and inclusion controls.
- `frontend/tests/validationView.test.ts` - frontend unit coverage for validation inclusion helpers.

Modify:

- `backend/prompt_lab/models/artifacts.py` - add `validator_model` to `ModelConfig`.
- `backend/prompt_lab/settings.py` - add `default_validator_model`.
- `backend/prompt_lab/experiment_seed.py` - seed `validator_model`.
- `backend/prompt_lab/storage.py` - load validators and validation artifacts.
- `backend/prompt_lab/dry_run.py` - add dry validator response JSON.
- `backend/prompt_lab/judge.py` - build judge prompts from validation evidence.
- `backend/prompt_lab/proposal.py` - replace rubric snapshot context with validation evidence.
- `backend/prompt_lab/compare.py` - replace LLM prompt builder with deterministic matrix aggregation.
- `backend/prompt_lab/api.py` - wire validation endpoints, judge validation precondition, proposal context, and compare response.
- `backend/prompt_lab/system_prompts/judge.md.jinja` - remove rubric/raw output sections; add validation evidence sections.
- `backend/prompt_lab/system_prompts/proposal.md.jinja` - remove rubric section; add validation context section.
- `backend/tests/test_*.py` - update/add focused backend tests listed in tasks below.
- `examples/*/experiment.json` - add `validator_model`.
- `examples/*/validators/*.json` - add example validators.
- `examples/*/rubric.md` - delete from committed examples.
- `FORMAT.md`, `README.md`, `examples/README.md`, `DESIGN.md` - update format and workflow docs.
- `frontend/src/types.ts` - add validator, validation, and compare matrix types; add `validator_model`.
- `frontend/src/api.ts` - add validation API helpers and update compare response type.
- `frontend/src/workflowActions.ts` - add validation/judge action state.
- `frontend/src/urlState.ts` and `frontend/src/components/WorkbenchTabs.tsx` - add `validation` tab.
- `frontend/src/App.tsx` - load validation state, run validation action, require validation before judge, pass validation/compare props.
- `frontend/src/components/ExperimentSettings.tsx` - add validator model field.
- `frontend/src/components/GlobalSettings.tsx` - add default validator model field.
- `frontend/src/components/ComparisonView.tsx` - render deterministic matrix.
- `frontend/src/styles.css` - add validation and matrix styling.
- `config/settings.json` - add default validator model.

---

### Task 1: Backend Contracts, Settings, And Seeding

**Files:**
- Create: `backend/prompt_lab/models/validators.py`
- Modify: `backend/prompt_lab/models/artifacts.py`
- Modify: `backend/prompt_lab/settings.py`
- Modify: `backend/prompt_lab/experiment_seed.py`
- Test: `backend/tests/test_validators.py`
- Test: `backend/tests/test_settings.py`
- Test: `backend/tests/test_experiment_seed.py`

- [ ] **Step 1: Write failing validator contract tests**

Add `backend/tests/test_validators.py`:

```python
from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from prompt_lab.models.validators import (
    AutomaticValidatorDefinition,
    LlmQuestionnaireValidatorDefinition,
    ValidationBatchArtifact,
    ValidationResultArtifact,
)


def assert_validation_error(model: type[Any], payload: dict[str, Any], text: str) -> None:
    try:
        model.model_validate(payload)
    except ValidationError as error:
        assert text in str(error)
    else:
        raise AssertionError(f"Expected validation error containing {text!r}")


def test_llm_questionnaire_validator_contract_accepts_checks() -> None:
    validator = LlmQuestionnaireValidatorDefinition.model_validate(
        {
            "schema_version": "prompt_lab.validator/v1",
            "validator_id": "scene-quality",
            "type": "llm_questionnaire",
            "title": "Scene quality",
            "description": "Check whether structured scenes preserve source meaning.",
            "enabled": True,
            "input_scope": "output_and_case",
            "checks": [
                {
                    "check_id": "coverage",
                    "title": "Coverage",
                    "question": "Does the output cover all source events without omission?",
                    "description": "Look for missing source paragraphs or events.",
                }
            ],
        }
    )

    assert validator.validator_id == "scene-quality"
    assert validator.checks[0].check_id == "coverage"


def test_llm_questionnaire_validator_rejects_duplicate_check_ids() -> None:
    assert_validation_error(
        LlmQuestionnaireValidatorDefinition,
        {
            "schema_version": "prompt_lab.validator/v1",
            "validator_id": "scene-quality",
            "type": "llm_questionnaire",
            "title": "Scene quality",
            "description": "Check scene quality.",
            "enabled": True,
            "input_scope": "output_only",
            "checks": [
                {
                    "check_id": "coverage",
                    "title": "Coverage",
                    "question": "Does it cover the source?",
                },
                {
                    "check_id": "coverage",
                    "title": "Coverage duplicate",
                    "question": "Does it cover the source again?",
                },
            ],
        },
        "duplicate check ids",
    )


def test_automatic_validator_contract_accepts_count_rule() -> None:
    validator = AutomaticValidatorDefinition.model_validate(
        {
            "schema_version": "prompt_lab.validator/v1",
            "validator_id": "summary-length",
            "type": "automatic",
            "title": "Summary length",
            "description": "Keep summaries compact.",
            "enabled": True,
            "input_scope": "output_only",
            "checks": [
                {
                    "check_id": "summary-word-count",
                    "title": "Summary word count",
                    "description": "Summary is at most 100 words.",
                    "rule": {
                        "kind": "word_count",
                        "source": "output_text",
                        "comparison": {"op": "lte", "value": 100},
                    },
                }
            ],
        }
    )

    assert validator.checks[0].rule.kind == "word_count"


def test_validation_batch_and_result_contracts() -> None:
    batch = ValidationBatchArtifact.model_validate(
        {
            "schema_version": "prompt_lab.validation_batch/v1",
            "validation_batch_id": "validation-001",
            "run_batch_id": "run-001",
            "version": "v001",
            "status": "completed",
            "started_at": "2026-06-19T00:00:00Z",
            "finished_at": "2026-06-19T00:01:00Z",
            "total_results": 1,
            "completed_results": 1,
            "validator_model": "openai/validator",
            "validator_ids": ["scene-quality"],
        }
    )
    result = ValidationResultArtifact.model_validate(
        {
            "schema_version": "prompt_lab.validation_result/v1",
            "validation_result_id": "validation-001-case-a-001-scene-quality",
            "validation_batch_id": batch.validation_batch_id,
            "run_batch_id": "run-001",
            "run_id": "run-001-case-a-repeat-001",
            "case_id": "case-a",
            "repeat_index": 1,
            "validator_id": "scene-quality",
            "validator_type": "llm_questionnaire",
            "status": "ok",
            "included_in_judge": True,
            "check_results": [
                {
                    "check_id": "coverage",
                    "verdict": "yes",
                    "comment": "All source events are represented.",
                    "included_in_judge": True,
                    "metrics": {},
                }
            ],
            "usage": {},
            "execution_error": None,
        }
    )

    assert batch.completed_results == 1
    assert result.check_results[0].verdict == "yes"
```

- [ ] **Step 2: Run validator contract tests and verify they fail**

Run:

```bash
PYTHONPATH=backend python backend/tests/test_validators.py
```

Expected: fails with `ModuleNotFoundError: No module named 'prompt_lab.models.validators'`.

- [ ] **Step 3: Implement validator contracts**

Create `backend/prompt_lab/models/validators.py` with these contracts:

```python
from __future__ import annotations

from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


NonEmptyString = Annotated[str, Field(min_length=1)]
JsonObject = dict[str, Any]
InputScope = Literal[
    "output_only",
    "output_and_prompt",
    "output_and_case",
    "output_prompt_and_case",
]
ValidatorType = Literal["llm_questionnaire", "automatic"]
ValidationBatchStatus = Literal["running", "completed", "failed", "cancelled"]
ValidationResultStatus = Literal["ok", "error"]
ValidationVerdict = Literal["yes", "no", "unknown"]
ComparisonStatus = Literal["pass", "fail", "mixed", "empty"]


class LlmValidatorCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: NonEmptyString
    title: NonEmptyString
    question: NonEmptyString
    description: str = ""


class CountComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["lt", "lte", "gt", "gte", "eq", "between"]
    value: int | None = Field(default=None, ge=0)
    min_value: int | None = Field(default=None, ge=0)
    max_value: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_values(self) -> Self:
        if self.op == "between":
            if self.min_value is None or self.max_value is None:
                raise ValueError("between comparison requires min_value and max_value")
            if self.min_value > self.max_value:
                raise ValueError("min_value cannot exceed max_value")
            if self.value is not None:
                raise ValueError("between comparison cannot include value")
        elif self.value is None:
            raise ValueError(f"{self.op} comparison requires value")
        elif self.min_value is not None or self.max_value is not None:
            raise ValueError(f"{self.op} comparison cannot include min_value or max_value")
        return self


class AutomaticRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal[
        "word_count",
        "sentence_count",
        "character_count",
        "json_path_count",
        "json_path_exists",
    ]
    source: Literal["output_text", "raw_output", "output_json"] = "output_text"
    path: str | None = None
    comparison: CountComparison | None = None

    @model_validator(mode="after")
    def validate_rule_shape(self) -> Self:
        if self.kind in {"json_path_count", "json_path_exists"}:
            if self.source != "output_json":
                raise ValueError(f"{self.kind} requires source output_json")
            if self.path is None or self.path.strip() == "":
                raise ValueError(f"{self.kind} requires path")
        elif self.path is not None:
            raise ValueError(f"{self.kind} cannot include path")
        if self.kind == "json_path_exists":
            if self.comparison is not None:
                raise ValueError("json_path_exists cannot include comparison")
        elif self.comparison is None:
            raise ValueError(f"{self.kind} requires comparison")
        return self


class AutomaticValidatorCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: NonEmptyString
    title: NonEmptyString
    description: str = ""
    rule: AutomaticRule


class BaseValidatorDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["prompt_lab.validator/v1"]
    validator_id: NonEmptyString
    type: ValidatorType
    title: NonEmptyString
    description: str = ""
    enabled: bool = True
    input_scope: InputScope = "output_only"


class LlmQuestionnaireValidatorDefinition(BaseValidatorDefinition):
    type: Literal["llm_questionnaire"]
    checks: list[LlmValidatorCheck] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_check_ids(self) -> Self:
        _validate_unique_check_ids([check.check_id for check in self.checks])
        return self


class AutomaticValidatorDefinition(BaseValidatorDefinition):
    type: Literal["automatic"]
    checks: list[AutomaticValidatorCheck] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_check_ids(self) -> Self:
        _validate_unique_check_ids([check.check_id for check in self.checks])
        return self


ValidatorDefinition = LlmQuestionnaireValidatorDefinition | AutomaticValidatorDefinition


def _validate_unique_check_ids(check_ids: list[str]) -> None:
    if len(check_ids) != len(set(check_ids)):
        raise ValueError("validator checks cannot contain duplicate check ids")


class ValidationBatchArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["prompt_lab.validation_batch/v1"]
    validation_batch_id: NonEmptyString
    run_batch_id: NonEmptyString
    version: NonEmptyString
    status: ValidationBatchStatus
    started_at: NonEmptyString
    finished_at: str | None = None
    total_results: int = Field(ge=0)
    completed_results: int = Field(ge=0)
    validator_model: NonEmptyString
    validator_ids: list[NonEmptyString]

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.completed_results > self.total_results:
            raise ValueError("completed_results cannot exceed total_results")
        return self


class ValidationCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: NonEmptyString
    verdict: ValidationVerdict
    comment: str = ""
    included_in_judge: bool = True
    metrics: JsonObject = Field(default_factory=dict)


class ValidationResultArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["prompt_lab.validation_result/v1"]
    validation_result_id: NonEmptyString
    validation_batch_id: NonEmptyString
    run_batch_id: NonEmptyString
    run_id: NonEmptyString
    case_id: NonEmptyString
    repeat_index: int = Field(ge=1)
    validator_id: NonEmptyString
    validator_type: ValidatorType
    status: ValidationResultStatus
    included_in_judge: bool = True
    check_results: list[ValidationCheckResult]
    usage: JsonObject = Field(default_factory=dict)
    execution_error: str | None = None

    @model_validator(mode="after")
    def validate_status_shape(self) -> Self:
        if self.status == "ok" and self.execution_error is not None:
            raise ValueError("ok validation result cannot include execution_error")
        if self.status == "error" and self.execution_error is None:
            raise ValueError("error validation result requires execution_error")
        return self


class LlmQuestionnaireCheckResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: NonEmptyString
    verdict: ValidationVerdict
    comment: NonEmptyString


class LlmQuestionnaireResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_results: list[LlmQuestionnaireCheckResponse] = Field(min_length=1)


class ValidationCheckInclusion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: NonEmptyString
    included_in_judge: bool


class ValidationResultInclusion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_result_id: NonEmptyString
    included_in_judge: bool
    check_results: list[ValidationCheckInclusion]


class ValidationInclusionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results: list[ValidationResultInclusion]


class ValidationState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_batch: ValidationBatchArtifact
    validators: list[JsonObject]
    results: list[ValidationResultArtifact]


class CompareCellDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: NonEmptyString
    repeat_index: int = Field(ge=1)
    validation_result_id: NonEmptyString
    verdict: ValidationVerdict | Literal["missing", "error"]
    comment: str = ""


class CompareMatrixCell(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: NonEmptyString
    status: ComparisonStatus
    yes_count: int = Field(ge=0)
    no_count: int = Field(ge=0)
    unknown_count: int = Field(ge=0)
    missing_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    total_count: int = Field(ge=0)
    details: list[CompareCellDetail]


class CompareMatrixRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validator_id: NonEmptyString
    validator_title: NonEmptyString
    check_id: NonEmptyString
    check_title: NonEmptyString
    check_description: str = ""
    cells: list[CompareMatrixCell]


class CompareMatrixResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["prompt_lab.compare_matrix/v1"]
    experiment_id: NonEmptyString
    versions: list[NonEmptyString] = Field(min_length=1)
    rows: list[CompareMatrixRow]
```

- [ ] **Step 4: Update experiment and settings models**

In `backend/prompt_lab/models/artifacts.py`, change `ModelConfig`:

```python
class ModelConfig(BaseModel):
    """Generator, validator, and judge model references."""

    model_config = ConfigDict(extra="forbid")

    generator_model: str
    validator_model: str
    judge_model: str
```

In `backend/prompt_lab/settings.py`, add:

```python
default_validator_model: str = Field(
    default="openai/example-large-model", min_length=1
)
```

In `backend/prompt_lab/experiment_seed.py`, update `_apply_settings_to_copied_manifest()`:

```python
"models": experiment.models.model_copy(
    update={
        "generator_model": settings.default_generator_model,
        "validator_model": settings.default_validator_model,
        "judge_model": settings.default_judge_model,
    }
),
```

- [ ] **Step 5: Update settings and seed tests**

Modify settings assertions to include `default_validator_model`. Add this assertion to `backend/tests/test_experiment_seed.py` where copied manifests are checked:

```python
assert saved["models"]["validator_model"] == "openai/configured-validator"
```

Use a settings fixture with:

```python
PromptLabSettings(
    default_generator_model="local/configured-generator",
    default_validator_model="openai/configured-validator",
    default_judge_model="openai/configured-judge",
    default_repeat_count=6,
)
```

- [ ] **Step 6: Run backend contract tests**

Run:

```bash
PYTHONPATH=backend python backend/tests/test_validators.py
PYTHONPATH=backend python backend/tests/test_settings.py
PYTHONPATH=backend python backend/tests/test_experiment_seed.py
```

Expected: all pass.

- [ ] **Step 7: Commit backend contracts**

Run:

```bash
git add backend/prompt_lab/models/validators.py backend/prompt_lab/models/artifacts.py backend/prompt_lab/settings.py backend/prompt_lab/experiment_seed.py backend/tests/test_validators.py backend/tests/test_settings.py backend/tests/test_experiment_seed.py
git commit -m "feat: add validator artifact contracts"
```

---

### Task 2: Storage And Automatic Validators

**Files:**
- Create: `backend/prompt_lab/automatic_validators.py`
- Modify: `backend/prompt_lab/storage.py`
- Test: `backend/tests/test_automatic_validators.py`
- Test: `backend/tests/test_storage.py`

- [ ] **Step 1: Write automatic validator tests**

Add `backend/tests/test_automatic_validators.py`:

```python
from __future__ import annotations

from prompt_lab.automatic_validators import execute_automatic_validator
from prompt_lab.models.artifacts import RunArtifact
from prompt_lab.models.validators import AutomaticValidatorDefinition


def run_artifact(**overrides: object) -> RunArtifact:
    payload = {
        "schema_version": "prompt_lab.run/v1",
        "run_id": "run-001-case-a-repeat-001",
        "run_batch_id": "run-001",
        "version": "v001",
        "case_id": "case-a",
        "repeat_index": 1,
        "generator_model": "local/generator",
        "status": "ok",
        "rendered_prompt": "Summarize this.",
        "raw_output": "one two three",
        "output_type": "text",
        "output_text": "one two three",
        "usage": {},
    }
    payload.update(overrides)
    return RunArtifact.model_validate(payload)


def test_word_count_rule_passes_when_within_limit() -> None:
    validator = AutomaticValidatorDefinition.model_validate(
        {
            "schema_version": "prompt_lab.validator/v1",
            "validator_id": "length",
            "type": "automatic",
            "title": "Length",
            "description": "",
            "enabled": True,
            "input_scope": "output_only",
            "checks": [
                {
                    "check_id": "word-limit",
                    "title": "Word limit",
                    "rule": {
                        "kind": "word_count",
                        "source": "output_text",
                        "comparison": {"op": "lte", "value": 3},
                    },
                }
            ],
        }
    )

    result = execute_automatic_validator(
        validation_batch_id="validation-001",
        run=run_artifact(),
        validator=validator,
    )

    assert result.status == "ok"
    assert result.check_results[0].verdict == "yes"
    assert result.check_results[0].metrics == {"value": 3}


def test_json_path_count_rule_counts_list_items() -> None:
    validator = AutomaticValidatorDefinition.model_validate(
        {
            "schema_version": "prompt_lab.validator/v1",
            "validator_id": "scene-count",
            "type": "automatic",
            "title": "Scene count",
            "description": "",
            "enabled": True,
            "input_scope": "output_only",
            "checks": [
                {
                    "check_id": "has-scenes",
                    "title": "Has scenes",
                    "rule": {
                        "kind": "json_path_count",
                        "source": "output_json",
                        "path": "scenes",
                        "comparison": {"op": "gte", "value": 2},
                    },
                }
            ],
        }
    )

    result = execute_automatic_validator(
        validation_batch_id="validation-001",
        run=run_artifact(output_type="pydantic", output_text=None, output_json={"scenes": [{}, {}]}),
        validator=validator,
    )

    assert result.check_results[0].verdict == "yes"
    assert result.check_results[0].metrics == {"value": 2}


def test_automatic_validator_records_error_result_for_invalid_source() -> None:
    validator = AutomaticValidatorDefinition.model_validate(
        {
            "schema_version": "prompt_lab.validator/v1",
            "validator_id": "scene-count",
            "type": "automatic",
            "title": "Scene count",
            "description": "",
            "enabled": True,
            "input_scope": "output_only",
            "checks": [
                {
                    "check_id": "has-scenes",
                    "title": "Has scenes",
                    "rule": {
                        "kind": "json_path_count",
                        "source": "output_json",
                        "path": "scenes",
                        "comparison": {"op": "gte", "value": 1},
                    },
                }
            ],
        }
    )

    result = execute_automatic_validator(
        validation_batch_id="validation-001",
        run=run_artifact(status="validation_error", output_json=None, validation_error="bad json"),
        validator=validator,
    )

    assert result.status == "error"
    assert result.execution_error is not None
```

- [ ] **Step 2: Run automatic validator tests and verify they fail**

Run:

```bash
PYTHONPATH=backend python backend/tests/test_automatic_validators.py
```

Expected: fails with `ModuleNotFoundError: No module named 'prompt_lab.automatic_validators'`.

- [ ] **Step 3: Implement automatic validators**

Create `backend/prompt_lab/automatic_validators.py`:

```python
from __future__ import annotations

import re
from typing import Any

from prompt_lab.models.artifacts import RunArtifact
from prompt_lab.models.validators import (
    AutomaticRule,
    AutomaticValidatorDefinition,
    CountComparison,
    ValidationCheckResult,
    ValidationResultArtifact,
)


def execute_automatic_validator(
    *,
    validation_batch_id: str,
    run: RunArtifact,
    validator: AutomaticValidatorDefinition,
) -> ValidationResultArtifact:
    try:
        checks = [
            _execute_check(rule=check.rule, check_id=check.check_id, run=run)
            for check in validator.checks
        ]
        return ValidationResultArtifact(
            schema_version="prompt_lab.validation_result/v1",
            validation_result_id=_result_id(validation_batch_id, run, validator.validator_id),
            validation_batch_id=validation_batch_id,
            run_batch_id=run.run_batch_id,
            run_id=run.run_id,
            case_id=run.case_id,
            repeat_index=run.repeat_index,
            validator_id=validator.validator_id,
            validator_type="automatic",
            status="ok",
            included_in_judge=True,
            check_results=checks,
            usage={},
            execution_error=None,
        )
    except ValueError as exc:
        return ValidationResultArtifact(
            schema_version="prompt_lab.validation_result/v1",
            validation_result_id=_result_id(validation_batch_id, run, validator.validator_id),
            validation_batch_id=validation_batch_id,
            run_batch_id=run.run_batch_id,
            run_id=run.run_id,
            case_id=run.case_id,
            repeat_index=run.repeat_index,
            validator_id=validator.validator_id,
            validator_type="automatic",
            status="error",
            included_in_judge=False,
            check_results=[],
            usage={},
            execution_error=str(exc),
        )


def _execute_check(
    *, rule: AutomaticRule, check_id: str, run: RunArtifact
) -> ValidationCheckResult:
    value = _rule_value(rule, run)
    passed = True if rule.kind == "json_path_exists" else _compare(value, rule.comparison)
    return ValidationCheckResult(
        check_id=check_id,
        verdict="yes" if passed else "no",
        comment=f"Measured value: {value}.",
        included_in_judge=True,
        metrics={"value": value},
    )


def _rule_value(rule: AutomaticRule, run: RunArtifact) -> int:
    source = _source_value(rule, run)
    if rule.kind == "word_count":
        if not isinstance(source, str):
            raise ValueError("word_count source must be text")
        return len(re.findall(r"\\b\\S+\\b", source))
    if rule.kind == "sentence_count":
        if not isinstance(source, str):
            raise ValueError("sentence_count source must be text")
        return len([part for part in re.split(r"[.!?]+\\s*", source.strip()) if part])
    if rule.kind == "character_count":
        if not isinstance(source, str):
            raise ValueError("character_count source must be text")
        return len(source)
    if rule.kind == "json_path_count":
        target = _resolve_json_path(source, rule.path or "")
        if isinstance(target, list):
            return len(target)
        if isinstance(target, dict):
            return len(target)
        if target is None:
            return 0
        return 1
    if rule.kind == "json_path_exists":
        _resolve_json_path(source, rule.path or "")
        return 1
    raise ValueError(f"Unsupported automatic rule kind: {rule.kind}")


def _source_value(rule: AutomaticRule, run: RunArtifact) -> Any:
    if rule.source == "output_text":
        if run.output_text is None:
            raise ValueError("output_text is not available")
        return run.output_text
    if rule.source == "raw_output":
        if run.raw_output is None:
            raise ValueError("raw_output is not available")
        return run.raw_output
    if run.output_json is None:
        raise ValueError("output_json is not available")
    return run.output_json


def _resolve_json_path(value: Any, path: str) -> Any:
    current = value
    for part in [segment for segment in path.split(".") if segment]:
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        if isinstance(current, list) and part.isdigit():
            index = int(part)
            if index < len(current):
                current = current[index]
                continue
        raise ValueError(f"JSON path not found: {path}")
    return current


def _compare(value: int, comparison: CountComparison | None) -> bool:
    if comparison is None:
        raise ValueError("count rule missing comparison")
    if comparison.op == "lt":
        return value < int(comparison.value)
    if comparison.op == "lte":
        return value <= int(comparison.value)
    if comparison.op == "gt":
        return value > int(comparison.value)
    if comparison.op == "gte":
        return value >= int(comparison.value)
    if comparison.op == "eq":
        return value == int(comparison.value)
    return int(comparison.min_value) <= value <= int(comparison.max_value)


def _result_id(
    validation_batch_id: str, run: RunArtifact, validator_id: str
) -> str:
    return (
        f"{validation_batch_id}-{run.case_id}-"
        f"repeat-{run.repeat_index:03d}-{validator_id}"
    )
```

- [ ] **Step 4: Add storage helpers for validators and validations**

Modify `backend/prompt_lab/storage.py` imports:

```python
from pydantic import TypeAdapter
from prompt_lab.models.validators import (
    ValidationBatchArtifact,
    ValidationResultArtifact,
    ValidatorDefinition,
)
```

Add a module-level adapter:

```python
VALIDATOR_DEFINITION_ADAPTER = TypeAdapter(ValidatorDefinition)
```

Add methods to `PromptLabStore`:

```python
def load_validators(self, experiment_id: str) -> list[ValidatorDefinition]:
    validators_dir = self.experiment_dir(experiment_id) / "validators"
    if not validators_dir.is_dir():
        return []
    return [
        VALIDATOR_DEFINITION_ADAPTER.validate_python(_read_json(path))
        for path in sorted(validators_dir.glob("*.json"))
    ]

def write_validation_artifact(
    self, experiment_id: str, version: str, relative_path: str, value: dict[str, Any]
) -> Path:
    path = _resolve_version_local_path(
        self.version_dir(experiment_id, version), relative_path
    )
    _write_json(path, value)
    return path

def load_validation_batch(
    self, experiment_id: str, version: str, validation_batch_id: str
) -> ValidationBatchArtifact:
    path = self.version_dir(experiment_id, version) / "validations" / validation_batch_id / "batch.json"
    if not path.is_file():
        raise NotFoundError("Validation batch not found")
    return ValidationBatchArtifact.model_validate(_read_json(path))

def load_validation_results(
    self, experiment_id: str, version: str, validation_batch_id: str
) -> list[ValidationResultArtifact]:
    batch_dir = self.version_dir(experiment_id, version) / "validations" / validation_batch_id
    if not batch_dir.is_dir():
        raise NotFoundError("Validation batch not found")
    return [
        ValidationResultArtifact.model_validate(_read_json(path))
        for path in sorted(batch_dir.glob("*/*/*.json"))
        if "validators_snapshot" not in path.parts and path.name != "batch.json"
    ]
```

- [ ] **Step 5: Run storage and automatic validator tests**

Run:

```bash
PYTHONPATH=backend python backend/tests/test_automatic_validators.py
PYTHONPATH=backend python backend/tests/test_storage.py
```

Expected: all pass.

- [ ] **Step 6: Commit storage and automatic validators**

Run:

```bash
git add backend/prompt_lab/automatic_validators.py backend/prompt_lab/storage.py backend/tests/test_automatic_validators.py backend/tests/test_storage.py
git commit -m "feat: add automatic validators"
```

---

### Task 3: Validation Prompting, Runner, And API

**Files:**
- Create: `backend/prompt_lab/validation.py`
- Create: `backend/prompt_lab/system_prompts/validator.md.jinja`
- Modify: `backend/prompt_lab/dry_run.py`
- Modify: `backend/prompt_lab/api.py`
- Test: `backend/tests/test_validation.py`
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: Write validation prompt and API tests**

Add `backend/tests/test_validation.py` with prompt and inclusion tests:

```python
from __future__ import annotations

from prompt_lab.models.artifacts import CaseArtifact, RunArtifact
from prompt_lab.models.validators import LlmQuestionnaireValidatorDefinition
from prompt_lab.validation import build_llm_validator_prompt, validate_llm_check_ids


def test_validator_prompt_respects_output_only_scope() -> None:
    validator = LlmQuestionnaireValidatorDefinition.model_validate(
        {
            "schema_version": "prompt_lab.validator/v1",
            "validator_id": "quality",
            "type": "llm_questionnaire",
            "title": "Quality",
            "description": "Check output quality.",
            "enabled": True,
            "input_scope": "output_only",
            "checks": [
                {
                    "check_id": "coverage",
                    "title": "Coverage",
                    "question": "Does the output cover the source?",
                }
            ],
        }
    )
    run = RunArtifact.model_validate(
        {
            "schema_version": "prompt_lab.run/v1",
            "run_id": "run-001-case-a-repeat-001",
            "run_batch_id": "run-001",
            "version": "v001",
            "case_id": "case-a",
            "repeat_index": 1,
            "generator_model": "local/generator",
            "status": "ok",
            "rendered_prompt": "SOURCE PROMPT",
            "raw_output": "RAW OUTPUT",
            "output_type": "text",
            "output_text": "OUTPUT TEXT",
            "usage": {},
        }
    )
    case = CaseArtifact.model_validate(
        {
            "schema_version": "prompt_lab.case/v2",
            "id": "case-a",
            "title": "Case A",
            "stores": {"case": {"kind": "flat_file_tree", "values": {}}},
            "bindings": {},
        }
    )

    prompt = build_llm_validator_prompt(
        experiment_id="demo",
        version="v001",
        validation_batch_id="validation-001",
        validator=validator,
        run=run,
        case=case,
        case_context={"secret_source": "case context"},
    )

    assert "OUTPUT TEXT" in prompt
    assert "SOURCE PROMPT" not in prompt
    assert "secret_source" not in prompt
    assert "coverage" in prompt
    assert "<<MODEL>>" in prompt


def test_validate_llm_check_ids_rejects_missing_response() -> None:
    validator = LlmQuestionnaireValidatorDefinition.model_validate(
        {
            "schema_version": "prompt_lab.validator/v1",
            "validator_id": "quality",
            "type": "llm_questionnaire",
            "title": "Quality",
            "description": "",
            "enabled": True,
            "input_scope": "output_only",
            "checks": [
                {"check_id": "coverage", "title": "Coverage", "question": "Coverage?"},
                {"check_id": "order", "title": "Order", "question": "Order?"},
            ],
        }
    )

    try:
        validate_llm_check_ids(validator, ["coverage"])
    except ValueError as error:
        assert "missing: order" in str(error)
    else:
        raise AssertionError("Expected missing check id validation error")
```

Add an API test to `backend/tests/test_api.py`:

```python
def test_api_validates_active_run_with_dry_run() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_demo_pydantic_experiment(root)
        validators_dir = root / "examples" / "demo" / "validators"
        validators_dir.mkdir()
        (validators_dir / "quality.json").write_text(
            json.dumps(
                {
                    "schema_version": "prompt_lab.validator/v1",
                    "validator_id": "quality",
                    "type": "llm_questionnaire",
                    "title": "Quality",
                    "description": "Check quality.",
                    "enabled": True,
                    "input_scope": "output_only",
                    "checks": [
                        {
                            "check_id": "parseable",
                            "title": "Parseable",
                            "question": "Is the output parseable?",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        app = create_app(PromptLabConfig.from_env(project_root=root))
        client = TestClient(app)
        run_response = client.post(
            "/api/experiments/demo/versions/v001/runs", json={"dry_run": True}
        )
        assert run_response.status_code == 200

        validation_response = client.post(
            "/api/experiments/demo/versions/v001/validations",
            json={"dry_run": True},
        )

        assert validation_response.status_code == 200
        body = validation_response.json()
        assert body["validation_batch"]["run_batch_id"] == run_response.json()["job_id"]
        assert body["results"][0]["validator_id"] == "quality"
        assert body["results"][0]["check_results"][0]["check_id"] == "parseable"
```

- [ ] **Step 2: Run validation tests and verify they fail**

Run:

```bash
PYTHONPATH=backend python backend/tests/test_validation.py
PYTHONPATH=backend python backend/tests/test_api.py
```

Expected: validation module test fails with missing module; API test fails with `404 Not Found` for `/validations`.

- [ ] **Step 3: Add validator prompt template**

Create `backend/prompt_lab/system_prompts/validator.md.jinja`:

```jinja
You are validating one Prompt Lab run result.

Return only JSON matching this response model:
```json
<<MODEL>>
```

Rules:

- Answer every check exactly once.
- Use only the provided validation context.
- Do not suggest prompt or model changes.
- Use verdict "yes" only when the condition is clearly satisfied.
- Use verdict "no" when the condition is clearly violated.
- Use verdict "unknown" when the provided context is insufficient.
- Keep comments short and cite concrete evidence from the provided context.

Experiment id: {{ experiment_id }}

Version: {{ version }}

Validation batch: {{ validation_batch_id }}

{{ validator_section }}

{{ run_metadata_section }}

{{ run_status_section }}

{{ output_section }}

{% if prompt_section is not none -%}
{{ prompt_section }}

{% endif -%}
{% if case_context_section is not none -%}
{{ case_context_section }}

{% endif -%}
{{ response_schema_section }}
```

- [ ] **Step 4: Implement validation helpers**

Create `backend/prompt_lab/validation.py` with:

```python
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from prompt_lab.automatic_validators import execute_automatic_validator
from prompt_lab.case_context import materialize_case_context
from prompt_lab.models.artifacts import CaseArtifact, RunArtifact
from prompt_lab.models.validators import (
    AutomaticValidatorDefinition,
    LlmQuestionnaireResponse,
    LlmQuestionnaireValidatorDefinition,
    ValidationBatchArtifact,
    ValidationCheckResult,
    ValidationInclusionUpdate,
    ValidationResultArtifact,
    ValidatorDefinition,
)
from prompt_lab.prompt_sections import fenced_section, json_block
from prompt_lab.prompt_templates import render_system_prompt


def enabled_validators(
    validators: list[ValidatorDefinition],
) -> list[ValidatorDefinition]:
    return [validator for validator in validators if validator.enabled]


def build_llm_validator_prompt(
    *,
    experiment_id: str,
    version: str,
    validation_batch_id: str,
    validator: LlmQuestionnaireValidatorDefinition,
    run: RunArtifact,
    case: CaseArtifact,
    case_context: dict[str, Any],
) -> str:
    prompt_section = (
        fenced_section("RENDERED_PROMPT", run.rendered_prompt)
        if validator.input_scope in {"output_and_prompt", "output_prompt_and_case"}
        else None
    )
    case_context_section = (
        fenced_section("CASE_CONTEXT_JSON", json_block(case_context), fence="json")
        if validator.input_scope in {"output_and_case", "output_prompt_and_case"}
        else None
    )
    return render_system_prompt(
        "validator.md.jinja",
        {
            "experiment_id": experiment_id,
            "version": version,
            "validation_batch_id": validation_batch_id,
            "validator_section": fenced_section(
                "VALIDATOR_JSON",
                json_block(validator.model_dump(mode="json")),
                fence="json",
            ),
            "run_metadata_section": fenced_section(
                "RUN_METADATA_JSON",
                json_block(
                    {
                        "run_id": run.run_id,
                        "run_batch_id": run.run_batch_id,
                        "case_id": run.case_id,
                        "repeat_index": run.repeat_index,
                        "generator_model": run.generator_model,
                    }
                ),
                fence="json",
            ),
            "run_status_section": fenced_section(
                "RUN_STATUS_JSON",
                json_block(
                    {
                        "status": run.status,
                        "validation_error": run.validation_error,
                        "execution_error": run.execution_error,
                    }
                ),
                fence="json",
            ),
            "output_section": fenced_section(
                "OUTPUT_JSON",
                json_block(
                    {
                        "raw_output": run.raw_output,
                        "output_text": run.output_text,
                        "output_json": run.output_json,
                    }
                ),
                fence="json",
            ),
            "prompt_section": prompt_section,
            "case_context_section": case_context_section,
            "response_schema_section": fenced_section(
                "VALIDATOR_RESPONSE_SCHEMA_JSON",
                json_block(LlmQuestionnaireResponse.model_json_schema()),
                fence="json",
            ),
        },
    )


def validate_llm_check_ids(
    validator: LlmQuestionnaireValidatorDefinition, response_check_ids: list[str]
) -> None:
    expected = {check.check_id for check in validator.checks}
    actual = set(response_check_ids)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if len(response_check_ids) != len(actual) or missing or unknown:
        parts: list[str] = ["validator response check ids must match validator checks"]
        if missing:
            parts.append(f"missing: {', '.join(missing)}")
        if unknown:
            parts.append(f"unknown: {', '.join(unknown)}")
        if len(response_check_ids) != len(actual):
            parts.append("duplicates present")
        raise ValueError("; ".join(parts))


def build_llm_validation_result(
    *,
    validation_batch_id: str,
    run: RunArtifact,
    validator: LlmQuestionnaireValidatorDefinition,
    response: LlmQuestionnaireResponse,
    usage: dict[str, Any],
) -> ValidationResultArtifact:
    validate_llm_check_ids(
        validator, [check_result.check_id for check_result in response.check_results]
    )
    return ValidationResultArtifact(
        schema_version="prompt_lab.validation_result/v1",
        validation_result_id=(
            f"{validation_batch_id}-{run.case_id}-"
            f"repeat-{run.repeat_index:03d}-{validator.validator_id}"
        ),
        validation_batch_id=validation_batch_id,
        run_batch_id=run.run_batch_id,
        run_id=run.run_id,
        case_id=run.case_id,
        repeat_index=run.repeat_index,
        validator_id=validator.validator_id,
        validator_type="llm_questionnaire",
        status="ok",
        included_in_judge=True,
        check_results=[
            ValidationCheckResult(
                check_id=item.check_id,
                verdict=item.verdict,
                comment=item.comment,
                included_in_judge=True,
                metrics={},
            )
            for item in response.check_results
        ],
        usage=usage,
        execution_error=None,
    )


def apply_inclusion_update(
    results: list[ValidationResultArtifact],
    update: ValidationInclusionUpdate,
) -> list[ValidationResultArtifact]:
    update_by_result = {item.validation_result_id: item for item in update.results}
    updated_results: list[ValidationResultArtifact] = []
    for result in results:
        result_update = update_by_result.get(result.validation_result_id)
        if result_update is None:
            updated_results.append(result)
            continue
        check_updates = {
            item.check_id: item.included_in_judge
            for item in result_update.check_results
        }
        updated_results.append(
            result.model_copy(
                update={
                    "included_in_judge": result_update.included_in_judge,
                    "check_results": [
                        check.model_copy(
                            update={
                                "included_in_judge": check_updates.get(
                                    check.check_id, check.included_in_judge
                                )
                            }
                        )
                        for check in result.check_results
                    ],
                }
            )
        )
    return updated_results
```

- [ ] **Step 5: Add dry validator response**

In `backend/prompt_lab/dry_run.py`, add:

```python
def dry_validator_response_json(check_ids: list[str]) -> str:
    return json.dumps(
        {
            "check_results": [
                {
                    "check_id": check_id,
                    "verdict": "yes",
                    "comment": f"Dry-run validator response for {check_id}.",
                }
                for check_id in check_ids
            ]
        },
        ensure_ascii=False,
    )
```

- [ ] **Step 6: Wire validation API**

In `backend/prompt_lab/api.py`:

1. Import validator models and helpers.
2. Add `POST /api/experiments/{experiment_id}/versions/{version}/validations`.
3. Add `GET /api/experiments/{experiment_id}/versions/{version}/validations/latest`.
4. Add `PUT /api/experiments/{experiment_id}/versions/{version}/validations/{validation_batch_id}/inclusion`.
5. In run completion cleanup, add `validations` to downstream cleanup.

Use this response shape for validation endpoints:

```python
{
    "validation_batch": batch.model_dump(mode="json"),
    "validators": [validator.model_dump(mode="json") for validator in validators],
    "results": [result.model_dump(mode="json") for result in results],
}
```

Use job kind `validate` and total units:

```python
total_units = len(run_artifacts) * len(enabled_validators(validators))
```

Write each validation result to:

```python
f"validations/{job_id}/{run.case_id}/repeat-{run.repeat_index:03d}/{validator.validator_id}.json"
```

Write validator snapshots to:

```python
f"validations/{job_id}/validators_snapshot/{validator.validator_id}.json"
```

- [ ] **Step 7: Run validation tests**

Run:

```bash
PYTHONPATH=backend python backend/tests/test_validation.py
PYTHONPATH=backend python backend/tests/test_api.py
```

Expected: all pass.

- [ ] **Step 8: Commit validation API**

Run:

```bash
git add backend/prompt_lab/validation.py backend/prompt_lab/system_prompts/validator.md.jinja backend/prompt_lab/dry_run.py backend/prompt_lab/api.py backend/tests/test_validation.py backend/tests/test_api.py
git commit -m "feat: add validation workflow"
```

---

### Task 4: Judge And Proposal From Validation Evidence

**Files:**
- Modify: `backend/prompt_lab/judge.py`
- Modify: `backend/prompt_lab/proposal.py`
- Modify: `backend/prompt_lab/system_prompts/judge.md.jinja`
- Modify: `backend/prompt_lab/system_prompts/proposal.md.jinja`
- Modify: `backend/prompt_lab/api.py`
- Test: `backend/tests/test_judge.py`
- Test: `backend/tests/test_proposal.py`

- [ ] **Step 1: Update judge tests for validation evidence**

In `backend/tests/test_judge.py`, add:

```python
def test_build_judge_prompt_uses_validation_evidence_without_raw_outputs() -> None:
    run = RunArtifact.model_validate(valid_run_payload(raw_output="RAW SECRET"))
    prompt = build_judge_prompt(
        experiment_id="demo",
        version="v001",
        run_batch_id="batch-001",
        validation_batch_id="validation-001",
        judge_model="openai/example-large-model",
        output_declaration="pydantic model: model.DemoOutput",
        prompt_template="Say {{ value }}",
        model_source="class DemoOutput: ...",
        validation_evidence=[
            {
                "validator_id": "quality",
                "validator_title": "Quality",
                "check_id": "coverage",
                "check_title": "Coverage",
                "case_id": "case-a",
                "repeat_index": 1,
                "verdict": "no",
                "comment": "The answer omits the final scene.",
            }
        ],
        run_errors=[
            {
                "case_id": run.case_id,
                "repeat_index": run.repeat_index,
                "status": run.status,
                "validation_error": run.validation_error,
                "execution_error": run.execution_error,
            }
        ],
    )

    assert "VALIDATION_EVIDENCE_JSON" in prompt
    assert "The answer omits the final scene." in prompt
    assert "RAW SECRET" not in prompt
    assert "RUBRIC" not in prompt
```

- [ ] **Step 2: Run judge tests and verify failure**

Run:

```bash
PYTHONPATH=backend python backend/tests/test_judge.py
```

Expected: fails because `build_judge_prompt` still requires `rubric`, `cases`, and `run_artifacts`.

- [ ] **Step 3: Refactor judge prompt builder**

Change `build_judge_prompt()` signature in `backend/prompt_lab/judge.py`:

```python
def build_judge_prompt(
    *,
    experiment_id: str,
    version: str,
    run_batch_id: str,
    validation_batch_id: str,
    judge_model: str,
    output_declaration: str,
    prompt_template: str,
    model_source: str | None,
    validation_evidence: list[dict[str, object]],
    run_errors: list[dict[str, object]],
) -> str:
```

Render sections:

```python
"validation_metadata_section": fenced_section(
    "VALIDATION_METADATA_JSON",
    json_block(
        {
            "run_batch_id": run_batch_id,
            "validation_batch_id": validation_batch_id,
        }
    ),
    fence="json",
),
"validation_evidence_section": fenced_section(
    "VALIDATION_EVIDENCE_JSON",
    json_block(validation_evidence),
    fence="json",
),
"run_errors_section": fenced_section(
    "RUN_ERRORS_JSON",
    json_block(run_errors),
    fence="json",
),
```

Remove rubric, case payloads, run artifacts, and raw output sections.

- [ ] **Step 4: Update judge prompt template**

In `backend/prompt_lab/system_prompts/judge.md.jinja`, remove rubric/raw output/cases sections. Include:

```jinja
{{ validation_metadata_section }}

{{ output_declaration_section }}

{{ prompt_template_section }}

{% if model_source_section is not none -%}
{{ model_source_section }}

{% endif -%}
{{ validation_evidence_section }}

{{ run_errors_section }}

{{ judgment_schema_section }}
```

Add rule:

```text
- Use validation evidence as the primary analysis of run outputs; do not ask for raw outputs.
```

- [ ] **Step 5: Update proposal prompt tests and implementation**

In `backend/tests/test_proposal.py`, replace rubric assertions with validation context:

```python
assert "VALIDATION_CONTEXT_JSON" in prompt
assert "validation-001" in prompt
assert "RUBRIC_SNAPSHOT_MD" not in prompt
```

Change `build_proposal_prompt()` parameters:

```python
validation_context: dict[str, Any],
```

Remove `rubric_snapshot`. Render:

```python
"validation_context_section": fenced_section(
    "VALIDATION_CONTEXT_JSON",
    json_block(validation_context),
    fence="json",
),
```

Update `proposal.md.jinja` to include `{{ validation_context_section }}` and remove `{{ rubric_section }}`.

- [ ] **Step 6: Wire API judge/proposal changes**

In `POST /judgments`:

1. Load latest validation batch.
2. Load validation results.
3. Build validation evidence only from effective included check results.
4. Reject with HTTP 400 if no validation batch exists.
5. Keep run errors from run artifacts.
6. Save validation metadata next to review, for example `validation_context.json`.

Evidence item shape:

```python
{
    "validator_id": result.validator_id,
    "check_id": check.check_id,
    "case_id": result.case_id,
    "repeat_index": result.repeat_index,
    "verdict": check.verdict,
    "comment": check.comment,
}
```

In proposal generation, read `validation_context.json` and pass it to `build_proposal_prompt()`.

- [ ] **Step 7: Run judge and proposal tests**

Run:

```bash
PYTHONPATH=backend python backend/tests/test_judge.py
PYTHONPATH=backend python backend/tests/test_proposal.py
PYTHONPATH=backend python backend/tests/test_api.py
```

Expected: all pass.

- [ ] **Step 8: Commit judge/proposal refactor**

Run:

```bash
git add backend/prompt_lab/judge.py backend/prompt_lab/proposal.py backend/prompt_lab/system_prompts/judge.md.jinja backend/prompt_lab/system_prompts/proposal.md.jinja backend/prompt_lab/api.py backend/tests/test_judge.py backend/tests/test_proposal.py backend/tests/test_api.py
git commit -m "feat: judge from validation evidence"
```

---

### Task 5: Deterministic Compare Matrix

**Files:**
- Modify: `backend/prompt_lab/compare.py`
- Modify: `backend/prompt_lab/api.py`
- Test: `backend/tests/test_compare.py`
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: Write compare aggregation tests**

Replace LLM prompt coverage in `backend/tests/test_compare.py` with:

```python
from __future__ import annotations

from prompt_lab.compare import build_compare_matrix
from prompt_lab.models.validators import ValidationResultArtifact


def validation_result(
    *, version: str, check_id: str, verdict: str, included: bool = True
) -> ValidationResultArtifact:
    return ValidationResultArtifact.model_validate(
        {
            "schema_version": "prompt_lab.validation_result/v1",
            "validation_result_id": f"validation-{version}-case-a-001-quality",
            "validation_batch_id": f"validation-{version}",
            "run_batch_id": f"run-{version}",
            "run_id": f"run-{version}-case-a-repeat-001",
            "case_id": "case-a",
            "repeat_index": 1,
            "validator_id": "quality",
            "validator_type": "llm_questionnaire",
            "status": "ok",
            "included_in_judge": True,
            "check_results": [
                {
                    "check_id": check_id,
                    "verdict": verdict,
                    "comment": f"{verdict} evidence",
                    "included_in_judge": included,
                    "metrics": {},
                }
            ],
            "usage": {},
            "execution_error": None,
        }
    )


def test_compare_matrix_marks_any_no_as_fail() -> None:
    matrix = build_compare_matrix(
        experiment_id="demo",
        versions=["v001", "v002"],
        validator_snapshots_by_version={
            "v001": [
                {
                    "validator_id": "quality",
                    "title": "Quality",
                    "checks": [{"check_id": "coverage", "title": "Coverage"}],
                }
            ],
            "v002": [
                {
                    "validator_id": "quality",
                    "title": "Quality",
                    "checks": [{"check_id": "coverage", "title": "Coverage"}],
                }
            ],
        },
        results_by_version={
            "v001": [validation_result(version="v001", check_id="coverage", verdict="yes")],
            "v002": [validation_result(version="v002", check_id="coverage", verdict="no")],
        },
    )

    assert matrix.rows[0].cells[0].status == "pass"
    assert matrix.rows[0].cells[1].status == "fail"
    assert matrix.rows[0].cells[1].no_count == 1


def test_compare_matrix_ignores_excluded_checks() -> None:
    matrix = build_compare_matrix(
        experiment_id="demo",
        versions=["v001"],
        validator_snapshots_by_version={
            "v001": [
                {
                    "validator_id": "quality",
                    "title": "Quality",
                    "checks": [{"check_id": "coverage", "title": "Coverage"}],
                }
            ]
        },
        results_by_version={
            "v001": [
                validation_result(
                    version="v001",
                    check_id="coverage",
                    verdict="no",
                    included=False,
                )
            ]
        },
    )

    assert matrix.rows[0].cells[0].status == "empty"
    assert matrix.rows[0].cells[0].total_count == 0
```

- [ ] **Step 2: Run compare tests and verify failure**

Run:

```bash
PYTHONPATH=backend python backend/tests/test_compare.py
```

Expected: fails because `build_compare_matrix` does not exist.

- [ ] **Step 3: Implement deterministic compare**

Replace prompt-building behavior in `backend/prompt_lab/compare.py` with `build_compare_matrix()`:

```python
from __future__ import annotations

from collections import Counter
from typing import Any

from prompt_lab.models.validators import (
    CompareCellDetail,
    CompareMatrixCell,
    CompareMatrixResponse,
    CompareMatrixRow,
    ValidationResultArtifact,
)


def build_compare_matrix(
    *,
    experiment_id: str,
    versions: list[str],
    validator_snapshots_by_version: dict[str, list[dict[str, Any]]],
    results_by_version: dict[str, list[ValidationResultArtifact]],
) -> CompareMatrixResponse:
    rows: list[CompareMatrixRow] = []
    for validator_id, validator_title, check_id, check_title, check_description in _row_keys(
        versions, validator_snapshots_by_version
    ):
        rows.append(
            CompareMatrixRow(
                validator_id=validator_id,
                validator_title=validator_title,
                check_id=check_id,
                check_title=check_title,
                check_description=check_description,
                cells=[
                    _cell_for_version(
                        version=version,
                        validator_id=validator_id,
                        check_id=check_id,
                        results=results_by_version.get(version, []),
                    )
                    for version in versions
                ],
            )
        )
    return CompareMatrixResponse(
        schema_version="prompt_lab.compare_matrix/v1",
        experiment_id=experiment_id,
        versions=versions,
        rows=rows,
    )


def _row_keys(
    versions: list[str],
    snapshots: dict[str, list[dict[str, Any]]],
) -> list[tuple[str, str, str, str, str]]:
    rows: dict[tuple[str, str], tuple[str, str, str, str, str]] = {}
    for version in versions:
        for validator in snapshots.get(version, []):
            validator_id = str(validator.get("validator_id", ""))
            validator_title = str(validator.get("title", validator_id))
            for check in validator.get("checks", []):
                if not isinstance(check, dict):
                    continue
                check_id = str(check.get("check_id", ""))
                rows[(validator_id, check_id)] = (
                    validator_id,
                    validator_title,
                    check_id,
                    str(check.get("title", check_id)),
                    str(check.get("description", "")),
                )
    return [rows[key] for key in sorted(rows)]


def _cell_for_version(
    *,
    version: str,
    validator_id: str,
    check_id: str,
    results: list[ValidationResultArtifact],
) -> CompareMatrixCell:
    details: list[CompareCellDetail] = []
    counts: Counter[str] = Counter()
    for result in results:
        if result.validator_id != validator_id or not result.included_in_judge:
            continue
        if result.status == "error":
            counts["error"] += 1
            details.append(
                CompareCellDetail(
                    case_id=result.case_id,
                    repeat_index=result.repeat_index,
                    validation_result_id=result.validation_result_id,
                    verdict="error",
                    comment=result.execution_error or "Validation result failed.",
                )
            )
            continue
        for check in result.check_results:
            if check.check_id != check_id or not check.included_in_judge:
                continue
            counts[check.verdict] += 1
            details.append(
                CompareCellDetail(
                    case_id=result.case_id,
                    repeat_index=result.repeat_index,
                    validation_result_id=result.validation_result_id,
                    verdict=check.verdict,
                    comment=check.comment,
                )
            )
    status = _status(counts)
    total = counts["yes"] + counts["no"] + counts["unknown"] + counts["error"]
    return CompareMatrixCell(
        version=version,
        status=status,
        yes_count=counts["yes"],
        no_count=counts["no"],
        unknown_count=counts["unknown"],
        missing_count=counts["missing"],
        error_count=counts["error"],
        total_count=total,
        details=details,
    )


def _status(counts: Counter[str]) -> str:
    total = counts["yes"] + counts["no"] + counts["unknown"] + counts["error"]
    if total == 0:
        return "empty"
    if counts["no"] > 0:
        return "fail"
    if counts["unknown"] > 0 or counts["error"] > 0:
        return "mixed"
    return "pass"
```

- [ ] **Step 4: Update compare API**

In `backend/prompt_lab/api.py`, update `/api/experiments/{experiment_id}/comparisons` to:

1. Accept two versions initially, preserving current request shape.
2. Load latest validation batch for both versions.
3. Load validator snapshots and validation results for each version.
4. Return `CompareMatrixResponse`.
5. Remove LLM generation and comparison artifact writing for MVP, or write `compare_matrix.json` if persistence is still desired.

Remove imports of `build_comparison_prompt`, `ComparisonArtifact`, and dry comparison generation where no longer used.

- [ ] **Step 5: Run compare tests**

Run:

```bash
PYTHONPATH=backend python backend/tests/test_compare.py
PYTHONPATH=backend python backend/tests/test_api.py
```

Expected: all pass.

- [ ] **Step 6: Commit deterministic compare**

Run:

```bash
git add backend/prompt_lab/compare.py backend/prompt_lab/api.py backend/tests/test_compare.py backend/tests/test_api.py
git commit -m "feat: compare validation matrices"
```

---

### Task 6: Examples And Documentation

**Files:**
- Modify: `examples/split-scenes/experiment.json`
- Create: `examples/split-scenes/validators/scene-quality.json`
- Create: `examples/split-scenes/validators/scene-count.json`
- Delete: `examples/split-scenes/rubric.md`
- Modify: `examples/summarize-chapter/experiment.json`
- Create: `examples/summarize-chapter/validators/summary-quality.json`
- Create: `examples/summarize-chapter/validators/summary-length.json`
- Delete: `examples/summarize-chapter/rubric.md`
- Modify: `FORMAT.md`
- Modify: `README.md`
- Modify: `examples/README.md`
- Modify: `DESIGN.md`
- Test: `backend/tests/test_experiment_seed.py`

- [ ] **Step 1: Update examples with validator model**

Add `validator_model` to both example manifests:

```json
"models": {
  "generator_model": "local/gpt-oss-120b",
  "validator_model": "openai/example-large-model",
  "judge_model": "openai/example-large-model"
}
```

- [ ] **Step 2: Add split-scenes validators**

Create `examples/split-scenes/validators/scene-quality.json`:

```json
{
  "schema_version": "prompt_lab.validator/v1",
  "validator_id": "scene-quality",
  "type": "llm_questionnaire",
  "title": "Scene quality",
  "description": "Checks whether structured scenes preserve source content and useful boundaries.",
  "enabled": true,
  "input_scope": "output_and_case",
  "checks": [
    {
      "check_id": "coverage",
      "title": "Coverage",
      "question": "Does the scene list cover every important source event without omission?",
      "description": "Compare the output to the source case context."
    },
    {
      "check_id": "order",
      "title": "Order",
      "question": "Are scenes in the same order as the source?"
    },
    {
      "check_id": "boundaries",
      "title": "Scene boundaries",
      "question": "Are scene boundaries based on stable place, continuous time, immediate focus, cast changes, or persistent mode shifts?"
    },
    {
      "check_id": "no-hallucinations",
      "title": "No hallucinations",
      "question": "Does the output avoid inventing events not present in the source?"
    },
    {
      "check_id": "concise-labels",
      "title": "Concise labels",
      "question": "Are scene titles and summaries concise and specific?"
    }
  ]
}
```

Create `examples/split-scenes/validators/scene-count.json`:

```json
{
  "schema_version": "prompt_lab.validator/v1",
  "validator_id": "scene-count",
  "type": "automatic",
  "title": "Scene count",
  "description": "Checks that structured output includes at least one scene.",
  "enabled": true,
  "input_scope": "output_only",
  "checks": [
    {
      "check_id": "has-scenes",
      "title": "Has scenes",
      "description": "Scene list contains at least one item.",
      "rule": {
        "kind": "json_path_count",
        "source": "output_json",
        "path": "scenes",
        "comparison": {
          "op": "gte",
          "value": 1
        }
      }
    }
  ]
}
```

- [ ] **Step 3: Add summarize-chapter validators**

Create `examples/summarize-chapter/validators/summary-quality.json`:

```json
{
  "schema_version": "prompt_lab.validator/v1",
  "validator_id": "summary-quality",
  "type": "llm_questionnaire",
  "title": "Summary quality",
  "description": "Checks whether a chapter summary is faithful and useful for later processing.",
  "enabled": true,
  "input_scope": "output_and_case",
  "checks": [
    {
      "check_id": "completeness",
      "title": "Completeness",
      "question": "Does the summary preserve the key events and context from the source?"
    },
    {
      "check_id": "no-hallucinations",
      "title": "No hallucinations",
      "question": "Does the summary avoid adding facts not present in the source?"
    },
    {
      "check_id": "future-context",
      "title": "Future context",
      "question": "Would this summary be useful as context for processing later story parts?"
    }
  ]
}
```

Create `examples/summarize-chapter/validators/summary-length.json`:

```json
{
  "schema_version": "prompt_lab.validator/v1",
  "validator_id": "summary-length",
  "type": "automatic",
  "title": "Summary length",
  "description": "Checks that summary length stays compact.",
  "enabled": true,
  "input_scope": "output_only",
  "checks": [
    {
      "check_id": "word-count",
      "title": "Word count",
      "description": "Summary is at most 180 words.",
      "rule": {
        "kind": "word_count",
        "source": "output_text",
        "comparison": {
          "op": "lte",
          "value": 180
        }
      }
    }
  ]
}
```

- [ ] **Step 4: Remove example rubric files**

Run:

```bash
git rm examples/split-scenes/rubric.md examples/summarize-chapter/rubric.md
```

Expected: both files staged for deletion.

- [ ] **Step 5: Update docs**

Update documentation to describe:

- `validators/` directory.
- `validator_model`.
- `Validate active run` between run and judge.
- deterministic compare matrix.
- no migration for existing runtime experiments.

In `README.md` smoke flow, change steps to:

```text
5. Run the active version.
6. Validate the active run.
7. Review validation results and optionally exclude weak evidence.
8. Judge the validated run.
9. Reject or defer at least one finding and add human notes.
10. Generate a proposal.
11. Create the next version.
12. Compare validation results between versions.
```

- [ ] **Step 6: Run seed and format tests**

Run:

```bash
PYTHONPATH=backend python backend/tests/test_experiment_seed.py
PYTHONPATH=backend python backend/tests/test_config.py
```

Expected: all pass.

- [ ] **Step 7: Commit examples and docs**

Run:

```bash
git add examples FORMAT.md README.md examples/README.md DESIGN.md backend/tests/test_experiment_seed.py
git commit -m "docs: update examples for validators"
```

---

### Task 7: Frontend Types, API, And Workflow State

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/workflowActions.ts`
- Modify: `frontend/src/urlState.ts`
- Modify: `frontend/src/components/WorkbenchTabs.tsx`
- Test: `frontend/tests/workflowActions.test.ts`
- Test: `frontend/tests/urlState.test.ts`

- [ ] **Step 1: Write frontend workflow tests**

In `frontend/tests/workflowActions.test.ts`, add:

```ts
import { describe, expect, it } from "vitest";
import { getJudgeActionState, getValidateActionState } from "../src/workflowActions.ts";

describe("validation workflow actions", () => {
  it("requires runs before validation", () => {
    expect(
      getValidateActionState({ hasRuns: false, hasValidation: false, isBusy: false })
    ).toEqual({
      disabled: true,
      disabledReason: "Create a run before validating.",
      label: "Validate active run"
    });
  });

  it("requires validation before judge", () => {
    expect(
      getJudgeActionState({
        hasReview: false,
        hasRuns: true,
        hasValidation: false,
        isBusy: false
      }).disabledReason
    ).toBe("Validate the active run before judging.");
  });
});
```

In `frontend/tests/urlState.test.ts`, assert `validation` is parsed:

```ts
expect(parseExperimentRoute(new URL("http://x.test/demo/validation"))).toEqual({
  experimentId: "demo",
  tab: "validation"
});
```

- [ ] **Step 2: Run frontend tests and verify failure**

Run:

```bash
cd frontend
pnpm test -- workflowActions.test.ts urlState.test.ts
```

Expected: fails because `validation` tab and `getValidateActionState` do not exist.

- [ ] **Step 3: Update frontend types**

In `frontend/src/types.ts`, add `validator_model`:

```ts
models: {
  generator_model: string;
  validator_model: string;
  judge_model: string;
};
```

Add validator and validation types matching backend JSON:

```ts
export type ValidatorType = "llm_questionnaire" | "automatic";
export type InputScope =
  | "output_only"
  | "output_and_prompt"
  | "output_and_case"
  | "output_prompt_and_case";
export type ValidationVerdict = "yes" | "no" | "unknown";
export type ValidationResultStatus = "ok" | "error";

export interface ValidatorCheck {
  check_id: string;
  title: string;
  question?: string;
  description?: string;
  rule?: Record<string, unknown>;
}

export interface ValidatorDefinition {
  schema_version: "prompt_lab.validator/v1";
  validator_id: string;
  type: ValidatorType;
  title: string;
  description: string;
  enabled: boolean;
  input_scope: InputScope;
  checks: ValidatorCheck[];
}

export interface ValidationBatch {
  schema_version: "prompt_lab.validation_batch/v1";
  validation_batch_id: string;
  run_batch_id: string;
  version: string;
  status: "running" | "completed" | "failed" | "cancelled";
  started_at: string;
  finished_at?: string | null;
  total_results: number;
  completed_results: number;
  validator_model: string;
  validator_ids: string[];
}

export interface ValidationCheckResult {
  check_id: string;
  verdict: ValidationVerdict;
  comment: string;
  included_in_judge: boolean;
  metrics: Record<string, unknown>;
}

export interface ValidationResult {
  schema_version: "prompt_lab.validation_result/v1";
  validation_result_id: string;
  validation_batch_id: string;
  run_batch_id: string;
  run_id: string;
  case_id: string;
  repeat_index: number;
  validator_id: string;
  validator_type: ValidatorType;
  status: ValidationResultStatus;
  included_in_judge: boolean;
  check_results: ValidationCheckResult[];
  usage: Record<string, unknown>;
  execution_error?: string | null;
}

export interface ValidationState {
  validation_batch: ValidationBatch;
  validators: ValidatorDefinition[];
  results: ValidationResult[];
}
```

Replace old `ComparisonArtifact` response with compare matrix types from backend.

- [ ] **Step 4: Update API helpers**

In `frontend/src/api.ts`, add:

```ts
export function validateVersion(
  experimentId: string,
  version: string,
  dryRun = false
): Promise<JobStatus> {
  return apiPost<JobStatus>(
    `/api/experiments/${encodeURIComponent(experimentId)}/versions/${encodeURIComponent(
      version
    )}/validations`,
    dryRun ? { dry_run: true } : undefined
  );
}

export async function getLatestValidationState(
  experimentId: string,
  version: string
): Promise<ValidationState | null> {
  const response = await fetch(
    `/api/experiments/${encodeURIComponent(experimentId)}/versions/${encodeURIComponent(
      version
    )}/validations/latest`
  );
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(await readErrorMessage(response));
  return response.json() as Promise<ValidationState>;
}

export function updateValidationInclusion(
  experimentId: string,
  version: string,
  validationBatchId: string,
  update: ValidationInclusionUpdate
): Promise<ValidationState> {
  return apiPut<ValidationState>(
    `/api/experiments/${encodeURIComponent(experimentId)}/versions/${encodeURIComponent(
      version
    )}/validations/${encodeURIComponent(validationBatchId)}/inclusion`,
    update
  );
}
```

Update `compareVersions()` to return `CompareMatrixResponse`.

- [ ] **Step 5: Update tabs and action states**

In `frontend/src/urlState.ts`, insert `"validation"` after `"runs"`.

In `WorkbenchTabs.tsx`, add:

```ts
validation: "Validation",
```

In `workflowActions.ts`, add `hasValidation` to `JudgeActionInput` and add:

```ts
export function getValidateActionState({
  hasRuns,
  hasValidation,
  isBusy
}: {
  hasRuns: boolean;
  hasValidation: boolean;
  isBusy: boolean;
}): ActionState {
  if (isBusy) {
    return {
      disabled: true,
      disabledReason: "Wait for the current workflow action to finish.",
      label: "Validating..."
    };
  }
  if (!hasRuns) {
    return {
      disabled: true,
      disabledReason: "Create a run before validating.",
      label: "Validate active run"
    };
  }
  return {
    disabled: false,
    disabledReason: null,
    label: hasValidation ? "Revalidate active run" : "Validate active run"
  };
}
```

In `getJudgeActionState()`, return disabled when `hasValidation` is false:

```ts
if (!hasValidation) {
  return {
    disabled: true,
    disabledReason: "Validate the active run before judging.",
    label: "Judge validated run"
  };
}
```

- [ ] **Step 6: Run frontend workflow tests**

Run:

```bash
cd frontend
pnpm test -- workflowActions.test.ts urlState.test.ts
```

Expected: all pass.

- [ ] **Step 7: Commit frontend contracts**

Run:

```bash
git add frontend/src/types.ts frontend/src/api.ts frontend/src/workflowActions.ts frontend/src/urlState.ts frontend/src/components/WorkbenchTabs.tsx frontend/tests/workflowActions.test.ts frontend/tests/urlState.test.ts
git commit -m "feat: add frontend validation contracts"
```

---

### Task 8: Frontend Validation, Settings, And Compare UI

**Files:**
- Create: `frontend/src/components/ValidationView.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/ExperimentSettings.tsx`
- Modify: `frontend/src/components/GlobalSettings.tsx`
- Modify: `frontend/src/components/ComparisonView.tsx`
- Modify: `frontend/src/styles.css`
- Test: `frontend/tests/validationView.test.ts`
- Test: `frontend/tests/workflowActions.test.ts`

- [ ] **Step 1: Write validation view helper tests**

Add `frontend/tests/validationView.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { buildValidationInclusionUpdate } from "../src/components/ValidationView.tsx";
import type { ValidationState } from "../src/types.ts";

function state(): ValidationState {
  return {
    validation_batch: {
      schema_version: "prompt_lab.validation_batch/v1",
      validation_batch_id: "validation-001",
      run_batch_id: "run-001",
      version: "v001",
      status: "completed",
      started_at: "2026-06-19T00:00:00Z",
      finished_at: "2026-06-19T00:01:00Z",
      total_results: 1,
      completed_results: 1,
      validator_model: "openai/validator",
      validator_ids: ["quality"]
    },
    validators: [],
    results: [
      {
        schema_version: "prompt_lab.validation_result/v1",
        validation_result_id: "result-001",
        validation_batch_id: "validation-001",
        run_batch_id: "run-001",
        run_id: "run-001-case-a-repeat-001",
        case_id: "case-a",
        repeat_index: 1,
        validator_id: "quality",
        validator_type: "llm_questionnaire",
        status: "ok",
        included_in_judge: true,
        check_results: [
          {
            check_id: "coverage",
            verdict: "yes",
            comment: "Good.",
            included_in_judge: false,
            metrics: {}
          }
        ],
        usage: {}
      }
    ]
  };
}

describe("buildValidationInclusionUpdate", () => {
  it("serializes result and check inclusion", () => {
    expect(buildValidationInclusionUpdate(state())).toEqual({
      results: [
        {
          validation_result_id: "result-001",
          included_in_judge: true,
          check_results: [
            {
              check_id: "coverage",
              included_in_judge: false
            }
          ]
        }
      ]
    });
  });
});
```

- [ ] **Step 2: Run validation view test and verify failure**

Run:

```bash
cd frontend
pnpm test -- validationView.test.ts
```

Expected: fails because `ValidationView.tsx` does not exist.

- [ ] **Step 3: Implement ValidationView**

Create `frontend/src/components/ValidationView.tsx`:

```tsx
import type { ValidationInclusionUpdate, ValidationState } from "../types";
import { TooltipButton } from "./TooltipButton";

interface ValidationViewProps {
  validationState: ValidationState | null;
  isBusy: boolean;
  hasUnsavedChanges: boolean;
  onValidate: () => void;
  onStateChange: (state: ValidationState) => void;
  onSaveInclusion: () => void;
}

export function buildValidationInclusionUpdate(
  state: ValidationState
): ValidationInclusionUpdate {
  return {
    results: state.results.map((result) => ({
      validation_result_id: result.validation_result_id,
      included_in_judge: result.included_in_judge,
      check_results: result.check_results.map((check) => ({
        check_id: check.check_id,
        included_in_judge: check.included_in_judge
      }))
    }))
  };
}

export function ValidationView({
  validationState,
  isBusy,
  hasUnsavedChanges,
  onValidate,
  onStateChange,
  onSaveInclusion
}: ValidationViewProps) {
  function updateResult(resultId: string, included: boolean) {
    if (validationState === null) return;
    onStateChange({
      ...validationState,
      results: validationState.results.map((result) =>
        result.validation_result_id === resultId
          ? { ...result, included_in_judge: included }
          : result
      )
    });
  }

  function updateCheck(resultId: string, checkId: string, included: boolean) {
    if (validationState === null) return;
    onStateChange({
      ...validationState,
      results: validationState.results.map((result) =>
        result.validation_result_id === resultId
          ? {
              ...result,
              check_results: result.check_results.map((check) =>
                check.check_id === checkId
                  ? { ...check, included_in_judge: included }
                  : check
              )
            }
          : result
      )
    });
  }

  return (
    <section className="validation-panel" aria-label="Validation">
      <div className="section-heading">
        <h3>Validation</h3>
        <div className="section-actions">
          <TooltipButton
            className="secondary-action"
            disabled={isBusy}
            disabledReason="Wait for the current workflow action to finish."
            onClick={onValidate}
            type="button"
          >
            {isBusy ? "Validating..." : "Validate active run"}
          </TooltipButton>
          <TooltipButton
            className="secondary-action"
            disabled={isBusy || !hasUnsavedChanges || validationState === null}
            disabledReason={
              isBusy
                ? "Wait for the current workflow action to finish."
                : "Change validation inclusion before saving."
            }
            onClick={onSaveInclusion}
            type="button"
          >
            Save inclusion
          </TooltipButton>
        </div>
      </div>

      {validationState === null ? (
        <div className="empty-inline">
          No validation loaded. Run this version, then validate the active run.
        </div>
      ) : (
        <div className="validation-content">
          <p className="muted-copy">
            Batch {validationState.validation_batch.validation_batch_id} for run{" "}
            {validationState.validation_batch.run_batch_id}
          </p>
          {hasUnsavedChanges ? (
            <p className="dirty-copy">Unsaved validation inclusion changes.</p>
          ) : null}
          {validationState.results.map((result) => (
            <article className="validation-card" key={result.validation_result_id}>
              <div className="validation-card-header">
                <label>
                  <input
                    checked={result.included_in_judge}
                    disabled={isBusy}
                    onChange={(event) =>
                      updateResult(
                        result.validation_result_id,
                        event.currentTarget.checked
                      )
                    }
                    type="checkbox"
                  />
                  Include result
                </label>
                <strong>
                  {result.case_id} repeat {result.repeat_index} ·{" "}
                  {result.validator_id}
                </strong>
                <span>{result.status}</span>
              </div>
              {result.execution_error ? (
                <p className="error-copy">{result.execution_error}</p>
              ) : null}
              <div className="validation-checks">
                {result.check_results.map((check) => (
                  <div className="validation-check" key={check.check_id}>
                    <label>
                      <input
                        checked={check.included_in_judge}
                        disabled={isBusy}
                        onChange={(event) =>
                          updateCheck(
                            result.validation_result_id,
                            check.check_id,
                            event.currentTarget.checked
                          )
                        }
                        type="checkbox"
                      />
                      Include check
                    </label>
                    <span className={`verdict-pill verdict-${check.verdict}`}>
                      {check.verdict}
                    </span>
                    <strong>{check.check_id}</strong>
                    <p>{check.comment}</p>
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 4: Update App state and handlers**

In `frontend/src/App.tsx`:

1. Import `ValidationView`, validation API helpers, and `buildValidationInclusionUpdate`.
2. Add state:

```ts
const [validationState, setValidationState] = useState<ValidationState | null>(null);
const [validationDirty, setValidationDirty] = useState(false);
```

3. Load latest validation state in `loadDetails()` and `refreshSelectedVersionArtifacts()`.
4. Clear validation on run.
5. Add `handleValidateVersion()` using `validateVersion()` and `followJobEvents()`.
6. Add `handleSaveValidationInclusion()`.
7. Pass `hasValidation: validationState !== null` into `getJudgeActionState()`.
8. Render `ValidationView` when `activeTab === "validation"`.

Use this handler pattern:

```ts
async function handleValidateVersion() {
  if (selectedExperiment === null || detailState.status !== "loaded") return;
  if (workflowLocked) {
    setWorkflowMessage("Wait for the current workflow action to finish.");
    return;
  }
  const experimentId = selectedExperiment.id;
  const version = selectedExperiment.active_version;
  const selectionKey = `${experimentId}:${version}`;
  const dryRun = workflowMode === "dry-run";
  const requestId = beginWorkflow(
    selectionKey,
    dryRun ? "Dry-run validating active run..." : "Validating active run..."
  );
  try {
    let job = await validateVersion(experimentId, version, dryRun);
    job = await followJobEvents(job.job_id, job, () =>
      isWorkflowCurrent(requestId, selectionKey)
    );
    if (job.status === "failed") throw new Error(job.message || "Validation failed.");
    const latestValidation = await getLatestValidationState(experimentId, version);
    if (!isWorkflowCurrent(requestId, selectionKey)) return;
    setValidationState(latestValidation);
    setValidationDirty(false);
    setReviewState(null);
    setProposalResponse(null);
    setComparison(null);
    setWorkflowMessage("Validation completed.");
    activateTab("validation");
  } catch (error) {
    if (isWorkflowCurrent(requestId, selectionKey)) {
      setWorkflowMessage(error instanceof Error ? error.message : "Unknown error");
    }
  } finally {
    if (isWorkflowCurrent(requestId, selectionKey)) {
      setWorkflowBusy(false);
    }
  }
}
```

- [ ] **Step 5: Update settings components**

In `ExperimentSettings.tsx`, add Validator model input between generator and judge:

```tsx
<label className="settings-field">
  <span>Validator model</span>
  <input
    required
    value={draft.models.validator_model}
    onChange={(event) =>
      updateDraft((current) => ({
        ...current,
        models: {
          ...current.models,
          validator_model: event.target.value
        }
      }))
    }
  />
</label>
```

In `GlobalSettings.tsx`, include `default_validator_model` in `prepareForSave()`, required validation, and form field.

- [ ] **Step 6: Update ComparisonView**

Change `ComparisonView` to render matrix rows from `CompareMatrixResponse`.

For each cell, use class:

```tsx
className={`compare-cell compare-cell-${cell.status}`}
```

Display:

```tsx
<strong>{cell.yes_count}/{cell.total_count} yes</strong>
<span>{cell.no_count} no · {cell.unknown_count} unknown · {cell.error_count} error</span>
```

Render details inside `<details>` so comments remain available without a modal.

- [ ] **Step 7: Add CSS**

In `frontend/src/styles.css`, add classes:

```css
.validation-content,
.validation-checks {
  display: grid;
  gap: 12px;
}

.validation-card,
.validation-check {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
}

.validation-card-header,
.section-actions {
  align-items: center;
  display: flex;
  gap: 12px;
  justify-content: space-between;
}

.verdict-pill,
.recommendation-pill {
  border-radius: 999px;
  font-size: 12px;
  padding: 2px 8px;
}

.verdict-yes,
.compare-cell-pass {
  background: #e7f6ed;
}

.verdict-no,
.compare-cell-fail {
  background: #fde8e8;
}

.verdict-unknown,
.compare-cell-mixed {
  background: #fff4d6;
}

.compare-cell-empty {
  background: #f2f4f7;
}

.compare-matrix {
  border-collapse: collapse;
  width: 100%;
}

.compare-matrix th,
.compare-matrix td {
  border: 1px solid var(--border);
  padding: 8px;
  vertical-align: top;
}
```

Use existing CSS variables if names differ; do not introduce a new one-note palette.

- [ ] **Step 8: Run frontend checks**

Run:

```bash
cd frontend
pnpm test -- validationView.test.ts workflowActions.test.ts urlState.test.ts
pnpm build
```

Expected: tests and build pass.

- [ ] **Step 9: Commit frontend UI**

Run:

```bash
git add frontend/src frontend/tests
git commit -m "feat: add validation UI"
```

---

### Task 9: Final Verification

**Files:**
- Verify all changed files.
- No code changes unless a verification failure points to a specific defect.

- [ ] **Step 1: Run required backend checks from AGENTS.md**

Run:

```bash
PYTHONPATH=backend python backend/tests/test_chat.py
PYTHONPATH=backend python backend/tests/test_chat_get_structured_lite.py
PYTHONPATH=backend python backend/tests/test_structured_lite_units.py
PYTHONPATH=backend python backend/tests/test_format_validation_errors.py
pyright --pythonpath .venv/bin/python
```

Expected: all pass. If `pyright` is only available under `.venv/bin/pyright`, run:

```bash
.venv/bin/pyright --project pyrightconfig.json --pythonpath .venv/bin/python
```

- [ ] **Step 2: Run focused backend suite**

Run:

```bash
PYTHONPATH=backend python backend/tests/test_validators.py
PYTHONPATH=backend python backend/tests/test_automatic_validators.py
PYTHONPATH=backend python backend/tests/test_validation.py
PYTHONPATH=backend python backend/tests/test_judge.py
PYTHONPATH=backend python backend/tests/test_proposal.py
PYTHONPATH=backend python backend/tests/test_compare.py
PYTHONPATH=backend python backend/tests/test_api.py
PYTHONPATH=backend python backend/tests/test_settings.py
PYTHONPATH=backend python backend/tests/test_experiment_seed.py
```

Expected: all pass.

- [ ] **Step 3: Run frontend checks**

Run:

```bash
cd frontend
pnpm test
pnpm build
```

Expected: all pass.

- [ ] **Step 4: Browser smoke**

Start servers if they are not already running:

```bash
PYTHONPATH=backend .venv/bin/python -m uvicorn prompt_lab.app:app --reload
cd frontend
pnpm dev
```

Open the app and exercise dry-run mode:

1. Open `http://127.0.0.1:5173/split-scenes/overview`.
2. Enable dry-run controls if available.
3. Run active version.
4. Validate active run.
5. Open Validation tab and toggle one check inclusion.
6. Save inclusion.
7. Judge validated run.
8. Generate proposal.
9. Create next version.
10. Compare versions and verify matrix cells render.

Expected: no console errors, no overlapping text, and each workflow action reaches a completed state.

- [ ] **Step 5: Final status and commit if fixes were needed**

Run:

```bash
git status --short
```

Expected: clean worktree if all task commits were made. If verification fixes were needed, commit them:

```bash
git add <fixed-files>
git commit -m "fix: stabilize validator pipeline"
```

---

## Plan Self-Review

Spec coverage:

- Validator definitions and `validators/`: Tasks 1, 2, 6.
- `validator_model` and global settings: Tasks 1, 7, 8.
- Required validation stage: Tasks 3, 7, 8.
- LLM questionnaire and automatic validators: Tasks 2, 3, 6.
- Human validators left for later: Task 1 contracts do not implement human type.
- Inclusion at result and check level: Tasks 1, 3, 8.
- Judge without raw outputs or rubric: Task 4.
- Proposal without rubric snapshot: Task 4.
- Deterministic compare: Task 5 and Task 8.
- Examples and docs: Task 6.
- Verification: Task 9.

Placeholder scan:

- No open-ended placeholder markers are used.
- Each implementation task has concrete file paths, commands, and expected results.
- The plan intentionally keeps exact final UI layout modest because the existing app design should guide component polish during implementation.

Type consistency:

- Backend `ValidationState`, `ValidationInclusionUpdate`, and `CompareMatrixResponse` names match frontend type names.
- `validator_model` is used consistently in backend settings, manifest model, and frontend settings forms.
- Compare status values are consistently `pass`, `fail`, `mixed`, and `empty`.
