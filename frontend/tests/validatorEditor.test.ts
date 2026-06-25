import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import type { ValidatorDefinition } from "../src/types.ts";

const {
  addValidatorCheck,
  convertValidatorType,
  createDefaultValidator,
  duplicateValidator,
  normalizeAutomaticRule,
  removeValidatorCheck,
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

test("addValidatorCheck appends default llm checks with unique ids", () => {
  const validator = createDefaultValidator("llm_questionnaire", []);
  validator.checks[0].check_id = "check-1";

  const next = addValidatorCheck(validator);

  assert.equal(next.type, "llm_questionnaire");
  assert.equal(next.checks.length, 2);
  assert.equal(next.checks[1].check_id, "check-2");
  assert.equal(next.checks[1].title, "New check");
  assert.equal(next.checks[1].question, "Does the output satisfy this check?");
});

test("addValidatorCheck appends default automatic checks with unique ids", () => {
  const validator = createDefaultValidator("automatic", []);
  validator.checks[0].check_id = "check-1";

  const next = addValidatorCheck(validator);

  assert.equal(next.type, "automatic");
  assert.equal(next.checks.length, 2);
  assert.equal(next.checks[1].check_id, "check-2");
  assert.equal(next.checks[1].title, "New check");
  assert.deepEqual(next.checks[1].rule, {
    kind: "word_count",
    source: "output_text",
    comparison: { op: "gte", value: 1 }
  });
});

test("removeValidatorCheck removes selected check but keeps the last one", () => {
  const validator = addValidatorCheck(createDefaultValidator("llm_questionnaire", []));
  validator.checks[0].check_id = "first";
  validator.checks[1].check_id = "second";

  const removed = removeValidatorCheck(validator, 0);
  const unchanged = removeValidatorCheck(removed, 0);

  assert.deepEqual(
    removed.checks.map((check) => check.check_id),
    ["second"]
  );
  assert.deepEqual(unchanged.checks, removed.checks);
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

test("ValidatorEditor renders friendly labels and select hints", () => {
  const llm = createDefaultValidator("llm_questionnaire", []);
  llm.input_scope = "output_prompt_and_case";
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

  assert.match(llmHtml, />LLM questionnaire</);
  assert.match(llmHtml, />Output \+ prompt \+ case</);
  assert.match(llmHtml, /Uses the validator model to answer check questions/);
  assert.match(llmHtml, /Generator output, rendered prompt, and case data/);
  assert.doesNotMatch(llmHtml, />llm_questionnaire</);
  assert.doesNotMatch(llmHtml, />output_prompt_and_case</);
  assert.match(automaticHtml, />Automatic</);
  assert.match(automaticHtml, />Word count</);
  assert.match(automaticHtml, />Output text</);
  assert.match(automaticHtml, />At least</);
});

test("ValidatorEditor renders add and delete check controls", () => {
  const validator = addValidatorCheck(createDefaultValidator("llm_questionnaire", []));

  const html = renderToStaticMarkup(
    React.createElement(ValidatorEditor, {
      existingValidatorIds: [validator.validator_id],
      onChange: () => undefined,
      validator
    })
  );

  assert.match(html, /Add check/);
  assert.match(html, /Delete check 1/);
  assert.match(html, /Delete check 2/);
  assert.doesNotMatch(html, /Delete check 1" disabled=""/);
});

test("ValidatorEditor disables delete for the last remaining check", () => {
  const validator = createDefaultValidator("automatic", []);

  const html = renderToStaticMarkup(
    React.createElement(ValidatorEditor, {
      existingValidatorIds: [validator.validator_id],
      onChange: () => undefined,
      validator
    })
  );

  assert.match(
    html,
    /<button(?=[^>]*aria-label="Delete check 1")(?=[^>]*disabled="")[^>]*>Delete<\/button>/
  );
});

const {
  describeAutomaticRule,
  ValidatorCard,
  inputScopeLabel,
  validatorTypeLabel
} = await import("../src/components/ValidatorCard.tsx");

const { ValidatorsPreview } = await import("../src/components/ValidatorsPreview.tsx");

test("validator card renders automatic checks as read-only prose", () => {
  const validator: ValidatorDefinition = {
    schema_version: "prompt_lab.validator/v1",
    validator_id: "report-shape",
    type: "automatic",
    title: "Report shape",
    description: "Local JSON checks that exercise automatic validators.",
    enabled: true,
    input_scope: "output_only",
    checks: [
      {
        check_id: "summary-present",
        title: "Summary present",
        description: "The structured output must include a summary field.",
        rule: {
          kind: "json_path_exists",
          source: "output_json",
          path: "$.summary"
        }
      },
      {
        check_id: "three-tags",
        title: "Three tags",
        description: "The tags list should contain exactly three items.",
        rule: {
          kind: "json_path_count",
          source: "output_json",
          path: "$.tags",
          comparison: { op: "eq", value: 3 }
        }
      }
    ]
  };

  const html = renderToStaticMarkup(
    React.createElement(ValidatorCard, {
      showActions: true,
      disabled: false,
      onDelete: () => undefined,
      onDuplicate: () => undefined,
      onEdit: () => undefined,
      validator
    })
  );

  assert.match(html, /Report shape/);
  assert.match(html, /Automatic/);
  assert.match(html, /Enabled/);
  assert.match(html, /Output only/);
  assert.match(html, /2 checks/);
  assert.match(html, /Requires \$\.summary in output_json to exist\./);
  assert.match(html, /Requires \$\.tags in output_json to contain exactly 3 items\./);
  assert.match(html, /summary-present - json_path_exists/);
  assert.match(html, /three-tags - json_path_count - eq 3/);
  assert.doesNotMatch(html, /<input|<select|<textarea/);
});

test("validator card renders llm questionnaire checks read-only", () => {
  const validator = createDefaultValidator("llm_questionnaire", []);
  if (validator.type !== "llm_questionnaire") throw new Error("Expected llm validator");
  validator.validator_id = "report-quality";
  validator.title = "Report quality";
  validator.checks[0] = {
    check_id: "grounded-summary",
    title: "Grounded summary",
    description: "Checks whether the summary is grounded.",
    question: "Is the summary grounded in the source material?"
  };

  const html = renderToStaticMarkup(
    React.createElement(ValidatorCard, {
      showActions: true,
      disabled: false,
      onDelete: () => undefined,
      onDuplicate: () => undefined,
      onEdit: () => undefined,
      validator
    })
  );

  assert.match(html, /LLM questionnaire/);
  assert.match(html, /Asks: Is the summary grounded in the source material\?/);
  assert.match(html, /grounded-summary - llm_questionnaire/);
  assert.doesNotMatch(html, /<input|<select|<textarea/);
});

test("bare ValidatorCard renders without action buttons", () => {
  const validator: ValidatorDefinition = {
    schema_version: "prompt_lab.validator/v1",
    validator_id: "bare-card",
    type: "automatic",
    title: "Bare card",
    description: "",
    enabled: true,
    input_scope: "output_only",
    checks: [
      {
        check_id: "summary-present",
        title: "Summary present",
        description: "Summary should exist in output_json.",
        rule: {
          kind: "json_path_exists",
          source: "output_json",
          path: "$.summary"
        }
      }
    ]
  };

  const html = renderToStaticMarkup(
    React.createElement(ValidatorCard, {
      validator
    })
  );

  assert.match(html, /Bare card/);
  assert.match(html, /summary-present - json_path_exists/);
  assert.doesNotMatch(html, /<button/);
  assert.doesNotMatch(html, />\s*Edit\s*</);
  assert.doesNotMatch(html, />\s*Duplicate\s*</);
  assert.doesNotMatch(html, />\s*Delete\s*</);
});

test("validator card formatting helpers use human-readable labels", () => {
  assert.equal(validatorTypeLabel("automatic"), "Automatic");
  assert.equal(validatorTypeLabel("llm_questionnaire"), "LLM questionnaire");
  assert.equal(inputScopeLabel("output_prompt_and_case"), "Output + prompt + case");
  assert.equal(
    describeAutomaticRule({
      kind: "word_count",
      source: "output_text",
      comparison: { op: "gte", value: 10 }
    }),
    "Requires output_text word count to be at least 10."
  );
  assert.equal(
    describeAutomaticRule({
      kind: "word_count",
      source: "output_text",
      comparison: { op: "gte", value: NaN }
    }),
    "Requires output_text word count to satisfy the configured comparison."
  );
  assert.equal(
    describeAutomaticRule({
      kind: "json_path_count",
      source: "output_json",
      path: "$.tags",
      comparison: { op: "between", min_value: 2, max_value: null }
    }),
    "Requires $.tags in output_json to satisfy the configured count comparison."
  );
  assert.equal(
    describeAutomaticRule({
      kind: "json_path_count",
      source: "output_json",
      path: "$.items",
      comparison: { op: "between", min_value: 2, max_value: null }
    }),
    "Requires $.items in output_json to satisfy the configured count comparison."
  );
});

test("ValidatorsPreview renders cards in read-only mode", () => {
  const validator = createDefaultValidator("automatic", []);
  if (validator.type !== "automatic") throw new Error("Expected automatic validator");
  validator.validator_id = "preview-shape";
  validator.title = "Preview shape";
  validator.input_scope = "output_prompt_and_case";
  validator.checks[0].rule = {
    kind: "word_count",
    source: "output_text",
    comparison: { op: "eq", value: 1 }
  };

  const html = renderToStaticMarkup(
    React.createElement(ValidatorsPreview, {
      validators: [validator]
    })
  );

  assert.match(html, /Preview shape/);
  assert.match(html, /Output \+ prompt \+ case/);
  assert.match(html, /Automatic/);
  assert.match(html, /Requires output_text word count to be exactly 1\./);
  assert.doesNotMatch(html, /<button/);
  assert.doesNotMatch(html, />\s*Edit\s*</);
  assert.doesNotMatch(html, />\s*Duplicate\s*</);
  assert.doesNotMatch(html, />\s*Delete\s*</);

  const fallbackHtml = renderToStaticMarkup(
    React.createElement(ValidatorCard, {
      showActions: false,
      validator: {
        ...validator,
        validator_id: "fallback-shape",
        title: "Fallback shape",
        checks: [
          {
            check_id: "bad-word-count",
            title: "Bad word count",
            description: "",
            rule: {
              kind: "word_count",
              source: "output_text",
              comparison: { op: "gt", value: Number.NaN }
            }
          },
          {
            check_id: "bad-json-path-count",
            title: "Bad json path count",
            description: "",
            rule: {
              kind: "json_path_count",
              source: "output_json",
              path: "$.items",
              comparison: { op: "between", min_value: 1, max_value: null }
            }
          }
        ]
      }
    })
  );

  assert.match(
    fallbackHtml,
    /Requires output_text word count to satisfy the configured comparison\./
  );
  assert.match(
    fallbackHtml,
    /Requires \$\.items in output_json to satisfy the configured count comparison\./
  );
  assert.match(
    fallbackHtml,
    /bad-word-count - word_count - configured comparison/
  );
  assert.match(
    fallbackHtml,
    /bad-json-path-count - json_path_count - configured range/
  );
});

const validatorsViewModule = await import("../src/components/ValidatorsView.tsx");
const {
  ValidatorEditModal,
  getValidatorEditorActionState,
  parseValidatorJsonDraft,
  switchValidatorModalViewModeState,
  shouldEmitValidatorsDraft,
  updateValidatorModalStructuredState,
  ValidatorsView
} = validatorsViewModule;

test("ValidatorsView renders validator cards instead of the editor by default", () => {
  const validator = createDefaultValidator("automatic", []);
  validator.validator_id = "report-shape";
  validator.title = "Report shape";

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
  assert.match(html, /Report shape/);
  assert.match(html, /Edit/);
  assert.match(html, /Duplicate/);
  assert.match(html, /Delete/);
  assert.match(html, /Overwrite current version/);
  assert.match(html, /Save as next version/);
  assert.doesNotMatch(html, /aria-label="Validator editor"/);
  assert.doesNotMatch(html, /Validator JSON/);
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

test("switchValidatorModalViewModeState keeps invalid JSON edits in place", () => {
  const validator = createDefaultValidator("llm_questionnaire", []);
  const invalidJsonText = '{ "validator_id": ';
  const nextState = switchValidatorModalViewModeState(
    {
      mode: "edit",
      sourceIndex: 0,
      initialValidator: JSON.parse(
        JSON.stringify(validator)
      ) as ValidatorDefinition,
      validator,
      viewMode: "json",
      jsonText: invalidJsonText,
      jsonError: "Unexpected end of JSON input",
      discardConfirming: true
    },
    "structured"
  );

  assert.equal(nextState.viewMode, "json");
  assert.equal(nextState.jsonError, "Unexpected end of JSON input");
  assert.equal(nextState.discardConfirming, true);
  assert.equal(nextState.jsonText, invalidJsonText);
});

test("updateValidatorModalStructuredState clears stale JSON error after structured edits", () => {
  const validator = createDefaultValidator("llm_questionnaire", []);
  const changedValidator = { ...validator, title: "Changed title" };
  const nextState = updateValidatorModalStructuredState(
    {
      mode: "edit",
      sourceIndex: 0,
      initialValidator: JSON.parse(
        JSON.stringify(validator)
      ) as ValidatorDefinition,
      validator,
      viewMode: "structured",
      jsonText: '{ "validator_id": ',
      jsonError: "Unexpected end of JSON input",
      discardConfirming: true
    },
    changedValidator
  );

  assert.equal(nextState.validator.title, "Changed title");
  assert.equal(nextState.jsonError, null);
  assert.equal(nextState.discardConfirming, false);
  assert.equal(nextState.jsonText, JSON.stringify(changedValidator, null, 2));
});

test("ValidatorEditModal renders only discard confirmation actions when confirming discard", () => {
  const validator = createDefaultValidator("automatic", []);
  const html = renderToStaticMarkup(
    React.createElement(ValidatorEditModal, {
      closeButtonRef: null,
      draftValidatorIds: [validator.validator_id],
      isBusy: false,
      modalState: {
        mode: "edit",
        sourceIndex: 0,
        initialValidator: JSON.parse(
          JSON.stringify(validator)
        ) as ValidatorDefinition,
        validator,
        viewMode: "structured",
        jsonText: JSON.stringify(validator, null, 2),
        jsonError: null,
        discardConfirming: true
      },
      modalValidationErrors: [],
      onClose: () => undefined,
      onDiscardEdits: () => undefined,
      onKeepEditing: () => undefined,
      onSave: () => undefined,
      onSwitchMode: () => undefined,
      onUpdateJson: () => undefined,
      onUpdateValidator: () => undefined
    })
  );

  assert.match(html, /Discard unsaved validator edits\?/);
  assert.match(html, /Keep editing/);
  assert.match(html, /Discard edits/);
  assert.doesNotMatch(html, /aria-label="Validator editor"/);
  assert.doesNotMatch(html, /Validator JSON/);
  assert.doesNotMatch(html, /Save changes/);
  assert.doesNotMatch(html, />Close</);
});

test("ValidatorEditModal renders normal editor controls outside discard confirmation", () => {
  const validator = createDefaultValidator("automatic", []);
  const html = renderToStaticMarkup(
    React.createElement(ValidatorEditModal, {
      closeButtonRef: null,
      draftValidatorIds: [validator.validator_id],
      isBusy: false,
      modalState: {
        mode: "edit",
        sourceIndex: 0,
        initialValidator: JSON.parse(
          JSON.stringify(validator)
        ) as ValidatorDefinition,
        validator,
        viewMode: "structured",
        jsonText: JSON.stringify(validator, null, 2),
        jsonError: null,
        discardConfirming: false
      },
      modalValidationErrors: [],
      onClose: () => undefined,
      onDiscardEdits: () => undefined,
      onKeepEditing: () => undefined,
      onSave: () => undefined,
      onSwitchMode: () => undefined,
      onUpdateJson: () => undefined,
      onUpdateValidator: () => undefined
    })
  );

  assert.match(html, /aria-label="Validator editor"/);
  assert.match(html, /Save changes/);
});

test("ValidatorEditModal disables mode tabs while JSON is invalid", () => {
  const validator = createDefaultValidator("automatic", []);
  const html = renderToStaticMarkup(
    React.createElement(ValidatorEditModal, {
      closeButtonRef: null,
      draftValidatorIds: [validator.validator_id],
      isBusy: false,
      modalState: {
        mode: "edit",
        sourceIndex: 0,
        initialValidator: JSON.parse(
          JSON.stringify(validator)
        ) as ValidatorDefinition,
        validator,
        viewMode: "json",
        jsonText: "{",
        jsonError: "Unexpected end of JSON input",
        discardConfirming: false
      },
      modalValidationErrors: [],
      onClose: () => undefined,
      onDiscardEdits: () => undefined,
      onKeepEditing: () => undefined,
      onSave: () => undefined,
      onSwitchMode: () => undefined,
      onUpdateJson: () => undefined,
      onUpdateValidator: () => undefined
    })
  );

  assert.match(html, /Invalid validator JSON/);
  assert.match(
    html,
    /<button(?=[^>]*disabled="")(?=[^>]*role="tab")[^>]*>Structured<\/button>/
  );
  assert.match(
    html,
    /<button(?=[^>]*disabled="")(?=[^>]*role="tab")[^>]*>JSON<\/button>/
  );
});
