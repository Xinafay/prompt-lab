from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, cast

from pydantic import BaseModel
from rich.console import Console
from rich.live import Live
from rich.text import Text

from shared.llm.chat import Chat
from shared.llm import chat_facade as chat_utils
from shared.llm.stream_callbacks import StreamCallbacks
from shared.llm.chat_get_structured_lite import chat_get_structured_lite
from shared.llm.chat_get_text import chat_get_text
from shared.llm.models import load_models_config


TEXT_PROMPT = "Reply with exactly: OK"
STREAM_PROMPT = (
    "Write 18 numbered lines about why automated tests matter. "
    "Each line must be short, concrete, and under 7 words. "
    "Do not add any intro or outro."
)
REASONING_PROMPT = (
    "Shelf A has twice as many books as Shelf B. "
    "Shelf C has 15 fewer books than Shelf A. "
    "Together the shelves hold 165 books. "
    "Think carefully and return one short sentence with the value of Shelf B."
)
STRUCTURED_PROMPT = (
    "Return only JSON matching this schema.\n"
    "Set status to 'ok' and echo to 'hello'.\n"
    "<<MODEL>>"
)
BASE_PRESET: dict[str, Any] = {}
_TRUE_ENV = {"1", "true", "yes", "on"}

console = Console()
_ENV_LOADED = False
_LOGGING_CONFIGURED = False


class _StructuredSmokePayload(BaseModel):
    status: str
    echo: str


