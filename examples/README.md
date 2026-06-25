# Prompt Lab Examples

These examples include complete neutral Prompt Lab experiments and reusable Case
Suites.

Case files are plain JSON context objects passed directly to prompt rendering
and validation. The committed prompts use the `jinjax` template engine copied
from Carmilla's portable `shared.jinjax` package.

Committed experiments live under `examples/experiments/`. Committed Case Suites
live under `examples/case_suites/`, and their `cases/` directories contain the
plain JSON payloads shared by experiments. Experiment manifests reference one
suite with `case_suite_id` and store per-experiment run inclusion in
`run_defaults.excluded_case_ids`. Version directories contain only
version-specific prompt/model files and generated runtime artifacts after
seeding into `experiments/`.

From the Carmilla repository root, regenerate an example with:

```bash
python -m python.workflow_runtime.eval_runner \
  --workflow story_parser \
  --test split-scenes \
  --export-prompt-lab /Users/karol/Projects/sinafai/prompt-lab/examples/experiments/split-scenes
```

The exporter reports created, existing, and skipped experiment files to stderr.
Case payload updates belong in the corresponding suite under
`examples/case_suites/`.

Examples:

- `experiments/demo-string`: plain text UI QA fixture with precomputed runs,
  validations, review, and proposal artifacts.
- `experiments/demo-json`: Pydantic structured-output UI QA fixture with precomputed runs,
  validations, review, and proposal artifacts.
- `experiments/split-scenes`: Pydantic structured output using `model.SceneList`.
- `experiments/summarize-chapter`: plain text output.
- `case_suites/demo-string-replies`: cases for the text demo.
- `case_suites/demo-json-briefs`: cases for the structured-output demo.
- `case_suites/story-chapters`: shared story-parser cases.

Use `demo-string` and `demo-json` for manual browser testing and UI regression
checks. They are intentionally small, deterministic, and include enough
committed runtime artifacts to exercise Prompt, Settings, Validators, Cases, Runs,
Validation, Review, Proposal, and Compare without spending real LLM tokens.
Each demo fixture keeps at least two cases and two repeats per case so UI tests
exercise the common case/repeat matrix instead of a single-output happy path.
`split-scenes` and `summarize-chapter` are realistic starter examples, not the
primary UI QA fixtures.

Each experiment chooses its tested generator model, validation model, and judge
model in `experiment.json`:

```json
{
  "models": {
    "generator_model": "local/qwen3-14b",
    "validator_model": "openai/gpt-5-mini",
    "judge_model": "openai/gpt-5-mini"
  }
}
```

`generator_model` is the model being evaluated. `validator_model` is used for
LLM questionnaire validation. `judge_model` is used for judgment and proposal
generation. Comparison uses deterministic validation results and does not call
an LLM. These values use the
`<server>/<model>` format, where `<server>` must be configured in `.servers.jsonc`.

Each example version can include a `versions/<version>/validators/` directory.
Validator definition files use `prompt_lab.validator/v1` and are seeded into
runtime experiments with the rest of the starter template. LLM questionnaire
validators assign `grade: 1..5 | null` to explicit checks over configured input
scope. Automatic validators run local rules such as word counts or JSON-path
counts and currently map binary rule outcomes to grade `5` or `1`.

The running app does not write into `examples/`. At backend startup, example
experiments and example Case Suites are independently copied into the runtime
`experiments/` and `case_suites/` roots when those workspaces are missing. Edit
and run from the runtime roots; update `examples/` only when changing the golden
starter templates.

Examples that contain committed runtime artifacts under version directories
(`runs/`, `validations/`, `reviews/`, or `comparisons/`) are copied exactly so
their saved artifacts stay consistent with their manifest. Global default models
and repeat count are applied only to starter examples without committed runtime
artifacts.

Existing runtime experiments and Case Suites are not migrated when committed
examples change. Delete or move `experiments/` and/or `case_suites/` only when
you intentionally want to reseed from the current examples.
