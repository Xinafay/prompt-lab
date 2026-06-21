---
name: "prompt-lab-frontend-ui"
description: "Use when modifying Prompt Lab frontend UI, React/Vite components, browser-tested workflows, artifact viewers, CodeMirror/DiffViewer displays, or local app interaction behavior."
---

# Prompt Lab Frontend UI

Use this skill when changing the Prompt Lab frontend or browser-visible behavior.

## Quick Start

1. Reuse existing React components and CSS patterns before adding new UI primitives.
2. Keep UI text in English unless the user explicitly requests another language.
3. Use `demo-string` and `demo-json` for manual browser checks and regression tests.
4. If the user says frontend/backend servers are running, use the current in-app browser tab and do not ask them to stop or restart servers.
5. Prefer the main repository checkout and small commits. Do not create a separate worktree for ordinary UI changes unless the user asks for one or a real checkout conflict requires it.

## Code And Artifact Viewers

- Use `CodeViewer` for read-only prompt, model, JSON, raw output, rendered prompt, and validation output displays.
- Use `DiffViewer` for read-only unified diffs. Keep prompt diff and model diff as separate panels when both artifacts exist.
- Use `language="markdown-jinja"` for prompts and rendered prompts, `language="python"` for Pydantic model source, `language="json"` for structured output, and `language="text"` for unstructured raw text.
- Avoid new raw `<pre>` artifact blocks unless SSR-only fallback markup is being implemented inside the shared viewer component.
- Keep `<<MODEL>>` and Jinja token highlighting distinct from diff colors. Do not use diff-like red or green for non-diff syntax markers.
- Keep code viewer backgrounds, borders, and headers aligned with existing light app surfaces unless the surrounding UI explicitly uses a dark surface.

## Browser Verification

- Prefer the Codex in-app Browser plugin via `node_repl` for inspecting the user's visible tab.
- Check for Vite overlays, console errors, layout overlap, and stale fallback markup such as old `<pre>` blocks after replacing artifact viewers.
- For CodeMirror changes, verify both DOM state and a screenshot or computed styles because editor content can be mounted after React's initial render.

## Test Defaults

Run targeted tests first, then broader frontend checks when behavior changes:

```bash
cd frontend
pnpm test
pnpm lint
pnpm build
```

Use `pnpm test:e2e` when the change affects routed workflows, browser interaction, or cross-tab behavior.
