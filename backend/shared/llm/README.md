# LLM Utilities

`shared.llm` contains Carmilla's provider-facing LLM helpers. It is shared by workflows, tests, and backend probes.

Primary entrypoints:

- `chat_get_text`: text generation wrapper.
- `chat_get_structured_lite`: structured-output wrapper with validation and fix retries.
- `chat_client`: default client, logging client, retrying client, and mock client wiring.
- `chat_request`: model/server resolution and provider request preparation.
- `chat_transport`: OpenAI hosted and OpenAI-compatible local transport execution.
- `cancellation`: cooperative request cancellation primitives.
- `stream_callbacks`: streaming text, reasoning, usage, and idle-panel callback helpers.
- `server_registry`: `.servers.jsonc` loading and model reference resolution.

Keep provider-specific request shaping under `transports/`, shared operation behavior in the top-level modules, and tests in `python/tests/`.

---

## Using outside the main project

### Installing dependencies

```
pip install openai pydantic json-repair pyjson5
```

Copy the `shared/llm` directory and make it importable as `shared.llm` (add its parent directory to `PYTHONPATH` or install it as a local package).

### Configuration file: `.servers.jsonc`

The module loads server definitions from `.servers.jsonc` in the current working directory. The file is a JSON object where each key is an arbitrary server name used as the `<server>` prefix in model references (e.g. `"openai/gpt-4o-mini"`, `"local/llama3"`).

#### Server types

**`"type": "openai"` — hosted OpenAI API**

```jsonc
{
  "openai": {
    "type": "openai",
    "api_key": "env:OPENAI_API_KEY"   // literal key or "env:VAR_NAME"
  }
}
```

`api_key` is required. Use `"env:VAR_NAME"` to read the value from an environment variable at runtime instead of hardcoding it.

**`"type": "local"` — local OpenAI-compatible server (Ollama, vLLM, LM Studio, etc.)**

```jsonc
{
  "local": {
    "type": "local",
    "host": "http://localhost:11434",  // required: base URL of the server
    "api_key": "not_needed",           // optional placeholder (some clients require a non-empty key)
    "no_verify_tls": false             // optional: set true to skip TLS verification for self-signed HTTPS
  }
}
```

`host` is required. `/v1` is appended automatically if the URL does not already end with it.

#### Multiple servers in one file

```jsonc
{
  "openai": {
    "type": "openai",
    "api_key": "env:OPENAI_API_KEY"
  },
  "local1": {
    "type": "local",
    "host": "http://localhost:8080"
  },
  "local2": {
    "type": "local",
    "host": "http://192.168.1.100:8080",
    "no_verify_tls": true
  }
}
```

Model references then look like `"openai/gpt-4o-mini"`, `"local1/llama3"`, `"local2/mistral"`, etc.

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `LLM_MODEL` | — | Default model reference (e.g. `openai/gpt-4o-mini`). Used when `model` is not passed in the request preset. |
| `LLM_CACHE` | `false` | Enable SQLite response cache by default. Accepted truthy values: `1`, `true`, `yes`, `on`. Individual requests may override this with `cache_enabled`. |
| `LLM_CACHE_DB_PATH` | `.cache/llm_cache.db` | Path to the SQLite cache database. Created automatically on first use. |
| `LLM_TRANSPORT_RETRIES` | `1` | Maximum number of retries on transient transport errors (rate limits, timeouts, connection errors). |
| `LLM_LOG_PROGRESS` | `1` | Log request progress and token usage. Set to `0`, `false`, `no`, or `off` to disable. |

### Code examples

#### Text generation

```python
from shared.llm.chat import Chat
from shared.llm.chat_get_text import chat_get_text

chat = Chat.with_system("You are a helpful assistant.")

preset = {
    "model": "openai/gpt-4o-mini",
    "temperature": 0.7,
    "max_tokens": 512,
}

result = chat_get_text(chat, "Explain recursion in one sentence.", preset)
print(result.output)
```

If `model` is omitted from `preset`, the module falls back to the `LLM_MODEL` environment variable (e.g. `LLM_MODEL=openai/gpt-4o-mini`).

Pass `cache_enabled=True` or `cache_enabled=False` to `chat_get_text` or
`chat_get_structured_lite` to override `LLM_CACHE` for one request. When omitted,
the helper uses the ambient workflow/session setting when present, then falls back
to `LLM_CACHE`.

#### Structured output

```python
from pydantic import BaseModel
from shared.llm.chat import Chat
from shared.llm.chat_get_structured_lite import chat_get_structured_lite

class Summary(BaseModel):
    title: str
    bullet_points: list[str]

chat = Chat()
preset = {"model": "openai/gpt-4o-mini", "temperature": 0.2}

result = chat_get_structured_lite(
    chat,
    "Summarize the water cycle.\n\nReturn json with following schema \n\n```\n<<MODEL>>\n```\n\nReturn only json."
    preset,
    response_model=Summary,
)
print(result.output.title)
print(result.output.bullet_points)
```

#### Multi-turn conversation

```python
from shared.llm.chat import Chat
from shared.llm.chat_get_text import chat_get_text

chat = Chat.with_system("You are a concise assistant.")
preset = {"model": "openai/gpt-4o-mini"}

result = chat_get_text(chat, "What is the capital of France?", preset)
print(result.output)

result = chat_get_text(chat, "And what is it known for?", preset)
print(result.output)
```

The `Chat` object accumulates message history — subsequent calls continue the same conversation.
Assistant messages may store `reasoning_content` when a provider exposes reasoning
text, but outbound LLM requests still include only `role` and `content`.

#### Token usage

```python
result = chat_get_text(chat, "Hello!", preset)
print(result.usage)  # {"prompt_tokens": ..., "completion_tokens": ..., "total_tokens": ...}
```

#### Conversation reasoning content

`ChatResult.conversation` and assistant entries in `Chat.messages` include
`reasoning_content` only when the provider returns exposed reasoning text, such
as OpenAI reasoning summaries or local OpenAI-compatible `reasoning_content` /
`reasoning` fields:

```python
result = chat_get_text(chat, "Think briefly, then answer.", preset, stream_callback=callbacks)
print(result.conversation[-1])
# {"role": "assistant", "content": "...", "reasoning_content": "..."}
```

The field is omitted when no non-empty reasoning text is present.

When `LLM_CACHE` is enabled, the cache stores one JSON response payload that
includes the projected content, usage, reasoning content, and raw provider
response/events when available. Existing local cache databases may be dropped and
rebuilt when this schema changes.

#### Optional cancellation

Cancellation is cooperative and opt-in. Calls without `StreamCallbacks` continue
to work without any cancellation setup.

```python
from shared.llm.cancellation import CancellationToken
from shared.llm.stream_callbacks import StreamCallbacks

token = CancellationToken()
callbacks = StreamCallbacks(cancel_check=token.raise_if_cancelled)

result = chat_get_text(chat, "Write a long answer.", preset, stream_callback=callbacks)
```

If `token.cancel()` is called while a stream is being consumed, transports raise
`LlmRequestCancelled`. The high-level wrappers do not retry that exception.
