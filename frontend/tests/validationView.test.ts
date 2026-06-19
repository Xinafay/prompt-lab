import assert from "node:assert/strict";
import test from "node:test";

import { buildValidationInclusionUpdate } from "../src/components/validationInclusion.ts";
import type { ValidationState } from "../src/types.ts";

function validationState(): ValidationState {
  return {
    validation_batch: {
      schema_version: "prompt_lab.validation_batch/v1",
      validation_batch_id: "validation-001",
      run_batch_id: "run-001",
      version: "v001",
      status: "completed",
      started_at: "2026-06-19T00:00:00Z",
      finished_at: "2026-06-19T00:01:00Z",
      total_results: 1,
      completed_results: 1,
      validator_model: "openai/validator",
      validator_ids: ["quality"]
    },
    validators: [],
    results: [
      {
        schema_version: "prompt_lab.validation_result/v1",
        validation_result_id: "result-001",
        validation_batch_id: "validation-001",
        run_batch_id: "run-001",
        run_id: "run-001-case-a-repeat-001",
        case_id: "case-a",
        repeat_index: 1,
        validator_id: "quality",
        validator_type: "llm_questionnaire",
        status: "ok",
        included_in_judge: true,
        check_results: [
          {
            check_id: "coverage",
            verdict: "yes",
            comment: "Good.",
            included_in_judge: false,
            metrics: {}
          }
        ],
        usage: {}
      }
    ]
  };
}

test("buildValidationInclusionUpdate serializes result and check inclusion", () => {
  assert.deepEqual(buildValidationInclusionUpdate(validationState()), {
    results: [
      {
        validation_result_id: "result-001",
        included_in_judge: true,
        check_results: [
          {
            check_id: "coverage",
            included_in_judge: false
          }
        ]
      }
    ]
  });
});
