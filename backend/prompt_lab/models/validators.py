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
ValidationResultStatus = Literal["ok", "error", "skipped"]
ValidationGrade = Annotated[int, Field(ge=1, le=5, strict=True)] | None
CompareDetailStatus = Literal["graded", "not_assessable", "error"]
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
    value: float | None = Field(default=None, ge=0)
    min_value: float | None = Field(default=None, ge=0)
    max_value: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        if self.op == "between":
            if self.min_value is None or self.max_value is None:
                raise ValueError("between comparison requires min_value and max_value")
            if self.min_value > self.max_value:
                raise ValueError("min_value cannot exceed max_value")
            if self.value is not None:
                raise ValueError("between comparison cannot include value")
        else:
            if self.value is None:
                raise ValueError("non-between comparison requires value")
            if self.min_value is not None or self.max_value is not None:
                raise ValueError(
                    "non-between comparison cannot include min_value or max_value"
                )
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
    path: NonEmptyString | None = None
    comparison: CountComparison | None = None

    @model_validator(mode="after")
    def validate_rule_shape(self) -> Self:
        if self.kind in {"json_path_count", "json_path_exists"}:
            if self.source != "output_json":
                raise ValueError(f"{self.kind} requires source output_json")
            if self.path is None:
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


def _find_duplicate_check_ids(
    checks: list[LlmValidatorCheck] | list[AutomaticValidatorCheck],
) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for check in checks:
        if check.check_id in seen and check.check_id not in duplicates:
            duplicates.append(check.check_id)
        seen.add(check.check_id)
    return duplicates


class LlmQuestionnaireValidatorDefinition(BaseValidatorDefinition):
    type: Literal["llm_questionnaire"]  # type: ignore[reportIncompatibleVariableOverride]
    checks: list[LlmValidatorCheck] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_check_ids(self) -> Self:
        duplicates = _find_duplicate_check_ids(self.checks)
        if duplicates:
            raise ValueError(f"duplicate check ids: {', '.join(duplicates)}")
        return self


class AutomaticValidatorDefinition(BaseValidatorDefinition):
    type: Literal["automatic"]  # type: ignore[reportIncompatibleVariableOverride]
    checks: list[AutomaticValidatorCheck] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_check_ids(self) -> Self:
        duplicates = _find_duplicate_check_ids(self.checks)
        if duplicates:
            raise ValueError(f"duplicate check ids: {', '.join(duplicates)}")
        return self


ValidatorDefinition = LlmQuestionnaireValidatorDefinition | AutomaticValidatorDefinition


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
    grade: ValidationGrade
    comment: str = ""
    included_in_judge: bool = True
    metrics: JsonObject = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_null_grade_comment(self) -> Self:
        if self.grade is None and self.comment.strip() == "":
            raise ValueError("null grade requires comment")
        return self


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
    def validate_status_fields(self) -> Self:
        if self.status == "ok" and self.execution_error is not None:
            raise ValueError("ok status cannot include execution_error")
        if self.status == "error" and self.execution_error is None:
            raise ValueError("error status requires execution_error")
        if self.status == "skipped":
            if self.execution_error is None:
                raise ValueError("skipped status requires execution_error")
            if self.included_in_judge:
                raise ValueError("skipped status cannot be included in judge")
            if self.check_results:
                raise ValueError("skipped status cannot include check_results")
        return self


class LlmQuestionnaireCheckResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: NonEmptyString
    grade: ValidationGrade
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
    validators: list[ValidatorDefinition]
    results: list[ValidationResultArtifact]


class CompareCellDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: NonEmptyString
    repeat_index: int = Field(ge=1)
    validation_result_id: NonEmptyString
    status: CompareDetailStatus
    grade: ValidationGrade
    comment: str = ""

    @model_validator(mode="after")
    def validate_status_grade_consistency(self) -> Self:
        if self.status == "graded" and self.grade is None:
            raise ValueError("graded status requires grade")
        if self.status in {"not_assessable", "error"} and self.grade is not None:
            raise ValueError(f"{self.status} status requires null grade")
        return self


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
