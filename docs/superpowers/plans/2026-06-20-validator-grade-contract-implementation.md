# Validator Grade Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace validator check `verdict` values with a global `grade: 1..5 | null` contract across backend artifacts, LLM validator prompts, automatic validators, compare, judge evidence, frontend UI, tests, and demo artifacts.

**Architecture:** This is a breaking validation artifact change. The canonical contract lives in `backend/prompt_lab/models/validators.py`; all generators, API evidence builders, compare aggregation, and frontend types should consume that contract directly. Existing runtime artifacts are not migrated, but committed demo/example artifacts must be updated so tests and manual UI checks exercise the new shape.

**Tech Stack:** Python 3.14, Pydantic v2, FastAPI TestClient, React/Vite TypeScript, Node test runner, filesystem JSON artifacts.

---

## File Structure

- `backend/prompt_lab/models/validators.py`: canonical Pydantic contract for validation check results, LLM questionnaire responses, and compare matrix cells.
- `backend/prompt_lab/validation.py`: LLM validator result construction and check-id validation.
- `backend/prompt_lab/system_prompts/validator.md.jinja`: global grade-scale instructions for LLM validators.
- `backend/prompt_lab/automatic_validators.py`: binary automatic-rule result mapping to `grade: 5` or `grade: 1`.
- `backend/prompt_lab/api.py`: validation evidence sent to judge and validation/compare invariant checks.
- `backend/prompt_lab/compare.py`: deterministic grade aggregation for comparison.
- `frontend/src/types.ts`: TypeScript mirrors of validation and compare contracts.
- `frontend/src/components/validationMatrix.ts`: frontend validation matrix cell model.
- `frontend/src/components/ValidationView.tsx`: grade display and aggregate status in the validation tab.
- `frontend/src/components/ComparisonView.tsx`: grade count summaries and detail display in comparison UI.
- `frontend/src/styles.css`: grade/status visual treatment.
- `backend/tests/*`, `frontend/tests/*`: contract, builder, automatic validator, compare, judge/proposal, and UI tests.
- `examples/demo-string/**`, `examples/demo-json/**`: committed validation and review artifacts updated from `verdict` to `grade`.
- `DESIGN.md`, `FORMAT.md`, `docs/superpowers/specs/2026-06-19-validator-pipeline-design.md`: docs updated to reference grades.

## Task 1: Backend Validation Grade Contract

**Files:**
- Modify: `backend/prompt_lab/models/validators.py`
- Modify: `backend/tests/test_validators.py`
- Modify: `backend/tests/test_storage.py`

- [ ] **Step 1: Write failing model-contract tests**

In `backend/tests/test_validators.py`, update `test_validation_batch_and_result_artifacts_accept_expected_fields` so the check result uses `grade`, not `verdict`:

```python
"check_results": [
    {
        "check_id": "direct",
        "grade": 4,
        "comment": "The answer is direct.",
        "included_in_judge": True,
        "metrics": {"word_count": 42},
    }
],
```

Replace the assertions for the first check with:

```python
assert result.check_results[0].grade == 4
assert result.check_results[0].comment == "The answer is direct."
assert result.check_results[0].included_in_judge is True
assert result.check_results[0].metrics == {"word_count": 42}
```

Add these tests below `test_validation_batch_and_result_artifacts_accept_expected_fields`:

