import type { MouseEvent } from "react";
import type {
  AutomaticValidatorDefinition,
  AutomaticRule,
  CountComparison,
  InputScope,
  LlmQuestionnaireValidatorDefinition,
  ValidatorDefinition,
  ValidatorType
} from "../types";

interface ValidatorCardReadOnlyProps {
  showActions?: false;
  validator: ValidatorDefinition;
}

interface ValidatorCardInteractiveProps {
  showActions: true;
  disabled: boolean;
  onDelete: (event: MouseEvent<HTMLButtonElement>) => void;
  onDuplicate: (event: MouseEvent<HTMLButtonElement>) => void;
  onEdit: (event: MouseEvent<HTMLButtonElement>) => void;
  validator: ValidatorDefinition;
}

type ValidatorCardProps = ValidatorCardReadOnlyProps | ValidatorCardInteractiveProps;

type ComparisonRender =
  | { kind: "configured" }
  | { kind: "configuredRange" }
  | { kind: "value"; text: string };

function comparisonMetadataText(comparison: CountComparison | null | undefined): string {
  if (comparison === null || comparison === undefined) {
    return "configured comparison";
  }
  if (comparison.op === "between") {
    if (!isFiniteComparisonValue(comparison.min_value) || !isFiniteComparisonValue(comparison.max_value)) {
      return "configured range";
    }
    return `between ${comparison.min_value}..${comparison.max_value}`;
  }
  if (!isFiniteComparisonValue(comparison.value)) {
    return "configured comparison";
  }
  return `${comparison.op} ${comparison.value}`;
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

function isFiniteComparisonValue(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function comparisonText(comparison: CountComparison | null | undefined): ComparisonRender {
  if (comparison === null || comparison === undefined) {
    return { kind: "configured" };
  }
  if (comparison.op === "between") {
    if (!isFiniteComparisonValue(comparison.min_value) || !isFiniteComparisonValue(comparison.max_value)) {
      return { kind: "configuredRange" };
    }
    return { kind: "value", text: `between ${comparison.min_value}..${comparison.max_value}` };
  }
  const operatorLabels: Record<Exclude<CountComparison["op"], "between">, string> = {
    eq: "exactly",
    gt: "more than",
    gte: "at least",
    lt: "less than",
    lte: "at most"
  };
  if (!isFiniteComparisonValue(comparison.value)) {
    return { kind: "configured" };
  }
  return { kind: "value", text: `${operatorLabels[comparison.op]} ${comparison.value}` };
}

export function describeAutomaticRule(rule: AutomaticRule): string {
  const source = rule.source;
  const path = rule.path ?? "the configured JSON path";
  const comparison = comparisonText(rule.comparison);

  if (rule.kind === "json_path_exists") {
    return `Requires ${path} in ${source} to exist.`;
  }
  if (rule.kind === "json_path_count") {
    if (comparison.kind === "configured" || comparison.kind === "configuredRange") {
      return `Requires ${path} in ${source} to satisfy the configured count comparison.`;
    }
    return `Requires ${path} in ${source} to contain ${comparison.text} items.`;
  }
  if (comparison.kind === "configured" || comparison.kind === "configuredRange") {
    return `Requires ${source} ${rule.kind.replace("_", " ")} to satisfy the configured comparison.`;
  }
  if (rule.kind === "word_count") {
    return `Requires ${source} word count to be ${comparison.text}.`;
  }
  if (rule.kind === "sentence_count") {
    return `Requires ${source} sentence count to be ${comparison.text}.`;
  }
  if (rule.kind === "character_count") {
    return `Requires ${source} character count to be ${comparison.text}.`;
  }
  return `Applies ${rule.kind} to ${source}.`;
}

function automaticRuleMetadata(rule: AutomaticRule): string {
  if (rule.kind === "json_path_exists") {
    return rule.kind;
  }
  const comparison = comparisonMetadataText(rule.comparison);

  return `${rule.kind} - ${comparison}`;
}

function renderCheck(
  check: { check_id: string; title: string; description: string },
  body: string,
  metadata: string
) {
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
}

function renderLlmCheck(check: LlmQuestionnaireValidatorDefinition["checks"][number]) {
  return renderCheck(
    check,
    `Asks: ${check.question}`,
    `${check.check_id} - llm_questionnaire`
  );
}

function renderAutomaticCheck(
  check: AutomaticValidatorDefinition["checks"][number]
) {
  return renderCheck(
    check,
    describeAutomaticRule(check.rule),
    `${check.check_id} - ${automaticRuleMetadata(check.rule)}`
  );
}

export function ValidatorCard(props: ValidatorCardProps) {
  const showActions = props.showActions === true;
  const { validator } = props;
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
        {showActions ? (
          <div className="validator-card-actions">
            <button
              className="primary-action"
              disabled={props.disabled}
              onClick={props.onEdit}
              type="button"
              aria-label={`Edit ${title} validator`}
            >
              Edit
            </button>
            <button
              className="secondary-action"
              disabled={props.disabled}
              onClick={props.onDuplicate}
              type="button"
              aria-label={`Duplicate ${title} validator`}
            >
              Duplicate
            </button>
            <button
              className="secondary-action danger-action"
              disabled={props.disabled}
              onClick={props.onDelete}
              type="button"
              aria-label={`Delete ${title} validator`}
            >
              Delete
            </button>
          </div>
        ) : null}
      </div>

      {validator.description.trim().length > 0 ? (
        <p className="validator-card-description">{validator.description}</p>
      ) : null}

      <div className="validator-card-checks" aria-label={`${title} checks`}>
        {validator.type === "llm_questionnaire"
          ? validator.checks.map(renderLlmCheck)
          : validator.checks.map(renderAutomaticCheck)}
      </div>
    </article>
  );
}
