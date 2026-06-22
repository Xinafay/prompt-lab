import type {
  AutomaticRule,
  AutomaticValidatorDefinition,
  CountComparison,
  InputScope,
  LlmQuestionnaireValidatorDefinition,
  ValidatorDefinition,
  ValidatorType
} from "../types";

const inputScopes: InputScope[] = [
  "output_only",
  "output_and_prompt",
  "output_and_case",
  "output_prompt_and_case"
];

const validatorTypes: ValidatorType[] = ["llm_questionnaire", "automatic"];

const ruleKinds: AutomaticRule["kind"][] = [
  "word_count",
  "sentence_count",
  "character_count",
  "json_path_count",
  "json_path_exists"
];

const ruleSources: AutomaticRule["source"][] = [
  "output_text",
  "raw_output",
  "output_json"
];

const comparisonOps: CountComparison["op"][] = [
  "lt",
  "lte",
  "gt",
  "gte",
  "eq",
  "between"
];

type ValidatorBasePatch = Partial<
  Pick<
    ValidatorDefinition,
    "validator_id" | "title" | "description" | "enabled" | "input_scope"
  >
>;

function nextId(base: string, existingIds: string[]): string {
  if (!existingIds.includes(base)) return base;
  let index = 1;
  while (existingIds.includes(`${base}-${index}`)) {
    index += 1;
  }
  return `${base}-${index}`;
}

function defaultRule(kind: AutomaticRule["kind"] = "word_count"): AutomaticRule {
  if (kind === "json_path_exists") {
    return { kind, source: "output_json", path: "$.field" };
  }
  if (kind === "json_path_count") {
    return {
      kind,
      source: "output_json",
      path: "$.items",
      comparison: { op: "gte", value: 1 }
    };
  }
  return {
    kind,
    source: "output_text",
    comparison: { op: "gte", value: 1 }
  };
}

function defaultComparison(op: CountComparison["op"] = "gte"): CountComparison {
  if (op === "between") {
    return { op, min_value: 1, max_value: 3 };
  }
  return { op, value: 1 };
}

export function createDefaultValidator(
  type: ValidatorType,
  existingValidatorIds: string[]
): ValidatorDefinition {
  const validator_id = nextId("validator-1", existingValidatorIds);

  if (type === "automatic") {
    return {
      schema_version: "prompt_lab.validator/v1",
      validator_id,
      type,
      title: "New automatic validator",
      description: "",
      enabled: true,
      input_scope: "output_only",
      checks: [
        {
          check_id: "check-1",
          title: "New check",
          description: "",
          rule: defaultRule()
        }
      ]
    };
  }

  return {
    schema_version: "prompt_lab.validator/v1",
    validator_id,
    type,
    title: "New questionnaire validator",
    description: "",
    enabled: true,
    input_scope: "output_only",
    checks: [
      {
        check_id: "check-1",
        title: "New check",
        question: "Does the output satisfy this check?",
        description: ""
      }
    ]
  };
}

export function duplicateValidator(
  validator: ValidatorDefinition,
  existingValidatorIds: string[]
): ValidatorDefinition {
  const validator_id = nextId(`${validator.validator_id}-copy`, existingValidatorIds);

  if (validator.type === "automatic") {
    const usedCheckIds: string[] = [];
    return {
      ...validator,
      validator_id,
      title: `${validator.title} copy`,
      checks: validator.checks.map((check) => {
        const check_id = nextId(`${check.check_id}-copy`, usedCheckIds);
        usedCheckIds.push(check_id);
        return {
          ...check,
          check_id,
          rule: { ...check.rule }
        };
      })
    };
  }

  const usedCheckIds: string[] = [];
  return {
    ...validator,
    validator_id,
    title: `${validator.title} copy`,
    checks: validator.checks.map((check) => {
      const check_id = nextId(`${check.check_id}-copy`, usedCheckIds);
      usedCheckIds.push(check_id);
      return { ...check, check_id };
    })
  };
}

