# Agents Guide - Prompt Lab

Prompt Lab is a local-first tool for iterative prompt and Pydantic structured-output evaluation.

## Boundaries

- Keep Prompt Lab independent from Carmilla workflow runtime.
- Do not import `workflow_runtime`, Story Parser workflow classes, `WorkflowState`, or Carmilla flat-file workflow context.
- Carmilla is only an external producer of neutral experiment/case bundles.
- The bundled `backend/shared/llm` module should be treated as imported vendor code until it is replaced by a shared package or subrepo.
- Prefer making many small commits after changes so individual steps can be reverted easily if needed.

## Python

- Use `backend/shared/llm` through a thin Prompt Lab wrapper when implementing application code.
- Keep generator-run LLM cache disabled.
- Store validation errors as run artifacts; they are meaningful eval results.
- Use Pydantic models for artifact contracts.
- Prefer filesystem artifacts as the source of truth.

## Prompt Construction

- Keep structured-output prompts explicit and minimal: each active prompt template
  that relies on `chat_get_structured_lite` must contain exactly one literal
  `<<MODEL>>`, normally in a fenced block near the end of the prompt.
- Do not pass the same Pydantic schema twice. If `<<MODEL>>` is present, do not
  also inject `model_json_schema()` or `*_SCHEMA_JSON` into the prompt body.
- Do not hide `<<MODEL>>` inside builder-provided Jinja variables; the marker
  should be visible in the `.jinja` or experiment `prompt.md` file itself.
- Remove obsolete prompt templates and their old artifact models/fake responses
  when a workflow no longer calls that prompt.

## Frontend

- Use React/Vite for the standalone UI.
- Keep UI text in English unless explicitly requested otherwise.
- Show run progress with current case and repeat.
- Show structured output as JSON and preserve raw output/validation errors.
- In-app browser automation may not visually trigger CSS hover tooltips even when
  the tooltip wrapper and accessible description are present; verify tooltip DOM
  state and, when needed, ask for/perform a manual visual check.

## Browser And Local Servers

- When the user says the backend/frontend servers are already running, assume they
  are running. Do not repeatedly try to start them or contradict the user because
  shell `curl` cannot reach `127.0.0.1`.
- Codex shell commands may run inside a macOS `seatbelt` sandbox with local
  networking and port binding restricted. A failed `curl`, failed server bind, or
  failed standalone Chromium launch from the shell is not evidence that the user's
  in-app browser or dev servers are broken.
- Prefer the Codex in-app Browser plugin for UI inspection. Bootstrap it through
  `node_repl` with:

```js
const { setupBrowserRuntime } = await import(
  "/Applications/Codex.app/Contents/Resources/plugins/openai-bundled/plugins/browser/scripts/browser-client.mjs"
);
await setupBrowserRuntime({ globals: globalThis });
globalThis.browser = await agent.browsers.get("iab");
nodeRepl.write(await browser.documentation());
```

- After bootstrapping, use `await browser.tabs.selected()` to inspect the current
  user-visible tab, then use `tab.playwright.domSnapshot()`, targeted locators,
  screenshots, and page evaluation through the browser API.
- Do not conclude that browser automation is unavailable just because no separate
  `browser.*` tool appears in the tool list. First try the Browser plugin via
  `node_repl` as above.
- Standalone Playwright from shell is useful for project e2e tests, but it may
  require running outside the sandbox. The in-app browser path is preferred for
  inspecting the page the user is actively viewing.

## Demo Experiments And E2E

- Use `demo-string` and `demo-json` for manual UI checks and automated frontend
  regression tests. They contain precomputed artifacts and avoid real token usage.
- The frontend has Playwright e2e configured under `frontend/e2e`. Run it with:

```bash
cd frontend
pnpm test:e2e
```

- Playwright e2e starts or reuses the backend on `127.0.0.1:8000` and Vite on
  `127.0.0.1:5173`. If the user already has those servers running, reuse them.
- Keep generated Playwright artifacts out of commits; `frontend/playwright-report/`
  and `frontend/test-results/` are ignored.

## Validation

From the Prompt Lab repository root:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_chat.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_chat_get_structured_lite.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_structured_lite_units.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_format_validation_errors.py
.venv/bin/pyright --project pyrightconfig.json --pythonpath .venv/bin/python
cd frontend && pnpm lint && pnpm test && pnpm build
```