```python
def test_validation_check_result_accepts_null_grade_with_comment() -> None:
    result = ValidationResultArtifact.model_validate(
        {
            "schema_version": "prompt_lab.validation_result/v1",
            "validation_result_id": "result-001",
            "validation_batch_id": "validation-001",
            "run_batch_id": "run-001",
            "run_id": "run-001-case-a-1",
            "case_id": "case-a",
            "repeat_index": 1,
            "validator_id": "clarity",
            "validator_type": "llm_questionnaire",
            "status": "ok",
            "included_in_judge": True,
            "check_results": [
                {
                    "check_id": "direct",
                    "grade": None,
                    "comment": "The provided output does not include enough evidence.",
                    "included_in_judge": True,
                    "metrics": {},
                }
            ],
            "usage": {},
        }
    )

    assert result.check_results[0].grade is None


def test_validation_check_result_rejects_out_of_range_grade() -> None:
    try:
        ValidationResultArtifact.model_validate(
            {
                "schema_version": "prompt_lab.validation_result/v1",
                "validation_result_id": "result-001",
                "validation_batch_id": "validation-001",
                "run_batch_id": "run-001",
                "run_id": "run-001-case-a-1",
                "case_id": "case-a",
                "repeat_index": 1,
                "validator_id": "clarity",
                "validator_type": "llm_questionnaire",
                "status": "ok",
                "included_in_judge": True,
                "check_results": [
                    {
                        "check_id": "direct",
                        "grade": 6,
                        "comment": "Out of range.",
                        "included_in_judge": True,
                        "metrics": {},
                    }
                ],
                "usage": {},
            }
        )
    except ValidationError as exc:
        assert "Input should be 1, 2, 3, 4 or 5" in str(exc)
    else:
        raise AssertionError("Expected out-of-range grade to be rejected")


def test_validation_check_result_rejects_verdict_field() -> None:
    try:
        ValidationResultArtifact.model_validate(
            {
                "schema_version": "prompt_lab.validation_result/v1",
                "validation_result_id": "result-001",
                "validation_batch_id": "validation-001",
                "run_batch_id": "run-001",
                "run_id": "run-001-case-a-1",
                "case_id": "case-a",
                "repeat_index": 1,
                "validator_id": "clarity",
                "validator_type": "llm_questionnaire",
                "status": "ok",
                "included_in_judge": True,
                "check_results": [
                    {
                        "check_id": "direct",
                        "verdict": "yes",
                        "comment": "Old shape.",
                        "included_in_judge": True,
                        "metrics": {},
                    }
                ],
                "usage": {},
            }
        )
    except ValidationError as exc:
        assert "grade" in str(exc)
        assert "verdict" in str(exc)
    else:
        raise AssertionError("Expected old verdict shape to be rejected")
```

Add the three new test functions to the `tests = [...]` list in `main()`.

In `backend/tests/test_storage.py`, replace the validation-result fixture check payload from:

```python
"verdict": "yes",
```

to:

```python
"grade": 5,
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_validators.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_storage.py
```

Expected: `test_validators.py` fails because `grade` is not a field yet and old `verdict` is still required. `test_storage.py` may fail for the same reason.

- [ ] **Step 3: Implement the Pydantic contract**

In `backend/prompt_lab/models/validators.py`, replace:

```python
ValidationVerdict = Literal["yes", "no", "unknown"]
ComparisonStatus = Literal["pass", "fail", "mixed", "empty"]
```

with:

```python
ValidationGrade = Literal[1, 2, 3, 4, 5] | None
CompareDetailStatus = Literal["graded", "not_assessable", "error"]
ComparisonStatus = Literal["pass", "fail", "mixed", "empty"]
```

Replace `ValidationCheckResult` with:

```python
class ValidationCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: NonEmptyString
    grade: ValidationGrade
    comment: str = ""
    included_in_judge: bool = True
    metrics: JsonObject = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_null_grade_comment(self) -> Self:
        if self.grade is None and self.comment.strip() == "":
            raise ValueError("null grade requires comment")
        return self
```

Replace `LlmQuestionnaireCheckResponse` with:

```python
class LlmQuestionnaireCheckResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: NonEmptyString
    grade: ValidationGrade
    comment: NonEmptyString
```

Replace `CompareCellDetail` and `CompareMatrixCell` with:

```python
class CompareCellDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: NonEmptyString
    repeat_index: int = Field(ge=1)
    validation_result_id: NonEmptyString
    status: CompareDetailStatus
    grade: ValidationGrade
    comment: str = ""


class CompareMatrixCell(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: NonEmptyString
    status: ComparisonStatus
    grade_5: int = Field(ge=0)
    grade_4: int = Field(ge=0)
    grade_3: int = Field(ge=0)
    grade_2: int = Field(ge=0)
    grade_1: int = Field(ge=0)
    not_assessable: int = Field(ge=0)
    missing: int = Field(ge=0)
    error: int = Field(ge=0)
    total: int = Field(ge=0)
    details: list[CompareCellDetail]
```

