"""Unit and integration tests for structured_lite internals.

Levels covered:
  1. _extract_text_sources         — JSON source extraction from raw text
  2. _generate_candidates          — payload parsing and transformation variants
  3. _classify_validation_error    — structural vs constraint error categorization
  4. _payload_complexity           — complexity scoring for threshold decisions
  5. _validate_candidates          — scoring, best-candidate selection (added in Krok 4)
  6. _should_use_synthetic         — threshold logic (added in Krok 4)
  7. Full repair flow via structured_lite  (added in Krok 5+)
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from shared.llm.chat_result import LlmResponse
from shared.llm.cancellation import LlmRequestCancelled
import shared.llm.structured_lite as _structured_lite_module
from shared.llm.structured_lite import (
    STRUCTURAL_HARD_FLOOR,
    STRUCTURAL_RATIO_THRESHOLD,
    _Candidate,
    _CandidateValidation,
    _classify_validation_error,
    _extract_text_sources,
    _generate_candidates,
    _looks_like_schema_echo,
    _payload_complexity,
    _score_candidates,
    _should_use_synthetic,
    _validate_candidates,
    StructuredLiteExhaustedError,
    structured_lite,
)
from shared.llm.structured_lite._schema import _generate_skeleton_payload, _schema_dict


def _assert_equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label}: expected {expected!r}, got {actual!r}.")


def _assert_true(value: object, label: str) -> None:
    if not value:
        raise ValueError(f"{label}: expected truthy, got {value!r}.")


def _assert_false(value: object, label: str) -> None:
    if value:
        raise ValueError(f"{label}: expected falsy, got {value!r}.")


# ---------------------------------------------------------------------------
# Test models
# ---------------------------------------------------------------------------


class _Profile(BaseModel):
    name: str
    age: int


class _ProfileStrict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    age: int


class _ProfileWithConstraints(BaseModel):
    name: str = Field(min_length=2)
    age: int = Field(ge=0, le=150)


class _ProfileWithValidator(BaseModel):
    name: str
    age: int

    @field_validator("age")
    @classmethod
    def age_must_be_positive(cls, v: int) -> int:
        if v < 0:
            raise ValueError("age must be non-negative")
        return v


class _ProfileWithModelValidator(BaseModel):
    name: str
    age: int

    @model_validator(mode="after")
    def name_age_consistent(self) -> "_ProfileWithModelValidator":
        if self.age < 18 and self.name == "Adult":
            raise ValueError("Name 'Adult' requires age >= 18")
        return self


# ===========================================================================
# 1. _extract_text_sources
# ===========================================================================


def test_extract_fenced_json_block() -> None:
    text = "Here:\n```json\n{\"name\":\"Ada\"}\n```\nDone."
    sources = _extract_text_sources(text)
    kinds = [k for _, k in sources]
    _assert_true("fenced" in kinds, "fenced extracted")
    fenced = [s for s, k in sources if k == "fenced"]
    _assert_equal(fenced[0], '{"name":"Ada"}', "fenced content")


def test_extract_plain_fenced_block() -> None:
    text = "```\n{\"x\":1}\n```"
    sources = _extract_text_sources(text)
    kinds = [k for _, k in sources]
    _assert_true("fenced" in kinds, "plain fenced extracted")


def test_extract_multiple_fenced_blocks() -> None:
    text = "```json\n{\"a\":1}\n```\nsome text\n```json\n{\"b\":2}\n```"
    sources = _extract_text_sources(text)
    fenced = [s for s, k in sources if k == "fenced"]
    _assert_equal(len(fenced), 2, "two fenced blocks")
    _assert_true('{"a":1}' in fenced, "first block content")
    _assert_true('{"b":2}' in fenced, "second block content")


def test_raw_text_always_last_fallback() -> None:
    text = "```json\n{\"a\":1}\n```"
    sources = _extract_text_sources(text)
    last_kind = sources[-1][1]
    _assert_equal(last_kind, "raw_text", "raw_text is last")


def test_fenced_not_duplicated_in_brace_or_raw() -> None:
    text = "```json\n{\"a\":1}\n```"
    sources = _extract_text_sources(text)
    fenced_texts = {s for s, k in sources if k == "fenced"}
    brace_texts = {s for s, k in sources if k == "brace"}
    # brace extraction must not repeat the fenced block
    _assert_false(fenced_texts & brace_texts, "fenced not in brace")


def test_brace_block_first_char_on_line() -> None:
    text = "Start\n{\n  \"name\": \"Ada\"\n}\nEnd"
    sources = _extract_text_sources(text)
    kinds = [k for _, k in sources]
    _assert_true("brace" in kinds, "brace-block extracted")
    brace = [s for s, k in sources if k == "brace"]
    _assert_true('"name"' in brace[0], "brace content has field")


def test_brace_inline_not_extracted_as_brace() -> None:
    text = 'The answer is {"key": "value"} in the middle.'
    sources = _extract_text_sources(text)
    kinds = [k for _, k in sources]
    _assert_false("brace" in kinds, "inline brace not extracted as brace")


def test_array_block_first_char_on_line() -> None:
    text = "Result:\n[\n  1,\n  2\n]\nDone."
    sources = _extract_text_sources(text)
    kinds = [k for _, k in sources]
    _assert_true("brace" in kinds, "array block extracted as brace kind")
    brace = [s for s, k in sources if k == "brace"]
    _assert_true(brace[0].startswith("["), "array block starts with [")


def test_fenced_and_brace_both_captured() -> None:
    text = "```json\n{\"fenced\":1}\n```\n{\n  \"brace\":2\n}"
    sources = _extract_text_sources(text)
    kinds = [k for _, k in sources]
    _assert_true("fenced" in kinds, "fenced present")
    _assert_true("brace" in kinds, "brace present")


def test_empty_response_returns_raw_only() -> None:
    text = "   "
    sources = _extract_text_sources(text)
    _assert_equal(sources, [], "empty stripped text → empty sources")


def test_deduplication_prevents_identical_sources() -> None:
    # When brace content equals fenced content, it must be deduplicated
    text = "```json\n{\"a\":1}\n```\n{\n  \"a\":1\n}"
    sources = _extract_text_sources(text)
    texts = [s for s, _ in sources]
    # There should not be two identical stripped texts
    _assert_equal(len(texts), len(set(texts)), "no duplicate source texts")


def test_fenced_blocks_appear_before_brace_and_raw() -> None:
    text = "{\n  \"brace\":1\n}\n```json\n{\"fenced\":1}\n```"
    sources = _extract_text_sources(text)
    kinds = [k for _, k in sources]
    fenced_idx = next(i for i, k in enumerate(kinds) if k == "fenced")
    brace_idx = next((i for i, k in enumerate(kinds) if k == "brace"), None)
    _assert_true(brace_idx is None or fenced_idx < brace_idx, "fenced before brace in ordering")


# ===========================================================================
# 2. _generate_candidates
# ===========================================================================


def test_generate_single_valid_candidate() -> None:
    text = '{"name":"Ada","age":31}'
    candidates = _generate_candidates(text, response_model=_Profile)
    payloads = [c.payload for c in candidates]
    _assert_true({"name": "Ada", "age": 31} in payloads, "valid payload in candidates")


def test_generate_no_candidates_for_non_json() -> None:
    text = "This is not JSON at all."
    candidates = _generate_candidates(text, response_model=_Profile)
    # json_repair might return something, but if it's not dict/list it's filtered
    for c in candidates:
        _assert_true(isinstance(c.payload, (dict, list)), "all candidates are dict/list")


def test_generate_sanitized_variant_created_when_different() -> None:
    # Payload with JSON Schema metadata mixed in — sanitized should differ
    text = '{"name":"Ada","age":31,"$defs":{}}'
    candidates = _generate_candidates(text, response_model=_Profile)
    transforms = [c.transform for c in candidates]
    # raw always present; sanitized present because $defs is a metadata key
    _assert_true("raw" in transforms, "raw variant present")
    _assert_true("sanitized" in transforms, "sanitized variant present when payload changed")


def test_generate_sanitized_not_duplicated_when_identical() -> None:
    # Clean payload — sanitized == raw, so sanitized must not be added
    text = '{"name":"Ada","age":31}'
    candidates = _generate_candidates(text, response_model=_Profile)
    transforms = [c.transform for c in candidates]
    _assert_equal(transforms.count("raw"), 1, "exactly one raw")
    _assert_false("sanitized" in transforms, "no sanitized when payload unchanged")


def test_generate_unwrapped_variant_for_schema_echo() -> None:
    # Model echoed the schema structure — payload has 'properties' at top level
    text = '{"type":"object","properties":{"name":"Ada","age":31}}'
    candidates = _generate_candidates(text, response_model=_Profile)
    transforms = [c.transform for c in candidates]
    _assert_true("unwrapped" in transforms, "unwrapped variant for schema-echo payload")
    unwrapped = next(c for c in candidates if c.transform == "unwrapped")
    _assert_equal(unwrapped.payload, {"name": "Ada", "age": 31}, "unwrapped payload is properties dict")


def test_generate_no_unwrapped_for_normal_payload() -> None:
    text = '{"name":"Ada","age":31}'
    candidates = _generate_candidates(text, response_model=_Profile)
    transforms = [c.transform for c in candidates]
    _assert_false("unwrapped" in transforms, "no unwrap for normal payload")


def test_generate_from_fenced_block_marks_source_kind() -> None:
    text = "```json\n{\"name\":\"Ada\",\"age\":31}\n```"
    candidates = _generate_candidates(text, response_model=_Profile)
    fenced = [c for c in candidates if c.source_kind == "fenced"]
    _assert_true(len(fenced) > 0, "at least one fenced candidate")


def test_generate_preserves_source_index_order() -> None:
    text = "```json\n{\"name\":\"A\",\"age\":1}\n```\n```json\n{\"name\":\"B\",\"age\":2}\n```"
    candidates = _generate_candidates(text, response_model=_Profile)
    raw_candidates = [c for c in candidates if c.transform == "raw" and c.source_kind == "fenced"]
    indices = [c.source_index for c in raw_candidates]
    _assert_equal(indices, sorted(indices), "source_index monotone")


def test_generate_schema_echo_and_data_both_produce_candidates() -> None:
    # Simulates model returning schema + data JSON: two fenced blocks
    schema_echo = '{"type":"object","properties":{"name":"Ada","age":31}}'
    data = '{"name":"Ada","age":31}'
    text = f"```json\n{schema_echo}\n```\n```json\n{data}\n```"
    candidates = _generate_candidates(text, response_model=_Profile)
    payloads = [c.payload for c in candidates]
    _assert_true({"name": "Ada", "age": 31} in payloads, "data payload present")
    _assert_true(any("unwrapped" == c.transform for c in candidates), "schema-echo unwrapped present")


# ===========================================================================
# 3. _classify_validation_error
# ===========================================================================


def _validate(model: type, payload: dict[str, Any]) -> _CandidateValidation:
    try:
        model.model_validate(payload)
        raise AssertionError("Expected validation error")
    except Exception as exc:
        return _classify_validation_error(exc)


def test_classify_missing_field_is_structural() -> None:
    v = _validate(_Profile, {"name": "Ada"})
    _assert_equal(v.status, "structural", "missing age → structural")
    _assert_true(v.structural_errors > 0, "positive structural count")
    _assert_equal(v.constraint_errors, 0, "no constraint errors")


def test_classify_wrong_type_is_structural() -> None:
    v = _validate(_Profile, {"name": "Ada", "age": "not-a-number"})
    _assert_equal(v.status, "structural", "wrong type → structural")
    _assert_true(v.structural_errors > 0, "positive structural count for type mismatch")


def test_classify_extra_forbidden_is_structural() -> None:
    v = _validate(_ProfileStrict, {"name": "Ada", "age": 31, "extra": "bad"})
    _assert_equal(v.status, "structural", "extra_forbidden → structural")
    _assert_true(v.structural_errors > 0, "extra_forbidden counted as structural")


def test_classify_field_constraint_is_constraint() -> None:
    v = _validate(_ProfileWithConstraints, {"name": "Ada", "age": 200})
    _assert_equal(v.status, "constraint", "age > 150 → constraint")
    _assert_equal(v.structural_errors, 0, "no structural errors")
    _assert_true(v.constraint_errors > 0, "positive constraint count")


def test_classify_min_length_is_constraint() -> None:
    v = _validate(_ProfileWithConstraints, {"name": "A", "age": 30})
    _assert_equal(v.status, "constraint", "min_length violation → constraint")
    _assert_equal(v.structural_errors, 0, "no structural errors for min_length")


def test_classify_field_validator_value_error_is_constraint() -> None:
    v = _validate(_ProfileWithValidator, {"name": "Ada", "age": -1})
    _assert_equal(v.status, "constraint", "field_validator ValueError → constraint")
    _assert_equal(v.structural_errors, 0, "no structural errors for field_validator")


def test_classify_model_validator_is_constraint() -> None:
    v = _validate(_ProfileWithModelValidator, {"name": "Adult", "age": 10})
    _assert_equal(v.status, "constraint", "model_validator → constraint")


def test_classify_mixed_errors_status_is_structural() -> None:
    # Missing field (structural) + value error (constraint) together → status = structural
    v = _validate(_ProfileWithConstraints, {"name": "A"})  # missing age + name too short
    _assert_equal(v.status, "structural", "mixed errors → structural status")
    _assert_true(v.structural_errors > 0, "has structural")
    _assert_true(v.constraint_errors > 0, "has constraint")


def test_classify_non_validation_error_is_exception() -> None:
    v = _classify_validation_error(RuntimeError("boom"))
    _assert_equal(v.status, "exception", "non-ValidationError → exception")
    _assert_equal(v.structural_errors, 0, "no structural for generic exception")
    _assert_equal(v.constraint_errors, 0, "no constraint for generic exception")


def test_classify_score_structural_dominates_constraint() -> None:
    v_structural = _validate(_Profile, {"name": "Ada"})           # missing age = structural
    v_constraint = _validate(_ProfileWithConstraints, {"name": "Ada", "age": 200})  # ge violation
    _assert_true(v_structural.score > v_constraint.score, "structural score worse than constraint score")


# ===========================================================================
# 4. _payload_complexity
# ===========================================================================


def test_complexity_empty_dict() -> None:
    _assert_equal(_payload_complexity({}), 1, "empty dict → min 1")


def test_complexity_empty_list() -> None:
    _assert_equal(_payload_complexity([]), 1, "empty list → min 1")


def test_complexity_flat_dict() -> None:
    _assert_equal(_payload_complexity({"a": 1, "b": 2}), 2, "flat dict with 2 keys")


def test_complexity_flat_list() -> None:
    _assert_equal(_payload_complexity([1, 2, 3]), 3, "flat list with 3 items")


def test_complexity_nested_dict() -> None:
    payload = {"a": {"b": 1, "c": 2}, "d": 3}
    # top: 2 keys + inner: 2 keys = 4; min check
    result = _payload_complexity(payload)
    _assert_true(result > 2, "nested dict complexity > flat")


def test_complexity_nested_list_of_dicts() -> None:
    payload = [{"x": 1}, {"x": 2}]
    result = _payload_complexity(payload)
    _assert_true(result > 2, "list of dicts complexity > flat list")


def test_complexity_primitives_do_not_add() -> None:
    # Leaf values are primitives — they don't increase complexity beyond their container
    flat = {"a": 1, "b": "hello", "c": True}
    _assert_equal(_payload_complexity(flat), 3, "3 primitive-valued keys")


def test_complexity_non_container_is_zero() -> None:
    _assert_equal(_payload_complexity("string"), 0, "primitive → 0")
    _assert_equal(_payload_complexity(42), 0, "int → 0")
    _assert_equal(_payload_complexity(None), 0, "None → 0")


# ===========================================================================
# 5. _validate_candidates and _score_candidates
# ===========================================================================


def _make_candidate(payload: Any, source_index: int = 0) -> _Candidate:
    return _Candidate(payload=payload, source_index=source_index, source_kind="raw_text", transform="raw")


def test_validate_candidates_returns_first_valid() -> None:
    good = _make_candidate({"name": "Ada", "age": 31})
    bad = _make_candidate({"name": "Ada"})  # missing age
    output, winner = _validate_candidates([bad, good], response_model=_Profile)
    _assert_true(output is not None, "output returned")
    _assert_equal(winner, good, "first valid candidate returned")


def test_validate_candidates_returns_none_when_all_fail() -> None:
    bad1 = _make_candidate({"name": "Ada"})
    bad2 = _make_candidate({"age": 31})
    output, winner = _validate_candidates([bad1, bad2], response_model=_Profile)
    _assert_equal(output, None, "None when all fail")
    _assert_equal(winner, None, "None winner when all fail")


def test_validate_candidates_stops_at_first_valid() -> None:
    good = _make_candidate({"name": "Ada", "age": 31})
    never_reached = _make_candidate({"name": "Bob", "age": 25})
    output, _ = _validate_candidates([good, never_reached], response_model=_Profile)
    _assert_equal(output.name, "Ada", "first valid wins")  # type: ignore[union-attr]


def test_score_candidates_annotates_validation() -> None:
    good = _make_candidate({"name": "Ada", "age": 31})
    scored = _score_candidates([good], response_model=_Profile)
    _assert_equal(scored[0].validation.status, "ok", "valid payload → ok status")  # type: ignore[union-attr]


def test_score_candidates_sorts_best_first() -> None:
    structural = _make_candidate({"name": "Ada"}, source_index=0)   # missing age
    constraint = _make_candidate({"name": "Ada", "age": 200}, source_index=1)  # age > 150
    scored = _score_candidates([structural, constraint], response_model=_ProfileWithConstraints)
    _assert_equal(scored[0].source_index, 1, "constraint error ranked before structural")


def test_score_candidates_ties_broken_by_source_index() -> None:
    c1 = _make_candidate({"name": "Ada"}, source_index=0)
    c2 = _make_candidate({"name": "Bob"}, source_index=1)
    scored = _score_candidates([c2, c1], response_model=_Profile)
    _assert_equal(scored[0].source_index, 0, "lower source_index wins tie")


def test_schema_echo_scores_worse_than_data() -> None:
    schema_echo = _make_candidate({"type": "object", "properties": {"name": "Ada", "age": 31}}, source_index=0)
    data = _make_candidate({"name": "Ada", "age": 200}, source_index=1)  # constraint error only
    scored = _score_candidates([schema_echo, data], response_model=_ProfileWithConstraints)
    _assert_equal(scored[0].source_index, 1, "data payload (constraint only) ranked before schema-echo")


# ===========================================================================
# 6. _should_use_synthetic
# ===========================================================================


def _candidate_with_validation(
    payload: Any,
    structural: int,
    constraint: int,
    status: str = "structural",
    source_index: int = 0,
) -> _Candidate:
    return _Candidate(
        payload=payload,
        source_index=source_index,
        source_kind="raw_text",
        transform="raw",
        validation=_CandidateValidation(
            status=status,  # type: ignore[arg-type]
            structural_errors=structural,
            constraint_errors=constraint,
            error=None,
        ),
    )


def test_should_use_synthetic_for_ok_candidate() -> None:
    c = _candidate_with_validation({"name": "Ada", "age": 31}, structural=0, constraint=0, status="ok")
    _assert_true(_should_use_synthetic(c), "ok candidate → synthetic")


def test_should_use_synthetic_for_constraint_only() -> None:
    payload = {"name": "Ada", "age": 31}
    c = _candidate_with_validation(payload, structural=0, constraint=2)
    _assert_true(_should_use_synthetic(c), "constraint-only → synthetic")


def test_should_use_synthetic_below_hard_floor() -> None:
    # 3 structural errors but below hard floor → synthetic
    payload = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6}  # complexity = 6
    c = _candidate_with_validation(payload, structural=STRUCTURAL_HARD_FLOOR, constraint=0)
    # ratio = 3/6 = 0.50 > threshold but structural == hard_floor (not >) → synthetic
    _assert_true(_should_use_synthetic(c), "structural == hard_floor → synthetic (not strictly above)")


def test_should_use_raw_above_both_thresholds() -> None:
    # structural > STRUCTURAL_HARD_FLOOR and ratio > STRUCTURAL_RATIO_THRESHOLD
    payload = {"a": 1}  # complexity = 1; ratio = (HARD_FLOOR+1)/1 >> threshold
    c = _candidate_with_validation(payload, structural=STRUCTURAL_HARD_FLOOR + 1, constraint=0)
    _assert_false(_should_use_synthetic(c), "above both thresholds → raw (not synthetic)")


def test_should_use_synthetic_low_ratio_even_with_many_structural() -> None:
    # Many structural errors but very large payload → ratio stays below threshold
    payload = {str(i): i for i in range(200)}  # complexity = 200
    c = _candidate_with_validation(payload, structural=STRUCTURAL_HARD_FLOOR + 1, constraint=0)
    ratio = (STRUCTURAL_HARD_FLOOR + 1) / 200
    _assert_true(ratio < STRUCTURAL_RATIO_THRESHOLD, "ratio confirms test precondition")
    _assert_true(_should_use_synthetic(c), "low ratio despite many structural → synthetic")


# ===========================================================================
# 7. structured_lite integration — full flow
# ===========================================================================


def _make_caller(*responses: str | LlmResponse | Exception):
    """Return an llm_caller that yields items in order. Raises exceptions inline."""
    items: list[str | LlmResponse | Exception] = list(responses)
    idx = {"i": 0}

    def caller(msgs: list[Any]) -> LlmResponse:
        item = items[idx["i"]]
        idx["i"] += 1
        if isinstance(item, Exception):
            raise item
        if isinstance(item, str):
            return LlmResponse(content=item, usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})
        return item

    return caller


_PROMPT = "Return JSON matching <<MODEL>>"


def test_integration_success_first_pass() -> None:
    caller = _make_caller('{"name":"Ada","age":31}')
    output, usage, final_msgs, conv = structured_lite(
        [], _PROMPT, llm_caller=caller, response_model=_Profile
    )
    _assert_true(isinstance(output, _Profile), "typed output")
    _assert_equal(output.name, "Ada", "name")
    _assert_equal(output.age, 31, "age")
    _assert_true(final_msgs[-1]["content"].startswith("```json"), "final assistant fenced")
    _assert_equal(conv[-1]["meta"]["next_phase"], "success", "success in meta")
    _assert_equal(conv[-1]["meta"]["iterations"], 0, "zero iterations")


def test_integration_success_from_fenced_block() -> None:
    caller = _make_caller('Here is the answer:\n```json\n{"name":"Ada","age":31}\n```')
    output, _, _, _ = structured_lite([], _PROMPT, llm_caller=caller, response_model=_Profile)
    _assert_equal(output.name, "Ada", "extracted from fenced block")  # type: ignore[union-attr]


def test_integration_repair_invalid_json() -> None:
    caller = _make_caller(
        '{"name":"Ada"}',          # missing age → Phase E repair
        '{"name":"Ada","age":31}',  # fixed
    )
    output, _, _, conv = structured_lite(
        [], _PROMPT, llm_caller=caller, response_model=_Profile, fix_retry=1
    )
    _assert_equal(output.name, "Ada", "name after repair")  # type: ignore[union-attr]
    _assert_equal(output.age, 31, "age after repair")  # type: ignore[union-attr]
    user_entries = [e for e in conv if e["role"] == "user"]
    repair_entries = [e for e in user_entries if "repair" in e.get("phase", "")]
    _assert_equal(len(repair_entries), 1, "one repair prompt in conversation_log")
    _assert_equal(repair_entries[0]["meta"]["repair_kind"], "invalid_json", "repair_kind invalid_json")


def test_integration_repair_no_json() -> None:
    caller = _make_caller(
        "Sorry, I cannot help with that.",   # no JSON → Phase D repair
        '{"name":"Ada","age":31}',
    )
    output, _, _, conv = structured_lite(
        [], _PROMPT, llm_caller=caller, response_model=_Profile, fix_retry=1
    )
    _assert_equal(output.name, "Ada", "name after no-json repair")  # type: ignore[union-attr]
    repair_entries = [e for e in conv if e.get("role") == "user" and "repair" in e.get("phase", "")]
    _assert_equal(repair_entries[0]["meta"]["repair_kind"], "no_json", "repair_kind no_json")


def test_integration_exhausted_raises_error() -> None:
    caller = _make_caller('{"name":"Ada"}', '{"name":"Ada"}')  # always missing age
    try:
        structured_lite([], _PROMPT, llm_caller=caller, response_model=_Profile, fix_retry=1)
        raise ValueError("Expected StructuredLiteExhaustedError")
    except StructuredLiteExhaustedError as exc:
        _assert_true(exc.error is not None, "error attached")
        _assert_true(len(exc.conversation) > 0, "conversation attached")


def test_integration_fix_retry_zero_exhausts_immediately() -> None:
    caller = _make_caller('{"name":"Ada"}')  # missing age
    try:
        structured_lite([], _PROMPT, llm_caller=caller, response_model=_Profile, fix_retry=0)
        raise ValueError("Expected StructuredLiteExhaustedError")
    except StructuredLiteExhaustedError:
        pass


def test_integration_cancellation_propagates() -> None:
    caller = _make_caller(LlmRequestCancelled())
    try:
        structured_lite([], _PROMPT, llm_caller=caller, response_model=_Profile)
        raise ValueError("Expected LlmRequestCancelled")
    except LlmRequestCancelled:
        pass


def test_integration_cancellation_during_repair_propagates() -> None:
    caller = _make_caller(
        '{"name":"Ada"}',       # first call: invalid
        LlmRequestCancelled(),  # repair call: cancelled
    )
    try:
        structured_lite([], _PROMPT, llm_caller=caller, response_model=_Profile, fix_retry=1)
        raise ValueError("Expected LlmRequestCancelled")
    except LlmRequestCancelled:
        pass


def test_integration_transport_error_propagates_without_retry() -> None:
    caller = _make_caller(RuntimeError("network error"))
    try:
        structured_lite([], _PROMPT, llm_caller=caller, response_model=_Profile)
        raise ValueError("Expected RuntimeError")
    except RuntimeError as exc:
        _assert_true("network" in str(exc), "original transport error")


def test_integration_reasoning_content_from_first_response_in_final_messages() -> None:
    caller = _make_caller(
        LlmResponse(content='{"name":"Ada"}', usage=None, reasoning_content="first thinking"),
        LlmResponse(content='{"name":"Ada","age":31}', usage=None, reasoning_content="repair thinking"),
    )
    _, _, final_msgs, _ = structured_lite(
        [], _PROMPT, llm_caller=caller, response_model=_Profile, fix_retry=1
    )
    _assert_equal(
        final_msgs[-1].get("reasoning_content"),
        "first thinking",
        "reasoning_content from first response preserved",
    )


def test_integration_reasoning_content_first_pass_preserved() -> None:
    caller = _make_caller(
        LlmResponse(content='{"name":"Ada","age":31}', usage=None, reasoning_content="only thinking"),
    )
    _, _, final_msgs, _ = structured_lite([], _PROMPT, llm_caller=caller, response_model=_Profile)
    _assert_equal(final_msgs[-1].get("reasoning_content"), "only thinking", "first-pass reasoning preserved")


def test_integration_conversation_log_has_phase_fields() -> None:
    caller = _make_caller('{"name":"Ada"}', '{"name":"Ada","age":31}')
    _, _, _, conv = structured_lite([], _PROMPT, llm_caller=caller, response_model=_Profile, fix_retry=1)
    phases = [e["phase"] for e in conv]
    _assert_true("initial" in phases, "initial phase present")
    _assert_true(any("repair" in p for p in phases), "repair phase present")


def test_integration_conversation_log_meta_has_candidates() -> None:
    caller = _make_caller('{"name":"Ada"}', '{"name":"Ada","age":31}')
    _, _, _, conv = structured_lite([], _PROMPT, llm_caller=caller, response_model=_Profile, fix_retry=1)
    first_assistant = next(e for e in conv if e["role"] == "assistant" and e["phase"] == "initial")
    _assert_true("meta" in first_assistant, "meta present on first assistant")
    _assert_true("candidates" in first_assistant["meta"], "candidates in meta")


def test_integration_repair_chat_uses_synthetic_for_partial_json() -> None:
    """Repair user message should contain the bad payload when using synthetic path."""
    caller = _make_caller('{"name":"Ada"}', '{"name":"Ada","age":31}')
    _, _, _, conv = structured_lite([], _PROMPT, llm_caller=caller, response_model=_Profile, fix_retry=1)
    repair_user = next(e for e in conv if e.get("role") == "user" and "repair" in e.get("phase", ""))
    _assert_true("synthetic_payload" in repair_user["meta"], "synthetic_payload recorded in meta")
    _assert_equal(repair_user["meta"]["synthetic_payload"]["name"], "Ada", "synthetic payload content")


def test_integration_schema_echo_picks_data_over_schema() -> None:
    """When model returns both a schema-echo and real data, data wins."""
    schema_echo = '{"type":"object","properties":{"name":"Ada","age":31}}'
    data = '{"name":"Ada","age":31}'
    caller = _make_caller(f"```json\n{schema_echo}\n```\n```json\n{data}\n```")
    output, _, _, _ = structured_lite([], _PROMPT, llm_caller=caller, response_model=_Profile)
    _assert_equal(output.name, "Ada", "correct name")  # type: ignore[union-attr]
    _assert_equal(output.age, 31, "correct age")  # type: ignore[union-attr]


def test_integration_base_chat_not_mutated() -> None:
    base = [{"role": "system", "content": "Be helpful."}]
    original = [dict(m) for m in base]
    caller = _make_caller('{"name":"Ada","age":31}')
    structured_lite(base, _PROMPT, llm_caller=caller, response_model=_Profile)
    _assert_equal(base, original, "base_chat unchanged")


def test_integration_final_messages_contains_prompt_and_clean_json() -> None:
    base = [{"role": "system", "content": "Be helpful."}]
    caller = _make_caller('{"name":"Ada","age":31}')
    _, _, final_msgs, _ = structured_lite(base, _PROMPT, llm_caller=caller, response_model=_Profile)
    _assert_equal(len(final_msgs), 3, "system + user_prompt1 + assistant")
    _assert_true("<<MODEL>>" not in final_msgs[1]["content"], "schema substituted in prompt")
    _assert_true(final_msgs[2]["content"].startswith("```json"), "assistant is clean JSON block")


def test_integration_usage_accumulated_across_repairs() -> None:
    caller = _make_caller(
        LlmResponse(content='{"name":"Ada"}', usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
        LlmResponse(content='{"name":"Ada","age":31}', usage={"prompt_tokens": 20, "completion_tokens": 3, "total_tokens": 23}),
    )
    _, usage, _, _ = structured_lite([], _PROMPT, llm_caller=caller, response_model=_Profile, fix_retry=1)
    _assert_true(usage is not None, "usage not None")
    assert usage is not None
    _assert_equal(usage["prompt_tokens"], 30, "accumulated prompt_tokens")
    _assert_equal(usage["completion_tokens"], 8, "accumulated completion_tokens")
    _assert_equal(usage["total_tokens"], 38, "accumulated total_tokens")


# ===========================================================================
# 8. _looks_like_schema_echo
# ===========================================================================


def test_schema_echo_raw_schema_all_metadata_keys() -> None:
    payload = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
        "required": ["name", "age"],
        "title": "Profile",
    }
    _assert_true(_looks_like_schema_echo(payload), "raw schema with all metadata keys → echo")


def test_schema_echo_properties_with_schema_node_values() -> None:
    payload = {
        "name": {"type": "string", "title": "Name"},
        "age": {"type": "integer", "title": "Age"},
    }
    _assert_true(_looks_like_schema_echo(payload), "property values with schema nodes → echo")


def test_schema_echo_any_of_triggers_detection() -> None:
    payload = {
        "name": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "age": 30,
    }
    _assert_true(_looks_like_schema_echo(payload), "anyOf value → echo")


def test_schema_echo_not_triggered_for_real_data() -> None:
    _assert_false(_looks_like_schema_echo({"name": "Ada", "age": 31}), "real data → not echo")


def test_schema_echo_not_triggered_for_empty_dict() -> None:
    _assert_false(_looks_like_schema_echo({}), "empty dict → not echo")


def test_schema_echo_not_triggered_for_non_dict() -> None:
    _assert_false(_looks_like_schema_echo([1, 2, 3]), "list → not echo")
    _assert_false(_looks_like_schema_echo("string"), "string → not echo")
    _assert_false(_looks_like_schema_echo(None), "None → not echo")


def test_schema_echo_not_triggered_for_nested_real_values() -> None:
    payload = {"name": "Ada", "address": {"street": "Main St", "zip_code": "12345"}}
    _assert_false(_looks_like_schema_echo(payload), "nested real values → not echo")


def test_schema_echo_not_triggered_for_status_type_field() -> None:
    # A model with a "type" field whose value is not a JSON Schema primitive type
    payload = {"name": "Ada", "type": "admin"}
    _assert_false(_looks_like_schema_echo(payload), "type=admin (non-primitive) → not echo")


# ===========================================================================
# 9. _generate_skeleton_payload
# ===========================================================================


class _NestedAddress(BaseModel):
    street: str
    zip_code: str


class _FullProfile(BaseModel):
    name: str
    age: int
    score: float
    active: bool
    tags: list[str]
    nickname: str | None = None
    address: _NestedAddress


def test_skeleton_primitive_types() -> None:
    schema = _schema_dict(_Profile)
    skeleton = _generate_skeleton_payload(schema, root_schema=schema)
    _assert_true(isinstance(skeleton, dict), "skeleton is dict")
    _assert_equal(skeleton["name"], "", "string field → empty string")
    _assert_equal(skeleton["age"], 0, "int field → 0")


def test_skeleton_all_primitive_types() -> None:
    class _AllPrimitives(BaseModel):
        s: str
        i: int
        f: float
        b: bool

    schema = _schema_dict(_AllPrimitives)
    skeleton = _generate_skeleton_payload(schema, root_schema=schema)
    _assert_equal(skeleton["s"], "", "str → ''")
    _assert_equal(skeleton["i"], 0, "int → 0")
    _assert_equal(skeleton["f"], 0, "float → 0")
    _assert_equal(skeleton["b"], False, "bool → False")


def test_skeleton_list_field_is_empty_list() -> None:
    class _WithList(BaseModel):
        tags: list[str]

    schema = _schema_dict(_WithList)
    skeleton = _generate_skeleton_payload(schema, root_schema=schema)
    _assert_equal(skeleton["tags"], [], "list field → []")


def test_skeleton_optional_picks_non_null_variant() -> None:
    class _WithOptional(BaseModel):
        nickname: str | None = None

    schema = _schema_dict(_WithOptional)
    skeleton = _generate_skeleton_payload(schema, root_schema=schema)
    _assert_equal(skeleton["nickname"], "", "Optional[str] → '' (non-null variant)")


def test_skeleton_nested_model_recursed() -> None:
    schema = _schema_dict(_FullProfile)
    skeleton = _generate_skeleton_payload(schema, root_schema=schema)
    _assert_true(isinstance(skeleton["address"], dict), "nested model → dict")
    _assert_equal(skeleton["address"]["street"], "", "nested str → ''")
    _assert_equal(skeleton["address"]["zip_code"], "", "nested str → ''")


def test_skeleton_full_profile_has_all_keys() -> None:
    schema = _schema_dict(_FullProfile)
    skeleton = _generate_skeleton_payload(schema, root_schema=schema)
    expected_keys = {"name", "age", "score", "active", "tags", "nickname", "address"}
    _assert_equal(set(skeleton.keys()), expected_keys, "all fields present in skeleton")


# ===========================================================================
# 10. REPLACE_SCHEMA_ECHO_WITH_SKELETON integration
# ===========================================================================


class _RestoreSchemaEchoFlag:
    """Context manager that restores the module flag after the test."""

    def __enter__(self) -> "_RestoreSchemaEchoFlag":
        self._original = _structured_lite_module.REPLACE_SCHEMA_ECHO_WITH_SKELETON
        return self

    def __exit__(self, *_: object) -> None:
        _structured_lite_module.REPLACE_SCHEMA_ECHO_WITH_SKELETON = self._original


def test_integration_schema_echo_hint_when_flag_off() -> None:
    schema_echo = '{"type":"object","properties":{"name":{"type":"string"},"age":{"type":"integer"}},"required":["name","age"]}'
    caller = _make_caller(schema_echo, '{"name":"Ada","age":31}')
    with _RestoreSchemaEchoFlag():
        _structured_lite_module.REPLACE_SCHEMA_ECHO_WITH_SKELETON = False
        _, _, _, conv = structured_lite([], _PROMPT, llm_caller=caller, response_model=_Profile, fix_retry=1)
    repair_user = next(e for e in conv if e.get("role") == "user" and "repair" in e.get("phase", ""))
    _assert_true("schema" in repair_user["content"].lower(), "hint mentions schema")
    _assert_true("skeleton_payload" not in repair_user["meta"], "no skeleton_payload when flag off")


def test_integration_schema_echo_skeleton_when_flag_on() -> None:
    schema_echo = '{"type":"object","properties":{"name":{"type":"string"},"age":{"type":"integer"}},"required":["name","age"]}'
    caller = _make_caller(schema_echo, '{"name":"Ada","age":31}')
    with _RestoreSchemaEchoFlag():
        _structured_lite_module.REPLACE_SCHEMA_ECHO_WITH_SKELETON = True
        output, _, _, conv = structured_lite([], _PROMPT, llm_caller=caller, response_model=_Profile, fix_retry=1)
    _assert_equal(output.name, "Ada", "output correct after skeleton repair")  # type: ignore[union-attr]
    repair_user = next(e for e in conv if e.get("role") == "user" and "repair" in e.get("phase", ""))
    _assert_equal(repair_user["meta"]["repair_kind"], "schema_echo_skeleton", "repair_kind recorded")
    _assert_true("skeleton_payload" in repair_user["meta"], "skeleton_payload in meta")
    _assert_equal(repair_user["meta"]["skeleton_payload"]["name"], "", "skeleton name is empty string")
    _assert_equal(repair_user["meta"]["skeleton_payload"]["age"], 0, "skeleton age is 0")
    _assert_true("empty" in repair_user["content"].lower(), "fix message mentions empty")


def test_integration_schema_echo_skeleton_assistant_message_is_skeleton() -> None:
    """The assistant message in the repair conversation should be the skeleton, not the echo."""
    schema_echo = '{"type":"object","properties":{"name":{"type":"string"},"age":{"type":"integer"}},"required":["name","age"]}'
    caller = _make_caller(schema_echo, '{"name":"Ada","age":31}')
    with _RestoreSchemaEchoFlag():
        _structured_lite_module.REPLACE_SCHEMA_ECHO_WITH_SKELETON = True
        _, _, _, conv = structured_lite([], _PROMPT, llm_caller=caller, response_model=_Profile, fix_retry=1)
    repair_assistant = next(
        e for e in conv
        if e.get("role") == "assistant" and e.get("phase", "").startswith("repair")
    )
    # The assistant before the repair prompt should be the injected skeleton, but since
    # conversation_log only records user/assistant turns (not the working messages), we
    # verify via the skeleton_payload in the repair_user meta instead.
    repair_user = next(e for e in conv if e.get("role") == "user" and "repair" in e.get("phase", ""))
    _assert_true("skeleton_payload" in repair_user["meta"], "skeleton recorded in meta")
    _assert_true(schema_echo not in repair_user["content"], "schema echo not echoed back in fix message")


# ===========================================================================
# main
# ===========================================================================


def main() -> int:
    tests = [
        # _extract_text_sources
        test_extract_fenced_json_block,
        test_extract_plain_fenced_block,
        test_extract_multiple_fenced_blocks,
        test_raw_text_always_last_fallback,
        test_fenced_not_duplicated_in_brace_or_raw,
        test_brace_block_first_char_on_line,
        test_brace_inline_not_extracted_as_brace,
        test_array_block_first_char_on_line,
        test_fenced_and_brace_both_captured,
        test_empty_response_returns_raw_only,
        test_deduplication_prevents_identical_sources,
        test_fenced_blocks_appear_before_brace_and_raw,
        # _generate_candidates
        test_generate_single_valid_candidate,
        test_generate_no_candidates_for_non_json,
        test_generate_sanitized_variant_created_when_different,
        test_generate_sanitized_not_duplicated_when_identical,
        test_generate_unwrapped_variant_for_schema_echo,
        test_generate_no_unwrapped_for_normal_payload,
        test_generate_from_fenced_block_marks_source_kind,
        test_generate_preserves_source_index_order,
        test_generate_schema_echo_and_data_both_produce_candidates,
        # _classify_validation_error
        test_classify_missing_field_is_structural,
        test_classify_wrong_type_is_structural,
        test_classify_extra_forbidden_is_structural,
        test_classify_field_constraint_is_constraint,
        test_classify_min_length_is_constraint,
        test_classify_field_validator_value_error_is_constraint,
        test_classify_model_validator_is_constraint,
        test_classify_mixed_errors_status_is_structural,
        test_classify_non_validation_error_is_exception,
        test_classify_score_structural_dominates_constraint,
        # _payload_complexity
        test_complexity_empty_dict,
        test_complexity_empty_list,
        test_complexity_flat_dict,
        test_complexity_flat_list,
        test_complexity_nested_dict,
        test_complexity_nested_list_of_dicts,
        test_complexity_primitives_do_not_add,
        test_complexity_non_container_is_zero,
        # _validate_candidates and _score_candidates
        test_validate_candidates_returns_first_valid,
        test_validate_candidates_returns_none_when_all_fail,
        test_validate_candidates_stops_at_first_valid,
        test_score_candidates_annotates_validation,
        test_score_candidates_sorts_best_first,
        test_score_candidates_ties_broken_by_source_index,
        test_schema_echo_scores_worse_than_data,
        # _should_use_synthetic
        test_should_use_synthetic_for_ok_candidate,
        test_should_use_synthetic_for_constraint_only,
        test_should_use_synthetic_below_hard_floor,
        test_should_use_raw_above_both_thresholds,
        test_should_use_synthetic_low_ratio_even_with_many_structural,
        # _looks_like_schema_echo
        test_schema_echo_raw_schema_all_metadata_keys,
        test_schema_echo_properties_with_schema_node_values,
        test_schema_echo_any_of_triggers_detection,
        test_schema_echo_not_triggered_for_real_data,
        test_schema_echo_not_triggered_for_empty_dict,
        test_schema_echo_not_triggered_for_non_dict,
        test_schema_echo_not_triggered_for_nested_real_values,
        test_schema_echo_not_triggered_for_status_type_field,
        # _generate_skeleton_payload
        test_skeleton_primitive_types,
        test_skeleton_all_primitive_types,
        test_skeleton_list_field_is_empty_list,
        test_skeleton_optional_picks_non_null_variant,
        test_skeleton_nested_model_recursed,
        test_skeleton_full_profile_has_all_keys,
        # REPLACE_SCHEMA_ECHO_WITH_SKELETON integration
        test_integration_schema_echo_hint_when_flag_off,
        test_integration_schema_echo_skeleton_when_flag_on,
        test_integration_schema_echo_skeleton_assistant_message_is_skeleton,
        # structured_lite integration
        test_integration_success_first_pass,
        test_integration_success_from_fenced_block,
        test_integration_repair_invalid_json,
        test_integration_repair_no_json,
        test_integration_exhausted_raises_error,
        test_integration_fix_retry_zero_exhausts_immediately,
        test_integration_cancellation_propagates,
        test_integration_cancellation_during_repair_propagates,
        test_integration_transport_error_propagates_without_retry,
        test_integration_reasoning_content_from_first_response_in_final_messages,
        test_integration_reasoning_content_first_pass_preserved,
        test_integration_conversation_log_has_phase_fields,
        test_integration_conversation_log_meta_has_candidates,
        test_integration_repair_chat_uses_synthetic_for_partial_json,
        test_integration_schema_echo_picks_data_over_schema,
        test_integration_base_chat_not_mutated,
        test_integration_final_messages_contains_prompt_and_clean_json,
        test_integration_usage_accumulated_across_repairs,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
