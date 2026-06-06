"""Diagnostic display test for _format_structured_error.

Run standalone to review how each Pydantic validation error type is
presented to the LLM repair prompt:

    python python/tests/test_format_validation_errors.py

For each case the script prints:
  - the raw error.errors() detail dict (url omitted)
  - the _format_structured_error(error) output

For schema echo cases (section D) it additionally prints both repair modes side by side:
  - hint-only mode (REPLACE_SCHEMA_ECHO_WITH_SKELETON = False): just the hint message
  - skeleton mode  (REPLACE_SCHEMA_ECHO_WITH_SKELETON = True): fake assistant skeleton JSON
    + the fix message the model would receive

No assertions — this is a human-review tool for deciding which error types
need better formatting or different display logic.

Cases are grouped:
  A. Structural errors  (missing, wrong type, extra keys, literal, union)
  B. Constraint errors  (field validators, string/numeric constraints)
  C. Multi-error cases  (mixed and nested)
  D. Schema echo cases  (model returned schema instead of data)
"""

from __future__ import annotations

import json
import sys
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

sys.path.insert(0, "python")
from shared.llm.structured_lite import _format_structured_error, _looks_like_schema_echo
from shared.llm.structured_lite import _SCHEMA_ECHO_HINT_MESSAGE, _SCHEMA_ECHO_SKELETON_FIX_MESSAGE  # type: ignore[attr-defined]
from shared.llm.structured_lite._schema import _generate_skeleton_payload, _schema_dict


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, Exception):
        return {"__exception__": str(value)}
    return repr(value)


def _trigger(model: type[BaseModel], data: Any) -> ValidationError:
    try:
        model.model_validate(data)
    except ValidationError as exc:
        return exc
    raise RuntimeError(f"Expected ValidationError but {model.__name__} accepted {data!r}")


def _print_case(label: str, error: ValidationError) -> None:
    print(f"\n{'═' * 64}")
    print(f"  {label}")
    print(f"{'═' * 64}")

    print("\nRAW error.errors():")
    for i, detail in enumerate(error.errors(include_url=False, include_input=True)):
        print(f"  [{i}]")
        for key, val in detail.items():
            serialized = json.dumps(_to_jsonable(val), ensure_ascii=False)
            # truncate very long values for readability
            if len(serialized) > 120:
                serialized = serialized[:117] + "..."
            print(f"      {key}: {serialized}")

    print("\nFORMATTED (_format_structured_error):")
    formatted = _format_structured_error(error)
    for line in formatted.splitlines():
        print(f"  {line}")


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------


class _Flat(BaseModel):
    name: str
    age: int


class _FlatStrict(BaseModel):
    model_config = ConfigDict(strict=True)
    name: str
    age: int


class _WithBool(BaseModel):
    model_config = ConfigDict(strict=True)
    active: bool


class _WithFloat(BaseModel):
    model_config = ConfigDict(strict=True)
    ratio: float


class _WithList(BaseModel):
    model_config = ConfigDict(strict=True)
    tags: list[str]


class _WithDict(BaseModel):
    model_config = ConfigDict(strict=True)
    meta: dict[str, int]


class _Address(BaseModel):
    street: str
    zip_code: Annotated[str, Field(min_length=5, max_length=5)]


class _Person(BaseModel):
    name: str
    age: int
    address: _Address


class _WithLiteral(BaseModel):
    status: Literal["active", "inactive", "pending"]


