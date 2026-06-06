from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterator, cast

from pydantic import BaseModel, ValidationError

from shared.llm.chat import Chat, ChatMessage
from shared.llm import chat_get_text as operation_utils
from shared.llm import chat_request as request_utils
from shared.llm import chat_transport as transport_utils
from shared.llm import server_registry as server_registry_utils
import shared.llm.transports.openai_client as openai_client_utils
from shared.llm.chat_client import default_chat_client
from shared.llm.chat_get_text import chat_get_text
from shared.llm.chat_result import LlmResponse
from shared.llm.clients import logging_client as logging_client_utils
from shared.llm.clients import retrying_client as retrying_utils
from shared.llm.clients.logging_client import LoggingChatClient
from shared.llm.clients.mock_client import MockChatClient
from shared.llm.clients.retrying_client import RetryingChatClient
from shared.llm.cancellation import LlmRequestCancelled
from shared.llm.llm_cache import llm_cache_enabled, reset_llm_cache
from shared.llm.stream_callbacks import StreamCallbacks


def _assert_equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: expected {expected!r}, got {actual!r}.")


def _assert_true(value: object, label: str) -> None:
    if not value:
        raise ValueError(f"{label} expected truthy value, got {value!r}.")


def _assert_usage_counts(
    usage: dict[str, Any] | None,
    *,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    label: str,
) -> None:
    if not isinstance(usage, dict):
        raise ValueError(f"{label} expected usage dict, got {usage!r}.")
    _assert_equal(usage.get("prompt_tokens"), prompt_tokens, f"{label} prompt_tokens")
    _assert_equal(usage.get("completion_tokens"), completion_tokens, f"{label} completion_tokens")
    _assert_equal(usage.get("total_tokens"), total_tokens, f"{label} total_tokens")


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
        }

        os.chdir(root)
        os.environ["OPENAI_API_KEY"] = "test-key"
        os.environ["LLM_LOG_PROGRESS"] = "0"
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


class _FakeUsage:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def model_dump(self) -> dict[str, Any]:
        return dict(self._payload)


class _FakeMessage:
    def __init__(self, content: str, reasoning_content: str | None = None) -> None:
        self.content = content
        self.reasoning_content = reasoning_content


class _FakeChoice:
    def __init__(self, content: str, reasoning_content: str | None = None) -> None:
        self.message = _FakeMessage(content, reasoning_content=reasoning_content)


class _FakeResponse:
    def __init__(
        self,
        content: str,
        usage: dict[str, Any],
        *,
        reasoning_content: str | None = None,
    ) -> None:
        self.choices = [_FakeChoice(content, reasoning_content=reasoning_content)]
        self.usage = _FakeUsage(usage)


class _ReasoningCallback:
    def __init__(self) -> None:
        self.content_parts: list[str] = []
        self.reasoning_parts: list[str] = []
        self.callbacks = StreamCallbacks(
            on_text_delta=self.content_parts.append,
            on_reasoning_delta=self.reasoning_parts.append,
        )


class _MonotonicSequence:
    def __init__(self, values: list[float]) -> None:
        self._values = list(values)
        self._fallback = values[-1] if values else 0.0

    def __call__(self) -> float:
        if self._values:
            return self._values.pop(0)
        return self._fallback


class _FakeDefaultHttpxClient:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = dict(kwargs)


class _FakeOpenAIClient:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = dict(kwargs)


class _UserProfile(BaseModel):
    name: str
    age: int


def test_chat_validates_messages_and_roles() -> None:
    chat = Chat.model_validate(
        {
            "messages": [
                {"role": "system", "content": "System"},
                {"role": "assistant", "content": "Answer", "usage": {"total_tokens": 3}},
            ]
        }
    )

    _assert_true(isinstance(chat.messages[0], ChatMessage), "chat stores typed messages")
    _assert_equal(chat.messages[1].usage, {"total_tokens": 3}, "message usage payload")

    try:
        Chat.model_validate({"messages": [{"role": "bogus", "content": "Nope"}]})
    except ValidationError as exc:
        _assert_true("role" in str(exc), "invalid role validation error")
    else:
        raise ValueError("Expected ValidationError for invalid chat role.")


