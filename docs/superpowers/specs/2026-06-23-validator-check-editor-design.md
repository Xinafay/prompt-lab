# Validator Check Editor Design

## Goal

Make the structured validator editor readable and complete enough to maintain checks without switching to JSON.

## User Experience

The validator modal keeps the current structured/JSON split. In structured mode, the validator metadata remains at the top and the checks section becomes a vertical list of full-width check cards. Each card shows a compact header with the check title and its position, editable fields below, and a delete action. Check cards may have different heights and should scan like the read-only validator cards in the overview.

Select controls must show user-facing labels instead of raw enum values:

- `llm_questionnaire` -> `LLM questionnaire`
- `automatic` -> `Automatic`
- `output_prompt_and_case` -> `Output + prompt + case`
- automatic rule kind/source/comparison values use short human names.

Short help text under key selects explains what the selected value means. The hints are informational only and do not change the stored JSON values.

The checks section has an `Add check` action. It appends a valid default check for the current validator type. Each check has a `Delete` action. The last remaining check cannot be deleted from the structured UI, because validators require at least one check and silently creating an invalid state would make the modal feel broken.

## Data Model

No schema changes. Structured edits still emit a `ValidatorDefinition` with the same enum values and check objects as before. JSON mode remains available for direct editing.

## Implementation

Add small helper functions in `ValidatorEditor.tsx` for:

- human labels and hints for enum values,
- creating a default LLM or automatic check with a unique `check_id`,
- appending and removing checks.

Update CSS so `.validator-check-editor` is a full-width card, not a two-column grid item.

## Testing

Add component tests for:

- human labels/hints in rendered editor markup,
- add/delete helper behavior for LLM checks,
- add/delete helper behavior for automatic checks,
- last-check delete disabled in markup.

Keep existing validation tests unchanged. Run frontend unit tests, typecheck, build, and targeted browser QA in the validator modal.
