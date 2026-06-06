---
name: "prompt-lab-llm-debug"
description: "Use when debugging Prompt Lab LLM routing, OpenAI-compatible servers, streaming, structured output, usage payloads, cache behavior, or live chat smoke tests."
---

# Prompt Lab LLM Debug

Use this skill when Prompt Lab cannot call a model, returns unexpected transport output, fails structured-output repair, or needs a live smoke test.

## Quick Start

1. Confirm `backend/shared/llm` is importable:

```bash
PYTHONPATH=backend python -c "from shared.llm.chat import Chat; print(Chat())"
```

2. Check local config:

```text
.servers.jsonc
.env
```

3. Run fast local tests first:

```bash
PYTHONPATH=backend python backend/tests/test_chat.py
PYTHONPATH=backend python backend/tests/test_chat_get_structured_lite.py
PYTHONPATH=backend python backend/tests/test_structured_lite_units.py
```

4. Run live smoke only when credentials/server are available:

```bash
PYTHONPATH=backend python backend/tests/test_chat_env.py
```

## Debug Rules

- Keep generator-run cache disabled in Prompt Lab experiments.
- Use `.servers.jsonc` model refs like `openai/gpt-5-mini` or `local/my-model`.
- For local servers, ensure the host is OpenAI-compatible and resolves to a `/v1` API.
- Enable `OPENAI_LOG=info` or `OPENAI_LOG=debug` only for diagnosis.
- If structured output fails, inspect raw output, extracted candidates, validation errors, and fix retries before changing transport code.