def test_chat_to_llm_messages_model_dump_and_clone_are_clean() -> None:
    chat = Chat.with_system("System prompt")
    chat.add_developer("Developer prompt")
    chat.add_user("Hello")
    chat.add_assistant("Hi")

    clone = chat.clone()
    clone.add_user("Extra")

    _assert_equal(
        chat.to_llm_messages(),
        [
            {"role": "system", "content": "System prompt"},
            {"role": "developer", "content": "Developer prompt"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ],
        "llm transport messages",
    )
    _assert_equal(
        chat.model_dump(mode="json", exclude_none=True),
        {
            "messages": [
                {"role": "system", "content": "System prompt"},
                {"role": "developer", "content": "Developer prompt"},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"},
            ]
        },
        "chat model_dump",
    )
    _assert_equal(chat.length, 4, "original chat length")
    _assert_equal(clone.length, 5, "clone length")


def test_chat_preserves_assistant_reasoning_without_sending_it_to_llm() -> None:
    chat = Chat()
    chat.add_user("Question")
    chat.add_assistant("Answer", reasoning_content="Visible reasoning summary")

    _assert_equal(
        chat.model_dump(mode="json", exclude_none=True)["messages"][1],
        {
            "role": "assistant",
            "content": "Answer",
            "reasoning_content": "Visible reasoning summary",
        },
        "chat message reasoning dump",
    )
    _assert_equal(
        chat.to_llm_messages(),
        [
            {"role": "user", "content": "Question"},
            {"role": "assistant", "content": "Answer"},
        ],
        "llm messages omit reasoning",
    )


def test_prepare_chat_request_routes_openai_and_local() -> None:
    with _temporary_chat_env():
        _extra2: dict[str, Any] = {"xtc-probability": 0.5}
        openai_request = request_utils.prepare_chat_request(
            [{"role": "user", "content": "Hello"}],
            model="openai/gpt-5-mini",
            temperature=0.2,
            start="ignored prefix",
            **_extra2,
        )
        _assert_equal(
            openai_request.messages,
            [{"role": "user", "content": "Hello"}],
            "openai messages",
        )
        _assert_equal(openai_request.extra_body, None, "openai extra_body")
        _assert_true("temperature" in openai_request.request_kwargs, "openai supported param")
        _assert_true("xtc-probability" not in openai_request.request_kwargs, "openai unsupported dropped")

        _extra: dict[str, Any] = {"xtc-probability": 0.5}
        local_request = request_utils.prepare_chat_request(
            [{"role": "user", "content": "Hello"}],
            model="local/Valkyrie",
            temperature=0.2,
            start="prefill",
            extra_body={"mirostat": 2},
            **_extra,
        )
        _assert_equal(local_request.messages[-1], {"role": "assistant", "content": "prefill"}, "local start prefill")
        _assert_equal(local_request.request_kwargs["temperature"], 0.2, "local supported param")
        _assert_equal(
            local_request.extra_body,
            {"mirostat": 2, "xtc-probability": 0.5},
            "local extra_body merge",
        )
        _assert_true(
            cast(str, local_request.spec.base_url).endswith("/v1"),
            "local base_url normalization",
        )


def test_no_verify_tls_server_option_configures_openai_client() -> None:
    with _temporary_chat_env() as root:
        _write_json(
            root / ".servers.jsonc",
            {
                "openai": {
                    "type": "openai",
                    "api_key": "env:OPENAI_API_KEY",
                },
                "local": {
                    "type": "local",
                    "host": "https://localhost:8000",
                    "api_key": "not_needed",
                    "no_verify_tls": True,
                },
                "local-dash": {
                    "type": "local",
                    "host": "https://localhost:8001",
                    "api_key": "not_needed",
                    "no-verify-tls": True,
                },
            },
        )
        _reset_transport_state()

        local_prepared = request_utils.prepare_chat_request(
            [{"role": "user", "content": "Hello"}],
            model="local/Valkyrie",
        )
        dash_prepared = request_utils.prepare_chat_request(
            [{"role": "user", "content": "Hello"}],
            model="local-dash/Valkyrie",
        )
        openai_prepared = request_utils.prepare_chat_request(
            [{"role": "user", "content": "Hello"}],
            model="openai/gpt-5-mini",
        )

        _assert_equal(local_prepared.spec.no_verify_tls, True, "local no_verify_tls")
        _assert_equal(dash_prepared.spec.no_verify_tls, True, "local-dash no_verify_tls alias")
        _assert_equal(openai_prepared.spec.no_verify_tls, False, "openai no_verify_tls default")

        with _patched(openai_client_utils, "DefaultHttpxClient", _FakeDefaultHttpxClient):
            with _patched(openai_client_utils, "OpenAI", _FakeOpenAIClient):
                local_client = openai_client_utils._get_openai_client(local_prepared)
                cached_local_client = openai_client_utils._get_openai_client(local_prepared)
                openai_client = openai_client_utils._get_openai_client(openai_prepared)

        _assert_true(local_client is cached_local_client, "no_verify_tls client cache")
        _assert_true(isinstance(local_client, _FakeOpenAIClient), "local fake client type")
        _assert_true(isinstance(openai_client, _FakeOpenAIClient), "openai fake client type")
        fake_local_client = cast(_FakeOpenAIClient, local_client)
        fake_openai_client = cast(_FakeOpenAIClient, openai_client)
        local_http_client = fake_local_client.kwargs.get("http_client")
        _assert_true(
            isinstance(local_http_client, _FakeDefaultHttpxClient),
            "local custom http client",
        )
        fake_http_client = cast(_FakeDefaultHttpxClient, local_http_client)
        _assert_equal(fake_http_client.kwargs.get("verify"), False, "local TLS verification disabled")
        _assert_true("http_client" not in fake_openai_client.kwargs, "openai default http client")


def test_build_openai_responses_request_maps_supported_fields() -> None:
    with _temporary_chat_env():
        prepared = request_utils.prepare_chat_request(
            [
                {"role": "system", "content": "Be brief."},
                {"role": "assistant", "content": "Ready."},
                {"role": "user", "content": "Say hi"},
            ],
            model="openai/gpt-5-mini",
            temperature=0.2,
            top_p=0.9,
            max_completion_tokens=128,
            verbosity="high",
            reasoning_effort="medium",
            metadata={"source": "test"},
            user="user-123",
            stop=["END"],
        )
        request = request_utils._build_openai_responses_request(
            prepared,
            stream_enabled=True,
            reasoning_summary_enabled=True,
        )

        _assert_equal(request["model"], "gpt-5-mini", "responses request model")
        _assert_equal(
            request["input"],
            [
                {"role": "system", "content": "Be brief."},
                {"role": "assistant", "content": "Ready."},
                {"role": "user", "content": "Say hi"},
            ],
            "responses request input",
        )
        _assert_equal(request["temperature"], 0.2, "responses request temperature")
        _assert_equal(request["top_p"], 0.9, "responses request top_p")
        _assert_equal(request["max_output_tokens"], 128, "responses request max_output_tokens")
        _assert_equal(request["text"], {"verbosity": "high"}, "responses request text config")
        _assert_equal(
            request["reasoning"],
            {"effort": "medium", "summary": "auto"},
            "responses request reasoning config",
        )
        _assert_equal(request["metadata"], {"source": "test"}, "responses request metadata")
        _assert_equal(request["user"], "user-123", "responses request user")
        _assert_true("stop" not in request, "responses request ignores unsupported stop")


def test_build_chat_completion_request_enables_usage_stream_options_for_local_streaming() -> None:
    with _temporary_chat_env():
        prepared = request_utils.prepare_chat_request(
            [{"role": "user", "content": "Say hi"}],
            model="local/Valkyrie",
        )

        streaming_request = request_utils._build_chat_completion_request(prepared, stream_enabled=True)
        non_stream_request = request_utils._build_chat_completion_request(prepared, stream_enabled=False)

        _assert_equal(
            streaming_request.get("stream_options"),
            {"include_usage": True},
            "local streaming request include_usage",
        )
        _assert_true("stream_options" not in non_stream_request, "local non-stream request omits stream_options")


def test_normalize_usage_adds_aliases_for_local_payloads() -> None:
    usage = transport_utils.normalize_usage(
        {
            "prompt_tokens": 7,
            "completion_tokens": 11,
            "total_tokens": 18,
            "prompt_tokens_details": {"cached_tokens": 0},
        }
    )

    _assert_usage_counts(
        usage,
        prompt_tokens=7,
        completion_tokens=11,
        total_tokens=18,
        label="normalized local usage",
    )
    _assert_equal(cast(dict[str, Any], usage).get("input_tokens"), 7, "normalized local input_tokens")
    _assert_equal(cast(dict[str, Any], usage).get("output_tokens"), 11, "normalized local output_tokens")
    _assert_equal(
        cast(dict[str, Any], usage).get("input_tokens_details"),
        {"cached_tokens": 0},
        "normalized local input_tokens_details",
    )


def test_execute_prepared_chat_request_openai_non_stream_usage() -> None:
    with _temporary_chat_env():
        prepared = request_utils.prepare_chat_request(
            [{"role": "user", "content": "Say hi"}],
            model="openai/gpt-5-mini",
            temperature=0.2,
        )

        def fake_call(
            _prepared: Any,
            *,
            stream_enabled: bool,
            reasoning_summary_enabled: bool,
        ) -> Any:
            _assert_equal(stream_enabled, False, "non-stream flag")
            _assert_equal(reasoning_summary_enabled, False, "non-stream reasoning summary flag")
            return {
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [{"type": "output_text", "text": "hello"}],
                    }
                ],
                "usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
            }

        with _patched(transport_utils, "_call_openai_responses", fake_call):
            response = transport_utils.execute_prepared_chat_request(prepared)

        _assert_equal(response.content, "hello", "non-stream content")
        _assert_usage_counts(
            response.usage,
            prompt_tokens=1,
            completion_tokens=2,
            total_tokens=3,
            label="non-stream usage",
        )


