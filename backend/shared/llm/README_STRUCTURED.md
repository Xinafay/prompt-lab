# Structured Lite — Validation and Repair Algorithm

Specification of `shared.llm.structured_lite.structured_lite` behavior. This document describes **what** the algorithm does, not **how** it is implemented — implementations may differ in detail as long as they honor the invariants below.

---

## 1. Scope and purpose

`structured_lite` accepts:

- `messages` — existing conversation (`base_chat`),
- `prompt` — user-message template containing the required `<<MODEL>>` placeholder,
- `response_model` — a Pydantic class or type annotation,
- `llm_caller` — callable that invokes the LLM,
- `fix_retry` — repair-attempt budget,
- optional: `validation_context`, `fix_prompt` (must contain `<<ERROR>>`), `stream_callback`.

Returns: `(output, usage, final_messages, conversation_log)`.

Goal: obtain a successfully validated instance of `response_model` from an LLM response, automatically repairing common format/validation failures.

---

## 2. Terminology

| Term | Meaning |
|---|---|
| `base_chat` | Input conversation, never mutated. |
| `user_prompt1` | `prompt` with `<<MODEL>>` substituted by the model's JSON schema. |
| `assistant_raw` | Raw LLM response (text + optional `reasoning_content`). |
| **Candidate** | A `(payload, transformation)` pair after extraction and `json_repair`, where `payload` is a `dict` or `list`. |
| **Validation outcome** | Categorization of a `ValidationError`: `ok`, `constraint`, `structural`. |
| **Score** | Tuple `(structural_errors, constraint_errors, source_index)` — smaller is better. |
| **Synthetic assistant** | Synthesized `assistant` message containing `best_candidate.payload` wrapped in a ```json fenced block. |
| `fix_retry` | Shared budget for repair attempts (covers both phase D and phase E). |
| `conversation_log` | Diagnostic record of raw exchanges plus metadata. Never consumed for further prompting. |
| `final_messages` | Conversation returned to the caller on success. |

---

## 3. Pydantic error categorization

Each entry in `ValidationError.errors()` carries a `type` field. Categorization:

### 3.1. Structural (`structural`)

The value does not match the model's type or shape:

`missing`, `model_type`, `model_attributes_type`, `dict_type`, `list_type`, `tuple_type`, `set_type`, `frozen_set_type`, `int_type`, `int_parsing`, `int_from_float`, `string_type`, `bool_type`, `bool_parsing`, `float_type`, `float_parsing`, `bytes_type`, `none_required`, `literal_error`, `enum`, `union_tag_invalid`, `union_tag_not_found`, `is_instance_of`, `is_subclass_of`, `callable_type`, `extra_forbidden`.

### 3.2. Constraint (`constraint`)

The type matches but the value violates a rule:

`value_error` (from `@field_validator`), `assertion_error` (from `@model_validator`), `string_pattern_mismatch`, `string_too_short`, `string_too_long`, `too_short`, `too_long`, `greater_than`, `greater_than_equal`, `less_than`, `less_than_equal`, `multiple_of`, `finite_number`, `unique`, `decimal_*`, `frozen_*`, …

### 3.3. Unknown types

Any `type` not listed above is treated as `structural` (conservative — produces a worse score than if it were `constraint`).

---

## 4. Phase A — initial call

1. `chat = base_chat + [{"role": "user", "content": user_prompt1}]`
2. `assistant_raw = llm_caller(chat)`
3. Append to `conversation_log`:
   - `{"role": "user", "content": user_prompt1, "phase": "initial"}`
   - `{"role": "assistant", "content": assistant_raw.content, "reasoning_content": assistant_raw.reasoning_content, "phase": "initial"}`

---

## 5. Phase B — candidate extraction

### 5.1. Text sources (in order)

1. **Fenced blocks** — every occurrence of ` ```json\n...\n``` ` or ` ```\n...\n``` `. Each block is a separate source.
2. **Brace-extracted** — substrings that begin with `{` or `[` as the **first non-whitespace character on the line** and end with the matching `}` or `]` as the **last non-whitespace character on the line**. Ranges already captured as fenced blocks are skipped.
3. **Raw text** — the entire `assistant_raw.content` as a last-resort fallback.

Each unique source string (after `strip`) enters the list with a `source_index` reflecting the order above.

### 5.2. Parsing

Every source is passed through `json_repair.loads`. Only results that are `dict` or `list` are kept. Other outcomes (None, primitives, parse errors) are discarded.

### 5.3. Transformations

For each parsed payload we generate up to four variants:

| Variant | Operation |
|---|---|
| `raw` | No change. |
| `sanitized` | Recursively strip JSON Schema metadata keys (`$defs`, `properties`, `type`, `required`, …) wherever they do not match model fields. |
| `unwrapped` | When the payload looks like an echo of the schema (top level contains `properties` plus metadata only), return `payload["properties"]`. |
| `sanitized+unwrapped` | First `unwrapped`, then `sanitized` over the result. |

A variant is dropped when its transformation produces no change. Each surviving variant becomes a separate **candidate** with its own `score`.

### 5.4. Branch

- If the candidate set is **empty** → **Phase D** (no-JSON repair) using `assistant_raw` as context.
- Otherwise → **Phase C**.

---

## 6. Phase C — validation and scoring

### 6.1. Validation loop

For each candidate, call `model_validate(payload, context=validation_context)` (or `TypeAdapter.validate_python` for non-Pydantic types):

- Success → **stop immediately**, jump to **Phase F** with this candidate as `output`. Remaining candidates are not inspected.
- `ValidationError` → count `structural_errors` and `constraint_errors` per section 3, compute `score = (structural_errors, constraint_errors, source_index)`.
- Any other exception → treat as a candidate with `score = (∞, ∞, source_index)` (effectively worst).

### 6.2. Picking `best_candidate`

If no candidate validated:

- `best_candidate` = candidate with the lowest `score` (lexicographic comparison).
- Ties are broken by `source_index` (earlier extraction wins).

### 6.3. Fit threshold (phase E vs phase D)

Compute `payload_complexity(best_candidate.payload)` as the sum of:

- the number of keys in every nested `dict` (recursively),
- the number of elements in every nested `list` (recursively).

Minimum `payload_complexity = 1`.

```
structural_ratio = best_candidate.score.structural_errors / payload_complexity
```

- `structural_ratio > 0.10` **and** `structural_errors > 3` → the candidate is too broken to serve as a useful synthetic. Fall through to **Phase D** (no-JSON repair) with `assistant_raw`.
- Otherwise → **Phase E** (invalid-JSON repair) with `best_candidate`.

The `0.10` ratio and the hard floor of `3` live as single-source-of-truth constants for tuning.

### 6.4. Logging to `conversation_log`

Every entry in `conversation_log` may carry an optional `"meta"` key with diagnostic data. Entries without diagnostics omit the key entirely. The `"phase"` field is always top-level.

After each Phase C the `assistant` entry produced in Phase A (or the most recent LLM call) is appended with:

```python
{
  "role": "assistant",
  "content": ...,
  "reasoning_content": ...,
  "phase": "initial" | "repair_N",
  "meta": {
    "candidates": [
      {"source_index": 0, "source_kind": "fenced", "transform": "raw",
       "score": [structural, constraint, source_index], "status": "constraint"},
      ...
    ],
    "best_candidate_index": 0,
    "structural_ratio": 0.0,
    "next_phase": "success" | "repair_invalid" | "repair_no_json",
  },
}
```

On success (Phase F) the final `assistant` entry additionally carries `"iterations": N` inside `meta`.

---

## 7. Phase D — "no-JSON" repair / candidate too broken

### 7.1. Chat construction

```
working_chat = base_chat
             + [user_prompt1]
             + [assistant_raw]                       ← original, unmodified
             + [repair_prompt(formatted_error)]
