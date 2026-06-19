from __future__ import annotations

import json
from typing import Any, cast

from shared.llm.chat_result import assistant_conversation_message
from shared.llm.cancellation import LlmRequestCancelled
from shared.llm.stream_callbacks import (
    StreamCallbacks,
    notify_prompt_messages,
    notify_stream_phase,
    notify_usage,
)
from shared.llm.transports.usage import _accumulate_usage

from shared.llm.structured_lite._types import (
    StructuredLiteExhaustedError,
    StructuredOutputT,
    LlmCaller,
    _Candidate,
    _CandidateValidation,
    _to_jsonable,
    _restore_structured_output,
    _serialize_output,
)
from shared.llm.structured_lite._schema import (
    _JSON_SCHEMA_METADATA_KEYS,
    _SCHEMA_PRIMITIVE_TYPES,
    _UNAMBIGUOUS_SCHEMA_KEYS,
    _generate_skeleton_payload,
    _resolve_schema_ref,
    _sanitize_payload_with_schema,
    _sanitize_structured_payload,
    _schema_dict,
    _looks_like_schema_echo,
    _try_unwrap_schema_shaped_payload,
    _coerce_schema_echo_values,
)
from shared.llm.structured_lite._errors import (
    _STRUCTURAL_ERROR_TYPES,
    _MESSAGE_PREFIXES_TO_STRIP,
    _classify_validation_error,
    _format_structured_error,
    _format_validation_location,
    _clean_validation_message,
    _indent_json,
)
from shared.llm.structured_lite._candidates import (
    STRUCTURAL_RATIO_THRESHOLD,
    STRUCTURAL_HARD_FLOOR,
    _payload_complexity,
    _extract_text_sources,
    _generate_candidates,
    _validate_candidates,
    _score_candidates,
    _should_use_synthetic,
)
from shared.llm.structured_lite._prompt import (
    _MODEL_PLACEHOLDER,
    _ERROR_PLACEHOLDER,
    _DEFAULT_FIX_PROMPT,
    _render_prompt,
    _render_fix_prompt_template,
    _visible_prompt_messages,
)

REPLACE_SCHEMA_ECHO_WITH_SKELETON: bool = False
_SCHEMA_ECHO_SKELETON_FIX_MESSAGE = (
    "Your previous response was an empty template — the fields had no actual values. "
    "Please fill in real values for each field based on the user's request."
)
_SCHEMA_ECHO_HINT_MESSAGE = (
    "You returned the JSON schema definition instead of filling it with actual data values."
)


__all__ = [
    "structured_lite",
    "StructuredLiteExhaustedError",
    "StructuredOutputT",
    "LlmCaller",
    "REPLACE_SCHEMA_ECHO_WITH_SKELETON",
    "_format_structured_error",
    "_looks_like_schema_echo",
    "_coerce_schema_echo_values",
    "_generate_skeleton_payload",
    "STRUCTURAL_RATIO_THRESHOLD",
    "STRUCTURAL_HARD_FLOOR",
    "_Candidate",
    "_CandidateValidation",
    "_classify_validation_error",
    "_extract_text_sources",
    "_generate_candidates",
    "_payload_complexity",
    "_score_candidates",
    "_should_use_synthetic",
    "_validate_candidates",
]