def test_execute_prepared_chat_request_does_not_stream_without_callback_even_if_progress_enabled() -> None:
    with _temporary_chat_env():
        os.environ["LLM_LOG_PROGRESS"] = "1"
        prepared = request_utils.prepare_chat_request(
            [{"role": "user", "content": "Say hi"}],
            model="openai/gpt-5-mini",
        )

        def fake_call(
            _prepared: Any,
            *,
            stream_enabled: bool,
            reasoning_summary_enabled: bool,
        ) -> Any:
            _assert_equal(stream_enabled, False, "non-callback request should stay non-stream")
            _assert_equal(reasoning_summary_enabled, False, "non-callback reasoning summary flag")
            return {
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [{"type": "output_text", "text": "hello"}],
                    }
                ],
                "usage": {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5},
            }

        with _patched(transport_utils, "_call_openai_responses", fake_call):
            response = transport_utils.execute_prepared_chat_request(prepared)

        _assert_equal(response.content, "hello", "non-stream content with progress enabled")
        _assert_usage_counts(
            response.usage,
            prompt_tokens=2,
            completion_tokens=3,
            total_tokens=5,
            label="non-stream usage with progress enabled",
        )


def test_execute_prepared_chat_request_openai_stream_usage_variants() -> None:
    with _temporary_chat_env():
        prepared = request_utils.prepare_chat_request(
            [{"role": "user", "content": "Stream hi"}],
            model="openai/gpt-5-mini",
        )

        streamed_chunks = [
            {"type": "response.created"},
            {"type": "response.output_text.delta", "item_id": "msg_1", "content_index": 0, "delta": "hel"},
            {"type": "response.output_text.delta", "item_id": "msg_1", "content_index": 0, "delta": "lo"},
            {
                "type": "response.completed",
                "response": {
                    "output": [
                        {
                            "id": "msg_1",
                            "type": "message",
                            "role": "assistant",
                            "status": "completed",
                            "content": [{"type": "output_text", "text": "hello"}],
                        }
                    ],
                    "usage": {"input_tokens": 4, "output_tokens": 5, "total_tokens": 9},
                },
            },
        ]
        interrupted_chunks = [
            {"type": "response.output_text.done", "item_id": "msg_2", "content_index": 0, "text": "bye"},
            {
                "type": "response.incomplete",
                "response": {
                    "output": [
                        {
                            "id": "msg_2",
                            "type": "message",
                            "role": "assistant",
                            "status": "incomplete",
                            "content": [{"type": "output_text", "text": "bye"}],
                        }
                    ],
                    "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
                },
            },
        ]
        calls = {"count": 0}

        def fake_call(
            _prepared: Any,
            *,
            stream_enabled: bool,
            reasoning_summary_enabled: bool,
        ) -> Any:
            _assert_equal(stream_enabled, True, "stream flag")
            _assert_equal(reasoning_summary_enabled, False, "stream reasoning summary flag")
            calls["count"] += 1
            if calls["count"] == 1:
                return streamed_chunks
            return interrupted_chunks

        streamed_parts: list[str] = []
        interrupted_parts: list[str] = []
        with _patched(transport_utils, "_call_openai_responses", fake_call):
            response = transport_utils.execute_prepared_chat_request(
                prepared,
                stream_callback=StreamCallbacks(on_text_delta=streamed_parts.append),
            )
            second_response = transport_utils.execute_prepared_chat_request(
                prepared,
                stream_callback=StreamCallbacks(on_text_delta=interrupted_parts.append),
            )

        _assert_equal(response.content, "hello", "streamed content")
        _assert_equal(streamed_parts, ["hel", "lo"], "stream callback parts")
        _assert_usage_counts(
            response.usage,
            prompt_tokens=4,
            completion_tokens=5,
            total_tokens=9,
            label="stream usage",
        )
        _assert_equal(second_response.content, "bye", "interrupted stream content")
        _assert_usage_counts(
            second_response.usage,
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            label="incomplete stream usage",
        )