- [ ] **Step 4: Run contract tests to verify they pass**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_validators.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_storage.py
```

Expected: both commands pass.

- [ ] **Step 5: Commit backend contract**

Run:

```bash
git add backend/prompt_lab/models/validators.py backend/tests/test_validators.py backend/tests/test_storage.py
git commit -m "Replace validation verdict with grade contract"
```

## Task 2: LLM Validator Prompt And Result Builder

**Files:**
- Modify: `backend/prompt_lab/validation.py`
- Modify: `backend/prompt_lab/system_prompts/validator.md.jinja`
- Modify: `backend/tests/test_validation.py`
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Write failing LLM validator tests**

In `backend/tests/test_validation.py`, update `_validation_result()` check payload to:

```python
"check_results": [
    {
        "check_id": "has-answer",
        "grade": 5,
        "comment": "ok",
        "included_in_judge": True,
        "metrics": {},
    }
],
```

Add this import:

```python
from prompt_lab.models.validators import LlmQuestionnaireResponse
```

Add this test after `test_build_llm_validator_prompt_respects_output_only_input_scope`:

```python
def test_build_llm_validator_prompt_defines_global_grade_scale() -> None:
    prompt = build_llm_validator_prompt(
        experiment_id="demo",
        version="v001",
        validation_batch_id="validation-001",
        validator=_validator(),
        run=_run_artifact(),
        case=_case_artifact(),
        case_context={},
    )

    assert "Use `5` for very good" in prompt
    assert "Use `4` for good" in prompt
    assert "Use `3` for acceptable but improvable" in prompt
    assert "Use `2` for weak" in prompt
    assert "Use `1` for bad" in prompt
    assert "Use `null` only when" in prompt
    assert "Use `yes`" not in prompt
    assert "Use `no`" not in prompt
    assert "Use `unknown`" not in prompt
```

Add this test after the prompt tests:

```python
def test_build_llm_validation_result_records_grades() -> None:
    result = build_llm_validation_result(
        "validation-001",
        _run_artifact(),
        _validator(),
        LlmQuestionnaireResponse.model_validate(
            {
                "check_results": [
                    {
                        "check_id": "has-answer",
                        "grade": 4,
                        "comment": "Good with minor omissions.",
                    }
                ]
            }
        ),
        usage={"total_tokens": 7},
    )

    assert result.status == "ok"
    assert result.check_results[0].grade == 4
    assert result.check_results[0].comment == "Good with minor omissions."
    assert result.check_results[0].included_in_judge is True
    assert result.usage == {"total_tokens": 7}
```

Add both new tests to `main()`.

In `backend/tests/test_api.py`, replace every fake LLM validator response shape:

```python
"verdict": "yes",
```

with:

```python
"grade": 5,
```

and replace failure examples:

```python
"verdict": "no",
```

with:

```python
"grade": 1,
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_validation.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_api.py
```

Expected: failures mention missing `grade` handling in `build_llm_validation_result` and stale validator prompt wording.

- [ ] **Step 3: Update LLM result construction**

In `backend/prompt_lab/validation.py`, replace the `ValidationCheckResult(...)` construction in `build_llm_validation_result` with:

```python
ValidationCheckResult(
    check_id=check_result.check_id,
    grade=check_result.grade,
    comment=check_result.comment,
    included_in_judge=True,
).model_dump(mode="json")
```

- [ ] **Step 4: Update validator prompt wording**

In `backend/prompt_lab/system_prompts/validator.md.jinja`, replace the three verdict rules:

```markdown
- Use `yes` when the provided context clearly satisfies the check.
- Use `no` when the provided context clearly fails the check.
- Use `unknown` when the provided context is insufficient or ambiguous.
```

with:

```markdown
- Use `5` for very good: the result satisfies the check with no meaningful issue.
- Use `4` for good: the result satisfies the check with minor improvement opportunities.
- Use `3` for acceptable but improvable: the result partially satisfies the check.
- Use `2` for weak: the result mostly fails the check, but contains some useful evidence.
- Use `1` for bad: the result fails the check.
- Use `null` only when the provided evidence is insufficient or ambiguous.
- Do not use `3` as a substitute for missing evidence.
```

- [ ] **Step 5: Run LLM validator tests**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_validation.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_api.py
```

Expected: both commands pass.

- [ ] **Step 6: Commit LLM validator grade flow**

Run:

```bash
git add backend/prompt_lab/validation.py backend/prompt_lab/system_prompts/validator.md.jinja backend/tests/test_validation.py backend/tests/test_api.py
git commit -m "Grade LLM validation checks"
```

## Task 3: Automatic Validators Map Binary Results To Grades

**Files:**
- Modify: `backend/prompt_lab/automatic_validators.py`
- Modify: `backend/tests/test_automatic_validators.py`

- [ ] **Step 1: Write failing automatic-validator tests**

In `backend/tests/test_automatic_validators.py`, replace pass assertions:

```python
assert result.check_results[0].verdict == "yes"
```

with:

```python
assert result.check_results[0].grade == 5
```

Add this test after `test_word_count_rule_passes_lte_limit`:

```python
def test_word_count_rule_failure_maps_to_min_grade() -> None:
    result = execute_automatic_validator(
        "validation-001",
        _run_artifact(output_text="one two three four", raw_output="one two three four"),
        _automatic_validator(
            {
                "kind": "word_count",
                "source": "output_text",
                "comparison": {"op": "lte", "value": 3},
            }
        ),
    )

    assert result.status == "ok"
    assert result.check_results[0].grade == 1
    assert result.check_results[0].metrics == {"value": 4}
```

