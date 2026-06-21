# CodeMirror Prompt And Model Viewers Design

## Context

Prompt Lab currently renders prompt and proposal artifacts as plain `<pre>` blocks.
The overview tab shows only the active prompt. The proposal tab shows separate
Prompt, Model, and Rationale tabs, with Model present only when the proposal
contains `model_py`.

This makes prompt/model review workable, but it hides syntax structure and makes
Pydantic proposal review less comparable to the overview state.

## Goals

- Render prompts and Pydantic models in read-only CodeMirror 6 viewers.
- Treat prompt text as Markdown with visible Jinja-oriented highlighting.
- Treat model text as Python.
- Show the active Pydantic model next to the active prompt on the overview tab.
- Reshape Pydantic proposals so prompt and model appear side by side, with the
  rationale spanning the full proposal width.
- Add a proposal view toggle between the proposed files and a diff against the
  current version.
- Keep text-output experiments free of empty model panels.

## Non-Goals

- Do not add in-browser editing for prompt or model artifacts.
- Do not build a complete Jinja parser.
- Do not change proposal generation semantics or structured-output prompt rules.
- Do not introduce Carmilla workflow runtime dependencies.

## Dependencies

Use current CodeMirror 6 packages:

- `codemirror`
- `@codemirror/lang-markdown`
- `@codemirror/lang-python`
- `@codemirror/merge`

As of 2026-06-21, `npm view` reports:

- `codemirror@6.0.2`
- `@codemirror/lang-markdown@6.5.0`
- `@codemirror/lang-python@6.2.1`
- `@codemirror/merge@6.12.2`

Install with `pnpm add` in `frontend` so `pnpm-lock.yaml` records the resolved
versions.

## Data Contract

Extend `VersionOverview` with optional model source fields for Pydantic
experiments:

```ts
interface VersionOverview {
  experiment: Experiment;
  version: string;
  prompt: string;
  model_py?: string | null;
  model_file?: string | null;
  rubric: string;
  cases: Case[];
  validators: ValidatorDefinition[];
}
```

The backend `GET /api/experiments/{experiment_id}/versions/{version}` endpoint
will read `experiment.output.model_file` only when `experiment.output.type` is
`"pydantic"` and return that source as `model_py`. Text-output experiments return
`model_py: null`.

Proposal responses already contain the proposed `prompt_md`, optional
`model_py`, and `rationale_md`. For the proposal diff view, the frontend can use
the active `VersionOverview.prompt` and `VersionOverview.model_py` as the
baseline, because the proposal is scoped to the selected experiment version and
review.

## Viewer Components

Add a small read-only viewer layer under `frontend/src/components`:

- `CodeViewer`: renders a single read-only CodeMirror editor.
- `DiffViewer`: renders a read-only CodeMirror unified diff.
- Shared language selection for `markdown-jinja` and `python`.

The Markdown/Jinja mode will use CodeMirror Markdown plus lightweight decorations
for Jinja delimiters and the `<<MODEL>>` marker. The objective is scanability, not
full template validation.

Viewers should:

- avoid editable affordances;
- preserve copy/select behavior;
- use stable heights with internal scrolling for long artifacts;
- match existing Prompt Lab visual density and border radius;
- work inside responsive one-column layouts on narrow screens.

## Overview UI

For text-output experiments, the overview tab keeps a single prompt viewer above
the validators and cases.

For Pydantic experiments, the overview tab shows:

- left: prompt viewer, labeled `Prompt`;
- right: Python model viewer, labeled with the model file when available;
- below: validators and cases spanning the full width.

This keeps the overview focused on the current version's source artifacts before
showing derived validation/case context.

## Proposal UI

When no proposal exists, the current empty states remain.

When a text-output proposal exists:

- show a two-state view toggle: `New version` and `Diff`;
- in `New version`, show the proposed prompt viewer and rationale;
- in `Diff`, show a unified diff from current prompt to proposed prompt, plus
  the same rationale.

When a Pydantic proposal exists:

- show the same `New version` and `Diff` toggle;
- show rationale as a full-width section above the artifacts;
- in `New version`, show prompt and model side by side;
- in `Diff`, show two artifact panels side by side: the prompt panel on the
  left and the model panel on the right, with each panel using one unified diff
  viewer rather than an old/new split view;
- collapse to a single column on mobile or narrow content widths.

The `Create next version` action remains in the proposal toolbar.

## Error Handling

- If `model_py` is unavailable for a Pydantic overview, show an inline empty
  state in the model panel rather than failing the whole page.
- If a proposal lacks `model_py` for a Pydantic experiment, preserve the existing
  behavior of not rendering a model panel and rely on backend validation to reject
  invalid generated proposals.
- If CodeMirror fails to initialize, React error boundaries are not introduced in
  this change; validation should catch build/runtime issues before delivery.

## Testing

Backend:

- Update the version overview API test to cover text output with `model_py: null`.
- Add or extend a Pydantic overview test to assert `model_py` and `model_file`.

Frontend unit/render tests:

- Add coverage for `CodeViewer` rendering without editable controls.
- Update overview tests for prompt-only and prompt-plus-model cases.
- Update proposal tests for text and Pydantic proposal layouts.

Frontend e2e:

- Keep using `demo-string` and `demo-json`.
- Verify `demo-string` proposal shows prompt/rationale and no model panel.
- Verify `demo-json` overview shows prompt and model viewers.
- Verify `demo-json` proposal can switch between `New version` and `Diff`.

Validation commands:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_api.py
cd frontend && pnpm lint && pnpm test && pnpm build
cd frontend && pnpm test:e2e
```

## Risks

- CodeMirror package additions increase frontend bundle size. This is acceptable
  for a local-first review tool, but the viewers should be lazy enough in usage
  that they do not create unrelated workflow latency.
- Jinja highlighting will be approximate. The implementation should make this
  visually obvious as token highlighting, not as validation.
- Diff layout can become cramped. Keep the side-by-side layout at the artifact
  level only, with prompt on the left and model on the right, and use unified
  diffs inside those panels instead of adding another old/new split layer.