def test_execute_prepared_chat_request_openai_stream_logs_progress() -> None:
    with _temporary_chat_env():
        os.environ["LLM_LOG_PROGRESS"] = "1"
        messages = [{"role": "user", "content": "Stream hi"}]
        preset = {"model": "openai/gpt-5-mini"}
        log_lines: list[str] = []

        def fake_info(message: str, *args: Any) -> None:
            log_lines.append(message % args if args else message)

        def fake_call(
            _prepared: Any,
            *,
            stream_enabled: bool,
            reasoning_summary_enabled: bool,
        ) -> Any:
            _assert_equal(stream_enabled, True, "openai progress stream flag")
            _assert_equal(reasoning_summary_enabled, False, "openai progress reasoning flag")
            return [
                {"type": "response.output_text.delta", "item_id": "msg_1", "content_index": 0, "delta": "hello"},
                {
                    "type": "response.completed",
                    "response": {
                        "output": [
                            {
                                "id": "msg_1",
                                "type": "message",
                                "role": "assistant",
                                "status": "completed",
                                "content": [{"type": "output_text", "text": "hello"}],
                            }
                        ],
                        "usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
                    },
                },
            ]

        # Sequence: start_time, next_at init, delta callback check, end duration
        monotonic = _MonotonicSequence([0.0, 0.0, 6.0, 7.0])
        with _patched(transport_utils, "_call_openai_responses", fake_call):
            with _patched(transport_utils.time, "monotonic", monotonic):
                with _patched(logging_client_utils._LOGGER, "info", fake_info):
                    client = default_chat_client()
                    response = client.complete(messages, preset=preset, stream_callback=StreamCallbacks(on_text_delta=lambda _: None))

        _assert_equal(response.content, "hello", "openai progress content")
        _assert_usage_counts(
            response.usage,
            prompt_tokens=1,
            completion_tokens=2,
            total_tokens=3,
            label="openai progress usage",
        )
        _assert_true(any("llm.request.progress" in line for line in log_lines), "openai progress log")


def test_execute_prepared_chat_request_local_chat_completions_stream_usage_variants() -> None:
    with _temporary_chat_env():
        prepared = request_utils.prepare_chat_request(
            [{"role": "user", "content": "Stream hi"}],
            model="local/Valkyrie",
        )

        streamed_chunks = [
            {"choices": [{"delta": {"content": "hel"}}], "usage": None},
            {"choices": [{"delta": {"content": "lo"}}], "usage": None},
            {"choices": [], "usage": {"prompt_tokens": 4, "completion_tokens": 5, "total_tokens": 9}},
        ]

        def fake_call(_prepared: Any, *, stream_enabled: bool) -> Any:
            _assert_equal(stream_enabled, True, "local stream flag")
            return streamed_chunks

        streamed_parts: list[str] = []
        with _patched(transport_utils, "_call_chat_completion", fake_call):
            response = transport_utils.execute_prepared_chat_request(
                prepared,
                stream_callback=StreamCallbacks(on_text_delta=streamed_parts.append),
            )

        _assert_equal(response.content, "hello", "local streamed content")
        _assert_equal(streamed_parts, ["hel", "lo"], "local stream callback parts")
        _assert_usage_counts(
            response.usage,
            prompt_tokens=4,
            completion_tokens=5,
            total_tokens=9,
            label="local stream usage",
        )
        _assert_equal(cast(dict[str, Any], response.usage).get("input_tokens"), 4, "local stream usage input_tokens")
        _assert_equal(cast(dict[str, Any], response.usage).get("output_tokens"), 5, "local stream usage output_tokens")


