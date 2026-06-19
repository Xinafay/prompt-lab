from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from prompt_lab.models.judgments import FindingDecisionSet, JudgmentArtifact
from prompt_lab.prompt_sections import fenced_section, json_block
from prompt_lab.prompt_templates import render_system_prompt


class ProposalDraft(BaseModel):
    """Structured proposal generated from a reviewed judgment."""

    model_config = ConfigDict(extra="forbid")

    prompt_md: str = Field(min_length=1)
    model_py: str | None = Field(default=None, min_length=1)
    rationale_md: str = Field(min_length=1)

    @field_validator("prompt_md", "model_py", "rationale_md", mode="before")
    @classmethod
    def strip_wrapping_code_fence(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        lines = value.strip().splitlines()
        if len(lines) < 2:
            return value
        first_line = lines[0].strip()
        last_line = lines[-1].strip()
        if first_line.startswith("```") and last_line == "```":
            return "\n".join(lines[1:-1]).strip()
        return value


class ProposalSource(BaseModel):
    """Traceability metadata saved next to a proposal draft."""

    model_config = ConfigDict(extra="allow")

    experiment_id: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    review_id: str = Field(min_length=1)
    judgment_id: str = Field(min_length=1)


def _decision_value(raw_decision: object) -> str:
    if isinstance(raw_decision, dict):
        value = raw_decision.get("decision")
        return value if isinstance(value, str) else ""
    value = getattr(raw_decision, "decision", "")
    return value if isinstance(value, str) else ""


def _decision_reason(raw_decision: object) -> str | None:
    if isinstance(raw_decision, dict):
        value = raw_decision.get("reason")
        return value if isinstance(value, str) else None
    value = getattr(raw_decision, "reason", None)
    return value if isinstance(value, str) else None


def build_proposal_prompt(
    *,
    experiment_id: str,
    version: str,
    current_model: str | None,
    output_type: str,
    prompt_template: str,
    model_source: str | None,
    validation_context: dict[str, Any],
    judgment: JudgmentArtifact | dict[str, Any],
    decisions: FindingDecisionSet | dict[str, Any],
    human_notes: str,
) -> str:
    judgment_artifact = (
        judgment
        if isinstance(judgment, JudgmentArtifact)
        else JudgmentArtifact.model_validate(judgment)
    )
    if isinstance(decisions, FindingDecisionSet):
        decision_map: dict[str, object] = dict(decisions.finding_decisions)
    else:
        raw_map = decisions.get("finding_decisions", decisions)
        decision_map = raw_map if isinstance(raw_map, dict) else {}

    accepted_findings: list[dict[str, object]] = []
    rejected_findings: list[dict[str, object]] = []
    for finding in judgment_artifact.findings:
        raw_decision = decision_map.get(finding.finding_id)
        decision = _decision_value(raw_decision)
        if decision not in {"accepted", "rejected"}:
            continue
        payload = finding.model_dump(mode="json")
        reason = _decision_reason(raw_decision)
        if reason is not None:
            payload["decision_reason"] = reason
        if decision == "accepted":
            accepted_findings.append(payload)
        else:
            rejected_findings.append(payload)

    current_model_section = (
        fenced_section("CURRENT_MODEL_PY", model_source, fence="python")
        if model_source is not None
        else None
    )
    return render_system_prompt(
        "proposal.md.jinja",
        {
            "experiment_id": experiment_id,
            "version": version,
            "current_model": current_model or "not specified",
            "current_model_section": current_model_section,
            "output_type": output_type,
            "current_prompt_section": fenced_section(
                "CURRENT_PROMPT_MD", prompt_template
            ),
            "validation_context_section": fenced_section(
                "VALIDATION_CONTEXT_JSON",
                json_block(validation_context),
                fence="json",
            ),
            "human_notes_section": fenced_section("HUMAN_NOTES_MD", human_notes),
            "accepted_findings_section": fenced_section(
                "ACCEPTED_FINDINGS_JSON",
                json_block(accepted_findings),
                fence="json",
            ),
            "rejected_findings_section": fenced_section(
                "REJECTED_FINDINGS_AS_CONSTRAINTS_JSON",
                json_block(rejected_findings),
                fence="json",
            ),
            "proposal_schema_section": fenced_section(
                "PROPOSAL_SCHEMA_JSON",
                json_block(ProposalDraft.model_json_schema()),
                fence="json",
            ),
        },
    )