Add the new test to `main()`.

- [ ] **Step 2: Run automatic-validator tests to verify they fail**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_automatic_validators.py
```

Expected: tests fail because `_execute_check` still returns `verdict`.

- [ ] **Step 3: Update automatic validator mapping**

In `backend/prompt_lab/automatic_validators.py`, replace `_execute_check` verdict logic with:

```python
value = _measure(run, rule)
if rule.kind == "json_path_exists":
    passed = value == 1
else:
    if rule.comparison is None:
        raise ValueError(f"{rule.kind} requires comparison")
    passed = _compare(value, rule.comparison)
return ValidationCheckResult(
    check_id=check_id,
    grade=5 if passed else 1,
    included_in_judge=True,
    metrics={"value": value},
)
```

- [ ] **Step 4: Run automatic-validator tests**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_automatic_validators.py
```

Expected: all automatic-validator tests pass.

- [ ] **Step 5: Commit automatic validator mapping**

Run:

```bash
git add backend/prompt_lab/automatic_validators.py backend/tests/test_automatic_validators.py
git commit -m "Map automatic validation checks to grades"
```

## Task 4: Judge Evidence And Proposal Context Use Grades

**Files:**
- Modify: `backend/prompt_lab/api.py`
- Modify: `backend/prompt_lab/system_prompts/judge.md.jinja`
- Modify: `backend/tests/test_judge.py`
- Modify: `backend/tests/test_proposal.py`

- [ ] **Step 1: Write failing judge/proposal tests**

In `backend/tests/test_judge.py`, replace validation evidence fixtures from:

```python
"verdict": "yes",
```

to:

```python
"grade": 5,
```

and from:

```python
"verdict": "no",
```

to:

```python
"grade": 1,
```

Add or update an assertion in the test that inspects judge prompt/context so it expects `"grade"` and does not expect `"verdict"`:

```python
assert '"grade": 1' in prompt
assert '"verdict"' not in prompt
```

In `backend/tests/test_proposal.py`, replace validation-context fixture entries:

```python
"verdict": "no",
```

with:

```python
"grade": 1,
```

and update prompt assertions to expect grade:

```python
assert '"grade": 1' in prompt
assert '"verdict"' not in prompt
```

- [ ] **Step 2: Run judge/proposal tests to verify they fail**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_judge.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_proposal.py
```

Expected: tests fail where `_build_validation_evidence` still emits `verdict`.

- [ ] **Step 3: Update validation evidence builder**

In `backend/prompt_lab/api.py`, replace this payload field in `_build_validation_evidence`:

```python
"verdict": check.verdict,
```

with:

```python
"grade": check.grade,
```

- [ ] **Step 4: Update judge prompt wording**

In `backend/prompt_lab/system_prompts/judge.md.jinja`, replace:

```markdown
- avoid numeric scorecards as primary output; use qualitative findings and evidence.
```

with:

```markdown
- validation grades are evidence, not your final output format; synthesize qualitative findings from the grade patterns and comments.
```

- [ ] **Step 5: Run judge/proposal tests**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_judge.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_proposal.py
```

Expected: both commands pass.

- [ ] **Step 6: Commit judge/proposal evidence changes**

Run:

```bash
git add backend/prompt_lab/api.py backend/prompt_lab/system_prompts/judge.md.jinja backend/tests/test_judge.py backend/tests/test_proposal.py
git commit -m "Pass validation grades to judge evidence"
```

## Task 5: Compare Aggregates Grade Counts

**Files:**
- Modify: `backend/prompt_lab/compare.py`
- Modify: `backend/tests/test_compare.py`

- [ ] **Step 1: Write failing compare tests**

In `backend/tests/test_compare.py`, change helper `validation_result` signature from:

```python
verdict: str = "yes",
```

to:

```python
grade: int | None = 5,
```

Inside the helper, replace:

```python
"verdict": verdict,
"comment": f"{verdict} evidence",
```

with:

```python
"grade": grade,
"comment": f"grade {grade} evidence",
```

Update call sites:

```python
verdict="yes" -> grade=5
verdict="no" -> grade=1
verdict="unknown" -> grade=None
```

Rename `test_compare_matrix_marks_any_no_as_fail` to `test_compare_matrix_marks_low_grades_as_fail` and assert:

```python
assert matrix.rows[0].cells[0].grade_5 == 1
assert matrix.rows[0].cells[1].grade_1 == 1
assert matrix.rows[0].cells[1].status == "fail"
```