def structured_lite(
    messages: list[dict[str, Any]],
    prompt: str,
    *,
    llm_caller: LlmCaller,
    response_model: type[StructuredOutputT] | Any,
    validation_context: dict[str, Any] | None = None,
    stream_callback: StreamCallbacks | None = None,
    fix_prompt: str | None = None,
    fix_retry: int = 1,
    require_model: bool = True,
) -> tuple[StructuredOutputT, dict[str, Any] | None, list[dict[str, Any]], list[dict[str, Any]]]:
    """Structured output with JSON repair and validation-guided repair retries.

    No LLM client dependency — the caller supplies ``llm_caller``, a function
    that accepts a message list and returns ``LlmResponse``.

    Returns ``(output, usage, updated_messages, conversation)`` where
    ``conversation`` holds the raw prompt/response exchange including diagnostic
    metadata on each entry.

    Transport retry logic is the responsibility of ``llm_caller``.

    When ``require_model`` is ``True`` (default) the prompt must contain the
    ``<<MODEL>>`` placeholder, which is replaced with the JSON schema. Set it to
    ``False`` to allow a prompt without the placeholder — useful for continuation
    turns where an earlier message in ``messages`` already stated the schema and
    only fresh input is being supplied. The placeholder is still substituted when
    present regardless of this flag.
    """
    if fix_retry < 0:
        raise ValueError("fix_retry cannot be negative.")

    schema_text = json.dumps(_schema_dict(response_model), ensure_ascii=False, indent=2)
    rendered_prompt = _render_prompt(prompt, schema_text=schema_text, require_model=require_model)
    rendered_fix_template = _render_fix_prompt_template(fix_prompt, schema_text=schema_text)
    base_messages = list(messages)
    callbacks = stream_callback

    initial_working = [*base_messages, {"role": "user", "content": rendered_prompt}]
    conversation_log: list[dict[str, Any]] = [
        {"role": "user", "content": rendered_prompt, "phase": "initial"},
    ]
    total_usage: dict[str, Any] | None = None

    notify_prompt_messages(
        callbacks,
        _visible_prompt_messages(base_messages, rendered_prompt, prompt_role="user", include_system_messages=True),
        attempt=1,
    )
    response = llm_caller(initial_working)
    response_text = response.content
    first_reasoning = response.reasoning_content
    total_usage = _accumulate_usage(total_usage, response.usage)
    notify_usage(callbacks, json.loads(json.dumps(total_usage)) if total_usage is not None else None, attempt=1)

    conversation_log.append({
        "role": "assistant",
        "content": response_text,
        "reasoning_content": first_reasoning,
        "phase": "initial",
    })

    last_error: Exception | None = None

    for iteration in range(fix_retry + 1):
        repair_phase = "initial" if iteration == 0 else f"repair_{iteration}"
        skeleton_payload: Any = None

        candidates = _generate_candidates(response_text, response_model=response_model)

        if not candidates:
            repair_kind = "no_json"
            repair_assistant_msg = assistant_conversation_message(response_text, response.reasoning_content)
            formatted_error = "No valid JSON object found in response."
            best: _Candidate | None = None
            conversation_log[-1]["meta"] = {"candidates": [], "next_phase": "repair_no_json"}
        else:
            output, winner = _validate_candidates(
                candidates,
                response_model=response_model,
                validation_context=validation_context,
            )
            if output is not None:
                conversation_log[-1]["meta"] = {
                    "next_phase": "success",
                    "iterations": iteration,
                }
                output_json = _serialize_output(output)
                final_messages = [
                    *base_messages,
                    {"role": "user", "content": rendered_prompt},
                    assistant_conversation_message(f"```json\n{output_json}```", first_reasoning),
                ]
                return cast(StructuredOutputT, output), total_usage, final_messages, conversation_log

            scored = _score_candidates(
                candidates,
                response_model=response_model,
                validation_context=validation_context,
            )
            best = scored[0]
            last_error = best.validation.error if best.validation else None

            schema_echo_detected = _looks_like_schema_echo(best.payload)

            if schema_echo_detected and REPLACE_SCHEMA_ECHO_WITH_SKELETON:
                schema = _schema_dict(response_model)
                skeleton_payload = _generate_skeleton_payload(schema, root_schema=schema)
                synthetic_content = "```json\n" + json.dumps(skeleton_payload, ensure_ascii=False) + "\n```"
                repair_assistant_msg = {"role": "assistant", "content": synthetic_content}
                repair_kind = "schema_echo_skeleton"
                next_phase_label = "repair_schema_echo"
                formatted_error = _SCHEMA_ECHO_SKELETON_FIX_MESSAGE
            else:
                if _should_use_synthetic(best):
                    repair_kind = "invalid_json"
                    next_phase_label = "repair_invalid"
                    synthetic_content = "```json\n" + json.dumps(_to_jsonable(best.payload), ensure_ascii=False) + "\n```"
                    repair_assistant_msg = {"role": "assistant", "content": synthetic_content}
                else:
                    repair_kind = "no_json"
                    next_phase_label = "repair_no_json"
                    repair_assistant_msg = assistant_conversation_message(response_text, response.reasoning_content)
                if schema_echo_detected:
                    formatted_error = _SCHEMA_ECHO_HINT_MESSAGE
                else:
                    formatted_error = _format_structured_error(cast(Exception, last_error))

            structural = best.validation.structural_errors if best.validation else 0
            complexity = _payload_complexity(best.payload)
            conversation_log[-1]["meta"] = {
                "candidates": [
                    {
                        "source_index": c.source_index,
                        "source_kind": c.source_kind,
                        "transform": c.transform,
                        "score": list(c.validation.score) if c.validation else None,
                        "status": c.validation.status if c.validation else None,
                    }
                    for c in scored
                ],
                "best_candidate_index": scored.index(best),
                "structural_ratio": round(structural / complexity, 4),
                "next_phase": next_phase_label,
            }

        if iteration >= fix_retry:
            break

        fix_message = rendered_fix_template.replace(_ERROR_PLACEHOLDER, formatted_error)
        repair_working = [
            *base_messages,
            {"role": "user", "content": rendered_prompt},
            repair_assistant_msg,
            {"role": "user", "content": fix_message},
        ]

        next_phase = f"repair_{iteration + 1}"
        repair_log_entry: dict[str, Any] = {
            "role": "user",
            "content": fix_message,
            "phase": next_phase,
            "meta": {"repair_kind": repair_kind},
        }
        if repair_kind == "invalid_json" and best is not None:
            repair_log_entry["meta"]["synthetic_payload"] = best.payload
        elif repair_kind == "schema_echo_skeleton":
            repair_log_entry["meta"]["skeleton_payload"] = skeleton_payload
        conversation_log.append(repair_log_entry)

        notify_stream_phase(
            callbacks,
            "fix_retry",
            reset=True,
            meta={"attempt": iteration + 1, "fix_retry": fix_retry, "kind": repair_kind},
        )
        notify_prompt_messages(
            callbacks,
            _visible_prompt_messages(base_messages, fix_message, prompt_role="fix", include_system_messages=False),
            attempt=iteration + 2,
        )

        response = llm_caller(repair_working)
        response_text = response.content
        total_usage = _accumulate_usage(total_usage, response.usage)
        notify_usage(callbacks, json.loads(json.dumps(total_usage)) if total_usage is not None else None, attempt=iteration + 2)

        conversation_log.append({
            "role": "assistant",
            "content": response_text,
            "reasoning_content": response.reasoning_content,
            "phase": next_phase,
        })

    raise StructuredLiteExhaustedError(
        error=cast(Exception, last_error) if last_error is not None else RuntimeError("All validation attempts exhausted."),
        conversation=conversation_log,
    )
