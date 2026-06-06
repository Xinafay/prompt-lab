# Prompt Lab Backend Seed

This backend seed contains the LLM layer copied from Carmilla:

```text
backend/shared/llm/
```

The copied module keeps its original import path, `shared.llm`, so commands should run with `PYTHONPATH=backend` from the future Prompt Lab repository root:

```bash
PYTHONPATH=backend python backend/tests/test_chat.py
PYTHONPATH=backend python backend/tests/test_chat_get_structured_lite.py
PYTHONPATH=backend python backend/tests/test_structured_lite_units.py
PYTHONPATH=backend python backend/tests/test_format_validation_errors.py
```

Live smoke testing uses configured real models and is intentionally separate from the local tests:

```bash
PYTHONPATH=backend python backend/tests/test_chat_env.py
```

Required local config:

```text
.servers.jsonc
.env
```

Start from the templates under `config/`.

The LLM cache should remain disabled for Prompt Lab generator runs. Repeated prompt tests need uncached model calls to expose output variance.