Rename `test_compare_matrix_marks_unknown_and_errors_as_mixed` to `test_compare_matrix_marks_null_grade_and_errors_as_mixed` and assert:

```python
assert matrix.rows[0].cells[0].not_assessable == 1
assert matrix.rows[0].cells[0].status == "mixed"
assert matrix.rows[0].cells[1].error == 1
assert matrix.rows[0].cells[1].details[0].status == "error"
assert matrix.rows[0].cells[1].details[0].grade is None
```

Add a test for grade `3` mixed status:

```python
def test_compare_matrix_marks_grade_three_as_mixed() -> None:
    matrix = build_compare_matrix(
        experiment_id="demo",
        versions=["v001"],
        validator_snapshots_by_version={"v001": [validator_snapshot()]},
        results_by_version={"v001": [validation_result(version="v001", grade=3)]},
    )

    cell = matrix.rows[0].cells[0]

    assert cell.grade_3 == 1
    assert cell.status == "mixed"
    assert cell.total == 1
```

Add the new test to `main()`.

- [ ] **Step 2: Run compare tests to verify they fail**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_compare.py
```

Expected: compare tests fail because `compare.py` still reads `check.verdict` and emits yes/no/unknown counts.

- [ ] **Step 3: Implement grade aggregation**

In `backend/prompt_lab/compare.py`, replace `_cell_for_version` and `_status` with:

```python
def _cell_for_version(
    *,
    version: str,
    validator_id: str,
    check_id: str,
    results: list[ValidationResultArtifact],
) -> CompareMatrixCell:
    counts: Counter[str] = Counter()
    details: list[CompareCellDetail] = []
    for result in sorted(
        results,
        key=lambda item: (item.case_id, item.repeat_index, item.validation_result_id),
    ):
        if result.validator_id != validator_id or not result.included_in_judge:
            continue
        if result.status == "error":
            counts["error"] += 1
            details.append(
                CompareCellDetail(
                    case_id=result.case_id,
                    repeat_index=result.repeat_index,
                    validation_result_id=result.validation_result_id,
                    status="error",
                    grade=None,
                    comment=result.execution_error or "Validation result failed.",
                )
            )
            continue
        for check in result.check_results:
            if check.check_id != check_id or not check.included_in_judge:
                continue
            if check.grade is None:
                counts["not_assessable"] += 1
                detail_status = "not_assessable"
            else:
                counts[f"grade_{check.grade}"] += 1
                detail_status = "graded"
            details.append(
                CompareCellDetail(
                    case_id=result.case_id,
                    repeat_index=result.repeat_index,
                    validation_result_id=result.validation_result_id,
                    status=detail_status,
                    grade=check.grade,
                    comment=check.comment,
                )
            )
    total = _total(counts)
    return CompareMatrixCell(
        version=version,
        status=_status(counts),
        grade_5=counts["grade_5"],
        grade_4=counts["grade_4"],
        grade_3=counts["grade_3"],
        grade_2=counts["grade_2"],
        grade_1=counts["grade_1"],
        not_assessable=counts["not_assessable"],
        missing=counts["missing"],
        error=counts["error"],
        total=total,
        details=details,
    )


def _total(counts: Counter[str]) -> int:
    return (
        counts["grade_5"]
        + counts["grade_4"]
        + counts["grade_3"]
        + counts["grade_2"]
        + counts["grade_1"]
        + counts["not_assessable"]
        + counts["error"]
    )


def _status(counts: Counter[str]) -> Literal["pass", "fail", "mixed", "empty"]:
    total = _total(counts)
    if total == 0:
        return "empty"
    if counts["grade_1"] > 0 or counts["grade_2"] > 0:
        return "fail"
    if (
        counts["grade_3"] > 0
        or counts["not_assessable"] > 0
        or counts["error"] > 0
    ):
        return "mixed"
    return "pass"
```

- [ ] **Step 4: Run compare tests**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_compare.py
```

Expected: all compare tests pass.

- [ ] **Step 5: Commit compare grade aggregation**

Run:

```bash
git add backend/prompt_lab/compare.py backend/tests/test_compare.py
git commit -m "Aggregate comparison by validation grades"
```

