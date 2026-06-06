from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field


FindingSeverity = Literal[
    "recommended", "optional", "do_not_change_yet", "regression_risk"
]
FindingDecisionValue = Literal["accepted", "rejected", "deferred"]


class EvidenceFinding(BaseModel):
    """A positive finding with cited run evidence."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    evidence: list[str]


class JudgmentFinding(BaseModel):
    """A judge finding that can be accepted, rejected, or deferred."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str = Field(min_length=1)
    severity: FindingSeverity
    area: str = Field(min_length=1)
    category: str = Field(min_length=1)
    description: str = Field(min_length=1)
    evidence: list[str] = Field(min_length=1)
    suggested_change: str = Field(min_length=1)


class DecisionPoint(BaseModel):
    """A judgment decision that needs explicit user choice."""

    model_config = ConfigDict(extra="forbid")

    decision_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    options: list[str] = Field(min_length=1)
    recommended_option: str = Field(min_length=1)


class JudgmentArtifact(BaseModel):
    """Structured qualitative analysis produced by the judge model."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["prompt_lab.judgment/v1"]
    judgment_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    run_batch_ids: list[str] = Field(min_length=1)
    judge_model: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    what_looks_correct: list[EvidenceFinding]
    findings: list[JudgmentFinding]
    decision_points: list[DecisionPoint]


class FindingDecision(BaseModel):
    """Human decision for one judge finding."""

    model_config = ConfigDict(extra="forbid")

    decision: FindingDecisionValue
    reason: str | None = Field(default=None, min_length=1)


class FindingDecisionSet(BaseModel):
    """Human decisions for all findings in a judgment."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["prompt_lab.decisions/v1"] = "prompt_lab.decisions/v1"
    finding_decisions: dict[str, FindingDecision]

    @classmethod
    def from_finding_ids(cls, finding_ids: list[str]) -> Self:
        return cls(
            finding_decisions={
                finding_id: FindingDecision(decision="accepted")
                for finding_id in finding_ids
            }
        )
