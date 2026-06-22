import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import type { ValidatorDefinition } from "../src/types.ts";

const {
  convertValidatorType,
  createDefaultValidator,
  duplicateValidator,
  normalizeAutomaticRule,
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

test("convertValidatorType preserves base fields and check labels", () => {
  const questionnaire: ValidatorDefinition = {
    schema_version: "prompt_lab.validator/v1",
    validator_id: "quality",
    type: "llm_questionnaire",
    title: "Quality",
    description: "Checks answer quality.",
    enabled: false,
    input_scope: "output_prompt_and_case",
    checks: [
      {
        check_id: "direct",
        title: "Direct answer",
        question: "Does it answer directly?",
        description: "Avoids evasive answers."
      }
    ]
  };

  const automatic = convertValidatorType(questionnaire, "automatic");

  assert.equal(automatic.validator_id, "quality");
  assert.equal(automatic.title, "Quality");
  assert.equal(automatic.description, "Checks answer quality.");
  assert.equal(automatic.enabled, false);
  assert.equal(automatic.input_scope, "output_prompt_and_case");
  assert.equal(automatic.type, "automatic");
  assert.equal(automatic.checks[0].check_id, "direct");
  assert.equal(automatic.checks[0].title, "Direct answer");
  assert.equal(automatic.checks[0].description, "Avoids evasive answers.");
  assert.deepEqual(automatic.checks[0].rule, {
    kind: "word_count",
    source: "output_text",
    comparison: { op: "gte", value: 1 }
  });

  const backToQuestionnaire = convertValidatorType(automatic, "llm_questionnaire");

  assert.equal(backToQuestionnaire.validator_id, "quality");
  assert.equal(backToQuestionnaire.type, "llm_questionnaire");
  assert.equal(backToQuestionnaire.checks[0].check_id, "direct");
  assert.equal(backToQuestionnaire.checks[0].title, "Direct answer");
  assert.equal(backToQuestionnaire.checks[0].description, "Avoids evasive answers.");
  assert.equal(
    backToQuestionnaire.checks[0].question,
    "Does the output satisfy this check?"
  );
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

test("validateValidatorDraft rejects backend-invalid automatic rules", () => {
  const wrongSource = createDefaultValidator("automatic", []);
  wrongSource.validator_id = "wrong-source";
  if (wrongSource.type !== "automatic") throw new Error("Expected automatic");
  wrongSource.checks[0].rule = {
    kind: "json_path_count",
    source: "output_text",
    path: "$.items",
    comparison: { op: "gte", value: 1 }
  };

  const blankPath = createDefaultValidator("automatic", []);
  blankPath.validator_id = "blank-path";
  if (blankPath.type !== "automatic") throw new Error("Expected automatic");
  blankPath.checks[0].rule = {
    kind: "json_path_exists",
    source: "output_json",
    path: "   "
  };

  assert.deepEqual(validateValidatorDraft([wrongSource, blankPath]), [
    "Rule for check check-1 in wrong-source must use output_json for json_path_count.",
    "Rule for check check-1 in blank-path needs a JSON path."
  ]);
});

test("validateValidatorDraft rejects missing and non-finite comparison values", () => {
  const missingValue = createDefaultValidator("automatic", []);
  missingValue.validator_id = "missing-value";
  if (missingValue.type !== "automatic") throw new Error("Expected automatic");
  missingValue.checks[0].rule = {
    kind: "word_count",
    source: "output_text",
    comparison: { op: "gte", value: null }
  };

  const nonFiniteValue = createDefaultValidator("automatic", []);
  nonFiniteValue.validator_id = "non-finite-value";
  if (nonFiniteValue.type !== "automatic") throw new Error("Expected automatic");
  nonFiniteValue.checks[0].rule = {
    kind: "sentence_count",
    source: "output_text",
    comparison: { op: "lte", value: Number.NaN }
  };

  const missingBetween = createDefaultValidator("automatic", []);
  missingBetween.validator_id = "missing-between";
  if (missingBetween.type !== "automatic") throw new Error("Expected automatic");
  missingBetween.checks[0].rule = {
    kind: "character_count",
    source: "output_text",
    comparison: { op: "between", min_value: 2, max_value: null }
  };

  assert.deepEqual(validateValidatorDraft([missingValue, nonFiniteValue, missingBetween]), [
    "Comparison for check check-1 in missing-value needs a value.",
    "Comparison for check check-1 in non-finite-value needs a finite value.",
    "Comparison for check check-1 in missing-between needs minimum and maximum values."
  ]);
});

test("normalizeAutomaticRule keeps rule shape compatible with backend", () => {
  assert.deepEqual(
    normalizeAutomaticRule({
      kind: "json_path_exists",
      source: "output_text",
      path: "$.items",
      comparison: { op: "gte", value: 2 }
    }),
    {
      kind: "json_path_exists",
      source: "output_json",
      path: "$.items"
    }
  );

  assert.deepEqual(
    normalizeAutomaticRule({
      kind: "word_count",
      source: "output_json",
      path: "$.items",
      comparison: { op: "gte", value: 2 }
    }),
    {
      kind: "word_count",
      source: "output_json",
      comparison: { op: "gte", value: 2 }
    }
  );
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

const {
  getValidatorEditorActionState,
  parseValidatorJsonDraft,
  shouldEmitValidatorsDraft,
  ValidatorsView
} = await import("../src/components/ValidatorsView.tsx");

test("ValidatorsView renders add duplicate delete and save actions", () => {
  const validator = createDefaultValidator("llm_questionnaire", []);
  const html = renderToStaticMarkup(
    React.createElement(ValidatorsView, {
      isBusy: false,
      message: null,
      onDraftChange: () => undefined,
      onOverwriteCurrent: () => undefined,
      onReset: () => undefined,
      onSaveAsNext: () => undefined,
      validators: [validator]
    })
  );

  assert.match(html, /Add validator/);
  assert.match(html, /Duplicate/);
  assert.match(html, /Delete/);
  assert.match(html, /Overwrite current version/);
  assert.match(html, /Save as next version/);
});

test("shouldEmitValidatorsDraft ignores semantically identical payloads", () => {
  const validator = createDefaultValidator("llm_questionnaire", []);
  const dirtyPayload = { validators: [validator] };
  const first = shouldEmitValidatorsDraft(undefined, dirtyPayload);

  assert.equal(first.shouldEmit, true);

  const repeatedDirty = shouldEmitValidatorsDraft(first.serialized, {
    validators: [JSON.parse(JSON.stringify(validator)) as ValidatorDefinition]
  });
  assert.equal(repeatedDirty.shouldEmit, false);

  const firstClean = shouldEmitValidatorsDraft(undefined, null);
  assert.equal(firstClean.shouldEmit, true);
  assert.equal(shouldEmitValidatorsDraft(firstClean.serialized, null).shouldEmit, false);
});

test("parseValidatorJsonDraft rejects valid JSON with invalid validator shape", () => {
  const result = parseValidatorJsonDraft("{}");

  assert.equal(result.ok, false);
  assert.match(result.error, /schema_version/);
});

test("parseValidatorJsonDraft rejects semantically invalid validator JSON", () => {
  const validator = createDefaultValidator("automatic", []);
  validator.title = "";

  const result = parseValidatorJsonDraft(JSON.stringify(validator));

  assert.equal(result.ok, false);
  assert.match(result.error, /title is required/);
});

test("parseValidatorJsonDraft accepts a complete validator", () => {
  const validator = createDefaultValidator("llm_questionnaire", []);
  const result = parseValidatorJsonDraft(JSON.stringify(validator));

  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.validator.validator_id, validator.validator_id);
});

test("validator editor action state blocks unsafe controls while JSON is invalid", () => {
  const state = getValidatorEditorActionState({
    isBusy: false,
    isDirty: false,
    jsonError: "Expected property name",
    validationErrorCount: 0
  });

  assert.equal(state.jsonUnsafeActionsDisabled, true);
  assert.equal(state.saveDisabled, true);
  assert.equal(state.resetDisabled, false);
});