## Task 6: Frontend Validation And Compare UI Use Grades

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/components/validationMatrix.ts`
- Modify: `frontend/src/components/ValidationView.tsx`
- Modify: `frontend/src/components/ComparisonView.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/validationView.test.ts`

- [ ] **Step 1: Write failing frontend tests**

In `frontend/tests/validationView.test.ts`, replace fixture check results:

```ts
verdict: "yes",
```

with:

```ts
grade: 5,
```

and:

```ts
verdict: "no",
```

with:

```ts
grade: 1,
```

Update the matrix grouping assertion:

```ts
assert.deepEqual(
  matrix.rows[0].cells.map((cell) => cell.grade),
  [5, 1]
);
```

Update the skipped assertion:

```ts
assert.equal(cell.grade, null);
assert.equal(cell.status, "skipped");
```

Update inclusion assertions to inspect `grade`:

```ts
assert.deepEqual(
  updated.results.map((result) => ({
    result: result.included_in_judge,
    check: result.check_results[0].included_in_judge,
    grade: result.check_results[0].grade
  })),
  [
    { result: true, check: false, grade: 5 },
    { result: false, check: false, grade: 1 }
  ]
);
```

and:

```ts
assert.equal(updated.results[0].check_results[0].grade, 5);
```

- [ ] **Step 2: Run frontend tests to verify they fail**

Run:

```bash
cd frontend && pnpm test
```

Expected: TypeScript tests fail because frontend types and matrix cells still use `verdict`.

- [ ] **Step 3: Update TypeScript contracts**

In `frontend/src/types.ts`, replace:

```ts
export type ValidationVerdict = "yes" | "no" | "unknown";
```

with:

```ts
export type ValidationGrade = 1 | 2 | 3 | 4 | 5 | null;
```

Replace `ValidationCheckResult.verdict` with:

```ts
grade: ValidationGrade;
```

Replace compare types with:

```ts
export type CompareDetailStatus = "graded" | "not_assessable" | "error";

export interface CompareCellDetail {
  case_id: string;
  repeat_index: number;
  validation_result_id: string;
  status: CompareDetailStatus;
  grade: ValidationGrade;
  comment: string;
}

export interface CompareMatrixCell {
  version: string;
  status: ComparisonStatus;
  grade_5: number;
  grade_4: number;
  grade_3: number;
  grade_2: number;
  grade_1: number;
  not_assessable: number;
  missing: number;
  error: number;
  total: number;
  details: CompareCellDetail[];
}
```

- [ ] **Step 4: Update validation matrix model**

In `frontend/src/components/validationMatrix.ts`, import `ValidationGrade` instead of `ValidationVerdict`.

Change `ValidationMatrixCell` fields:

```ts
grade: ValidationGrade;
status: "ok" | "error" | "missing" | "skipped";
```

Remove the `verdict` field.

In `buildCell`, set skipped/missing/error grades to `null`:

```ts
grade: null,
```

and for the normal path:

```ts
grade: check.grade,
```

- [ ] **Step 5: Update validation view aggregate and display**

In `frontend/src/components/ValidationView.tsx`, update `aggregateStatus`:

```ts
const missingOrError = cells.filter(
  (cell) =>
    cell.status === "missing" ||
    cell.status === "error" ||
    cell.status === "skipped"
).length;
const failed = cells.filter(
  (cell) => cell.grade === 1 || cell.grade === 2
).length;
const mixed = cells.filter(
  (cell) => cell.grade === 3 || cell.grade === null
).length;
if (missingOrError > 0 || failed > 0) {
  return {
    className: "compare-cell-fail",
    label: `${missingOrError + failed} fail`
  };
}
if (mixed > 0) {
  return {
    className: "compare-cell-mixed",
    label: `${mixed} mixed`
  };
}
return { className: "compare-cell-pass", label: "pass" };
```

Replace `verdictLabel` with:

```ts
function gradeLabel(value: ValidationMatrixCell["grade"], status: ValidationMatrixCell["status"]): string {
  if (status === "skipped") return "skipped";
  if (status === "missing") return "missing";
  if (status === "error") return "error";
  return value === null ? "n/a" : String(value);
}
```

Replace `verdict-${cell.verdict}` class usage with:

```tsx
className={`verdict-pill ${gradeClassName(cell.grade, cell.status)}`}
```

and render:

```tsx
{gradeLabel(cell.grade, cell.status)}
```

Add this helper next to `gradeLabel`:

```ts
function gradeClassName(
  value: ValidationMatrixCell["grade"],
  status: ValidationMatrixCell["status"]
): string {
  if (status === "skipped") return "verdict-skipped";
  if (status === "missing") return "verdict-missing";
  if (status === "error") return "verdict-error";
  return `grade-${value ?? "na"}`;
}
```

- [ ] **Step 6: Update comparison view**

In `frontend/src/components/ComparisonView.tsx`, update `emptyCell` to return grade counts:

```ts
grade_5: 0,
grade_4: 0,
grade_3: 0,
grade_2: 0,
grade_1: 0,
not_assessable: 0,
missing: 0,
error: 0,
```

Replace `statusLabel` with:

```ts
function statusLabel(cell: CompareMatrixCell): string {
  if (cell.total === 0) return "empty";
  if (cell.status === "pass") return "pass";
  if (cell.status === "fail") return `${cell.grade_1 + cell.grade_2} low`;
  if (cell.error > 0) return `${cell.error} error`;
  if (cell.not_assessable > 0) return `${cell.not_assessable} n/a`;
  if (cell.grade_3 > 0) return `${cell.grade_3} mixed`;
  return "mixed";
}
```

Replace `detailSnippet` candidate selection with:

```ts
const failing = cell.details.find(
  (detail) => detail.status === "error" || detail.grade === 1 || detail.grade === 2
);
const mixed = cell.details.find(
  (detail) => detail.grade === 3 || detail.status === "not_assessable"
);
const candidate = failing ?? mixed ?? cell.details[0] ?? null;
```

Replace `countSummary` with:

```ts
function countSummary(cell: CompareMatrixCell): string {
  if (cell.total === 0) return "0 included checks";
  const parts: string[] = [];
  if (cell.grade_5 > 0) parts.push(`5: ${cell.grade_5}`);
  if (cell.grade_4 > 0) parts.push(`4: ${cell.grade_4}`);
  if (cell.grade_3 > 0) parts.push(`3: ${cell.grade_3}`);
  if (cell.grade_2 > 0) parts.push(`2: ${cell.grade_2}`);
  if (cell.grade_1 > 0) parts.push(`1: ${cell.grade_1}`);
  if (cell.not_assessable > 0) parts.push(`${cell.not_assessable} n/a`);
  if (cell.error > 0) parts.push(`${cell.error} error`);
  if (cell.missing > 0) parts.push(`${cell.missing} missing`);
  return parts.join(" · ");
}
```

In `CompareCellModal`, replace detail keys and labels:

```tsx
key={`${detail.validation_result_id}:${detail.case_id}:${detail.repeat_index}:${detail.status}:${detail.grade ?? "na"}:${index}`}
```

and:

```tsx
<strong>
  {detail.status === "error"
    ? "error"
    : detail.grade === null
      ? "n/a"
      : `grade ${detail.grade}`}
