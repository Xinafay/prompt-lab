# Prompt Lab Examples

These examples are generated from Carmilla Story Parser eval fixtures and
exported as complete neutral Prompt Lab experiments.

Case files use `prompt_lab.case/v2`: serialized `stores` plus top-level
`bindings` that become the prompt/validation context. The committed prompts use
the `jinjax` template engine copied from Carmilla's portable `shared.jinjax`
package.

Each example keeps workflow state cases in the experiment-level `cases/`
directory. Version directories contain only version-specific prompt/model files
and generated runtime artifacts after seeding into `experiments/`; cases are
shared by all versions of an experiment.

From the Carmilla repository root, regenerate an example with:

```bash
python -m python.workflow_runtime.eval_runner \
  --workflow story_parser \
  --test split-scenes \
  --export-prompt-lab /Users/karol/Projects/sinafai/prompt-lab/examples/split-scenes
```

The exporter reports created, existing, and skipped files to stderr.

Examples:

- `demo-string`: plain text UI QA fixture with precomputed runs,
  validations, review, and proposal artifacts.
- `demo-json`: Pydantic structured-output UI QA fixture with precomputed runs,
  validations, review, and proposal artifacts.
- `split-scenes`: Pydantic structured output using `model.SceneList`.
- `summarize-chapter`: plain text output.

Use `demo-string` and `demo-json` for manual browser testing and UI regression
checks. They are intentionally small, deterministic, and include enough
committed runtime artifacts to exercise Overview, Settings, Cases, Runs,
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

Each example can include a top-level `validators/` directory. Validator
definition files use `prompt_lab.validator/v1` and are seeded into runtime
experiments with the rest of the starter template. LLM questionnaire validators
ask explicit yes/no/unknown checks over configured input scope. Automatic
validators run local rules such as word counts or JSON-path counts.

The running app does not write into `examples/`. At backend startup, examples are
copied into `experiments/` only when the runtime workspace is missing or has no
experiment manifests. Edit and run experiments from `experiments/`; update
`examples/` only when changing the golden starter templates.

Examples that contain committed runtime artifacts under version directories
(`runs/`, `validations/`, `reviews/`, or `comparisons/`) are copied exactly so
their saved artifacts stay consistent with their manifest. Global default models
and repeat count are applied only to starter examples without committed runtime
artifacts.

Existing runtime experiments are not migrated when committed examples change.
Delete or move `experiments/` only when you intentionally want to reseed from the
current examples.