```

where:

- if Phase B found no candidates → `formatted_error = "No valid JSON object found in response."`
- if Phase C disqualified the candidate via the threshold → `formatted_error = _format_structured_error(best_candidate.error)` (same format as Phase E).

`repair_prompt` is the configured `fix_prompt` template with `<<ERROR>>` (and optionally `<<MODEL>>`) substituted.

### 7.2. Execution

1. Consume **1** unit from `fix_retry`. If the budget is exhausted → `StructuredLiteExhaustedError` (section 10).
2. Append to `conversation_log`:
   - `{"role": "user", "content": repair_prompt, "phase": "repair_N", "meta": {"repair_kind": "no_json"}}`
3. `assistant_raw_new = llm_caller(working_chat)`
4. Append `assistant_raw_new` to `conversation_log` (as in 4.3).
5. Return to **Phase B** with the new response.

---

## 8. Phase E — "invalid-JSON" repair

### 8.1. Synthetic assistant

```
assistant_synthetic_content = "```json\n" + json.dumps(best_candidate.payload, ensure_ascii=False) + "\n```"
```

Synthetic `reasoning_content`: **empty**. The synthetic message is a prompting construct, not a record of actual model thinking.

### 8.2. Chat construction

```
working_chat = base_chat
             + [user_prompt1]
             + [{"role": "assistant", "content": assistant_synthetic_content}]
             + [repair_prompt(_format_structured_error(best_candidate.error))]
```

`_format_structured_error` produces a list of errors with location (`loc`), message (`msg`), and the received value (`input`). It **does not** quote the full JSON — the candidate is already in the assistant message above.

### 8.3. Execution

1. Consume **1** unit from `fix_retry`. If exhausted → `StructuredLiteExhaustedError`.
2. Append to `conversation_log`:
   - `{"role": "user", "content": repair_prompt, "phase": "repair_N", "meta": {"repair_kind": "invalid_json", "synthetic_payload": best_candidate.payload}}`
3. `assistant_raw_new = llm_caller(working_chat)`
4. Append to `conversation_log` (as in 4.3).
5. Return to **Phase B** with the new response.

### 8.4. Iterations and stale candidates

Each Phase B+C iteration operates **exclusively** on candidates from the most recent `assistant_raw`. Candidates from earlier iterations are not carried into scoring. A new `best_candidate` may be substantively worse than the previous one — that is acceptable (assumption: if the model failed to improve given a fresh synthetic plus the error list, further iterations will not help).

---

## 9. Phase F — success

### 9.1. Output format

```
output = best_candidate.payload (validated against response_model)
output_json = json.dumps(model_dump_json(output), ensure_ascii=False)

