from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


FindingSeverity = Literal[
    "recommended", "optional", "do_not_change_yet", "regression_risk"
]
FindingDecisionValue = Literal["accepted", "rejected", "deferred"]
NonEmptyString = Annotated[str, Field(min_length=1)]


class EvidenceFinding(BaseModel):
    """A positive finding with cited run evidence."""

    model_config = ConfigDict(extra="forbid")

    finding_id: NonEmptyString
    description: NonEmptyString
    evidence: list[NonEmptyString] = Field(min_length=1)


class JudgmentFinding(BaseModel):
    """A judge finding that can be accepted, rejected, or deferred."""

    model_config = ConfigDict(extra="forbid")

    finding_id: NonEmptyString
    severity: FindingSeverity
    area: NonEmptyString
    category: NonEmptyString
    description: NonEmptyString
    evidence: list[NonEmptyString] = Field(min_length=1)
    suggested_change: NonEmptyString


class DecisionPoint(BaseModel):
    """A judgment decision that needs explicit user choice."""

    model_config = ConfigDict(extra="forbid")

    decision_id: NonEmptyString
    description: NonEmptyString
    options: list[NonEmptyString] = Field(min_length=1)
    recommended_option: NonEmptyString

    @model_validator(mode="after")
    def validate_recommended_option(self) -> Self:
        if self.recommended_option not in self.options:
            raise ValueError("recommended_option must be one of options")
        return self


class JudgmentArtifact(BaseModel):
    """Structured qualitative analysis produced by the judge model."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["prompt_lab.judgment/v1"]
    judgment_id: NonEmptyString
    version: NonEmptyString
    run_batch_ids: list[NonEmptyString] = Field(min_length=1)
    judge_model: NonEmptyString
    summary: NonEmptyString
    what_looks_correct: list[EvidenceFinding]
    findings: list[JudgmentFinding]
    decision_points: list[DecisionPoint]


class FindingDecision(BaseModel):
    """Human decision for one judge finding."""

    model_config = ConfigDict(extra="forbid")

    decision: FindingDecisionValue
    reason: NonEmptyString | None = None


class FindingDecisionSet(BaseModel):
    """Human decisions for all findings in a judgment."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["prompt_lab.decisions/v1"] = "prompt_lab.decisions/v1"
    finding_decisions: dict[NonEmptyString, FindingDecision]

    @field_validator("finding_decisions", mode="before")
    @classmethod
    def validate_raw_finding_ids(cls, value: object) -> object:
        if isinstance(value, dict) and "" in value:
            raise ValueError("finding_decisions cannot contain empty finding ids")
        return value

    @model_validator(mode="after")
    def validate_finding_ids(self) -> Self:
        if "" in self.finding_decisions:
            raise ValueError("finding_decisions cannot contain empty finding ids")
        return self

    @classmethod
    def from_finding_ids(cls, finding_ids: list[NonEmptyString]) -> Self:
        if "" in finding_ids:
            raise ValueError("finding_ids cannot contain empty ids")
        if len(finding_ids) != len(set(finding_ids)):
            raise ValueError("finding_ids cannot contain duplicate ids")
        return cls(
            finding_decisions={
                finding_id: FindingDecision(decision="accepted")
                for finding_id in finding_ids
            }
        )