def test_execute_prepared_chat_request_chat_completions_non_stream_preserves_reasoning() -> None:
    with _temporary_chat_env():
        prepared = request_utils.prepare_chat_request(
            [{"role": "user", "content": "Think briefly"}],
            model="local/Valkyrie",
        )

        def fake_call(_prepared: Any, *, stream_enabled: bool) -> Any:
            _assert_equal(stream_enabled, False, "non-stream reasoning flag")
            return _FakeResponse(
                "answer",
                {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
                reasoning_content="We need a short answer.",
            )

        with _patched(transport_utils, "_call_chat_completion", fake_call):
            response = transport_utils.execute_prepared_chat_request(prepared)

        _assert_equal(response.content, "answer", "non-stream reasoning content")
        _assert_equal(response.reasoning_content, "We need a short answer.", "non-stream reasoning content field")
        _assert_usage_counts(
            response.usage,
            prompt_tokens=1,
            completion_tokens=2,
            total_tokens=3,
            label="non-stream reasoning usage",
        )


def test_execute_prepared_chat_request_local_stream_logs_progress() -> None:
    with _temporary_chat_env():
        os.environ["LLM_LOG_PROGRESS"] = "1"
        messages = [{"role": "user", "content": "Stream hi"}]
        preset = {"model": "local/Valkyrie"}
        log_lines: list[str] = []

        def fake_info(message: str, *args: Any) -> None:
            log_lines.append(message % args if args else message)

        def fake_call(_prepared: Any, *, stream_enabled: bool) -> Any:
            _assert_equal(stream_enabled, True, "local progress stream flag")
            return [
                {"choices": [{"delta": {"content": "hello"}}], "usage": None},
                {"choices": [], "usage": {"prompt_tokens": 4, "completion_tokens": 5, "total_tokens": 9}},
            ]

        # Sequence: start_time, next_at init, delta callback check, end duration
        monotonic = _MonotonicSequence([0.0, 0.0, 6.0, 7.0])
        with _patched(transport_utils, "_call_chat_completion", fake_call):
            with _patched(transport_utils.time, "monotonic", monotonic):
                with _patched(logging_client_utils._LOGGER, "info", fake_info):
                    client = default_chat_client()
                    response = client.complete(messages, preset=preset, stream_callback=StreamCallbacks(on_text_delta=lambda _: None))

        _assert_equal(response.content, "hello", "local progress content")
        _assert_usage_counts(
            response.usage,
            prompt_tokens=4,
            completion_tokens=5,
            total_tokens=9,
            label="local progress usage",
        )
        _assert_true(any("llm.request.progress" in line for line in log_lines), "local progress log")


def test_execute_prepared_chat_request_openai_streams_reasoning_summary_to_optional_hook() -> None:
    with _temporary_chat_env():
        prepared = request_utils.prepare_chat_request(
            [{"role": "user", "content": "Think aloud"}],
            model="openai/gpt-5-mini",
            reasoning_effort="high",
        )
        callback = _ReasoningCallback()
        streamed_chunks = [
            {
                "type": "response.reasoning_summary_text.delta",
                "item_id": "rs_1",
                "summary_index": 0,
                "delta": "We",
            },
            {
                "type": "response.reasoning_summary_text.delta",
                "item_id": "rs_1",
                "summary_index": 0,
                "delta": " need",
            },
            {"type": "response.output_text.delta", "item_id": "msg_1", "content_index": 0, "delta": "answer"},
            {
                "type": "response.completed",
                "response": {
                    "output": [
                        {
                            "id": "rs_1",
                            "type": "reasoning",
                            "summary": [{"type": "summary_text", "text": "We need"}],
                        },
                        {
                            "id": "msg_1",
                            "type": "message",
                            "role": "assistant",
                            "status": "completed",
                            "content": [{"type": "output_text", "text": "answer"}],
                        },
                    ],
                    "usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
                },
            },
        ]

        def fake_call(
            _prepared: Any,
            *,
            stream_enabled: bool,
            reasoning_summary_enabled: bool,
        ) -> Any:
            _assert_equal(stream_enabled, True, "reasoning stream flag")
            _assert_equal(reasoning_summary_enabled, True, "reasoning summary flag")
            return streamed_chunks

        with _patched(transport_utils, "_call_openai_responses", fake_call):
            response = transport_utils.execute_prepared_chat_request(
                prepared,
                stream_callback=callback.callbacks,
            )

        _assert_equal(response.content, "answer", "reasoning stream content")
        _assert_equal(callback.content_parts, ["answer"], "reasoning callback content parts")
        _assert_equal(callback.reasoning_parts, ["We", " need"], "reasoning callback deltas")
        _assert_equal(response.reasoning_content, "We need", "openai stream reasoning content field")
        _assert_usage_counts(
            response.usage,
            prompt_tokens=1,
            completion_tokens=2,
            total_tokens=3,
            label="reasoning stream usage",
        )


def test_execute_prepared_chat_request_streams_local_reasoning_deltas_to_optional_hook() -> None:
    with _temporary_chat_env():
        prepared = request_utils.prepare_chat_request(
            [{"role": "user", "content": "Think aloud"}],
            model="local/Valkyrie",
        )
        callback = _ReasoningCallback()
        streamed_chunks = [
            {"choices": [{"delta": {"role": "assistant", "content": None}}], "usage": None},
            {"choices": [{"delta": {"reasoning_content": "We"}}], "usage": None},
            {"choices": [{"delta": {"reasoning_content": " need"}}], "usage": None},
            {"choices": [{"delta": {"content": "answer"}}], "usage": None},
            {"choices": [], "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}},
        ]

        def fake_call(_prepared: Any, *, stream_enabled: bool) -> Any:
            _assert_equal(stream_enabled, True, "reasoning stream flag")
            return streamed_chunks

        with _patched(transport_utils, "_call_chat_completion", fake_call):
            response = transport_utils.execute_prepared_chat_request(
                prepared,
                stream_callback=callback.callbacks,
            )

        _assert_equal(response.content, "answer", "reasoning stream content")
        _assert_equal(callback.content_parts, ["answer"], "reasoning callback content parts")
        _assert_equal(callback.reasoning_parts, ["We", " need"], "reasoning callback deltas")
        _assert_equal(response.reasoning_content, "We need", "local stream reasoning content field")
        _assert_usage_counts(
            response.usage,
            prompt_tokens=1,
            completion_tokens=2,
            total_tokens=3,
            label="local reasoning stream usage",
        )


def test_execute_prepared_chat_request_openai_reasoning_only_incomplete_raises_error() -> None:
    with _temporary_chat_env():
        prepared = request_utils.prepare_chat_request(
            [{"role": "user", "content": "Think aloud"}],
            model="openai/gpt-5-mini",
            reasoning_effort="high",
        )
        callback = _ReasoningCallback()
        streamed_chunks = [
            {
                "type": "response.reasoning_summary_text.delta",
                "item_id": "rs_1",
                "summary_index": 0,
                "delta": "Thinking",
            },
            {
                "type": "response.incomplete",
                "response": {
                    "output": [
                        {
                            "id": "rs_1",
                            "type": "reasoning",
                            "summary": [{"type": "summary_text", "text": "Thinking"}],
                        }
                    ],
                    "usage": {"input_tokens": 1, "output_tokens": 4, "total_tokens": 5},
                },
            },
        ]

        def fake_call(
            _prepared: Any,
            *,
            stream_enabled: bool,
            reasoning_summary_enabled: bool,
        ) -> Any:
            _assert_equal(stream_enabled, True, "incomplete stream flag")
            _assert_equal(reasoning_summary_enabled, True, "incomplete reasoning summary flag")
            return streamed_chunks

        with _patched(transport_utils, "_call_openai_responses", fake_call):
            try:
                transport_utils.execute_prepared_chat_request(
                    prepared,
                    stream_callback=callback.callbacks,
                )
            except ValueError as exc:
                _assert_true("empty" in str(exc).lower(), "incomplete empty-content error")
            else:
                raise ValueError("Expected ValueError for reasoning-only incomplete OpenAI response.")

        _assert_equal(callback.reasoning_parts, ["Thinking"], "incomplete reasoning callback parts")
        _assert_equal(callback.content_parts, [], "incomplete content callback parts")


def test_logging_client_emits_start_end_and_error() -> None:
    with _temporary_chat_env():
        log_lines: list[str] = []

        def fake_info(message: str, *args: Any) -> None:
            log_lines.append(message % args if args else message)

        success_client = LoggingChatClient(
            MockChatClient(
                [
                    LlmResponse(
                        content="hello",
                        usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
                    )
                ]
            )
        )
        with _patched(logging_client_utils._LOGGER, "info", fake_info):
            response = success_client.complete(
                [{"role": "user", "content": "hi"}],
                preset={"model": "local/Valkyrie"},
            )

        _assert_equal(response.content, "hello", "logging client content")
        _assert_true(any("llm.request.start" in line for line in log_lines), "logging start")
        _assert_true(any("llm.request.end" in line for line in log_lines), "logging end")

        exc_log: list[str] = []

        def fake_exception(message: str, *args: Any) -> None:
            exc_log.append(message % args if args else message)

        class _BoomClient:
            def complete(self, messages: Any, *, preset: Any, stream_callback: Any = None) -> Any:
                raise RuntimeError("boom")

        error_client = LoggingChatClient(_BoomClient())
        with _patched(logging_client_utils._LOGGER, "exception", fake_exception):
            try:
                error_client.complete([{"role": "user", "content": "hi"}], preset={"model": "local/Valkyrie"})
            except RuntimeError:
                pass

        _assert_true(any("llm.request.error" in line for line in exc_log), "logging error")


def _make_rate_limit_error() -> Any:
    import httpx
    import openai

    req = httpx.Request("POST", "https://api.openai.com/v1/responses")
    resp = httpx.Response(429, request=req)
    return openai.RateLimitError("rate limited", response=resp, body=None)


def test_retrying_client_retries_on_rate_limit() -> None:
    import openai

    calls: list[int] = []
    rate_limit_err = _make_rate_limit_error()

    class _FlakyClient:
        def complete(self, messages: Any, *, preset: Any, stream_callback: Any = None) -> Any:
            calls.append(1)
            if len(calls) == 1:
                raise rate_limit_err
            return LlmResponse(content="hello")

    slept: list[float] = []
    with _patched(retrying_utils.random, "uniform", lambda _a, _b: 1.0):
        with _patched(retrying_utils.time, "sleep", lambda s: slept.append(s)):
            client = RetryingChatClient(_FlakyClient(), max_retries=2)
            response = client.complete([], preset={"model": "local/Valkyrie"})

    _assert_equal(response.content, "hello", "retrying client success content")
    _assert_equal(len(calls), 2, "retrying client call count")
    _assert_equal(len(slept), 1, "retrying client sleep count")
    _assert_equal(slept[0], 1.0, "retrying client initial delay")


def test_retrying_client_raises_after_max_retries() -> None:
    import openai

    calls: list[int] = []
    rate_limit_err = _make_rate_limit_error()

    class _AlwaysFailClient:
        def complete(self, messages: Any, *, preset: Any, stream_callback: Any = None) -> Any:
            calls.append(1)
            raise rate_limit_err

    slept: list[float] = []
    with _patched(retrying_utils.random, "uniform", lambda _a, _b: 1.0):
        with _patched(retrying_utils.time, "sleep", lambda s: slept.append(s)):
            client = RetryingChatClient(_AlwaysFailClient(), max_retries=2)
            try:
                client.complete([], preset={"model": "local/Valkyrie"})
            except openai.RateLimitError:
                pass
            else:
                raise ValueError("Expected RateLimitError after max retries.")

    _assert_equal(len(calls), 3, "retrying client total attempts (1 + 2 retries)")
    _assert_equal(len(slept), 2, "retrying client sleep count for 2 retries")
    _assert_equal(slept, [1.0, 2.0], "retrying client exponential backoff")


def test_retrying_client_does_not_retry_cancelled_request() -> None:
    calls: list[int] = []

    class _CancelledClient:
        def complete(self, messages: Any, *, preset: Any, stream_callback: Any = None) -> Any:
            calls.append(1)
            raise LlmRequestCancelled("cancelled")

    client = RetryingChatClient(_CancelledClient(), max_retries=2)
    try:
        client.complete([], preset={"model": "local/Valkyrie"})
    except LlmRequestCancelled:
        pass
    else:
        raise ValueError("Expected cancellation to pass through retrying client.")

    _assert_equal(len(calls), 1, "cancelled retrying client call count")


def test_mock_client_returns_responses_in_order() -> None:
    client = MockChatClient(
        [
            "first",
            LlmResponse(
                content="second",
                usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            ),
        ]
    )

    parts: list[str] = []
    first = client.complete([], preset={}, stream_callback=StreamCallbacks(on_text_delta=parts.append))
    second = client.complete([], preset={})

    _assert_equal(first.content, "first", "mock first response")
    _assert_equal(first.usage, None, "mock first usage")
    _assert_equal(parts, ["first"], "mock stream callback")
    _assert_equal(second.content, "second", "mock second response")
    _assert_equal(second.usage, {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}, "mock second usage")


def test_build_cache_request_marks_transport_and_reasoning_summary_opt_in() -> None:
    with _temporary_chat_env():
        openai_prepared = request_utils.prepare_chat_request(
            [{"role": "user", "content": "Hello"}],
            model="openai/gpt-5-mini",
        )
        local_prepared = request_utils.prepare_chat_request(
            [{"role": "user", "content": "Hello"}],
            model="local/Valkyrie",
        )
        openai_request = request_utils.build_cache_request(
            openai_prepared,
            reasoning_summary_enabled=True,
        )
        local_request = request_utils.build_cache_request(
            local_prepared,
            reasoning_summary_enabled=False,
        )

        _assert_equal(openai_request["transport"], "responses", "openai transport marker")
        _assert_equal(local_request["transport"], "chat_completions", "local transport marker")
        _assert_true("stream" not in openai_request["request"], "openai cache request omits stream")
        _assert_equal(
            openai_request["request"]["reasoning"]["summary"],
            "auto",
            "openai reasoning cache marker",
        )
        _assert_true("stream" not in local_request["request"], "local cache request omits stream")


def test_raw_cache_replays_callbacks_for_text_wrapper() -> None:
    with _temporary_chat_env(enable_cache=True):
        calls = {"count": 0}

        def fake_call(
            _prepared: Any,
            *,
            stream_enabled: bool,
            reasoning_summary_enabled: bool,
        ) -> Any:
            _assert_equal(reasoning_summary_enabled, False, "cache reasoning summary flag")
            calls["count"] += 1
            return {
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [{"type": "output_text", "text": "hello cached"}],
                    }
                ],
                "usage": {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5},
            }

        cached_parts: list[str] = []
        with _patched(transport_utils, "_call_openai_responses", fake_call):
            first = chat_get_text(Chat(), "Return text", {"model": "openai/gpt-5-mini"})
            second = chat_get_text(
                Chat(),
                "Return text",
                {"model": "openai/gpt-5-mini"},
                stream_callback=StreamCallbacks(on_text_delta=cached_parts.append),
            )

        _assert_equal(calls["count"], 1, "transport call count with shared raw cache")
        _assert_equal(first.output, "hello cached", "first cached text")
        _assert_equal(second.output, "hello cached", "second cached text")
        _assert_equal(cached_parts, ["hello cached"], "cached callback replay")


