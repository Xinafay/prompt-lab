# Prompt Lab Examples

These examples are generated from Carmilla Story Parser eval fixtures and converted to a neutral Prompt Lab format.

Case files use `prompt_lab.case/v2`: serialized `stores` plus top-level
`bindings` that become the prompt/validation context. The committed prompts use
the `jinjax` template engine copied from Carmilla's portable `shared.jinjax`
package.

Examples:

- `split-scenes`: Pydantic structured output using `model.SceneList`.
- `summarize-chapter`: plain text output.

Each experiment chooses its tested generator model and its judge model in
`experiment.json`:

```json
{
  "models": {
    "generator_model": "local/qwen3-14b",
    "judge_model": "openai/gpt-5-mini"
  }
}
```

`generator_model` is the model being evaluated. `judge_model` is used for
judgment, proposal generation, and comparison. Both values use the
`<server>/<model>` format, where `<server>` must be configured in `.servers.jsonc`.

The running app does not write into `examples/`. At backend startup, examples are
copied into `experiments/` only when the runtime workspace is missing or has no
experiment manifests. Edit and run experiments from `experiments/`; update
`examples/` only when changing the golden starter templates.
