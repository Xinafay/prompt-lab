from __future__ import annotations


def main() -> int:
    raise SystemExit(
        "Examples are generated from the Carmilla repo root.\n\n"
        "Example:\n"
        "cd /Users/karol/Projects/sinafai/carmilla\n"
        "PYTHONPATH=python ./.venv/bin/python -m "
        "python.workflow_runtime.eval_runner \\\n"
        "  --workflow story_parser \\\n"
        "  --test split-scenes \\\n"
        "  --export-prompt-lab "
        "/Users/karol/Projects/sinafai/prompt-lab/examples/split-scenes\n\n"
        "Replace --test and the output path for other examples, such as "
        "summarize-chapter."
    )


if __name__ == "__main__":
    raise SystemExit(main())
