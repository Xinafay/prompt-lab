# Experiments Seeded From Examples Design

## Goal

Make `examples/` a versioned golden template and make `experiments/` the only runtime workspace. This prevents generated runs, reviews, proposals, and GUI edits from modifying examples.

## Current State

`PromptLabStore` currently lists and resolves experiments from both `examples/` and `experiments/`, preferring `experiments/` when both contain the same id. This is convenient for demos, but it makes `examples/` both a template source and a possible runtime source.

## Target Behavior

On backend startup, Prompt Lab seeds `experiments/` from `examples/` only when `experiments/` does not exist or contains no `*/experiment.json` manifests.

After this seed step:

- `examples/` is never used as a runtime experiment source.
- `experiments/` is the only directory read by `PromptLabStore`.
- Generated artifacts are written only under `experiments/`.
- GUI edits to `experiment.json` will update only `experiments/<id>/experiment.json`.
- No automatic sync happens when `experiments/` already contains at least one experiment.

## Directory Ownership

`examples/`:

- committed to git;
- treated as immutable golden templates during normal app use;
- safe to update manually when changing starter examples.

`experiments/`:

- local runtime workspace;
- ignored by git;
- may contain user edits, runs, reviews, proposals, and generated versions.

## Backend Design

Add a seeding function near config/app initialization:

1. Resolve `experiments_root` and `examples_root` from `PromptLabConfig`.
2. If `experiments_root` contains any `*/experiment.json`, do nothing.
3. If `examples_root` does not exist, create `experiments_root` and continue with an empty workspace.
4. Otherwise copy each top-level experiment directory from `examples_root` to `experiments_root`.

Use directory copy semantics that preserve files and subdirectories. Do not overwrite an existing non-empty `experiments_root`.

Update `PromptLabStore` so listing and resolving experiments reads only `experiments_root`. Keep `examples_root` in config for seeding, not for runtime fallback.

## Frontend Impact

No immediate UI change is required. The existing API will list experiments from `experiments/` after backend startup. This design makes a later `experiment.json` settings form safer because edits will target local runtime data only.

## Error Handling

- If `experiments_root` exists but is empty, seed it.
- If `experiments_root` exists and contains files but no `*/experiment.json`, treat it as empty for seeding purposes.
- If copying an example fails, backend startup should fail with a clear error rather than silently running with a partial workspace.
- If an example experiment id is unsafe or malformed, validation should fail when the seeded manifest is loaded, as it does today.

## Gitignore

Add `experiments/` to `.gitignore`. Keep `examples/` tracked.

## Tests

Backend tests should cover:

- missing `experiments/` seeds from `examples/`;
- empty `experiments/` seeds from `examples/`;
- existing experiment in `experiments/` prevents seeding;
- `PromptLabStore.list_experiments()` no longer lists `examples/` directly;
- run artifacts are written under `experiments/` after seeding.

Existing API tests that create only `examples/` fixtures should be updated to run through seeding or to create fixtures under `experiments/`.

## Non-Goals

- No manual reset/import-from-examples command.
- No automatic syncing of new examples into an existing workspace.
- No GUI settings form in this change; this design only prepares safe storage semantics for it.
