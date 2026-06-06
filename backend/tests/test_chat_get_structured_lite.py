from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterator, cast

from pydantic import BaseModel, ConfigDict, ValidationInfo, model_validator

from shared.llm.chat import Chat
from shared.llm import chat_request as request_utils
from shared.llm import chat_transport as transport_utils
from shared.llm import chat_get_structured_lite as lite_utils
from shared.llm import server_registry as server_registry_utils
from shared.llm.chat_get_structured_lite import chat_get_structured_lite
from shared.llm.chat_result import LlmResponse
from shared.llm.cancellation import LlmRequestCancelled
from shared.llm.clients.mock_client import MockChatClient
from shared.llm._io import load_json
from shared.llm.llm_cache import reset_llm_cache
from shared.llm.stream_callbacks import StreamCallbacks


def _assert_equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: expected {expected!r}, got {actual!r}.")


def _assert_true(value: object, label: str) -> None:
    if not value:
        raise ValueError(f"{label} expected truthy value, got {value!r}.")


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _reset_transport_state() -> None:
    server_registry_utils.reset_default_server_registry()
    transport_utils._OPENAI_CLIENT_CACHE.clear()
    reset_llm_cache()


@contextmanager
def _temporary_chat_env(*, enable_cache: bool = False) -> Iterator[Path]:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_json(
            root / ".servers.jsonc",
            {
                "openai": {
                    "type": "openai",
                    "api_key": "env:OPENAI_API_KEY",
                },
                "local": {
                    "type": "local",
                    "host": "http://localhost:8000",
                    "api_key": "not_needed",
                },
            },
        )

        previous_cwd = Path.cwd()
        tracked_env = {
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            "LLM_CACHE": os.environ.get("LLM_CACHE"),
            "LLM_CACHE_DB_PATH": os.environ.get("LLM_CACHE_DB_PATH"),
            "LLM_LOG_PROGRESS": os.environ.get("LLM_LOG_PROGRESS"),
            "LLM_MODEL": os.environ.get("LLM_MODEL"),
        }

        os.chdir(root)
        os.environ["OPENAI_API_KEY"] = "test-key"
        os.environ["LLM_LOG_PROGRESS"] = "0"
        os.environ.pop("LLM_MODEL", None)
        if enable_cache:
            os.environ["LLM_CACHE"] = "1"
            os.environ["LLM_CACHE_DB_PATH"] = str(root / ".cache" / "llm_cache.db")
        else:
            os.environ.pop("LLM_CACHE", None)
            os.environ.pop("LLM_CACHE_DB_PATH", None)
        _reset_transport_state()
        try:
            yield root
        finally:
            os.chdir(previous_cwd)
            for key, value in tracked_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            _reset_transport_state()


@contextmanager
def _patched(obj: Any, attr: str, value: Any) -> Iterator[None]:
    original = getattr(obj, attr)
    setattr(obj, attr, value)
    try:
        yield
    finally:
        setattr(obj, attr, original)


class _StrictProfile(BaseModel):
    model_config = ConfigDict(strict=True)

    name: str
    age: int


