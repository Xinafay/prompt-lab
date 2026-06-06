# Prompt Lab Project Seed

Prompt Lab is a standalone local application for improving prompts through repeated model runs, qualitative LLM judgment, human review, proposal generation, and version comparison.

Carmilla is a separate local storytelling/workflow project. It is relevant here only as an external producer of neutral Prompt Lab experiment bundles and as the original reference for the bundled `shared.llm` model-routing layer. Prompt Lab should not import Carmilla workflow runtime or workflow state.

The design document is:

```text
DESIGN.md
```

Contents:

```text
prompt-lab/
  AGENTS.md
  DESIGN.md
  FORMAT.md
  IMPLEMENTATION_PLAN.md
  README.md
  TRANSFER.md
  backend/
    shared/llm/
    tests/
    requirements.txt
    requirements-dev.txt
  config/
  examples/
    split-scenes/
    summarize-chapter/
  .agents/skills/
  tools/
    export_carmilla_eval_examples.py
```

The examples use the same neutral bundle format that an external project such as Carmilla can export.

They intentionally use a neutral Prompt Lab format:

- no `WorkflowState`;
- no `workflow_runtime`;
- no Story Parser workflow imports;
- simple Jinja2 variables;
- optional local `model.py` for Pydantic output.

Optional source-adapter note: `tools/export_carmilla_eval_examples.py` is useful only when this code is placed inside a Carmilla checkout. Standalone Prompt Lab implementation does not depend on this helper.

```bash
./.venv/bin/python prompt_lab/tools/export_carmilla_eval_examples.py
```

In a standalone Prompt Lab repository, Carmilla-specific exporters should stay outside the Prompt Lab runtime or live as optional adapters.

For bootstrap/setup notes, read:

```text
TRANSFER.md
```

When starting implementation in the standalone repository, give the agent:

```text
IMPLEMENTATION_PLAN.md
```