export function validateValidatorDraft(
  validators: ValidatorDefinition[]
): string[] {
  const errors: string[] = [];
  const seenValidatorIds = new Set<string>();

  for (const validator of validators) {
    if (seenValidatorIds.has(validator.validator_id)) {
      errors.push(`Validator id ${validator.validator_id} is duplicated.`);
    }
    seenValidatorIds.add(validator.validator_id);

    if (validator.validator_id.trim().length === 0) {
      errors.push("Validator id is required.");
    }
    if (validator.title.trim().length === 0) {
      errors.push(`Validator ${validator.validator_id || "(new)"} title is required.`);
    }
    if (validator.checks.length === 0) {
      errors.push(`Validator ${validator.validator_id} needs at least one check.`);
    }

    const seenCheckIds = new Set<string>();
    for (const check of validator.checks) {
      if (seenCheckIds.has(check.check_id)) {
        errors.push(
          `Check id ${check.check_id} is duplicated in ${validator.validator_id}.`
        );
      }
      seenCheckIds.add(check.check_id);

      if (check.check_id.trim().length === 0) {
        errors.push(`Validator ${validator.validator_id} has a check without an id.`);
      }
      if (check.title.trim().length === 0) {
        errors.push(`Check ${check.check_id || "(new)"} needs a title.`);
      }
      if (
        validator.type === "llm_questionnaire" &&
        check.question.trim().length === 0
      ) {
        errors.push(`Check ${check.check_id} needs a question.`);
      }
    }
  }

  return errors;
}

interface ValidatorEditorProps {
  existingValidatorIds: string[];
  onChange: (validator: ValidatorDefinition) => void;
  validator: ValidatorDefinition;
}