def test_chat_get_text_conversation_preserves_openai_reasoning_and_cache_hit() -> None:
    with _temporary_chat_env(enable_cache=True):
        calls = {"count": 0}

        def fake_call(
            _prepared: Any,
            *,
            stream_enabled: bool,
            reasoning_summary_enabled: bool,
        ) -> Any:
            _assert_equal(reasoning_summary_enabled, True, "conversation reasoning summary flag")
            _assert_equal(stream_enabled, True, "conversation stream flag")
            calls["count"] += 1
            return [
                {
                    "type": "response.reasoning_summary_text.delta",
                    "item_id": "rs_1",
                    "summary_index": 0,
                    "delta": "We",
                },
                {
                    "type": "response.reasoning_summary_text.delta",
                    "item_id": "rs_1",
                    "summary_index": 0,
                    "delta": " decide",
                },
                {
                    "type": "response.output_text.delta",
                    "item_id": "msg_1",
                    "content_index": 0,
                    "delta": "cached answer",
                },
                {
                    "type": "response.completed",
                    "response": {
                        "output": [
                            {
                                "id": "rs_1",
                                "type": "reasoning",
                                "summary": [{"type": "summary_text", "text": "We decide"}],
                            },
                            {
                                "id": "msg_1",
                                "type": "message",
                                "role": "assistant",
                                "status": "completed",
                                "content": [{"type": "output_text", "text": "cached answer"}],
                            },
                        ],
                        "usage": {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5},
                    },
                },
            ]

        with _patched(transport_utils, "_call_openai_responses", fake_call):
            first_reasoning_chunks: list[str] = []
            second_reasoning_chunks: list[str] = []
            first_chat = Chat()
            second_chat = Chat()
            first = chat_get_text(
                first_chat,
                "Return text",
                {"model": "openai/gpt-5-mini", "reasoning_effort": "high"},
                stream_callback=StreamCallbacks(
                    on_text_delta=lambda _chunk: None,
                    on_reasoning_delta=first_reasoning_chunks.append,
                ),
            )
            second = chat_get_text(
                second_chat,
                "Return text",
                {"model": "openai/gpt-5-mini", "reasoning_effort": "high"},
                stream_callback=StreamCallbacks(
                    on_text_delta=lambda _chunk: None,
                    on_reasoning_delta=second_reasoning_chunks.append,
                ),
            )

        _assert_equal(calls["count"], 1, "reasoning cache transport call count")
        _assert_equal(first.conversation[1]["reasoning_content"], "We decide", "first reasoning conversation")
        _assert_equal(second.conversation[1]["reasoning_content"], "We decide", "cached reasoning conversation")
        _assert_equal(first.conversation[1]["reasoning_content"], first_chat.messages[-1].reasoning_content, "first chat reasoning stored")
        _assert_equal(second.conversation[1]["reasoning_content"], second_chat.messages[-1].reasoning_content, "cached chat reasoning stored")
        _assert_equal(first_reasoning_chunks, ["We", " decide"], "first reasoning callback chunks")
        _assert_equal(second_reasoning_chunks, ["We decide"], "cached reasoning callback chunks")

        db_path = Path(os.environ["LLM_CACHE_DB_PATH"])
        with sqlite3.connect(str(db_path)) as conn:
            columns = [row[1] for row in conn.execute("PRAGMA table_info(llm_cache)").fetchall()]
            row = conn.execute("SELECT response_json FROM llm_cache").fetchone()

        _assert_equal(
            columns,
            ["request_hash", "request_json", "response_json", "created_at"],
            "future-proof cache columns",
        )
        cached_response = json.loads(str(row[0]))
        _assert_equal(cached_response["content"], "cached answer", "cached response content")
        _assert_equal(cached_response["reasoning_content"], "We decide", "cached response reasoning")
        _assert_true(
            isinstance(cached_response.get("raw_response"), list),
            f"cached raw response events in {cached_response!r}",
        )