final_messages = base_chat
               + [{"role": "user", "content": user_prompt1}]
               + [{"role": "assistant",
                   "content": "```json\n" + output_json + "\n```",
                   "reasoning_content": <rule 9.2>}]
```

### 9.2. Reasoning content in `final_messages`

- If success occurred on the first validation (no repair iterations) → use `assistant_raw.reasoning_content` from Phase A.
- If any repairs ran → still use the `reasoning_content` from the **first** LLM response (Phase A), **not** the last. Rationale: the first thinking pass covered substance; subsequent passes were about format repair.

### 9.3. `conversation_log`

Returned unchanged (with full raw responses plus diagnostic metadata). The final `assistant` entry (the validated response) carries success metadata inside its `meta` key — no separate trailing entry is appended.

```python
# final assistant entry in conversation_log (Phase F success)
{
  "role": "assistant",
  "content": ...,          # raw model content (not the clean JSON block)
  "reasoning_content": ...,
  "phase": "initial" | "repair_N",
  "meta": {
    "candidates": [...],
    "best_candidate_index": 0,
    "structural_ratio": 0.0,
    "next_phase": "success",
    "iterations": N,         # total repair iterations used (0 = first attempt succeeded)
  },
}
```

---

## 10. Budget exhaustion — `StructuredLiteExhaustedError`

When `fix_retry` is consumed and the most recent Phase C/D/E still failed:

```python
raise StructuredLiteExhaustedError(
    error=last_error,                 # ValidationError from the last best_candidate (or a generic "no JSON" error)
    conversation=conversation_log,    # full log including all metadata
)
```

The caller has access to `exc.error` and `exc.conversation`. For diagnostics the first N-1 entries of `conversation_log` are the attempt history; trailing entries hold metadata for every repair round.

---

## 11. Cancellation and invariants

- `LlmRequestCancelled` from `llm_caller` is **re-raised immediately** at every layer. It does not mutate `base_chat`, does not return a result, does not persist repair state.
- `validation_context` is forwarded **unchanged** to every `model_validate` / `TypeAdapter.validate_python` call.
- `base_chat` is treated as **immutable**; internal logic operates on copies.
- Transport errors from `llm_caller` (other than `LlmRequestCancelled`) are **not caught** by `structured_lite`. They propagate to the caller. Transport retry logic is the responsibility of `llm_caller`.
- The outer `retry_count` parameter from the previous API **no longer exists**. All resilience against repeated validation failures is concentrated in `fix_retry`.

---

## 12. Stream callbacks

| Event | Call |
|---|---|
| Before Phase A | `notify_prompt_messages(callbacks, [..., user_prompt1], attempt=1)` |
| After Phase A (and after each iteration) | `notify_usage(callbacks, accumulated_usage, attempt=N)` |
| Entering Phase D or Phase E | `notify_stream_phase(callbacks, "fix_retry", reset=True, meta={"attempt": N, "fix_retry": MAX, "kind": "no_json" \| "invalid_json"})` |
| Before each repair LLM call | `notify_prompt_messages(callbacks, [repair_prompt], attempt=N+1)` |

---

## 13. Tunable parameters

Module-level constants defined at the top of `structured_lite.py`. Not environment variables, not function arguments — a single in-code source of truth, edited by changing the file.

| Constant | Default | Meaning |
|---|---|---|
| `STRUCTURAL_RATIO_THRESHOLD` | `0.10` | Threshold on `structural_errors / payload_complexity` above which synthetic is rejected in favor of raw. |
| `STRUCTURAL_HARD_FLOOR` | `3` | Absolute minimum structural-error count below which the ratio threshold is ignored (tolerate small payloads). |
| `DEFAULT_FIX_PROMPT` | (section 14) | Default repair prompt template. |

---

## 14. Default `fix_prompt`

```
Your previous response was invalid for the required JSON schema.

Error:
<<ERROR>>

Return only corrected JSON that matches this schema:
<<MODEL>>
```

`<<ERROR>>` is required. `<<MODEL>>` is optional — if present, it is substituted with the full schema (a deliberate restatement from `user_prompt1` for clarity).

---

## 15. What the algorithm does **not** do

- It does not heuristically repair JSON beyond what `json_repair` provides (e.g., it does not inject missing required fields with defaults).
- It does not retry the whole operation once `fix_retry` is exhausted — that is the caller's responsibility.
- It does not write to any global logger. Diagnostics flow exclusively through `conversation_log` and `stream_callback`.
- It does not redact sensitive data in `conversation_log` — that is the caller's responsibility.