export function ValidatorEditor({
  existingValidatorIds,
  onChange,
  validator
}: ValidatorEditorProps) {
  function updateBase(update: ValidatorBasePatch) {
    onChange({ ...validator, ...update });
  }

  function changeType(type: ValidatorType) {
    if (type === validator.type) return;
    onChange(
      createDefaultValidator(
        type,
        existingValidatorIds.filter((id) => id !== validator.validator_id)
      )
    );
  }

  return (
    <section className="validator-editor" aria-label="Validator editor">
      <div className="settings-section">
        <h3>Validator</h3>
        <label className="settings-field">
          <span>Validator ID</span>
          <input
            required
            value={validator.validator_id}
            onChange={(event) => updateBase({ validator_id: event.target.value })}
          />
        </label>
        <label className="settings-field">
          <span>Type</span>
          <select
            value={validator.type}
            onChange={(event) => changeType(event.target.value as ValidatorType)}
          >
            {validatorTypes.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </label>
        <label className="settings-field">
          <span>Title</span>
          <input
            required
            value={validator.title}
            onChange={(event) => updateBase({ title: event.target.value })}
          />
        </label>
        <label className="settings-field">
          <span>Input scope</span>
          <select
            value={validator.input_scope}
            onChange={(event) =>
              updateBase({ input_scope: event.target.value as InputScope })
            }
          >
            {inputScopes.map((scope) => (
              <option key={scope} value={scope}>
                {scope}
              </option>
            ))}
          </select>
        </label>
        <label className="settings-field settings-field-wide">
          <span>Description</span>
          <textarea
            rows={3}
            value={validator.description}
            onChange={(event) => updateBase({ description: event.target.value })}
          />
        </label>
        <label className="settings-checkbox">
          <input
            checked={validator.enabled}
            onChange={(event) => updateBase({ enabled: event.target.checked })}
            type="checkbox"
          />
          <span>Enabled</span>
        </label>
      </div>

      {validator.type === "llm_questionnaire" ? (
        <LlmChecksEditor validator={validator} onChange={onChange} />
      ) : (
        <AutomaticChecksEditor validator={validator} onChange={onChange} />
      )}
    </section>
  );
}

function LlmChecksEditor({
  onChange,
  validator
}: {
  onChange: (validator: ValidatorDefinition) => void;
  validator: LlmQuestionnaireValidatorDefinition;
}) {
  function updateCheck(
    index: number,
    update: Partial<LlmQuestionnaireValidatorDefinition["checks"][number]>
  ) {
    const checks = validator.checks.map((check, checkIndex) =>
      checkIndex === index ? { ...check, ...update } : check
    );
    onChange({ ...validator, checks });
  }

  return (
    <section className="settings-section">
      <h3>Checks</h3>
      {validator.checks.map((check, index) => (
        <div className="validator-check-editor" key={`${check.check_id}-${index}`}>
          <label className="settings-field">
            <span>Check ID</span>
            <input
              value={check.check_id}
              onChange={(event) =>
                updateCheck(index, { check_id: event.target.value })
              }
            />
          </label>
          <label className="settings-field">
            <span>Title</span>
            <input
              value={check.title}
              onChange={(event) => updateCheck(index, { title: event.target.value })}
            />
          </label>
          <label className="settings-field settings-field-wide">
            <span>Question</span>
            <textarea
              rows={3}
              value={check.question}
              onChange={(event) =>
                updateCheck(index, { question: event.target.value })
              }
            />
          </label>
          <label className="settings-field settings-field-wide">
            <span>Description</span>
            <textarea
              rows={2}
              value={check.description}
              onChange={(event) =>
                updateCheck(index, { description: event.target.value })
              }
            />
          </label>
        </div>
      ))}
    </section>
  );
}

function AutomaticChecksEditor({
  onChange,
  validator
}: {
  onChange: (validator: ValidatorDefinition) => void;
  validator: AutomaticValidatorDefinition;
}) {
  function updateCheck(
    index: number,
    update: Partial<AutomaticValidatorDefinition["checks"][number]>
  ) {
    const checks = validator.checks.map((check, checkIndex) =>
      checkIndex === index ? { ...check, ...update } : check
    );
    onChange({ ...validator, checks });
  }

  function updateRule(index: number, rule: AutomaticRule) {
    updateCheck(index, { rule });
  }

  return (
    <section className="settings-section">
      <h3>Checks</h3>
      {validator.checks.map((check, index) => (
        <div className="validator-check-editor" key={`${check.check_id}-${index}`}>
          <label className="settings-field">
            <span>Check ID</span>
            <input
              value={check.check_id}
              onChange={(event) =>
                updateCheck(index, { check_id: event.target.value })
              }
            />
          </label>
          <label className="settings-field">
            <span>Title</span>
            <input
              value={check.title}
              onChange={(event) => updateCheck(index, { title: event.target.value })}
            />
          </label>
          <label className="settings-field">
            <span>Rule kind</span>
            <select
              value={check.rule.kind}
              onChange={(event) =>
                updateRule(
                  index,
                  defaultRule(event.target.value as AutomaticRule["kind"])
                )
              }
            >
              {ruleKinds.map((kind) => (
                <option key={kind} value={kind}>
                  {kind}
                </option>
              ))}
            </select>
          </label>
          <label className="settings-field">
            <span>Rule source</span>
            <select
              value={check.rule.source}
              onChange={(event) =>
                updateRule(index, {
                  ...check.rule,
                  source: event.target.value as AutomaticRule["source"]
                })
              }
            >
              {ruleSources.map((source) => (
                <option key={source} value={source}>
                  {source}
                </option>
              ))}
            </select>
          </label>
          {check.rule.kind === "json_path_count" ||
          check.rule.kind === "json_path_exists" ? (
            <label className="settings-field">
              <span>JSON path</span>
              <input
                value={check.rule.path ?? ""}
                onChange={(event) =>
                  updateRule(index, { ...check.rule, path: event.target.value })
                }
              />
            </label>
          ) : null}
          {check.rule.kind !== "json_path_exists" ? (
            <ComparisonEditor
              comparison={check.rule.comparison ?? defaultComparison()}
              onChange={(comparison) =>
                updateRule(index, { ...check.rule, comparison })
              }
            />
          ) : null}
          <label className="settings-field settings-field-wide">
            <span>Description</span>
            <textarea
              rows={2}
              value={check.description}
              onChange={(event) =>
                updateCheck(index, { description: event.target.value })
              }
            />
          </label>
        </div>
      ))}
    </section>
  );
}

function ComparisonEditor({
  comparison,
  onChange
}: {
  comparison: CountComparison;
  onChange: (comparison: CountComparison) => void;
}) {
  return (
    <>
      <label className="settings-field">
        <span>Comparison</span>
        <select
          value={comparison.op}
          onChange={(event) =>
            onChange(defaultComparison(event.target.value as CountComparison["op"]))
          }
        >
          {comparisonOps.map((op) => (
            <option key={op} value={op}>
              {op}
            </option>
          ))}
        </select>
      </label>
      {comparison.op === "between" ? (
        <>
          <label className="settings-field">
            <span>Minimum</span>
            <input
              type="number"
              value={comparison.min_value ?? 0}
              onChange={(event) =>
                onChange({ ...comparison, min_value: event.target.valueAsNumber })
              }
            />
          </label>
          <label className="settings-field">
            <span>Maximum</span>
            <input
              type="number"
              value={comparison.max_value ?? 0}
              onChange={(event) =>
                onChange({ ...comparison, max_value: event.target.valueAsNumber })
              }
            />
          </label>
        </>
      ) : (
        <label className="settings-field">
          <span>Value</span>
          <input
            type="number"
            value={comparison.value ?? 0}
            onChange={(event) =>
              onChange({ ...comparison, value: event.target.valueAsNumber })
            }
          />
        </label>
      )}
    </>
  );
}
