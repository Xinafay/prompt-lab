from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from prompt_lab.models.judgments import FindingDecisionSet, JudgmentArtifact
from prompt_lab.prompt_sections import fenced_section, json_block
from prompt_lab.prompt_templates import render_system_prompt


_MODEL_PLACEHOLDER = "<<MODEL>>"
_EMBEDDED_MODEL_PLACEHOLDER = "[MODEL_MARKER_LITERAL]"
_OUTPUT_MODEL_PLACEHOLDER = "[OUTPUT_MODEL_SCHEMA: see CURRENT_MODEL_PY]"


def _strip_wrapping_code_fence(value: object) -> object:
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


class TextProposalDraft(BaseModel):
    """Structured proposal for an experiment that returns plain text."""

    model_config = ConfigDict(extra="forbid")

    prompt_md: str = Field(
        min_length=1,
        description=(
            "Complete replacement contents for prompt.md. The experiment returns "
            "plain text, so do not include the structured-output schema marker."
        ),
    )
    rationale_md: str = Field(
        min_length=1,
        description="Short rationale explaining how the proposal addresses accepted findings.",
    )

    @field_validator("prompt_md", "rationale_md", mode="before")
    @classmethod
    def strip_wrapping_code_fence(cls, value: object) -> object:
        return _strip_wrapping_code_fence(value)

    @field_validator("prompt_md")
    @classmethod
    def reject_model_marker(cls, value: str) -> str:
        if _MODEL_PLACEHOLDER in value:
            raise ValueError("text proposal prompt_md cannot contain <<MODEL>>")
        return value


class ProposalDraft(BaseModel):
    """Structured proposal generated from a reviewed judgment."""

    model_config = ConfigDict(extra="forbid")

    prompt_md: str = Field(
        min_length=1,
        description=(
            "Complete replacement contents for prompt.md. For pydantic output, "
            "include exactly one literal <<MODEL>> marker for the generator output schema."
        ),
    )
    model_py: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "Complete replacement contents for model.py only when the pydantic "
            "output contract needs to change; otherwise null or omit it."
        ),
    )
    rationale_md: str = Field(
        min_length=1,
        description="Short rationale explaining how the proposal addresses accepted findings.",
    )

    @field_validator("prompt_md", "model_py", "rationale_md", mode="before")
    @classmethod
    def strip_wrapping_code_fence(cls, value: object) -> object:
        return _strip_wrapping_code_fence(value)


class PydanticProposalDraft(BaseModel):
    """Structured proposal for an experiment that returns a Pydantic model."""

    model_config = ConfigDict(extra="forbid")

    prompt_md: str = Field(
        min_length=1,
        description=(
            "Complete replacement contents for prompt.md. Include exactly one "
            "literal <<MODEL>> marker for the generator output schema."
        ),
    )
    model_py: str = Field(
        min_length=1,
        description=(
            "Complete replacement contents for model.py. If the output contract "
            "does not change, return the current model.py contents unchanged."
        ),
    )
    rationale_md: str = Field(
        min_length=1,
        description="Short rationale explaining how the proposal addresses accepted findings.",
    )

    @field_validator("prompt_md", "model_py", "rationale_md", mode="before")
    @classmethod
    def strip_wrapping_code_fence(cls, value: object) -> object:
        return _strip_wrapping_code_fence(value)

    @field_validator("prompt_md")
    @classmethod
    def require_one_model_marker(cls, value: str) -> str:
        if value.count(_MODEL_PLACEHOLDER) != 1:
            raise ValueError(
                "pydantic proposal prompt_md must contain exactly one <<MODEL>>"
            )
        return value

    @field_validator("model_py", mode="before")
    @classmethod
    def require_model_py(cls, value: object) -> object:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("pydantic proposal model_py must contain complete model.py")
        return value


ProposalResponseModel = type[TextProposalDraft] | type[PydanticProposalDraft]


def proposal_response_model(output_type: str) -> ProposalResponseModel:
    if output_type == "text":
        return TextProposalDraft
    return PydanticProposalDraft


def proposal_response_to_draft(output: object) -> ProposalDraft:
    if isinstance(output, ProposalDraft):
        return ProposalDraft.model_validate(output.model_dump(mode="json"))
    if isinstance(output, PydanticProposalDraft):
        return ProposalDraft.model_validate(output.model_dump(mode="json"))
    if isinstance(output, TextProposalDraft):
        return ProposalDraft(
            prompt_md=output.prompt_md,
            model_py=None,
            rationale_md=output.rationale_md,
        )
    return ProposalDraft.model_validate(output)


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


def _display_prompt_template(prompt_template: str, *, output_type: str) -> str:
    replacement = (
        _OUTPUT_MODEL_PLACEHOLDER
        if output_type == "pydantic"
        else _EMBEDDED_MODEL_PLACEHOLDER
    )
    return prompt_template.replace(_MODEL_PLACEHOLDER, replacement)


def _display_embedded_content(content: str) -> str:
    return content.replace(_MODEL_PLACEHOLDER, _EMBEDDED_MODEL_PLACEHOLDER)


def _validation_metadata(validation_context: dict[str, Any]) -> dict[str, object]:
    metadata: dict[str, object] = {}
    for key in ("validation_batch_id", "run_batch_id"):
        value = validation_context.get(key)
        if isinstance(value, str):
            metadata[key] = value
    return metadata


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
        fenced_section(
            "CURRENT_MODEL_PY",
            _display_embedded_content(model_source),
            fence="python",
        )
        if model_source is not None
        else None
    )
    return render_system_prompt(
        "proposal.md.jinja",
        {
            "experiment_id": _display_embedded_content(experiment_id),
            "version": _display_embedded_content(version),
            "current_model": _display_embedded_content(
                current_model or "not specified"
            ),
            "current_model_section": current_model_section,
            "output_type": output_type,
            "current_prompt_section": fenced_section(
                "CURRENT_PROMPT_MD",
                _display_prompt_template(prompt_template, output_type=output_type),
            ),
            "validation_metadata_section": fenced_section(
                "VALIDATION_METADATA_JSON",
                _display_embedded_content(
                    json_block(_validation_metadata(validation_context))
                ),
                fence="json",
            ),
            "human_notes_section": fenced_section(
                "HUMAN_NOTES_MD", _display_embedded_content(human_notes)
            ),
            "accepted_findings_section": fenced_section(
                "ACCEPTED_FINDINGS_JSON",
                _display_embedded_content(json_block(accepted_findings)),
                fence="json",
            ),
            "rejected_findings_section": fenced_section(
                "REJECTED_FINDINGS_AS_CONSTRAINTS_JSON",
                _display_embedded_content(json_block(rejected_findings)),
                fence="json",
            ),
        },
    )
