from __future__ import annotations

import json

from prompt_lab.models.artifacts import CaseArtifact, RunArtifact
from prompt_lab.models.judgments import JudgmentArtifact


def _json_block(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def build_judge_prompt(
    *,
    experiment_id: str,
    version: str,
    output_declaration: str,
    rubric: str,
    prompt_template: str,
    cases: list[CaseArtifact],
    run_artifacts: list[RunArtifact],
) -> str:
    case_lines = [
        f"Case {case.id}: {case.title}\nVariables:\n{_json_block(case.variables)}"
        for case in cases
    ]
    run_lines = []
    for run in sorted(run_artifacts, key=lambda item: (item.case_id, item.repeat_index)):
        run_lines.append(
            "\n".join(
                [
                    f"Case/repeat: {run.case_id} repeat {run.repeat_index}",
                    f"Run id: {run.run_id}",
                    f"Run batch: {run.run_batch_id}",
                    f"Status: {run.status}",
                    f"Raw output: {run.raw_output}",
                    f"Output JSON: {_json_block(run.output_json)}",
                    f"Output text: {run.output_text}",
                    f"Validation error: {run.validation_error}",
                    f"Execution error: {run.execution_error}",
                ]
            )
        )

    schema = _json_block(JudgmentArtifact.model_json_schema())
    return "\n\n".join(
        [
            "You are judging one Prompt Lab experiment version.",
            "Operational rules:",
            "- distinguish recurring problems from one-off deviations before recommending prompt changes.",
            "- cite case/repeat evidence for every positive observation and every finding.",
            "- produce JSON matching JudgmentArtifact exactly.",
            "- avoid numeric scorecards as primary output; use qualitative findings and evidence.",
            "- Treat validation errors, parse failures, and execution errors as normal run evidence.",
            f"Experiment id: {experiment_id}",
            f"Version: {version}",
            f"Output declaration:\n{output_declaration}",
            f"Rubric snapshot:\n{rubric}",
            f"Prompt template:\n{prompt_template}",
            "Cases:\n" + "\n\n".join(case_lines),
            "Run artifacts:\n" + "\n\n".join(run_lines),
            f"JudgmentArtifact JSON schema:\n{schema}",
        ]
    )