def _env_flag(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in _TRUE_ENV


def _ensure_env_loaded() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise RuntimeError("python-dotenv is required in .venv to run the chat smoke test.") from exc
    env_path = Path(".env")
    if not env_path.is_file():
        env_path = Path(__file__).parent.parent.parent / ".env"
    load_dotenv(env_path)
    if not _env_flag("CHAT_ENV_USE_CACHE"):
        os.environ["LLM_CACHE"] = "0"
        os.environ.pop("LLM_CACHE_DB_PATH", None)
    _ENV_LOADED = True


def _ensure_logging_configured() -> None:
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return
    if not _env_flag("CHAT_ENV_LLM_LOGS", default=True):
        return
    logging.basicConfig(level=logging.INFO, format="%(message)s", force=True)
    logging.getLogger("utils.chat").setLevel(logging.INFO)
    _LOGGING_CONFIGURED = True


class _LiveStreamProbe:
    def __init__(
        self,
        *,
        label: str,
        dump_hooks: bool,
    ) -> None:
        self.label = label
        self.dump_hooks = dump_hooks
        self.content_text = Text()
        self.content_chunks: list[str] = []
        self.reasoning_chunks: list[str] = []
        self.reasoning_segments = 0
        self.prompt_events: list[dict[str, Any]] = []
        self.usage_events: list[dict[str, Any]] = []
        self.phase_events: list[dict[str, Any]] = []
        self._live: Live | None = None

    def attach_live(self, live: Live) -> None:
        self._live = live

    def __call__(self, chunk: str) -> None:
        if not chunk:
            return
        self.content_chunks.append(chunk)
        self.content_text.append(chunk)
        if self._live is not None:
            self._live.update(self.content_text)
        if self.dump_hooks:
            console.print(f"[cyan]{self.label} content[/cyan] {chunk!r}")

    def on_reasoning_delta(self, chunk: str) -> None:
        if not chunk:
            return
        self.reasoning_chunks.append(chunk)
        if self.dump_hooks:
            console.print(f"[magenta]{self.label} reasoning[/magenta] {chunk!r}")

    def on_reasoning_segment_done(self) -> None:
        self.reasoning_segments += 1
        if self.dump_hooks:
            console.print(f"[magenta]{self.label} reasoning_done[/magenta]")

    def on_prompt_messages(self, messages: list[dict[str, Any]], *, attempt: int) -> None:
        event = {"attempt": attempt, "messages": messages}
        self.prompt_events.append(event)
        if self.dump_hooks:
            console.print(
                f"[yellow]{self.label} prompt_messages[/yellow] "
                f"{json.dumps(event, ensure_ascii=False, indent=2)}"
            )

    def on_usage(self, usage: dict[str, Any] | None, *, attempt: int) -> None:
        event = {"attempt": attempt, "usage": usage}
        self.usage_events.append(event)
        if self.dump_hooks:
            console.print(
                f"[green]{self.label} usage[/green] "
                f"{json.dumps(event, ensure_ascii=False, indent=2)}"
            )

    def on_stream_phase(
        self,
        phase: str,
        *,
        reset: bool = False,
        meta: dict[str, Any] | None = None,
    ) -> None:
        event = {"phase": phase, "reset": reset, "meta": meta}
        self.phase_events.append(event)
        if self.dump_hooks:
            console.print(
                f"[yellow]{self.label} phase[/yellow] "
                f"{json.dumps(event, ensure_ascii=False, indent=2)}"
            )

    @property
    def callbacks(self) -> StreamCallbacks:
        return StreamCallbacks(
            on_text_delta=self,
            on_reasoning_delta=self.on_reasoning_delta,
            on_reasoning_segment_done=self.on_reasoning_segment_done,
            on_prompt_messages=self.on_prompt_messages,
            on_usage=self.on_usage,
            on_stream_phase=self.on_stream_phase,
        )

    def print_summary(self) -> None:
        content = "".join(self.content_chunks)
        reasoning = "".join(self.reasoning_chunks)
        console.print(
            f"{self.label}: chunks={len(self.content_chunks)} "
            f"content_chars={len(content)} "
            f"reasoning_chunks={len(self.reasoning_chunks)} "
            f"reasoning_segments={self.reasoning_segments}"
        )
        if reasoning:
            console.print(f"{self.label} reasoning: {reasoning!r}")
        if self.prompt_events:
            console.print(f"{self.label} prompt_events: {len(self.prompt_events)}")
        if self.usage_events:
            console.print(f"{self.label} usage_events: {len(self.usage_events)}")
        if self.phase_events:
            console.print(
                f"{self.label} phases: {json.dumps(self.phase_events, ensure_ascii=False)}"
            )


@contextmanager
def _live_probe(label: str, *, dump_hooks: bool) -> Iterator[_LiveStreamProbe]:
    probe = _LiveStreamProbe(label=label, dump_hooks=dump_hooks)
    console.print(f"[bold]{label}[/bold]")
    with Live(probe.content_text, console=console, refresh_per_second=12) as live:
        probe.attach_live(live)
        yield probe
    console.print()


def _base_preset(model: str, *, reasoning: bool = False) -> dict[str, Any]:
    preset = BASE_PRESET | {"model": model}
    if reasoning and model.startswith("openai/"):
        preset["reasoning_effort"] = "high"
    return preset


def _stream_text_probe(model: str) -> None:
    with _live_probe("stream_text", dump_hooks=_env_flag("CHAT_ENV_DUMP_HOOKS")) as probe:
        result = chat_get_text(
            Chat(),
            STREAM_PROMPT,
            _base_preset(model),
            stream_callback=probe.callbacks,
        )

    probe.print_summary()
    console.print(f"stream_text result chars: {len(result.output)}")
    console.print(f"stream_text usage: {result.usage}")
    if not probe.content_chunks:
        raise ValueError("Streaming text probe did not emit any streamed content chunks.")


def _reasoning_text_probe(model: str) -> None:
    with _live_probe("reasoning_text", dump_hooks=_env_flag("CHAT_ENV_DUMP_HOOKS")) as probe:
        result = chat_get_text(
            Chat(),
            REASONING_PROMPT,
            _base_preset(model, reasoning=True),
            stream_callback=probe.callbacks,
        )

    probe.print_summary()
    console.print(f"reasoning_text result: {result.output!r}")
    console.print(f"reasoning_text usage: {result.usage}")
    if not probe.content_chunks:
        raise ValueError("Reasoning text probe did not emit any streamed content chunks.")
    if model.startswith("openai/") and not probe.reasoning_chunks:
        raise ValueError("OpenAI reasoning probe did not emit any reasoning summary chunks.")


def _structured_probe(model: str) -> None:
    with _live_probe("structured", dump_hooks=_env_flag("CHAT_ENV_DUMP_HOOKS")) as probe:
        result = chat_get_structured_lite(
            Chat(),
            STRUCTURED_PROMPT,
            _base_preset(model, reasoning=True),
            response_model=_StructuredSmokePayload,
            stream_callback=probe.callbacks,
            fix_retry=0,
        )

    probe.print_summary()
    payload = result.output
    console.print(f"structured result: {payload.model_dump(mode='json')}")
    console.print(f"structured usage: {result.usage}")
    if payload.status != "ok" or payload.echo != "hello":
        raise ValueError(f"Unexpected structured payload: {payload.model_dump(mode='json')}")


def _dump_raw_transport(model: str) -> None:
    if not _env_flag("CHAT_ENV_DUMP_RAW"):
        return

    console.rule(f"[bold]raw transport dump: {model}[/bold]")
    prepared = chat_utils.prepare_chat_request(
        [{"role": "user", "content": REASONING_PROMPT}],
        **_base_preset(model, reasoning=True),
    )

    if prepared.spec.server_type == "openai":
        stream = chat_utils._call_openai_responses(
            prepared,
            stream_enabled=True,
            reasoning_summary_enabled=True,
        )
        for event in stream:
            payload = chat_utils._to_plain_payload(event)
            console.print(json.dumps(payload, ensure_ascii=False, indent=2))
        final_payload = chat_utils._to_plain_payload(
            chat_utils._call_openai_responses(
                prepared,
                stream_enabled=False,
                reasoning_summary_enabled=True,
            )
        )
        console.print(json.dumps(final_payload, ensure_ascii=False, indent=2))
        return

    stream = chat_utils._call_chat_completion(prepared, stream_enabled=True)
    for chunk in stream:
        payload = chat_utils._to_plain_payload(chunk)
        console.print(json.dumps(payload, ensure_ascii=False, indent=2))
    final_payload = chat_utils._to_plain_payload(
        chat_utils._call_chat_completion(prepared, stream_enabled=False)
    )
    console.print(json.dumps(final_payload, ensure_ascii=False, indent=2))


def run_model(model: str) -> None:
    """Run text, streaming, reasoning, and structured-output checks for a single model."""

    _ensure_env_loaded()
    _ensure_logging_configured()
    if model.startswith("openai/") and not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is missing after loading .env.")

    console.rule(f"[bold]{model}[/bold]")

    with _live_probe("text", dump_hooks=_env_flag("CHAT_ENV_DUMP_HOOKS")) as probe:
        text_result = chat_get_text(
            Chat(),
            TEXT_PROMPT,
            _base_preset(model),
            stream_callback=probe.callbacks,
        )
    probe.print_summary()
    text = text_result.output
    console.print(f"text result: {text!r}")
    console.print(f"text usage: {text_result.usage}")
    if text != "OK":
        raise ValueError(f"Unexpected text payload: {text!r}")

    if _env_flag("CHAT_ENV_RUN_STREAM_PROBE", default=True):
        _stream_text_probe(model)

    if _env_flag("CHAT_ENV_RUN_REASONING_PROBE", default=True):
        _reasoning_text_probe(model)

    _structured_probe(model)
    _dump_raw_transport(model)


def main() -> int:
    """CLI entrypoint for the chat environment smoke and streaming probes."""

    models = load_models_config()
    for model in models:
        try:
            run_model(model)
        except Exception as exc:
            console.print(f"[red]Error while testing {model}: {exc}[/red]")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
