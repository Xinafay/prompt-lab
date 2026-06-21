# Validator Grade Contract Design

Date: 2026-06-20

Status: implemented

## Context

Prompt Lab validation checks originally returned `verdict: yes | no | unknown`.
That contract was simple, but it hid useful quality gradients. Many LLM
validators need to say that an output is excellent, good, acceptable, weak, or
bad rather than only whether it passed. The judge can use that gradient to
separate hard failures from weaker areas worth improving.

This design supersedes the check-level verdict portion of
`2026-06-19-validator-pipeline-design.md`. It is a breaking artifact-format
change. Runtime experiment migration is not required.

## Goals

- Replace check-level `verdict` with one global grade scale.
- Keep validator questionnaires simple; do not require per-check scale authoring.
- Preserve a way to represent "not assessable" without forcing false precision.
- Let judge and compare interpret grades consistently.
- Keep binary automatic validators working with a deterministic mapping.

## Non-Goals

- Per-check custom grading scales.
- Weighted scoring or an overall numeric experiment score.
- Migrating old runtime validation artifacts.
- Making automatic validators non-binary in this change.

## Check Result Contract

Each validation check result records:

- `check_id`
- `grade`: `1`, `2`, `3`, `4`, `5`, or `null`
- `comment`
- `metrics`
- `included_in_judge`

`verdict` is removed.

Grade meanings are global:

- `5`: very good; satisfies the check with no meaningful issue.
- `4`: good; satisfies the check, with minor improvement opportunities.
- `3`: acceptable but visibly improvable; partial satisfaction.
- `2`: weak; mostly fails the check, but contains some useful evidence.
- `1`: bad; fails the check.
- `null`: not assessable from the provided evidence.

`grade: null` replaces the old `unknown` concept. It must not mean "middle
quality". It means the validator lacks enough evidence to grade the check.
The `comment` must explain why the check is not assessable.

## LLM Questionnaire Response

The structured response model for LLM validators should ask for:

- one result per check id
- `grade`
- `comment`

The response model should not ask for `verdict`, pass/fail status, threshold
decisions, or prompt-improvement advice. The validator's job is to grade the
provided output for each check. Prompt/model change synthesis stays with judge
and proposal generation.

The validator prompt must define the global scale directly near the response
schema. It should make these rules explicit:

- Use `5` for very good, `4` for good, `3` for acceptable but improvable, `2`
  for weak, and `1` for bad.
- Use `null` only when the provided evidence is insufficient or ambiguous.
- Do not use `3` as a substitute for "unknown".
- Do not infer missing context beyond the provided validation input.

## Automatic Validators

Existing automatic validators remain binary in the first implementation:

- passing rule -> `grade: 5`
- failing rule -> `grade: 1`

They continue to store raw measurements in `metrics`, for example
`{"value": 742}`.

They should also write a short measurement comment so UI and judge evidence are
useful without decoding metrics, for example `Word count 742.` or
`JSON path count scenes 12.`.

Future automatic validators can map distance from an ideal value onto `1..5`
without changing the artifact contract. For example, an ideal-length validator
could grade by deviation from a target length while still storing the measured
length and target in `metrics`.

Unavailable automatic-validator sources remain validation-result errors, not
`grade: null`, because they indicate the configured rule could not run.

## Judge Interpretation

Judge receives included check results with grades and comments.

Default interpretation:

- `4` and `5`: positive evidence.
- `3`: partial evidence and an improvement signal.
- `1` and `2`: negative evidence.
- `null`: unknown or missing evidence.

Judge should not treat the grade threshold as part of the validator's response.
The validator grades like a teacher; Prompt Lab and judge decide how to interpret
those grades for pass/fail, comparison, and proposals.

## Compare Interpretation

Comparison remains deterministic and does not call an LLM.

Compare cells should aggregate included validation evidence by grade:

- `grade_5`
- `grade_4`
- `grade_3`
- `grade_2`
- `grade_1`
- `not_assessable`
- `missing`
- `error`
- `total`

Initial cell status rules:

- `pass`: all included graded results are `4` or `5`.
- `fail`: at least one included graded result is `1` or `2`.
- `mixed`: at least one included graded result is `3`, any `null`, or any error,
  and no `1` or `2`.
- `empty`: no included data.

The UI can show compact summaries such as `5: 7, 4: 2, 3: 1` and expand to
case/repeat details with grade and comment.

## UI Interpretation

The validation matrix should display grades instead of verdict pills.

Suggested visual treatment:

- `5`: strong positive
- `4`: positive
- `3`: mixed/improvable
- `2`: weak negative
- `1`: negative
- `null`: neutral/unknown

Inclusion behavior stays unchanged:

```text
validation_result.included_in_judge && check_result.included_in_judge
```

Skipped validation results remain non-includable and have no check results.

## Testing

Backend tests should cover:

- `ValidationCheckResult` accepts `grade` values `1..5` and `null`.
- `ValidationCheckResult` rejects values outside `1..5`.
- LLM validator fake responses validate `grade` and no longer accept `verdict`.
- LLM validator prompt contains the global grade scale.
- Automatic validators map pass to `5` and fail to `1`.
- Judge evidence contains grades.
- Compare aggregates grade counts and statuses.

Frontend tests should cover:

- validation matrix cells render grades and `null`.
- inclusion updates remain unchanged.
- compare summaries use grade counts.

## Rollout Notes

This is a breaking change for validation artifacts. Existing runtime artifacts
with `verdict` do not need migration. Example/demo artifacts should be updated
with the implementation so tests and manual UI checks exercise the new contract.