def test_chat_get_text_cache_enabled_override_forces_cache_when_env_disabled() -> None:
    with _temporary_chat_env(enable_cache=False):
        calls = {"count": 0}

        def fake_call(
            _prepared: Any,
            *,
            stream_enabled: bool,
            reasoning_summary_enabled: bool,
        ) -> Any:
            calls["count"] += 1
            return {
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [{"type": "output_text", "text": "forced cached"}],
                    }
                ],
                "usage": {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5},
            }

        with _patched(transport_utils, "_call_openai_responses", fake_call):
            first = chat_get_text(
                Chat(),
                "Return text",
                {"model": "openai/gpt-5-mini"},
                cache_enabled=True,
            )
            second = chat_get_text(
                Chat(),
                "Return text",
                {"model": "openai/gpt-5-mini"},
                cache_enabled=True,
            )

        _assert_equal(calls["count"], 1, "forced cache transport call count")
        _assert_equal(first.output, "forced cached", "forced cache first response")
        _assert_equal(second.output, "forced cached", "forced cache second response")


def test_chat_get_text_cache_enabled_override_disables_cache_when_env_enabled() -> None:
    with _temporary_chat_env(enable_cache=True):
        calls = {"count": 0}

        def fake_call(
            _prepared: Any,
            *,
            stream_enabled: bool,
            reasoning_summary_enabled: bool,
        ) -> Any:
            calls["count"] += 1
            return {
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [{"type": "output_text", "text": f"uncached {calls['count']}"}],
                    }
                ],
                "usage": {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5},
            }

        with _patched(transport_utils, "_call_openai_responses", fake_call):
            first = chat_get_text(
                Chat(),
                "Return text",
                {"model": "openai/gpt-5-mini"},
                cache_enabled=False,
            )
            second = chat_get_text(
                Chat(),
                "Return text",
                {"model": "openai/gpt-5-mini"},
                cache_enabled=False,
            )

        _assert_equal(calls["count"], 2, "disabled cache transport call count")
        _assert_equal(first.output, "uncached 1", "disabled cache first response")
        _assert_equal(second.output, "uncached 2", "disabled cache second response")


