from __future__ import annotations

from pydantic import BaseModel

from prompt_lab import llm_client


class DemoModel(BaseModel):
    name: str


def test_text_wrapper_disables_cache(monkeypatch: object | None = None) -> None:
    calls: list[dict[str, object]] = []

    def fake_chat_get_text(
        chat: object,
        prompt: str,
        preset: dict[str, object],
        *,
        cache_enabled: bool,
        stream_callback: object | None = None,
    ) -> object:
        calls.append({"prompt": prompt, "preset": preset, "cache_enabled": cache_enabled})

        class Result:
            output = "hello"
            usage = {"total_tokens": 3}
            response = None

        return Result()

    original = llm_client.chat_get_text
    llm_client.chat_get_text = fake_chat_get_text  # type: ignore[assignment]
    try:
        result = llm_client.generate_text("local/model", "Prompt")
    finally:
        llm_client.chat_get_text = original

    assert result.output == "hello"
    assert calls[0]["cache_enabled"] is False


def test_structured_wrapper_disables_cache() -> None:
    calls: list[dict[str, object]] = []

    def fake_structured(
        chat: object,
        prompt: str,
        *,
        preset: dict[str, object],
        response_model: type[BaseModel],
        validation_context: object | None,
        cache_enabled: bool,
        stream_callback: object | None = None,
    ) -> object:
        calls.append({"prompt": prompt, "cache_enabled": cache_enabled, "validation_context": validation_context})

        class Result:
            output = DemoModel(name="Ada")
            usage = {"total_tokens": 4}
            response = None

        return Result()

    original = llm_client.chat_get_structured_lite
    llm_client.chat_get_structured_lite = fake_structured  # type: ignore[assignment]
    try:
        result = llm_client.generate_structured("local/model", "Prompt", DemoModel, {"x": 1})
    finally:
        llm_client.chat_get_structured_lite = original

    assert result.output.model_dump() == {"name": "Ada"}
    assert calls[0]["cache_enabled"] is False


def main() -> int:
    tests = [
        test_text_wrapper_disables_cache,
        test_structured_wrapper_disables_cache,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
