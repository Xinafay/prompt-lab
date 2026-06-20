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
            response = {"id": "text-response"}

        return Result()

    original = llm_client.chat_get_text
    llm_client.chat_get_text = fake_chat_get_text  # type: ignore[assignment]
    try:
        result = llm_client.generate_text("local/model", "Prompt")
    finally:
        llm_client.chat_get_text = original

    assert result.output == "hello"
    assert result.raw_response == {"id": "text-response"}
    assert calls[0]["preset"] == {"model": "local/model"}
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
        calls.append(
            {
                "prompt": prompt,
                "preset": preset,
                "response_model": response_model,
                "cache_enabled": cache_enabled,
                "validation_context": validation_context,
            }
        )

        class Result:
            output = DemoModel(name="Ada")
            usage = {"total_tokens": 4}
            response = None
            conversation = [{"role": "assistant", "content": "{\"name\":\"Ada\"}"}]

        return Result()

    original = llm_client.chat_get_structured_lite
    llm_client.chat_get_structured_lite = fake_structured  # type: ignore[assignment]
    try:
        result = llm_client.generate_structured("local/model", "Prompt", DemoModel, {"x": 1})
    finally:
        llm_client.chat_get_structured_lite = original

    assert result.output.model_dump() == {"name": "Ada"}
    assert result.raw_response == [{"role": "assistant", "content": "{\"name\":\"Ada\"}"}]
    assert calls[0]["preset"] == {"model": "local/model"}
    assert calls[0]["response_model"] is DemoModel
    assert calls[0]["validation_context"] == {"x": 1}
    assert calls[0]["cache_enabled"] is False


def test_text_fake_response_uses_dry_run_usage() -> None:
    result = llm_client.generate_text_from_fake_response(
        "local/model",
        "Prompt",
        "fake text",
    )

    assert result.output == "fake text"
    assert result.usage == {"dry_run": True}
    assert result.raw_response[0]["role"] == "user"
    assert result.raw_response[0]["content"] == "Prompt"
    assert result.raw_response[1]["role"] == "assistant"
    assert result.raw_response[1]["content"] == "fake text"


def test_structured_fake_response_validates_with_structured_lite() -> None:
    result = llm_client.generate_structured_from_fake_response(
        "local/model",
        "Prompt <<MODEL>>",
        DemoModel,
        {"x": 1},
        '{"name": "Ada"}',
    )

    assert result.output.model_dump() == {"name": "Ada"}
    assert result.usage == {"dry_run": True}
    assert result.raw_response[0]["role"] == "user"
    assert result.raw_response[1]["role"] == "assistant"


def test_structured_fake_response_wraps_validation_errors() -> None:
    try:
        llm_client.generate_structured_from_fake_response(
            "local/model",
            "Prompt <<MODEL>>",
            DemoModel,
            None,
            '{"name": 1}',
        )
    except llm_client.PromptLabStructuredValidationError as exc:
        assert "name" in str(exc)
        assert "Input should be a valid string" in str(exc)
        assert exc.raw_output == '{"name": 1}'
    else:
        raise AssertionError("Expected PromptLabStructuredValidationError")


def main() -> int:
    tests = [
        test_text_wrapper_disables_cache,
        test_structured_wrapper_disables_cache,
        test_text_fake_response_uses_dry_run_usage,
        test_structured_fake_response_validates_with_structured_lite,
        test_structured_fake_response_wraps_validation_errors,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
