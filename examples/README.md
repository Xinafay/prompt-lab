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

- `split-scenes`: Pydantic structured output using `model.SceneList`.
- `summarize-chapter`: plain text output.

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
validation. `judge_model` is used for judgment, proposal generation, and
comparison. These values use the
`<server>/<model>` format, where `<server>` must be configured in `.servers.jsonc`.

The running app does not write into `examples/`. At backend startup, examples are
copied into `experiments/` only when the runtime workspace is missing or has no
experiment manifests. Edit and run experiments from `experiments/`; update
`examples/` only when changing the golden starter templates.
