from __future__ import annotations

import re
from typing import Any, Literal

import json_repair

from shared.llm.cancellation import LlmRequestCancelled
from shared.llm.structured_lite._errors import _classify_validation_error
from shared.llm.structured_lite._schema import _sanitize_structured_payload, _try_unwrap_schema_shaped_payload
from shared.llm.structured_lite._types import _Candidate, _CandidateValidation, _restore_structured_output


STRUCTURAL_RATIO_THRESHOLD: float = 0.10
STRUCTURAL_HARD_FLOOR: int = 3


def _payload_complexity(payload: Any) -> int:
    if isinstance(payload, dict):
        total = len(payload)
        for value in payload.values():
            total += _payload_complexity(value)
        return max(total, 1)
    if isinstance(payload, list):
        total = len(payload)
        for item in payload:
            total += _payload_complexity(item)
        return max(total, 1)
    return 0


def _extract_text_sources(text: str) -> list[tuple[str, str]]:
    sources: list[tuple[str, str]] = []
    seen: set[str] = set()
    fenced_spans: list[tuple[int, int]] = []

    for match in re.finditer(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL):
        block = match.group(1).strip()
        if block and block not in seen:
            seen.add(block)
            sources.append((block, "fenced"))
        fenced_spans.append((match.start(), match.end()))

    lines = text.splitlines(keepends=True)
    line_offsets: list[int] = []
    offset = 0
    for line in lines:
        line_offsets.append(offset)
        offset += len(line)

    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped and stripped[0] in "{[":
            opener = stripped[0]
            closer = "}" if opener == "{" else "]"
            start_offset = line_offsets[i]
            j = i
            while j < len(lines):
                end_stripped = lines[j].rstrip()
                if end_stripped and end_stripped[-1] == closer:
                    end_offset = line_offsets[j] + len(lines[j].rstrip())
                    in_fenced = any(fs <= start_offset and end_offset <= fe for fs, fe in fenced_spans)
                    if not in_fenced:
                        block = text[start_offset:end_offset].strip()
                        if block and block not in seen:
                            seen.add(block)
                            sources.append((block, "brace"))
                    i = j
                    break
                j += 1
        i += 1

    raw = text.strip()
    if raw and raw not in seen:
        sources.append((raw, "raw_text"))

    return sources


def _generate_candidates(text: str, *, response_model: Any) -> list[_Candidate]:
    sources = _extract_text_sources(text)
    candidates: list[_Candidate] = []

    for source_index, (source_text, source_kind) in enumerate(sources):
        raw_payload = json_repair.loads(source_text)
        if not isinstance(raw_payload, (dict, list)):
            continue

        sanitized = _sanitize_structured_payload(raw_payload, response_model=response_model)
        unwrapped = _try_unwrap_schema_shaped_payload(raw_payload)
        sanitized_unwrapped = (
            _sanitize_structured_payload(unwrapped, response_model=response_model)
            if unwrapped is not None
            else None
        )

        variants: list[tuple[Any, Literal["raw", "sanitized", "unwrapped", "sanitized+unwrapped"]]] = [
            (raw_payload, "raw"),
        ]
        if sanitized != raw_payload:
            variants.append((sanitized, "sanitized"))
        if unwrapped is not None:
            variants.append((unwrapped, "unwrapped"))
        if sanitized_unwrapped is not None and sanitized_unwrapped != unwrapped:
            variants.append((sanitized_unwrapped, "sanitized+unwrapped"))

        for payload, transform in variants:
            candidates.append(_Candidate(
                payload=payload,
                source_index=source_index,
                source_kind=source_kind,  # type: ignore[arg-type]
                transform=transform,
            ))

    return candidates


def _validate_candidates(
    candidates: list[_Candidate],
    *,
    response_model: Any,
    validation_context: dict[str, Any] | None = None,
) -> tuple[Any, _Candidate] | tuple[None, None]:
    for candidate in candidates:
        try:
            output = _restore_structured_output(
                response_model,
                candidate.payload,
                validation_context=validation_context,
            )
            return output, candidate
        except LlmRequestCancelled:
            raise
        except Exception:
            pass
    return None, None


def _score_candidates(
    candidates: list[_Candidate],
    *,
    response_model: Any,
    validation_context: dict[str, Any] | None = None,
) -> list[_Candidate]:
    scored: list[_Candidate] = []
    for candidate in candidates:
        try:
            _restore_structured_output(
                response_model,
                candidate.payload,
                validation_context=validation_context,
            )
            validation = _CandidateValidation(
                status="ok",
                structural_errors=0,
                constraint_errors=0,
                error=None,
            )
        except LlmRequestCancelled:
            raise
        except Exception as exc:
            validation = _classify_validation_error(exc)
        scored.append(_Candidate(
            payload=candidate.payload,
            source_index=candidate.source_index,
            source_kind=candidate.source_kind,
            transform=candidate.transform,
            validation=validation,
        ))
    return sorted(scored, key=lambda c: (
        c.validation.score if c.validation else (999, 999),
        c.source_index,
    ))


def _should_use_synthetic(candidate: _Candidate) -> bool:
    v = candidate.validation
    if v is None or v.status == "ok":
        return True
    structural = v.structural_errors
    complexity = _payload_complexity(candidate.payload)
    ratio = structural / complexity
    return not (ratio > STRUCTURAL_RATIO_THRESHOLD and structural > STRUCTURAL_HARD_FLOOR)
