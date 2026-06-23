import type { MouseEvent } from "react";
import type {
  AutomaticRule,
  CountComparison,
  InputScope,
  ValidatorDefinition,
  ValidatorType
} from "../types";

interface ValidatorCardProps {
  disabled: boolean;
  onDelete: (event: MouseEvent<HTMLButtonElement>) => void;
  onDuplicate: (event: MouseEvent<HTMLButtonElement>) => void;
  onEdit: (event: MouseEvent<HTMLButtonElement>) => void;
  validator: ValidatorDefinition;
}

export function validatorTypeLabel(type: ValidatorType): string {
  if (type === "llm_questionnaire") return "LLM questionnaire";
  if (type === "automatic") return "Automatic";
  return type;
}

export function inputScopeLabel(scope: InputScope): string {
  if (scope === "output_only") return "Output only";
  if (scope === "output_and_prompt") return "Output + prompt";
  if (scope === "output_and_case") return "Output + case";
  if (scope === "output_prompt_and_case") return "Output + prompt + case";
  return scope;
}

function comparisonPhrase(comparison: CountComparison | null | undefined): string {
  if (comparison === null || comparison === undefined) return "without a comparison";
  if (comparison.op === "between") {
    return `between ${comparison.min_value} and ${comparison.max_value}`;
  }
  const operatorLabels: Record<Exclude<CountComparison["op"], "between">, string> = {
    eq: "exactly",
    gt: "more than",
    gte: "at least",
    lt: "less than",
    lte: "at most"
  };
  return `${operatorLabels[comparison.op]} ${comparison.value}`;
}

export function describeAutomaticRule(rule: AutomaticRule): string {
  const source = rule.source;
  const path = rule.path ?? "the configured JSON path";

  if (rule.kind === "json_path_exists") {
    return `Requires ${path} in ${source} to exist.`;
  }
  if (rule.kind === "json_path_count") {
    return `Requires ${path} in ${source} to contain ${comparisonPhrase(
      rule.comparison
    )} items.`;
  }
  if (rule.kind === "word_count") {
    return `Requires ${source} word count to be ${comparisonPhrase(rule.comparison)}.`;
  }
  if (rule.kind === "sentence_count") {
    return `Requires ${source} sentence count to be ${comparisonPhrase(
      rule.comparison
    )}.`;
  }
  if (rule.kind === "character_count") {
    return `Requires ${source} character count to be ${comparisonPhrase(
      rule.comparison
    )}.`;
  }
  return `Applies ${rule.kind} to ${source}.`;
}

function automaticRuleMetadata(rule: AutomaticRule): string {
  const comparison = rule.comparison;
  if (comparison === null || comparison === undefined) {
    return rule.kind;
  }
  if (comparison.op === "between") {
    return `${rule.kind} - between ${comparison.min_value}..${comparison.max_value}`;
  }
  return `${rule.kind} - ${comparison.op} ${comparison.value}`;
}

export function ValidatorCard({
  disabled,
  onDelete,
  onDuplicate,
  onEdit,
  validator
}: ValidatorCardProps) {
  const title = validator.title || "(untitled)";
  const checkCount = validator.checks.length;
  const checkLabel = checkCount === 1 ? "1 check" : `${checkCount} checks`;

  return (
    <article
      className={`validator-card${validator.enabled ? "" : " is-disabled"}`}
      aria-label={`${title} validator`}
    >
      <div className="validator-card-header">
        <div>
          <h3>{title}</h3>
          <div className="validator-card-meta">
            <span>{validatorTypeLabel(validator.type)}</span>
            <span>{validator.enabled ? "Enabled" : "Disabled"}</span>
            <span>{inputScopeLabel(validator.input_scope)}</span>
            <span>{checkLabel}</span>
          </div>
        </div>
        <div className="validator-card-actions">
          <button
            className="primary-action"
            disabled={disabled}
            onClick={onEdit}
            type="button"
            aria-label={`Edit ${title} validator`}
          >
            Edit
          </button>
          <button
            className="secondary-action"
            disabled={disabled}
            onClick={onDuplicate}
            type="button"
            aria-label={`Duplicate ${title} validator`}
          >
            Duplicate
          </button>
          <button
            className="secondary-action danger-action"
            disabled={disabled}
            onClick={onDelete}
            type="button"
            aria-label={`Delete ${title} validator`}
          >
            Delete
          </button>
        </div>
      </div>

      {validator.description.trim().length > 0 ? (
        <p className="validator-card-description">{validator.description}</p>
      ) : null}

      <div className="validator-card-checks" aria-label={`${title} checks`}>
        {validator.checks.map((check) => {
          const body =
            validator.type === "llm_questionnaire"
              ? `Asks: ${check.question}`
              : describeAutomaticRule(check.rule);
          const metadata =
            validator.type === "llm_questionnaire"
              ? `${check.check_id} - llm_questionnaire`
              : `${check.check_id} - ${automaticRuleMetadata(check.rule)}`;

          return (
            <section className="validator-card-check" key={check.check_id}>
              <div>
                <h4>{check.title || check.check_id}</h4>
                {check.description.trim().length > 0 ? <p>{check.description}</p> : null}
              </div>
              <div>
                <p>{body}</p>
                <span>{metadata}</span>
              </div>
            </section>
          );
        })}
      </div>
    </article>
  );
}
