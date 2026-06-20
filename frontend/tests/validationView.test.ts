import assert from "node:assert/strict";
import test from "node:test";

import {
  buildValidationMatrix,
  setValidationInclusion
} from "../src/components/validationMatrix.ts";
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
      total_results: 2,
      completed_results: 2,
      validator_model: "openai/validator",
      validator_ids: ["quality"]
    },
    validators: [
      {
        schema_version: "prompt_lab.validator/v1",
        validator_id: "quality",
        type: "llm_questionnaire",
        title: "Quality",
        description: "Checks answer quality.",
        enabled: true,
        input_scope: "output_only",
        checks: [
          {
            check_id: "coverage",
            title: "Coverage",
            question: "Does it answer the case?",
            description: "Answer should cover the request."
          }
        ]
      }
    ],
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

test("buildValidationMatrix groups checks by validator rows and case-repeat columns", () => {
  const matrix = buildValidationMatrix({
    ...validationState(),
    results: [
      ...validationState().results,
      {
        ...validationState().results[0],
        validation_result_id: "result-002",
        run_id: "run-001-case-a-repeat-002",
        repeat_index: 2,
        check_results: [
          {
            check_id: "coverage",
            verdict: "no",
            comment: "Missing.",
            included_in_judge: true,
            metrics: {}
          }
        ]
      }
    ]
  });

  assert.deepEqual(
    matrix.columns.map((column) => column.title),
    ["case-a · r1", "case-a · r2"]
  );
  assert.equal(matrix.rows.length, 1);
  assert.equal(matrix.rows[0].validator_title, "Quality");
  assert.equal(matrix.rows[0].check_title, "Coverage");
  assert.deepEqual(
    matrix.rows[0].cells.map((cell) => cell.verdict),
    ["yes", "no"]
  );
});

test("buildValidationMatrix shows skipped validation results as non-includable cells", () => {
  const matrix = buildValidationMatrix({
    ...validationState(),
    results: [
      {
        ...validationState().results[0],
        status: "skipped",
        included_in_judge: false,
        check_results: [],
        execution_error: "Generator execution_error; validator skipped."
      }
    ]
  });

  const cell = matrix.rows[0].cells[0];

  assert.equal(cell.verdict, "skipped");
  assert.equal(cell.status, "skipped");
  assert.equal(cell.result_included_in_judge, false);
  assert.equal(cell.check_included_in_judge, false);
  assert.equal(cell.included_in_judge, false);
  assert.equal(cell.check, null);
  assert.equal(cell.comment, "Generator execution_error; validator skipped.");
});

test("setValidationInclusion toggles a whole check row", () => {
  const updated = setValidationInclusion(
    {
      ...validationState(),
      results: [
        ...validationState().results,
        {
          ...validationState().results[0],
          validation_result_id: "result-002",
          run_id: "run-001-case-a-repeat-002",
          repeat_index: 2,
          check_results: [
            {
              check_id: "coverage",
              verdict: "no",
              comment: "Missing.",
              included_in_judge: true,
              metrics: {}
            }
          ]
        }
      ]
    },
    { kind: "row", rowKey: "quality\u0000coverage" },
    false
  );

  assert.deepEqual(
    updated.results.map((result) => result.check_results[0].included_in_judge),
    [false, false]
  );
});

test("setValidationInclusion toggles a whole output column", () => {
  const updated = setValidationInclusion(
    {
      ...validationState(),
      results: [
        ...validationState().results,
        {
          ...validationState().results[0],
          validation_result_id: "result-002",
          run_id: "run-001-case-a-repeat-002",
          repeat_index: 2,
          check_results: [
            {
              check_id: "coverage",
              verdict: "no",
              comment: "Missing.",
              included_in_judge: true,
              metrics: {}
            }
          ]
        }
      ]
    },
    { kind: "column", columnKey: "case-a\u00002" },
    false
  );

  assert.deepEqual(
    updated.results.map((result) => ({
      result: result.included_in_judge,
      check: result.check_results[0].included_in_judge,
      verdict: result.check_results[0].verdict
    })),
    [
      { result: true, check: false, verdict: "yes" },
      { result: false, check: false, verdict: "no" }
    ]
  );
});

test("setValidationInclusion re-includes the result when a single cell is enabled", () => {
  const updated = setValidationInclusion(
    {
      ...validationState(),
      results: [
        {
          ...validationState().results[0],
          included_in_judge: false,
          check_results: [
            {
              ...validationState().results[0].check_results[0],
              included_in_judge: false
            }
          ]
        }
      ]
    },
    {
      kind: "cell",
      rowKey: "quality\u0000coverage",
      columnKey: "case-a\u00001"
    },
    true
  );

  assert.equal(updated.results[0].included_in_judge, true);
  assert.equal(updated.results[0].check_results[0].included_in_judge, true);
  assert.equal(updated.results[0].check_results[0].verdict, "yes");
});