class _StrictProfileNoExtra(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    name: str
    age: int


class _LivePayload(BaseModel):
    status: str
    echo: str


class _ContextBoundValue(BaseModel):
    value: int

    @model_validator(mode="after")
    def validate_max_value(self, info: ValidationInfo) -> "_ContextBoundValue":
        context = info.context if isinstance(info.context, dict) else None
        if context is None:
            return self
        max_value = context.get("max_value")
        if not isinstance(max_value, int):
            raise ValueError("max_value context is required.")
        if self.value > max_value:
            raise ValueError(f"value must be <= {max_value}")
        return self


class _ContextBoundPayload(BaseModel):
    value: int
    note: str

    @model_validator(mode="after")
    def validate_max_value(self, info: ValidationInfo) -> "_ContextBoundPayload":
        context = info.context if isinstance(info.context, dict) else None
        if context is None:
            return self
        max_value = context.get("max_value")
        if not isinstance(max_value, int):
            raise ValueError("max_value context is required.")
        if self.value > max_value:
            raise ValueError(f"value must be <= {max_value}")
        return self


@contextmanager
def fake_llm(*responses: Any) -> Iterator[MockChatClient]:
    normalized: list[str | LlmResponse] = []
    for response in responses:
        if isinstance(response, tuple):
            text, usage = response
            normalized.append(LlmResponse(content=text, usage=usage))
        else:
            normalized.append(response)
    mock = MockChatClient(normalized)

    def _stub(messages: Any, *, preset: Any, stream_callback: Any = None) -> Any:
        return mock.complete(messages, preset=preset, stream_callback=stream_callback)

    with _patched(lite_utils, "request_chat_raw_text", _stub):
        yield mock


def _mock_response(content: str, usage: dict[str, Any] | None) -> LlmResponse:
    return LlmResponse(content=content, usage=usage)


class _StructuredLiteProbe:
    def __init__(self) -> None:
        self.chunks: list[str] = []
        self.prompts: list[dict[str, Any]] = []
        self.usages: list[dict[str, Any]] = []
        self.phases: list[tuple[str, bool, dict[str, Any] | None]] = []
        self.callbacks = StreamCallbacks(
            on_text_delta=self.chunks.append,
            on_prompt_messages=lambda messages, *, attempt: self.prompts.append({"attempt": attempt, "messages": messages}),
            on_usage=lambda usage, *, attempt: self.usages.append({"attempt": attempt, "usage": usage}),
            on_stream_phase=lambda phase, *, reset=False, meta=None: self.phases.append((phase, reset, meta)),
        )


def test_success_first_pass_appends_only_final_chat() -> None:
    with _temporary_chat_env():
        chat = Chat.with_system("System message")
        original_messages = chat.model_dump(mode="json", exclude_none=True)["messages"]

        with fake_llm(('{"name":"Ada","age":31}', {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3})):
            result = chat_get_structured_lite(
                chat,
                "Return only JSON matching this schema:\n<<MODEL>>",
                {"model": "openai/gpt-5-mini"},
                response_model=_StrictProfile,
            )

        _assert_true(isinstance(result.output, _StrictProfile), "typed output")
        _assert_equal(result.output.name, "Ada", "result name")
        _assert_equal(result.output.age, 31, "result age")
        current_messages = chat.model_dump(mode="json", exclude_none=True)["messages"]
        _assert_equal(current_messages[:len(original_messages)], original_messages, "preserved chat prefix")
        _assert_equal(chat.length, len(original_messages) + 2, "chat length after success")
        _assert_true("<<MODEL>>" not in chat.messages[-2].content, "schema placeholder removed")
        _assert_true(chat.messages[-1].content.startswith("```json\n"), "assistant JSON fence")
        _assert_equal(
            result.usage,
            {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            "single-pass usage",
        )


def test_success_first_pass_conversation_preserves_reasoning_content() -> None:
    with _temporary_chat_env():
        chat = Chat()

        with fake_llm(
            LlmResponse(
                content='{"name":"Ada","age":31}',
                usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
                reasoning_content="Schema requires name and age.",
            )
        ):
            result = chat_get_structured_lite(
                chat,
                "Return only JSON matching this schema:\n<<MODEL>>",
                {"model": "openai/gpt-5-mini"},
                response_model=_StrictProfile,
            )

        _assert_true(isinstance(result.output, _StrictProfile), "typed output with reasoning")
        _assert_equal(
            result.conversation[1]["reasoning_content"],
            "Schema requires name and age.",
            "structured first-pass reasoning",
        )
        _assert_equal(
            chat.messages[-1].reasoning_content,
            "Schema requires name and age.",
            "structured final chat reasoning",
        )


def test_fix_flow_aggregates_usage_streams_attempts_and_keeps_clean_chat() -> None:
    with _temporary_chat_env():
        streamed: list[str] = []
        chat = Chat()

        with fake_llm(
            ('{"name":"Ada"}', {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3, "prompt_tokens_details": {"cached_tokens": 4}, "ignored": "x"}),
            ('{"name":"Ada","age":31}', {"prompt_tokens": 10, "completion_tokens": 11, "total_tokens": 21, "prompt_tokens_details": {"cached_tokens": 1}, "completion_tokens_details": {"reasoning_tokens": 2}}),
        ):
            result = chat_get_structured_lite(
                chat,
                "Return only JSON matching this schema:\n<<MODEL>>",
                {"model": "openai/gpt-5-mini"},
                response_model=_StrictProfile,
                stream_callback=StreamCallbacks(on_text_delta=streamed.append),
                fix_retry=1,
            )

        _assert_equal(streamed, ['{"name":"Ada"}', '{"name":"Ada","age":31}'], "streamed attempts")
        _assert_equal(chat.length, 2, "chat remains clean after fix")
        _assert_true("<<ERROR>>" not in chat.messages[0].content, "no fix prompt in final chat")
        _assert_true(chat.messages[1].content.endswith("```"), "final assistant fencing")
        _assert_equal(
            result.usage,
            {
                "prompt_tokens": 11,
                "completion_tokens": 13,
                "total_tokens": 24,
                "prompt_tokens_details": {"cached_tokens": 5},
                "completion_tokens_details": {"reasoning_tokens": 2},
            },
            "aggregated usage",
        )


def test_fix_flow_conversation_preserves_reasoning_per_assistant_attempt() -> None:
    with _temporary_chat_env():
        with fake_llm(
            LlmResponse(
                content='{"name":"Ada"}',
                usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
                reasoning_content="Forgot age.",
            ),
            LlmResponse(
                content='{"name":"Ada","age":31}',
                usage={"prompt_tokens": 4, "completion_tokens": 5, "total_tokens": 9},
                reasoning_content="Added required age.",
            ),
        ):
            result = chat_get_structured_lite(
                Chat(),
                "Return only JSON matching this schema:\n<<MODEL>>",
                {"model": "openai/gpt-5-mini"},
                response_model=_StrictProfile,
                fix_retry=1,
            )

        assistant_entries = [
            item for item in result.conversation if item.get("role") == "assistant"
        ]
        _assert_equal(
            [item.get("reasoning_content") for item in assistant_entries],
            ["Forgot age.", "Added required age."],
            "structured fix reasoning entries",
        )


def test_fix_flow_emits_prompt_and_usage_metadata_for_idle_stream() -> None:
    with _temporary_chat_env():
        probe = _StructuredLiteProbe()

        with fake_llm(
            ('{"name":"Ada"}', {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}),
            ('{"name":"Ada","age":31}', {"prompt_tokens": 10, "completion_tokens": 11, "total_tokens": 21}),
        ):
            result = chat_get_structured_lite(
                Chat.with_system("System message"),
                "Return only JSON matching this schema:\n<<MODEL>>",
                {"model": "openai/gpt-5-mini"},
                response_model=_StrictProfile,
                stream_callback=probe.callbacks,
                fix_retry=1,
            )

        _assert_true(isinstance(result.output, _StrictProfile), "probe typed output")
        _assert_equal(probe.chunks, ['{"name":"Ada"}', '{"name":"Ada","age":31}'], "probe streamed chunks")
        _assert_equal(len(probe.prompts), 2, "probe prompt event count")
        _assert_equal(probe.prompts[0]["attempt"], 1, "first prompt attempt")
        _assert_equal(
            probe.prompts[0]["messages"][0],
            {"role": "system", "content": "System message"},
            "first prompt system message",
        )
        _assert_equal(probe.prompts[0]["messages"][1]["role"], "user", "first prompt user role")
        _assert_true("<<MODEL>>" not in probe.prompts[0]["messages"][1]["content"], "rendered user prompt")
        _assert_equal(probe.prompts[1]["attempt"], 2, "fix prompt attempt")
        _assert_equal(probe.prompts[1]["messages"][0]["role"], "fix", "fix prompt role")
        _assert_true("<<ERROR>>" not in probe.prompts[1]["messages"][0]["content"], "rendered fix prompt")
        _assert_equal(
            probe.usages,
            [
                {
                    "attempt": 1,
                    "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
                },
                {
                    "attempt": 2,
                    "usage": {"prompt_tokens": 11, "completion_tokens": 13, "total_tokens": 24},
                },
            ],
            "probe aggregated usages by attempt",
        )
        _assert_equal(len(probe.phases), 1, "probe phase event count")
        _assert_equal(probe.phases[0][0], "fix_retry", "probe phase name")
        _assert_equal(probe.phases[0][1], True, "probe phase reset")
        phase_meta = probe.phases[0][2]
        _assert_true(phase_meta is not None, "probe phase meta not None")
        assert phase_meta is not None
        _assert_equal(phase_meta["attempt"], 1, "probe phase attempt")
        _assert_equal(phase_meta["fix_retry"], 1, "probe phase fix_retry")
        _assert_true("kind" in phase_meta, "probe phase has kind")


def test_exhausted_fix_retries_restore_original_chat() -> None:
    with _temporary_chat_env():
        chat = Chat.with_system("Keep me intact")
        original_chat = chat.model_dump(mode="json", exclude_none=True)

        with fake_llm(
            ('{"name":"Ada"}', {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}),
            ('{"name":"Ada"}', {"prompt_tokens": 4, "completion_tokens": 5, "total_tokens": 9}),
        ):
            try:
                chat_get_structured_lite(
                    chat,
                    "Return only JSON matching this schema:\n<<MODEL>>",
                    {"model": "openai/gpt-5-mini"},
                    response_model=_StrictProfile,
                    fix_retry=1,
                )
            except Exception:
                pass
            else:
                raise ValueError("Expected structured_lite failure after exhausted fix retries.")

        _assert_equal(
            chat.model_dump(mode="json", exclude_none=True),
            original_chat,
            "chat restored after failure",
        )


def test_exhausted_fix_retries_preserve_reasoning_in_error_conversation() -> None:
    with _temporary_chat_env():
        with fake_llm(
            LlmResponse(
                content='{"name":"Ada"}',
                usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
                reasoning_content="Still missing age.",
            ),
            LlmResponse(
                content='{"name":"Ada"}',
                usage={"prompt_tokens": 4, "completion_tokens": 5, "total_tokens": 9},
                reasoning_content="Failed to repair age.",
            ),
        ):
            try:
                chat_get_structured_lite(
                    Chat(),
                    "Return only JSON matching this schema:\n<<MODEL>>",
                    {"model": "openai/gpt-5-mini"},
                    response_model=_StrictProfile,
                    fix_retry=1,
                )
            except Exception as exc:
                conversation = getattr(exc, "conversation", None)
                _assert_true(isinstance(conversation, list), "exhausted conversation list")
                conversation = cast(list[dict[str, Any]], conversation)
                assistant_entries = [
                    item for item in conversation if item.get("role") == "assistant"
                ]
                _assert_equal(
                    [item.get("reasoning_content") for item in assistant_entries],
                    ["Still missing age.", "Failed to repair age."],
                    "exhausted reasoning entries",
                )
                return
            raise ValueError("Expected structured_lite failure with reasoning conversation.")


def test_cache_hit_skips_transport_and_replays_final_json() -> None:
    with _temporary_chat_env(enable_cache=True):
        mock = MockChatClient(
            [
                LlmResponse(
                    content='{"name":"Ada","age":31}',
                    usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
                )
            ]
        )
        first_chat = Chat()
        second_chat = Chat()
        replayed: list[str] = []

        def _fake_uncached(prepared: Any, *, stream_callback: Any = None, **_kw: Any) -> Any:
            return mock.complete([], preset={}, stream_callback=stream_callback)

        with _patched(transport_utils, "_execute_prepared_chat_request_uncached", _fake_uncached):
            first = chat_get_structured_lite(
                first_chat,
                "Return only JSON matching this schema:\n<<MODEL>>",
                {"model": "openai/gpt-5-mini"},
                response_model=_StrictProfile,
            )
            second = chat_get_structured_lite(
                second_chat,
                "Return only JSON matching this schema:\n<<MODEL>>",
                {"model": "openai/gpt-5-mini"},
                response_model=_StrictProfile,
                stream_callback=StreamCallbacks(on_text_delta=replayed.append),
            )

        _assert_equal(mock.calls, 1, "transport calls with cache")
        _assert_true(isinstance(first.output, _StrictProfile), "first cached type")
        _assert_true(isinstance(second.output, _StrictProfile), "second cached type")
        _assert_equal(replayed, ['{"name":"Ada","age":31}'], "cache replay")


def test_schema_metadata_keys_are_ignored_when_payload_contains_valid_object() -> None:
    with _temporary_chat_env():
        with fake_llm((
            json.dumps({"$defs": {"Nested": {"type": "object", "properties": {"value": {"type": "string"}}}}, "properties": {"name": {"title": "Name", "type": "string"}, "age": {"title": "Age", "type": "integer"}}, "required": ["name", "age"], "title": "_StrictProfile", "type": "object", "name": "Ada", "age": 31}),
            {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        )):
            result = chat_get_structured_lite(
                Chat(),
                "Return only JSON matching this schema:\n<<MODEL>>",
                {"model": "openai/gpt-5-mini"},
                response_model=_StrictProfileNoExtra,
                fix_retry=0,
            )

        _assert_true(isinstance(result.output, _StrictProfileNoExtra), "schema metadata typed output")
        _assert_equal(result.output.name, "Ada", "schema metadata name")
        _assert_equal(result.output.age, 31, "schema metadata age")


def test_non_schema_extra_keys_are_still_rejected() -> None:
    with _temporary_chat_env():
        with fake_llm(('{"$defs":{},"name":"Ada","age":31,"nickname":"A"}', {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3})):
            try:
                chat_get_structured_lite(
                    Chat(),
                    "Return only JSON matching this schema:\n<<MODEL>>",
                    {"model": "openai/gpt-5-mini"},
                    response_model=_StrictProfileNoExtra,
                    fix_retry=0,
                )
            except Exception as exc:
                _assert_true("nickname" in str(exc), "non-schema extra key error")
                return
            raise ValueError("Expected validation failure for non-schema extra key.")


def test_validation_context_is_passed_into_model_validation() -> None:
    with _temporary_chat_env():
        with fake_llm(('{"value":3}', {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3})):
            result = chat_get_structured_lite(
                Chat(),
                "Return only JSON matching this schema:\n<<MODEL>>",
                {"model": "openai/gpt-5-mini"},
                response_model=_ContextBoundValue,
                validation_context={"max_value": 5},
                fix_retry=0,
            )

        _assert_true(isinstance(result.output, _ContextBoundValue), "context-bound typed output")
        _assert_equal(result.output.value, 3, "context-bound value")


def test_validation_context_errors_flow_through_fix_retry() -> None:
    with _temporary_chat_env():
        with fake_llm(
            ('{"value":7}', {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}),
            ('{"value":6}', {"prompt_tokens": 4, "completion_tokens": 5, "total_tokens": 9}),
        ) as mock:
            try:
                chat_get_structured_lite(
                    Chat(),
                    "Return only JSON matching this schema:\n<<MODEL>>",
                    {"model": "openai/gpt-5-mini"},
                    response_model=_ContextBoundValue,
                    validation_context={"max_value": 5},
                    fix_retry=1,
                )
            except Exception as exc:
                _assert_true("value must be <= 5" in str(exc), "validation context retry error")
                _assert_equal(mock.calls, 2, "validation context retry calls")
                return
            raise ValueError("Expected validation failure from context-aware validator.")


def test_validation_error_format_for_fix_prompt_is_readable() -> None:
    with _temporary_chat_env():
        long_note = "fluid_hardens_epoxy should not be both the merge target and a dropped entity"
        probe = _StructuredLiteProbe()

        with fake_llm(
            (json.dumps({"value": 7, "note": long_note}), {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}),
            (json.dumps({"value": 5, "note": "fixed"}), {"prompt_tokens": 4, "completion_tokens": 5, "total_tokens": 9}),
        ):
            result = chat_get_structured_lite(
                Chat(),
                "Return only JSON matching this schema:\n<<MODEL>>",
                {"model": "openai/gpt-5-mini"},
                response_model=_ContextBoundPayload,
                validation_context={"max_value": 5},
                stream_callback=probe.callbacks,
                fix_retry=1,
            )

        _assert_equal(result.output.value, 5, "formatted validation error retry output")
        fix_prompt = probe.prompts[1]["messages"][0]["content"]
        _assert_true("For further information" not in fix_prompt, "fix prompt omits pydantic docs URL text")
        _assert_true("https://errors.pydantic.dev" not in fix_prompt, "fix prompt omits pydantic docs URL")
        _assert_true("Value error," not in fix_prompt, "fix prompt strips pydantic value-error prefix")
        _assert_true("value must be <= 5" in fix_prompt, "fix prompt preserves validation message")
        _assert_true("path:" not in fix_prompt and "message:" not in fix_prompt, "fix prompt avoids technical field labels")
        _assert_true("Received value:" not in fix_prompt, "fix prompt omits full root input payload")


def test_first_pass_raw_cache_is_reused_during_fix_flow() -> None:
    with _temporary_chat_env(enable_cache=True):
        mock = MockChatClient(
            [
                _mock_response('{"name":"Ada"}', {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}),
                _mock_response('{"name":"Ada","age":31}', {"prompt_tokens": 4, "completion_tokens": 5, "total_tokens": 9}),
            ]
        )

        def _fake_uncached(prepared: Any, *, stream_callback: Any = None, **_kw: Any) -> Any:
            return mock.complete([], preset={}, stream_callback=stream_callback)

        with _patched(transport_utils, "_execute_prepared_chat_request_uncached", _fake_uncached):
            first = chat_get_structured_lite(
                Chat(),
                "Return only JSON matching this schema:\n<<MODEL>>",
                {"model": "openai/gpt-5-mini"},
                response_model=_StrictProfile,
                fix_retry=1,
            )
            second = chat_get_structured_lite(
                Chat(),
                "Return only JSON matching this schema:\n<<MODEL>>",
                {"model": "openai/gpt-5-mini"},
                response_model=_StrictProfile,
                fix_retry=1,
            )

        _assert_true(isinstance(first.output, _StrictProfile), "first cached fix-flow type")
        _assert_true(isinstance(second.output, _StrictProfile), "second cached fix-flow type")
        _assert_equal(mock.calls, 2, "raw cache reused across fix-flow attempts")


def test_validation_context_reuses_first_raw_response_but_not_fix_prompt() -> None:
    with _temporary_chat_env(enable_cache=True):
        mock = MockChatClient(
            [
                _mock_response('{"value":4}', {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}),
                _mock_response('{"value":3}', {"prompt_tokens": 4, "completion_tokens": 5, "total_tokens": 9}),
                _mock_response('{"value":2}', {"prompt_tokens": 7, "completion_tokens": 8, "total_tokens": 15}),
            ]
        )

        def _fake_uncached(prepared: Any, *, stream_callback: Any = None, **_kw: Any) -> Any:
            return mock.complete([], preset={}, stream_callback=stream_callback)

        with _patched(transport_utils, "_execute_prepared_chat_request_uncached", _fake_uncached):
            first = chat_get_structured_lite(
                Chat(),
                "Return only JSON matching this schema:\n<<MODEL>>",
                {"model": "openai/gpt-5-mini"},
                response_model=_ContextBoundValue,
                validation_context={"max_value": 3},
                fix_retry=1,
            )
            second = chat_get_structured_lite(
                Chat(),
                "Return only JSON matching this schema:\n<<MODEL>>",
                {"model": "openai/gpt-5-mini"},
                response_model=_ContextBoundValue,
                validation_context={"max_value": 2},
                fix_retry=1,
            )

        _assert_true(isinstance(first.output, _ContextBoundValue), "first validation-context type")
        _assert_true(isinstance(second.output, _ContextBoundValue), "second validation-context type")
        _assert_equal(first.output.value, 3, "first validation-context value")
        _assert_equal(second.output.value, 2, "second validation-context value")
        _assert_equal(mock.calls, 3, "shared first raw response but distinct fix prompts")


def test_cache_hit_restoration_still_enforces_validation_context() -> None:
    with _temporary_chat_env(enable_cache=True):
        mock = MockChatClient(
            [
                LlmResponse(
                    content='{"value":3}',
                    usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
                )
            ]
        )

        def _fake_uncached(prepared: Any, *, stream_callback: Any = None, **_kw: Any) -> Any:
            return mock.complete([], preset={}, stream_callback=stream_callback)

        with _patched(transport_utils, "_execute_prepared_chat_request_uncached", _fake_uncached):
            first = chat_get_structured_lite(
                Chat(),
                "Return only JSON matching this schema:\n<<MODEL>>",
                {"model": "openai/gpt-5-mini"},
                response_model=_ContextBoundValue,
                validation_context={"max_value": 3},
                fix_retry=0,
            )
            _assert_equal(first.output.value, 3, "cached validation first value")

            try:
                chat_get_structured_lite(
                    Chat(),
                    "Return only JSON matching this schema:\n<<MODEL>>",
                    {"model": "openai/gpt-5-mini"},
                    response_model=_ContextBoundValue,
                    validation_context={"max_value": 2},
                    fix_retry=0,
                )
            except Exception as exc:
                _assert_true("value must be <= 2" in str(exc), "cache hit validation context error")
                _assert_equal(mock.calls, 1, "cache hit skips repeated transport")
                return
            raise ValueError("Expected cache-hit validation to enforce validation_context.")


def test_cancelled_structured_request_does_not_retry() -> None:
    with _temporary_chat_env():
        calls = {"count": 0}

        def cancelled(*_args: Any, **_kwargs: Any) -> LlmResponse:
            calls["count"] += 1
            raise LlmRequestCancelled("cancelled")

        with _patched(lite_utils, "request_chat_raw_text", cancelled):
            try:
                chat_get_structured_lite(
                    Chat(),
                    "Return only JSON matching this schema:\n<<MODEL>>",
                    {"model": "openai/gpt-5-mini"},
                    response_model=_StrictProfile,
                    fix_retry=1,
                )
            except LlmRequestCancelled:
                pass
            else:
                raise ValueError("Expected structured cancellation.")

        _assert_equal(calls["count"], 1, "structured cancellation call count")


def test_prompt_placeholder_is_required() -> None:
    try:
        chat_get_structured_lite(
            Chat(),
            "Return JSON without placeholder",
            {"model": "openai/gpt-5-mini"},
            response_model=_StrictProfile,
        )
    except ValueError as exc:
        _assert_true("<<MODEL>>" in str(exc), "placeholder error message")
        return
    raise ValueError("Expected ValueError for missing <<MODEL>> placeholder.")


def test_custom_fix_prompt_requires_error_placeholder() -> None:
    try:
        chat_get_structured_lite(
            Chat(),
            "Return only JSON matching this schema:\n<<MODEL>>",
            {"model": "openai/gpt-5-mini"},
            response_model=_StrictProfile,
            fix_prompt="Fix the JSON using this schema:\n<<MODEL>>",
        )
    except ValueError as exc:
        _assert_true("<<ERROR>>" in str(exc), "fix prompt error message")
        return
    raise ValueError("Expected ValueError for fix_prompt without <<ERROR>> placeholder.")


def _resolve_live_model() -> str:
    env_model = os.getenv("LLM_MODEL")
    if isinstance(env_model, str) and env_model.strip():
        return env_model.strip()

    workflow_runtime_path = Path(".workflow_runtime.jsonc")
    if workflow_runtime_path.exists():
        workflow_runtime_config = load_json(str(workflow_runtime_path))
        if isinstance(workflow_runtime_config, dict):
            model = workflow_runtime_config.get("model")
            if isinstance(model, str) and model.strip():
                return model.strip()

    models_path = Path(".models.jsonc")
    if models_path.exists():
        models_config = load_json(str(models_path))
        if isinstance(models_config, list):
            for item in models_config:
                if isinstance(item, str) and item.strip():
                    return item.strip()

    raise ValueError(
        "Unable to resolve a live model. Set LLM_MODEL, add model to .workflow_runtime.jsonc, or add one to .models.jsonc."
    )


def _run_live_smoke_call(model: str) -> None:
    chat = Chat()
    result = chat_get_structured_lite(
        chat,
        (
            "Return only JSON matching this schema.\n"
            "Set status to 'ok' and echo to 'hello'.\n"
            "<<MODEL>>"
        ),
        {"model": model},
        response_model=_LivePayload,
        fix_retry=0,
    )
    _assert_true(isinstance(result.output, _LivePayload), "live typed output")
    _assert_equal(result.output.status, "ok", "live status")
    _assert_equal(result.output.echo, "hello", "live echo")


def _run_live_smoke_openai() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is missing after loading .env.")
    _run_live_smoke_call(_resolve_live_model())


def _run_live_smoke_local() -> None:
    base_url = os.getenv("LOCAL_LLM_BASE_URL", "").strip()
    api_key = os.getenv("LOCAL_LLM_API_KEY", "").strip()
    model_name = os.getenv("LOCAL_LLM_MODEL", "").strip()
    no_verify_raw = os.getenv("LOCAL_LLM_NO_VERIFY_TLS", "").strip().lower()
    no_verify_tls = no_verify_raw in {"1", "true", "yes", "on"}

    if not base_url:
        raise RuntimeError("LOCAL_LLM_BASE_URL is missing after loading .env.")
    if not api_key:
        raise RuntimeError("LOCAL_LLM_API_KEY is missing after loading .env.")
    if not model_name:
        raise RuntimeError("LOCAL_LLM_MODEL is missing after loading .env.")

    model_ref = f"local/{model_name}"
    server_entry = {
        "type": "local",
        "host": base_url,
        "api_key": api_key,
        "no_verify_tls": no_verify_tls,
    }

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_json(root / ".servers.jsonc", {"local": server_entry})
        previous_cwd = Path.cwd()
        os.chdir(root)
        _reset_transport_state()
        try:
            _run_live_smoke_call(model_ref)
        finally:
            os.chdir(previous_cwd)
            _reset_transport_state()


def test_live_smoke() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise RuntimeError("python-dotenv is required in .venv to run the live smoke test.") from exc

    env_path = Path(".env")
    if not env_path.is_file():
        env_path = Path(__file__).parent.parent.parent / ".env"
    load_dotenv(env_path)
    test_mode = os.getenv("LLM_TEST_MODE", "").strip().lower()

    if test_mode == "local":
        _run_live_smoke_local()
    else:
        _run_live_smoke_openai()


def main() -> int:
    tests = [
        test_success_first_pass_appends_only_final_chat,
        test_success_first_pass_conversation_preserves_reasoning_content,
        test_fix_flow_aggregates_usage_streams_attempts_and_keeps_clean_chat,
        test_fix_flow_conversation_preserves_reasoning_per_assistant_attempt,
        test_fix_flow_emits_prompt_and_usage_metadata_for_idle_stream,
        test_exhausted_fix_retries_restore_original_chat,
        test_exhausted_fix_retries_preserve_reasoning_in_error_conversation,
        test_cache_hit_skips_transport_and_replays_final_json,
        test_schema_metadata_keys_are_ignored_when_payload_contains_valid_object,
        test_non_schema_extra_keys_are_still_rejected,
        test_validation_context_is_passed_into_model_validation,
        test_validation_context_errors_flow_through_fix_retry,
        test_validation_error_format_for_fix_prompt_is_readable,
        test_first_pass_raw_cache_is_reused_during_fix_flow,
        test_validation_context_reuses_first_raw_response_but_not_fix_prompt,
        test_cache_hit_restoration_still_enforces_validation_context,
        test_cancelled_structured_request_does_not_retry,
        test_prompt_placeholder_is_required,
        test_custom_fix_prompt_requires_error_placeholder,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
