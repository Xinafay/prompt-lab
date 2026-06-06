from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from prompt_lab.models.judgments import FindingDecisionSet, JudgmentArtifact


class ProposalDraft(BaseModel):
    """Structured proposal generated from a reviewed judgment."""

    model_config = ConfigDict(extra="forbid")

    prompt_md: str = Field(min_length=1)
    model_py: str | None = Field(default=None, min_length=1)
    rationale_md: str = Field(min_length=1)


class ProposalSource(BaseModel):
    """Traceability metadata saved next to a proposal draft."""

    model_config = ConfigDict(extra="allow")

    experiment_id: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    review_id: str = Field(min_length=1)
    judgment_id: str = Field(min_length=1)


def _json_block(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _section(name: str, body: str, *, fence: str = "text") -> str:
    return f"<<<{name}\n```{fence}\n{body}\n```\n{name}>>>"


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
    rubric_snapshot: str,
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

    sections = [
        "You are generating a Prompt Lab proposal for one reviewed experiment version.",
        "Return JSON matching ProposalDraft exactly.",
        "Rules:",
        "- human notes override all judge findings.",
        "- accepted findings are requested changes.",
        "- rejected findings are constraints.",
        "- deferred findings are ignored.",
        "- preserve task scope.",
        "- change `model.py` only when contract changes are clearly needed.",
        "- If the experiment output is text, normally leave model_py absent.",
        "- If the experiment output is pydantic, prefer prompt changes unless the output contract clearly needs a model.py change.",
        f"Experiment id: {experiment_id}",
        f"Source version: {version}",
        f"Current model: {current_model or 'not specified'}",
        f"Output type: {output_type}",
        _section("CURRENT_PROMPT_MD", prompt_template),
        _section("RUBRIC_SNAPSHOT_MD", rubric_snapshot),
        _section("HUMAN_NOTES_MD", human_notes),
        _section(
            "ACCEPTED_FINDINGS_JSON",
            _json_block(accepted_findings),
            fence="json",
        ),
        _section(
            "REJECTED_FINDINGS_AS_CONSTRAINTS_JSON",
            _json_block(rejected_findings),
            fence="json",
        ),
        _section(
            "PROPOSAL_SCHEMA_JSON",
            _json_block(ProposalDraft.model_json_schema()),
            fence="json",
        ),
    ]
    if model_source is not None:
        sections.insert(
            14,
            _section("CURRENT_MODEL_PY", model_source, fence="python"),
        )
    return "\n\n".join(sections)