class _WithExtra(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    age: int


class _NullRequired(BaseModel):
    deleted_at: None


class _WithScoreValidator(BaseModel):
    name: str
    score: int

    @field_validator("score")
    @classmethod
    def score_must_be_positive(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Score must be non-negative")
        return v


class _WithAssertValidator(BaseModel):
    name: str
    score: int

    @field_validator("score")
    @classmethod
    def score_assert(cls, v: int) -> int:
        assert v <= 100, "Score cannot exceed 100"
        return v


class _WithModelValidator(BaseModel):
    start: int
    end: int

    @model_validator(mode="after")
    def check_range(self) -> "_WithModelValidator":
        if self.end <= self.start:
            raise ValueError("end must be greater than start")
        return self


class _WithStringConstraints(BaseModel):
    code: Annotated[str, Field(min_length=3, max_length=8, pattern=r"^\d+$")]


class _WithNumericConstraints(BaseModel):
    value: Annotated[int, Field(gt=0, lt=100)]


class _WithGeLeConstraints(BaseModel):
    value: Annotated[int, Field(ge=1, le=99)]


class _WithDiscriminatedUnion(BaseModel):
    kind: Literal["cat", "dog"]
    name: str


# ---------------------------------------------------------------------------
# A. Structural errors
# ---------------------------------------------------------------------------


def _section_a() -> None:
    print("\n\n" + "█" * 64)
    print("  A. STRUCTURAL ERRORS")
    print("█" * 64)

    _print_case(
        "A1  missing — single required field",
        _trigger(_Flat, {"name": "Ada"}),
    )

    _print_case(
        "A2  missing — all fields absent",
        _trigger(_Flat, {}),
    )

    _print_case(
        "A3  missing — nested field (address.zip_code)",
        _trigger(_Person, {"name": "Ada", "age": 30, "address": {"street": "Main St"}}),
    )

    _print_case(
        "A4  int_type — string passed for int (strict mode)",
        _trigger(_FlatStrict, {"name": "Ada", "age": "thirty"}),
    )

    _print_case(
        "A5  int_parsing — unparseable string for int (coerce mode)",
        _trigger(_Flat, {"name": "Ada", "age": "not-a-number"}),
    )

    _print_case(
        "A6  int_from_float — fractional float for int",
        _trigger(_Flat, {"name": "Ada", "age": 30.7}),
    )

    _print_case(
        "A7  string_type — int passed for str (strict mode)",
        _trigger(_FlatStrict, {"name": 42, "age": 30}),
    )

    _print_case(
        "A8  bool_type — string passed for bool (strict mode)",
        _trigger(_WithBool, {"active": "yes"}),
    )

    _print_case(
        "A9  bool_parsing — unparseable string for bool (coerce mode)",
        _trigger(type("_CoerceBool", (BaseModel,), {"__annotations__": {"active": bool}}), {"active": "maybe"}),
    )

    _print_case(
        "A10 float_type — string passed for float (strict mode)",
        _trigger(_WithFloat, {"ratio": "high"}),
    )

    _print_case(
        "A11 list_type — dict passed for list (strict mode)",
        _trigger(_WithList, {"tags": {"a": "b"}}),
    )

    _print_case(
        "A12 dict_type — list passed for dict (strict mode)",
        _trigger(_WithDict, {"meta": [1, 2, 3]}),
    )

    _print_case(
        "A13 model_type — string passed for nested model",
        _trigger(_Person, {"name": "Ada", "age": 30, "address": "123 Main St"}),
    )

    _print_case(
        "A14 literal_error — value not in Literal set",
        _trigger(_WithLiteral, {"status": "archived"}),
    )

    _print_case(
        "A15 extra_forbidden — unknown key present",
        _trigger(_WithExtra, {"name": "Ada", "age": 30, "nickname": "Addie"}),
    )

    _print_case(
        "A16 extra_forbidden — multiple unknown keys",
        _trigger(_WithExtra, {"name": "Ada", "age": 30, "nickname": "Addie", "role": "admin"}),
    )

    _print_case(
        "A17 none_required — non-None passed where None required",
        _trigger(_NullRequired, {"deleted_at": "2024-01-01"}),
    )


# ---------------------------------------------------------------------------
# B. Constraint errors
# ---------------------------------------------------------------------------


def _section_b() -> None:
    print("\n\n" + "█" * 64)
    print("  B. CONSTRAINT ERRORS")
    print("█" * 64)

    _print_case(
        "B1  value_error — @field_validator raises ValueError",
        _trigger(_WithScoreValidator, {"name": "Ada", "score": -5}),
    )

    _print_case(
        "B2  assertion_error — @field_validator raises AssertionError",
        _trigger(_WithAssertValidator, {"name": "Ada", "score": 150}),
    )

    _print_case(
        "B3  value_error — @model_validator raises ValueError",
        _trigger(_WithModelValidator, {"start": 10, "end": 5}),
    )

    _print_case(
        "B4  string_too_short — below min_length=3",
        _trigger(_WithStringConstraints, {"code": "12"}),
    )

    _print_case(
        "B5  string_too_long — above max_length=8",
        _trigger(_WithStringConstraints, {"code": "123456789"}),
    )

    _print_case(
        "B6  string_pattern_mismatch — doesn't match pattern r'^\\d+$'",
        _trigger(_WithStringConstraints, {"code": "abc"}),
    )

    _print_case(
        "B7  greater_than — value not > 0 (gt=0)",
        _trigger(_WithNumericConstraints, {"value": 0}),
    )

    _print_case(
        "B8  less_than — value not < 100 (lt=100)",
        _trigger(_WithNumericConstraints, {"value": 100}),
    )

    _print_case(
        "B9  greater_than_equal — value not >= 1 (ge=1)",
        _trigger(_WithGeLeConstraints, {"value": 0}),
    )

    _print_case(
        "B10 less_than_equal — value not <= 99 (le=99)",
        _trigger(_WithGeLeConstraints, {"value": 100}),
    )


# ---------------------------------------------------------------------------
# C. Multi-error and deep-nesting cases
# ---------------------------------------------------------------------------


def _section_c() -> None:
    print("\n\n" + "█" * 64)
    print("  C. MULTI-ERROR AND NESTED CASES")
    print("█" * 64)

    _print_case(
        "C1  multiple missing fields",
        _trigger(_Person, {}),
    )

    _print_case(
        "C2  structural + constraint in same object",
        _trigger(
            _WithScoreValidator,
            {"score": -3},   # name missing (structural) + score invalid (constraint)
        ),
    )

    _print_case(
        "C3  missing + wrong type together",
        _trigger(_Flat, {"age": "not-a-number"}),  # name missing + age unparseable
    )

    _print_case(
        "C4  nested: wrong type deep inside structure",
        _trigger(_Person, {"name": "Ada", "age": 30, "address": {"street": "Main St", "zip_code": 12345}}),
    )

    _print_case(
        "C5  nested: multiple errors across levels",
        _trigger(_Person, {
            "name": "Ada",
            "age": "thirty",          # int_parsing
            "address": {
                "street": "Main St",
                "zip_code": "12",      # string_too_short
            },
        }),
    )

    _print_case(
        "C6  large parent shown as input for missing field",
        _trigger(_Person, {
            "name": "Ada",
            "age": 30,
            "address": {
                "street": "123 Very Long Street Name That Goes On For A While, Apartment 42B",
                # zip_code missing — input shown is the whole address dict
            },
        }),
    )

    _print_case(
        "C7  extra_forbidden + missing together",
        _trigger(_WithExtra, {"nickname": "Addie"}),  # name+age missing, nickname extra
    )


# ---------------------------------------------------------------------------
# D. Schema echo cases
# ---------------------------------------------------------------------------


def _print_schema_echo_case(label: str, payload: Any, model: type[BaseModel]) -> None:
    try:
        model.model_validate(payload)
        error: ValidationError | None = None
    except ValidationError as exc:
        error = exc

    print(f"\n{'═' * 64}")
    print(f"  {label}")
    print(f"{'═' * 64}")

    print(f"\nPAYLOAD: {json.dumps(_to_jsonable(payload), ensure_ascii=False)}")
    detected = _looks_like_schema_echo(payload)
    print(f"_looks_like_schema_echo → {detected}")

    if not detected:
        if error is not None:
            print("\nREPAIR ERROR (standard path):")
            for line in _format_structured_error(error).splitlines():
                print(f"  {line}")
        else:
            print("  (validation passed — no error to format)")
        return

    print("\n── hint-only mode (REPLACE_SCHEMA_ECHO_WITH_SKELETON = False) ──────")
    print("\nREPAIR ERROR:")
    print(f"  {_SCHEMA_ECHO_HINT_MESSAGE}")

    print("\n── skeleton mode (REPLACE_SCHEMA_ECHO_WITH_SKELETON = True) ────────")
    schema = _schema_dict(model)
    skeleton = _generate_skeleton_payload(schema, root_schema=schema)
    skeleton_json = json.dumps(skeleton, ensure_ascii=False, indent=2)
    print("\nFAKE ASSISTANT (injected skeleton):")
    print("  ```json")
    for line in skeleton_json.splitlines():
        print(f"  {line}")
    print("  ```")
    print("\nFIX MESSAGE:")
    print(f"  {_SCHEMA_ECHO_SKELETON_FIX_MESSAGE}")


def _section_d() -> None:
    print("\n\n" + "█" * 64)
    print("  D. SCHEMA ECHO CASES")
    print("█" * 64)

    _print_schema_echo_case(
        "D1  raw schema returned verbatim (all top-level keys are schema metadata)",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
            "required": ["name", "age"],
            "title": "Flat",
        },
        _Flat,
    )

    _print_schema_echo_case(
        "D2  properties echoed as values (unwrapped scenario — schema nodes as field values)",
        {
            "name": {"type": "string", "title": "Name"},
            "age": {"type": "integer", "title": "Age"},
        },
        _Flat,
    )

    _print_schema_echo_case(
        "D3  schema with $ref and title in properties",
        {
            "type": "object",
            "properties": {
                "name": {"title": "Name", "anyOf": [{"type": "string"}, {"type": "null"}]},
                "age": {"title": "Age", "type": "integer"},
            },
            "required": ["age"],
        },
        _Flat,
    )

    _print_schema_echo_case(
        "D4  partial echo — one field real data, one field schema node (false positive check)",
        {
            "name": "Ada",
            "age": {"type": "integer"},
        },
        _Flat,
    )

    _print_schema_echo_case(
        "D5  real data with nested object — should NOT be detected as schema echo",
        {
            "name": "Ada",
            "age": 30,
        },
        _Flat,
    )

    _print_schema_echo_case(
        "D6  nested model: schema echo inside address field",
        {
            "name": "Ada",
            "age": 30,
            "address": {"type": "object", "properties": {"street": {"type": "string"}, "zip_code": {"type": "string"}}},
        },
        _Person,
    )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> None:
    _section_a()
    _section_b()
    _section_c()
    _section_d()
    print(f"\n{'═' * 64}")
    print("  Done. Review output above — no assertions were made.")
    print(f"{'═' * 64}\n")


if __name__ == "__main__":
    main()
