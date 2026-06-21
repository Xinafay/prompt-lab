import type {
  AutomaticRule,
  CountComparison,
  InputScope,
  ValidatorDefinition,
  ValidatorType
} from "../types";

interface ValidatorsPreviewProps {
  validators: ValidatorDefinition[];
}

function validatorTypeLabel(type: ValidatorType): string {
  if (type === "llm_questionnaire") return "LLM questionnaire";
  if (type === "automatic") return "Automatic";
  return type;
}

function inputScopeLabel(scope: InputScope): string {
  if (scope === "output_only") return "Output only";
  if (scope === "output_and_prompt") return "Output + prompt";
  if (scope === "output_and_case") return "Output + case";
  if (scope === "output_prompt_and_case") return "Output + prompt + case";
  return scope;
}

function comparisonLabel(comparison: CountComparison | null | undefined): string {
  if (comparison === null || comparison === undefined) return "";
  if (comparison.op === "between") {
    return `between ${comparison.min_value} and ${comparison.max_value}`;
  }
  const operatorLabels: Record<CountComparison["op"], string> = {
    between: "between",
    eq: "=",
    gt: ">",
    gte: ">=",
    lt: "<",
    lte: "<="
  };
  return `${operatorLabels[comparison.op]} ${comparison.value}`;
}

function ruleLabel(rule: AutomaticRule): string {
  const comparison = comparisonLabel(rule.comparison);
  if (rule.kind === "json_path_exists") {
    return `JSON path exists: ${rule.path}`;
  }
  if (rule.kind === "json_path_count") {
    return `JSON path count ${rule.path} ${comparison}`;
  }
  if (rule.kind === "word_count") return `Word count ${comparison}`;
  if (rule.kind === "sentence_count") return `Sentence count ${comparison}`;
  if (rule.kind === "character_count") return `Character count ${comparison}`;
  return rule.kind;
}

export function ValidatorsPreview({ validators }: ValidatorsPreviewProps) {
  return (
    <div className="validators-preview">
      {validators.length === 0 ? (
        <div className="empty-state compact-empty-state">
          <h2>No validators configured</h2>
          <p>Add validators before running validation.</p>
        </div>
      ) : (
        validators.map((validator) => (
          <article
            className={`validator-preview-card${
              validator.enabled ? "" : " is-disabled"
            }`}
            key={validator.validator_id}
          >
            <div className="validator-preview-header">
              <div>
                <h4>{validator.title}</h4>
                <p>{validator.description || validator.validator_id}</p>
              </div>
              <div className="validator-preview-pills">
                <span className="neutral-pill">{validatorTypeLabel(validator.type)}</span>
                <span className="neutral-pill">{inputScopeLabel(validator.input_scope)}</span>
                <span
                  className={
                    validator.enabled
                      ? "status-pill status-pill-pass"
                      : "status-pill status-pill-empty"
                  }
                >
                  {validator.enabled ? "enabled" : "disabled"}
                </span>
              </div>
            </div>

            <div className="validator-check-preview-list">
              {validator.type === "llm_questionnaire"
                ? validator.checks.map((check) => (
                    <div className="validator-check-preview" key={check.check_id}>
                      <div>
                        <strong>{check.title}</strong>
                        <span>{check.description || check.check_id}</span>
                      </div>
                      <p>{check.question}</p>
                    </div>
                  ))
                : validator.checks.map((check) => (
                    <div className="validator-check-preview" key={check.check_id}>
                      <div>
                        <strong>{check.title}</strong>
                        <span>{check.description || check.check_id}</span>
                      </div>
                      <p>{ruleLabel(check.rule)}</p>
                    </div>
                  ))}
            </div>
          </article>
        ))
      )}
    </div>
  );
}
