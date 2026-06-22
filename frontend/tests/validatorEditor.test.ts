import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import type { ValidatorDefinition } from "../src/types.ts";

const {
  createDefaultValidator,
  duplicateValidator,
  validateValidatorDraft,
  ValidatorEditor
} = await import("../src/components/ValidatorEditor.tsx");

test("createDefaultValidator creates editable llm validator", () => {
  const validator = createDefaultValidator("llm_questionnaire", ["quality"]);

  assert.equal(validator.validator_id, "validator-1");
  assert.equal(validator.type, "llm_questionnaire");
  assert.equal(validator.checks[0].check_id, "check-1");
});

test("duplicateValidator creates unique validator and check ids", () => {
  const original: ValidatorDefinition = {
    schema_version: "prompt_lab.validator/v1",
    validator_id: "quality",
    type: "automatic",
    title: "Quality",
    description: "",
    enabled: true,
    input_scope: "output_only",
    checks: [
      {
        check_id: "length",
        title: "Length",
        description: "",
        rule: {
          kind: "word_count",
          source: "output_text",
          comparison: { op: "gte", value: 1 }
        }
      }
    ]
  };

  const duplicate = duplicateValidator(original, ["quality"]);

  assert.equal(duplicate.validator_id, "quality-copy");
  assert.equal(duplicate.checks[0].check_id, "length-copy");
});

test("validateValidatorDraft rejects duplicate ids", () => {
  const validators = [
    createDefaultValidator("llm_questionnaire", []),
    createDefaultValidator("automatic", [])
  ];
  validators[1].validator_id = validators[0].validator_id;

  assert.deepEqual(validateValidatorDraft(validators), [
    "Validator id validator-1 is duplicated."
  ]);
});

test("ValidatorEditor renders llm and automatic controls", () => {
  const llm = createDefaultValidator("llm_questionnaire", []);
  const automatic = createDefaultValidator("automatic", []);

  const llmHtml = renderToStaticMarkup(
    React.createElement(ValidatorEditor, {
      existingValidatorIds: [llm.validator_id],
      onChange: () => undefined,
      validator: llm
    })
  );
  const automaticHtml = renderToStaticMarkup(
    React.createElement(ValidatorEditor, {
      existingValidatorIds: [automatic.validator_id],
      onChange: () => undefined,
      validator: automatic
    })
  );

  assert.match(llmHtml, /Question/);
  assert.match(llmHtml, /Input scope/);
  assert.match(automaticHtml, /Rule kind/);
  assert.match(automaticHtml, /Comparison/);
});
