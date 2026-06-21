---
name: "prompt-lab-experiment-review"
description: "Use when running or reviewing Prompt Lab experiments, repeated prompt outputs, judge reports, comparisons, human decisions, or proposal quality."
---

# Prompt Lab Experiment Review

Use this skill to evaluate whether a prompt/model version improved and what should change next.

## Run Defaults

- Use 3 uncached repeats by default.
- Keep generator LLM cache disabled.
- Run case-major: `A-A-A-B-B-B`, not `A-B-A-B-A-B`.
- Validation/parse failures are run results, not suite failures.

## Review Checklist

For each experiment version, inspect:

- status per case/repeat;
- raw output and parsed JSON/text;
- validation errors;
- recurring semantic problems;
- one-off deviations;
- omitted important content;
- hallucinated content;
- category/field boundary errors;
- whether results support downstream processing.

## Reporting

Include explicit sections:

- What looks correct.
- What looks questionable.
- Suggested changes marked `recommended`, `optional`, or `do not change yet`.
- User decision points.

When comparing versions, also include:

- improvements;
- regressions;
- unchanged problems;
- new problems;
- stability changes;
- recommendation: `keep_new_version`, `revise_new_version`, `revert_to_baseline`, or `inconclusive`.

Accepted judge findings feed proposal generation. Rejected findings become constraints. Deferred findings are ignored unless human notes mention them. Human notes override judge findings.

In the UI, validation inclusion edits and review edits are saved from the sticky
workflow toolbar. Before judging or generating proposals, resolve dirty state
with `Save`, `Discard changes`, or `Stay`; proposal generation uses only saved
review decisions and human notes.