def test_chat_get_text_uses_ambient_cache_override_when_request_override_is_none() -> None:
    with _temporary_chat_env(enable_cache=False):
        calls = {"count": 0}

        def fake_call(
            _prepared: Any,
            *,
            stream_enabled: bool,
            reasoning_summary_enabled: bool,
        ) -> Any:
            calls["count"] += 1
            return {
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [{"type": "output_text", "text": "ambient cached"}],
                    }
                ],
                "usage": {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5},
            }

        with _patched(transport_utils, "_call_openai_responses", fake_call):
            with llm_cache_enabled(True):
                first = chat_get_text(Chat(), "Return text", {"model": "openai/gpt-5-mini"})
                second = chat_get_text(Chat(), "Return text", {"model": "openai/gpt-5-mini"})

        _assert_equal(calls["count"], 1, "ambient cache transport call count")
        _assert_equal(first.output, "ambient cached", "ambient cache first response")
        _assert_equal(second.output, "ambient cached", "ambient cache second response")


def test_chat_get_text_retry_count_zero_does_not_retry() -> None:
    with _temporary_chat_env():
        calls = {"count": 0}

        def fail(*_args: Any, **_kwargs: Any) -> LlmResponse:
            calls["count"] += 1
            raise RuntimeError("boom")

        with _patched(operation_utils, "request_chat_raw_text", fail):
            try:
                chat_get_text(
                    Chat(),
                    "Return text",
                    {"model": "openai/gpt-5-mini"},
                    retry_count=0,
                )
            except RuntimeError as exc:
                _assert_true("boom" in str(exc), "retry_count zero error")
            else:
                raise ValueError("Expected text failure without retry.")

        _assert_equal(calls["count"], 1, "retry_count zero call count")


def test_chat_get_text_retry_count_one_retries_once() -> None:
    with _temporary_chat_env():
        calls = {"count": 0}

        def flaky(*_args: Any, **_kwargs: Any) -> LlmResponse:
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("boom")
            return LlmResponse(
                content="hello",
                usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            )

        with _patched(operation_utils, "request_chat_raw_text", flaky):
            result = chat_get_text(
                Chat(),
                "Return text",
                {"model": "openai/gpt-5-mini"},
                retry_count=1,
            )

        _assert_equal(calls["count"], 2, "retry_count one call count")
        _assert_equal(result.output, "hello", "retry_count one output")
        _assert_usage_counts(
            result.usage,
            prompt_tokens=1,
            completion_tokens=2,
            total_tokens=3,
            label="retry_count one usage",
        )


def test_chat_get_text_does_not_retry_cancelled_request() -> None:
    with _temporary_chat_env():
        calls = {"count": 0}

        def cancelled(*_args: Any, **_kwargs: Any) -> LlmResponse:
            calls["count"] += 1
            raise LlmRequestCancelled("cancelled")

        with _patched(operation_utils, "request_chat_raw_text", cancelled):
            try:
                chat_get_text(
                    Chat(),
                    "Return text",
                    {"model": "openai/gpt-5-mini"},
                    retry_count=1,
                )
            except LlmRequestCancelled:
                pass
            else:
                raise ValueError("Expected text cancellation.")

        _assert_equal(calls["count"], 1, "text cancellation call count")


def test_text_failure_restores_original_chat() -> None:
    with _temporary_chat_env():
        chat = Chat.with_system("Keep me intact")
        original_chat = chat.model_dump(mode="json", exclude_none=True)

        def fail(*_args: Any, **_kwargs: Any) -> LlmResponse:
            raise RuntimeError("boom")

        with _patched(operation_utils, "request_chat_raw_text", fail):
            try:
                chat_get_text(
                    chat,
                    "Return text",
                    {"model": "openai/gpt-5-mini"},
                    retry_count=1,
                )
            except RuntimeError as exc:
                _assert_true("boom" in str(exc), "text failure error")
            else:
                raise ValueError("Expected text failure.")

        _assert_equal(
            chat.model_dump(mode="json", exclude_none=True),
            original_chat,
            "text chat restored after failure",
        )


def main() -> int:
    tests = [
        test_chat_validates_messages_and_roles,
        test_chat_to_llm_messages_model_dump_and_clone_are_clean,
        test_chat_preserves_assistant_reasoning_without_sending_it_to_llm,
        test_prepare_chat_request_routes_openai_and_local,
        test_no_verify_tls_server_option_configures_openai_client,
        test_build_openai_responses_request_maps_supported_fields,
        test_build_chat_completion_request_enables_usage_stream_options_for_local_streaming,
        test_normalize_usage_adds_aliases_for_local_payloads,
        test_execute_prepared_chat_request_openai_non_stream_usage,
        test_execute_prepared_chat_request_does_not_stream_without_callback_even_if_progress_enabled,
        test_execute_prepared_chat_request_openai_stream_usage_variants,
        test_execute_prepared_chat_request_openai_stream_logs_progress,
        test_execute_prepared_chat_request_local_chat_completions_stream_usage_variants,
        test_execute_prepared_chat_request_chat_completions_non_stream_preserves_reasoning,
        test_execute_prepared_chat_request_local_stream_logs_progress,
        test_execute_prepared_chat_request_openai_streams_reasoning_summary_to_optional_hook,
        test_execute_prepared_chat_request_streams_local_reasoning_deltas_to_optional_hook,
        test_execute_prepared_chat_request_openai_reasoning_only_incomplete_raises_error,
        test_logging_client_emits_start_end_and_error,
        test_retrying_client_retries_on_rate_limit,
        test_retrying_client_raises_after_max_retries,
        test_retrying_client_does_not_retry_cancelled_request,
        test_mock_client_returns_responses_in_order,
        test_build_cache_request_marks_transport_and_reasoning_summary_opt_in,
        test_raw_cache_replays_callbacks_for_text_wrapper,
        test_chat_get_text_conversation_preserves_openai_reasoning_and_cache_hit,
        test_chat_get_text_cache_enabled_override_forces_cache_when_env_disabled,
        test_chat_get_text_cache_enabled_override_disables_cache_when_env_enabled,
        test_chat_get_text_uses_ambient_cache_override_when_request_override_is_none,
        test_chat_get_text_retry_count_zero_does_not_retry,
        test_chat_get_text_retry_count_one_retries_once,
        test_chat_get_text_does_not_retry_cancelled_request,
        test_text_failure_restores_original_chat,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
