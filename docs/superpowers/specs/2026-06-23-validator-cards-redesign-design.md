# Validator Cards Redesign Design

## Summary

Redesign the `Validators` tab from an always-visible structured editor into a
read-only overview of large validator cards. Each card should show the complete
validator configuration, including all checks, in a form that is understandable
without entering edit mode. Editing moves into a full-screen modal or drawer
opened from an `Edit` action.

This is a UX redesign over the validator editing functionality introduced in
`2026-06-22-validator-editing-design.md`. The source-of-truth data model remains
version-level validator JSON files.

## Goals

- Make the `Validators` tab answer: "What does this version validate?"
- Show each validator as one large, readable card.
- Show every check inside its validator card without requiring expansion.
- Keep checks read-only in the overview.
- Move add/edit workflows into a full-screen modal or drawer.
- Preserve the version-level save workflow:
  - `Reset`
  - `Overwrite current version`
  - `Save as next version`
- Keep the layout consistent with the existing Prompt Lab app shell and tab
  behavior.

## Non-Goals

- Do not change validator storage or backend API contracts.
- Do not add new validator types or automatic rule kinds.
- Do not allow inline check editing from overview cards.
- Do not introduce a separate route for validator editing.
- Do not redesign unrelated tabs.

## Overview Layout

The `Validators` tab should be an overview page, not an editor by default.

Top area:

- page title: `Validators`
- short helper text: `Review and edit validators stored with this version.`
- version-level actions aligned with the existing prompt/settings save pattern:
  - `Reset`
  - `Overwrite current version`
  - `Save as next version`

Main content:

- one-column list of large validator cards;
- cards are stacked vertically and can have different heights;
- the list should optimize for one to three validators, not dozens;
- no separate master-detail split is shown in the default state;
- no large empty "add" cards are shown.

Add action:

- a normal `Add validator` button appears above the card list;
- clicking it opens the same full-screen editor shell in create mode;
- the create flow lets the user choose or set the validator type.

Empty state:

- if the version has no validators, show a compact empty state with one
  `Add validator` action;
- keep the validation workflow behavior that rejects validation when no enabled
  validators exist.

## Validator Card

Each validator card should be a documentation-style summary of one validator.
It should avoid looking like a form.

Header content:

- validator title;
- status and type metadata:
  - type, for example `Automatic` or `LLM questionnaire`;
  - enabled state;
  - input scope in human-readable wording;
  - check count;
- actions:
  - primary `Edit`;
  - secondary actions for `Duplicate` and `Delete`.

Body content:

- validator description when present;
- check list containing all checks for the validator;
- optional low-emphasis technical metadata such as ids and rule kinds.

The card should make a validator understandable at a glance. Technical field
names can appear, but they should not be the primary language of the card.

## Check Presentation

Checks are read-only in the overview card.

Each check should be displayed as a compact block or row containing:

- check title;
- a human-readable rule sentence;
- optional description;
- subtle technical metadata.

Automatic rule examples:

```text
Summary present
Requires $.summary in output_json to exist.
summary-present - json_path_exists
```

```text
Three tags
Requires $.tags in output_json to contain exactly 3 items.
three-tags - json_path_count - eq 3
```

```text
Risk count
Requires $.risks in output_json to contain between 1 and 3 items.
risk-count - json_path_count - between 1..3
```

LLM questionnaire examples:

```text
Grounded summary
Asks whether the answer is grounded in the source material.
grounded-summary - llm_questionnaire
```

If a rule cannot be confidently rendered as a sentence, fall back to a compact
technical summary rather than showing editable controls.

## Editing Modal

Clicking `Edit` opens a full-screen modal or drawer on the same tab and URL.

The editor shell should contain:

- title such as `Edit validator: Report shape`;
- `Cancel` and `Save changes` actions;
- structured edit mode as the default;
- advanced `JSON` mode as an escape hatch;
- dirty-close handling when unsaved edits exist.

Create mode uses the same shell with a title such as `Add validator`.

The editor is allowed to show structured form controls, because the user has
explicitly entered edit mode. The default overview should not expose those
controls.

## Mutations And Dirty State

Local edits made inside the modal update the validators draft only after the
user saves the modal changes.

After modal save:

- the modal closes;
- the overview card list reflects the updated local draft;
- version-level actions become enabled when the draft differs from persisted
  version source.

Version-level persistence keeps the existing behavior:

- `Reset` discards the entire validators draft;
- `Save as next version` creates a new version, switches to it, refreshes data,
  and stays on `Validators`;
- `Overwrite current version` asks for explicit confirmation because it removes
  generated validation, review, proposal, and comparison artifacts for that
  version.

Leaving the `Validators` tab with a dirty validators draft should use the same
unsaved-change confirmation pattern as `Prompt` and `Settings`.

## Component Shape

The implementation should keep the overview and editor separated:

- `ValidatorsView` owns the page layout, version-level actions, card list, and
  modal state.
- `ValidatorCard` renders one read-only validator card.
- `ValidatorCheckSummary` renders one read-only check description.
- `ValidatorEditor` continues to own structured and JSON editing controls.

The read-only card components should accept normalized validator data and should
not mutate drafts directly.

## Visual Direction

Use restrained app-native styling:

- one vertical column of cards;
- cards with clear internal hierarchy and moderate padding;
- no nested card-in-card appearance for every field;
- no huge empty action boxes;
- metadata shown as small badges or subdued inline text;
- destructive actions visually secondary until invoked;
- stable button placement across cards.

The design should support long descriptions and multiple checks without layout
overlap. Cards may become tall, and that is acceptable because the expected
validator count is low.

## Accessibility And Responsive Behavior

- Card actions must be keyboard reachable.
- `Edit`, `Duplicate`, and `Delete` actions must have clear accessible names.
- The modal should trap focus while open and restore focus to the originating
  card action when closed.
- On narrow screens, cards remain one column and actions may wrap under the
  header metadata.
- Check sentences should wrap naturally without horizontal scrolling.

## Testing

Frontend unit/render tests:

- render validator overview cards for automatic validators;
- render all checks inside the card;
- render LLM questionnaire checks read-only;
- verify `Edit` opens the editor modal;
- verify modal save updates the local draft and closes the modal;
- verify overview check content is not editable;
- verify add flow opens create mode;
- verify version-level dirty actions enable after modal save.

Frontend e2e:

- use `demo-json`;
- verify the `Validators` tab shows large read-only cards;
- verify all checks for `Report shape` are visible without expanding;
- verify `Edit` opens the full-screen editor;
- verify closing with unsaved modal edits asks for confirmation;
- verify `Save as next version` still creates and switches to the new version.

Validation commands:

```bash
cd frontend && pnpm lint && pnpm test && pnpm build
cd frontend && pnpm test:e2e
```

## Risks

- Large cards can become too dense if every technical field is displayed with
  equal weight. Human-readable summaries should lead, with ids and rule kinds as
  secondary metadata.
- Full-screen modal editing creates two save layers: modal save into local draft,
  then version-level save. The UI must label this clearly enough that users
  understand whether they have saved the card draft or persisted the version.
- Rendering every check as prose requires careful rule formatting. Unknown or
  future rule shapes should degrade to a technical summary rather than failing
  the whole card.