</strong>
```

- [ ] **Step 7: Update CSS grade classes**

In `frontend/src/styles.css`, keep existing `.verdict-pill` base class and replace verdict color classes with:

```css
.grade-5 {
  background: #ecfdf3;
  color: #027a48;
}

.grade-4 {
  background: #f0fdf4;
  color: #15803d;
}

.grade-3,
.grade-na {
  background: #fffaeb;
  color: #b54708;
}

.grade-2,
.grade-1 {
  background: #fef3f2;
  color: #b42318;
}
```

Keep `.verdict-error`, `.verdict-missing`, `.verdict-skipped`, and `.validation-status-skipped` because status-only validation cells still use them through `gradeClassName`.

- [ ] **Step 8: Run frontend checks**

Run:

```bash
cd frontend && pnpm lint && pnpm test && pnpm build
```

Expected: lint, tests, and build pass.

- [ ] **Step 9: Commit frontend grade UI**

Run:

```bash
git add frontend/src/types.ts frontend/src/components/validationMatrix.ts frontend/src/components/ValidationView.tsx frontend/src/components/ComparisonView.tsx frontend/src/styles.css frontend/tests/validationView.test.ts
git commit -m "Show validation grades in frontend"
```

## Task 7: Demo Artifacts And Documentation

**Files:**
- Modify: `examples/demo-string/**`
- Modify: `examples/demo-json/**`
- Modify: `DESIGN.md`
- Modify: `FORMAT.md`
- Modify: `docs/superpowers/specs/2026-06-19-validator-pipeline-design.md`
- Modify: `docs/superpowers/specs/2026-06-20-validator-grade-contract-design.md` only if implementation uncovers a necessary clarification.

- [ ] **Step 1: Mechanically rewrite committed JSON artifacts**

Run this Node script from the repository root to convert example/demo `verdict` fields:

```bash
node - <<'NODE'
const fs = require("fs");
const path = require("path");

const roots = ["examples/demo-string", "examples/demo-json"];

function walk(dir) {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name);
    const stat = fs.statSync(full);
    if (stat.isDirectory()) {
      walk(full);
      continue;
    }
    if (!full.endsWith(".json")) continue;
    const text = fs.readFileSync(full, "utf8");
    if (!text.includes('"verdict"')) continue;
    const data = JSON.parse(text);
    convert(data);
    fs.writeFileSync(full, JSON.stringify(data, null, 2) + "\n", "utf8");
  }
}

function convert(value) {
  if (Array.isArray(value)) {
    for (const item of value) convert(item);
    return;
  }
  if (value === null || typeof value !== "object") return;
  if (Object.prototype.hasOwnProperty.call(value, "verdict")) {
    const verdict = value.verdict;
    delete value.verdict;
    value.grade = verdict === "yes" ? 5 : verdict === "no" ? 1 : null;
  }
  for (const item of Object.values(value)) convert(item);
}

for (const root of roots) walk(root);
NODE
```

- [ ] **Step 2: Update docs wording**

In `DESIGN.md`, replace:

```markdown
Validation results include check verdicts and `included_in_judge` flags.
```

with:

```markdown
Validation results include check grades and `included_in_judge` flags.
```

In `FORMAT.md`, add this paragraph to the validator section after the `input_scope` paragraph:

```markdown
Validation check results use `grade: 1..5 | null`, not pass/fail verdicts.
`5` means very good, `4` good, `3` acceptable but improvable, `2` weak,
`1` bad, and `null` not assessable from the provided evidence.
```

In `docs/superpowers/specs/2026-06-19-validator-pipeline-design.md`, replace the old check-result bullets:

```markdown
- verdict: `yes`, `no`, or `unknown`
```

with:

```markdown
- grade: `1`, `2`, `3`, `4`, `5`, or `null`
```

Replace compare-count bullets:

```markdown
- yes count
- no count
- unknown count
```

with:

```markdown
- grade 5 count
- grade 4 count
- grade 3 count
- grade 2 count
- grade 1 count
- not assessable count
```

Replace:

```markdown
- detail rows with case id, repeat index, verdict, and comment
```

with:

```markdown
- detail rows with case id, repeat index, grade, and comment
```

Replace:

```markdown
- check verdicts and comments
```

with:

```markdown
- check grades and comments
```

Replace:

```markdown
human comparison of pass/fail/unknown rates across versions.
```

with:

```markdown
human comparison of grade distributions across versions.
```

- [ ] **Step 3: Confirm no stale verdict references in active code/docs**

Run:

```bash
rg -n 'ValidationVerdict|verdict|yes count|no count|unknown count' backend/prompt_lab backend/tests frontend/src frontend/tests examples DESIGN.md FORMAT.md docs/superpowers/specs/2026-06-19-validator-pipeline-design.md
```

Expected: no matches, except historical references inside older plan documents under `docs/superpowers/plans/`.

- [ ] **Step 4: Run docs/data validation tests**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_artifacts.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_api.py
```

Expected: both commands pass with updated example artifacts.

- [ ] **Step 5: Commit docs and demo artifacts**

Run:

```bash
git add examples/demo-string examples/demo-json DESIGN.md FORMAT.md docs/superpowers/specs/2026-06-19-validator-pipeline-design.md docs/superpowers/specs/2026-06-20-validator-grade-contract-design.md
git commit -m "Update demo validation artifacts to grades"
```

## Task 8: Final Verification

**Files:**
- No planned code edits.
- Verify all modified systems together.

- [ ] **Step 1: Run backend validation suite from AGENTS.md**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_chat.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_chat_get_structured_lite.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_structured_lite_units.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_format_validation_errors.py
.venv/bin/pyright --project pyrightconfig.json --pythonpath .venv/bin/python
```

Expected: all commands pass. `test_format_validation_errors.py` prints diagnostic examples and exits successfully.

- [ ] **Step 2: Run validation-specific backend tests**

Run:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_validators.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_validation.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_automatic_validators.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_compare.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_judge.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_proposal.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_api.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_artifacts.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_storage.py
```

Expected: all commands pass. FastAPI TestClient deprecation warnings are acceptable if tests pass.

- [ ] **Step 3: Run frontend verification**

Run:

```bash
cd frontend && pnpm lint && pnpm test && pnpm build
```

Expected: all commands pass.

- [ ] **Step 4: Run final repository checks**

Run:

```bash
git diff --check
git status --short
```

Expected: `git diff --check` prints nothing. `git status --short` shows only intended modified files if final fixes remain unstaged; otherwise it is clean.

- [ ] **Step 5: Confirm clean repository**

Run:

```bash
git status --short
```

Expected: no output. If there is output, inspect it and either commit the exact files in the task that created them or revert only generated files that are not part of this plan.
