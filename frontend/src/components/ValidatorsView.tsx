import { useEffect, useMemo, useRef, useState } from "react";

import type {
  ValidatorDefinition,
  ValidatorType,
  VersionValidatorsDraft
} from "../types";
import {
  createDefaultValidator,
  duplicateValidator,
  validateValidatorDraft,
  ValidatorEditor
} from "./ValidatorEditor";
import { ValidatorsPreview } from "./ValidatorsPreview";

interface ValidatorsViewProps {
  isBusy?: boolean;
  message?: string | null;
  onDraftChange?: (draft: VersionValidatorsDraft | null) => void;
  onOverwriteCurrent?: () => void;
  onReset?: () => void;
  onSaveAsNext?: () => void;
  validators: ValidatorDefinition[];
}

function cloneValidators(validators: ValidatorDefinition[]): ValidatorDefinition[] {
  return JSON.parse(JSON.stringify(validators)) as ValidatorDefinition[];
}

function validatorsEqual(
  left: ValidatorDefinition[],
  right: ValidatorDefinition[]
): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function formatValidatorType(type: ValidatorType): string {
  return type === "llm_questionnaire" ? "LLM questionnaire" : "Automatic";
}

type ValidatorJsonParseResult =
  | { ok: true; validator: ValidatorDefinition }
  | { ok: false; error: string };

const validatorTypes: ValidatorType[] = ["llm_questionnaire", "automatic"];
const inputScopes = [
  "output_only",
  "output_and_prompt",
  "output_and_case",
  "output_prompt_and_case"
] as const;
const ruleKinds = [
  "word_count",
  "sentence_count",
  "character_count",
  "json_path_count",
  "json_path_exists"
] as const;
const ruleSources = ["output_text", "raw_output", "output_json"] as const;
const comparisonOps = ["lt", "lte", "gt", "gte", "eq", "between"] as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasStringField(record: Record<string, unknown>, field: string): boolean {
  return typeof record[field] === "string";
}

function validateComparisonShape(value: unknown, label: string): string | null {
  if (value === null || value === undefined) return null;
  if (!isRecord(value)) return `${label} comparison must be an object.`;
  if (!comparisonOps.includes(value.op as (typeof comparisonOps)[number])) {
    return `${label} comparison must include a valid op.`;
  }
  for (const field of ["value", "min_value", "max_value"]) {
    const fieldValue = value[field];
    if (
      fieldValue !== null &&
      fieldValue !== undefined &&
      typeof fieldValue !== "number"
    ) {
      return `${label} comparison ${field} must be a number or null.`;
    }
  }
  return null;
}

function validateRuleShape(value: unknown, label: string): string | null {
  if (!isRecord(value)) return `${label} rule must be an object.`;
  if (!ruleKinds.includes(value.kind as (typeof ruleKinds)[number])) {
    return `${label} rule must include a valid kind.`;
  }
  if (!ruleSources.includes(value.source as (typeof ruleSources)[number])) {
    return `${label} rule must include a valid source.`;
  }
  if (
    value.path !== null &&
    value.path !== undefined &&
    typeof value.path !== "string"
  ) {
    return `${label} rule path must be a string or null.`;
  }
  return validateComparisonShape(value.comparison, label);
}

function validateValidatorShape(value: unknown): string | null {
  if (!isRecord(value)) return "Validator JSON must be an object.";
  if (value.schema_version !== "prompt_lab.validator/v1") {
    return 'Validator JSON must include schema_version "prompt_lab.validator/v1".';
  }
  for (const field of ["validator_id", "title", "description"]) {
    if (!hasStringField(value, field)) {
      return `Validator JSON field ${field} must be a string.`;
    }
  }
  if (typeof value.enabled !== "boolean") {
    return "Validator JSON field enabled must be a boolean.";
  }
  if (!validatorTypes.includes(value.type as ValidatorType)) {
    return "Validator JSON field type must be a supported validator type.";
  }
  if (!inputScopes.includes(value.input_scope as (typeof inputScopes)[number])) {
    return "Validator JSON field input_scope must be a supported input scope.";
  }
  if (!Array.isArray(value.checks)) {
    return "Validator JSON field checks must be an array.";
  }

  for (const [index, check] of value.checks.entries()) {
    const label = `Check ${index + 1}`;
    if (!isRecord(check)) return `${label} must be an object.`;
    for (const field of ["check_id", "title", "description"]) {
      if (!hasStringField(check, field)) {
        return `${label} field ${field} must be a string.`;
      }
    }
    if (value.type === "llm_questionnaire") {
      if (!hasStringField(check, "question")) {
        return `${label} field question must be a string.`;
      }
    } else {
      const ruleError = validateRuleShape(check.rule, label);
      if (ruleError !== null) return ruleError;
    }
  }

  return null;
}

export function parseValidatorJsonDraft(value: string): ValidatorJsonParseResult {
  let parsed: unknown;
  try {
    parsed = JSON.parse(value) as unknown;
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : "Invalid JSON."
    };
  }

  const shapeError = validateValidatorShape(parsed);
  if (shapeError !== null) {
    return { ok: false, error: shapeError };
  }

  const validator = parsed as ValidatorDefinition;
  const validationErrors = validateValidatorDraft([validator]);
  if (validationErrors.length > 0) {
    return { ok: false, error: validationErrors.join(" ") };
  }

  return { ok: true, validator };
}

export function shouldEmitValidatorsDraft(
  previousSerialized: string | undefined,
  draft: VersionValidatorsDraft | null
): { serialized: string; shouldEmit: boolean } {
  const serialized = JSON.stringify(draft);
  return {
    serialized,
    shouldEmit: previousSerialized !== serialized
  };
}

export function getValidatorEditorActionState({
  isBusy,
  isDirty,
  jsonError,
  validationErrorCount
}: {
  isBusy: boolean;
  isDirty: boolean;
  jsonError: string | null;
  validationErrorCount: number;
}) {
  const hasJsonError = jsonError !== null;
  return {
    jsonUnsafeActionsDisabled: isBusy || hasJsonError,
    resetDisabled: isBusy || (!isDirty && !hasJsonError),
    saveDisabled: isBusy || !isDirty || validationErrorCount > 0 || hasJsonError
  };
}

export function applyValidatorJsonDraftEdit(
  currentDraft: ValidatorDefinition[],
  selectedIndex: number,
  value: string
): {
  draft: ValidatorDefinition[];
  jsonError: string | null;
  jsonText: string;
} {
  const result = parseValidatorJsonDraft(value);
  if (!result.ok) {
    return {
      draft: currentDraft,
      jsonError: result.error,
      jsonText: value
    };
  }

  return {
    draft: currentDraft.map((validator, validatorIndex) =>
      validatorIndex === selectedIndex ? result.validator : validator
    ),
    jsonError: null,
    jsonText: value
  };
}

export function createValidatorJsonResetState(
  validators: ValidatorDefinition[]
): {
  draft: ValidatorDefinition[];
  jsonError: string | null;
  jsonText: string;
  selectedIndex: number;
} {
  return {
    draft: cloneValidators(validators),
    jsonError: null,
    jsonText: "",
    selectedIndex: validators.length > 0 ? 0 : -1
  };
}

export function ValidatorsView({
  isBusy = false,
  message = null,
  onDraftChange = () => undefined,
  onOverwriteCurrent = () => undefined,
  onReset = () => undefined,
  onSaveAsNext = () => undefined,
  validators
}: ValidatorsViewProps) {
  const [draft, setDraft] = useState<ValidatorDefinition[]>(() =>
    cloneValidators(validators)
  );
  const [selectedIndex, setSelectedIndex] = useState(validators.length > 0 ? 0 : -1);
  const [viewMode, setViewMode] = useState<"structured" | "json">("structured");
  const [jsonText, setJsonText] = useState("");
  const [jsonError, setJsonError] = useState<string | null>(null);
  const lastDraftEmissionRef = useRef(JSON.stringify(null));

  useEffect(() => {
    setDraft(cloneValidators(validators));
    setSelectedIndex(validators.length > 0 ? 0 : -1);
    setViewMode("structured");
    setJsonText("");
    setJsonError(null);
  }, [validators]);

  const selected = draft[selectedIndex] ?? null;
  const isDirty = useMemo(() => !validatorsEqual(draft, validators), [
    draft,
    validators
  ]);
  const validationErrors = useMemo(() => validateValidatorDraft(draft), [draft]);
  const actionState = getValidatorEditorActionState({
    isBusy,
    isDirty,
    jsonError,
    validationErrorCount: validationErrors.length
  });

  useEffect(() => {
    const nextDraft = isDirty ? { validators: draft } : null;
    const emission = shouldEmitValidatorsDraft(
      lastDraftEmissionRef.current,
      nextDraft
    );
    if (!emission.shouldEmit) return;
    lastDraftEmissionRef.current = emission.serialized;
    onDraftChange(nextDraft);
  }, [draft, isDirty, onDraftChange]);

  useEffect(() => {
    if (viewMode !== "json" || selected === null || jsonError !== null) return;
    setJsonText(JSON.stringify(selected, null, 2));
  }, [jsonError, selected, viewMode]);

  function setDraftAndSelect(
    nextDraft: ValidatorDefinition[],
    nextSelectedIndex: number
  ) {
    setDraft(nextDraft);
    setSelectedIndex(nextSelectedIndex);
    setJsonError(null);
  }

  function addValidator(type: ValidatorType) {
    if (actionState.jsonUnsafeActionsDisabled) return;
    const nextValidator = createDefaultValidator(
      type,
      draft.map((validator) => validator.validator_id)
    );
    setDraftAndSelect([...draft, nextValidator], draft.length);
  }

  function updateSelected(nextValidator: ValidatorDefinition) {
    if (selected === null) return;
    setDraft((current) =>
      current.map((validator, validatorIndex) =>
        validatorIndex === selectedIndex ? nextValidator : validator
      )
    );
  }

  function duplicateSelected() {
    if (actionState.jsonUnsafeActionsDisabled) return;
    if (selected === null) return;
    const copy = duplicateValidator(
      selected,
      draft.map((validator) => validator.validator_id)
    );
    setDraftAndSelect([...draft, copy], draft.length);
  }

  function deleteSelected() {
    if (actionState.jsonUnsafeActionsDisabled) return;
    if (selected === null) return;
    const nextDraft = draft.filter(
      (_validator, validatorIndex) => validatorIndex !== selectedIndex
    );
    setDraftAndSelect(
      nextDraft,
      nextDraft.length === 0 ? -1 : Math.min(selectedIndex, nextDraft.length - 1)
    );
  }

  function resetDraft() {
    const nextState = createValidatorJsonResetState(validators);
    setDraft(nextState.draft);
    setSelectedIndex(nextState.selectedIndex);
    setJsonError(nextState.jsonError);
    setJsonText(nextState.jsonText);
    onReset();
  }

  function toggleViewMode(mode: "structured" | "json") {
    if (jsonError !== null) return;
    setViewMode(mode);
    setJsonError(null);
    setJsonText(selected === null ? "" : JSON.stringify(selected, null, 2));
  }

  function updateJson(value: string) {
    const nextState = applyValidatorJsonDraftEdit(draft, selectedIndex, value);
    setJsonText(nextState.jsonText);
    setDraft(nextState.draft);
    setJsonError(nextState.jsonError);
  }

  return (
    <section className="validators-editor-panel" aria-label="Validators">
      <div className="settings-header">
        <div>
          <h2>Validators</h2>
          <p>Edit validators stored with this version.</p>
        </div>
        <div className="validators-editor-actions">
          <button
            className="secondary-action"
            disabled={actionState.resetDisabled}
            onClick={resetDraft}
            type="button"
          >
            Reset
          </button>
          <button
            className="secondary-action danger-action"
            disabled={actionState.saveDisabled}
            onClick={onOverwriteCurrent}
            type="button"
          >
            Overwrite current version
          </button>
          <button
            className="primary-action"
            disabled={actionState.saveDisabled}
            onClick={onSaveAsNext}
            type="button"
          >
            {isBusy ? "Saving..." : "Save as next version"}
          </button>
        </div>
      </div>

      {message !== null ? <div className="settings-message">{message}</div> : null}
      {jsonError !== null ? (
        <div className="settings-error">Invalid validator JSON: {jsonError}</div>
      ) : null}
      {validationErrors.length > 0 ? (
        <div className="settings-error">{validationErrors.join(" ")}</div>
      ) : null}

      <div className="validators-editor-layout">
        <aside className="validators-editor-list" aria-label="Validator list">
          <div className="validators-editor-add-actions">
            <button
              className="secondary-action"
              disabled={actionState.jsonUnsafeActionsDisabled}
              onClick={() => addValidator("llm_questionnaire")}
              type="button"
            >
              Add validator
            </button>
            <button
              className="secondary-action"
              disabled={actionState.jsonUnsafeActionsDisabled}
              onClick={() => addValidator("automatic")}
              type="button"
            >
              Add automatic
            </button>
          </div>
          {draft.length === 0 ? (
            <div className="empty-state compact-empty-state">
              <h2>No validators configured</h2>
              <p>Add validator definitions before running validation.</p>
            </div>
          ) : (
            <div className="validator-list-items">
              {draft.map((validator, validatorIndex) => (
                <button
                  aria-pressed={selectedIndex === validatorIndex}
                  className={
                    selectedIndex === validatorIndex
                      ? "validator-list-item is-active"
                      : "validator-list-item"
                  }
                  key={`${validator.validator_id}-${validatorIndex}`}
                  disabled={actionState.jsonUnsafeActionsDisabled}
                  onClick={() => {
                    if (actionState.jsonUnsafeActionsDisabled) return;
                    setSelectedIndex(validatorIndex);
                    setJsonError(null);
                  }}
                  type="button"
                >
                  <strong>{validator.title || "(untitled)"}</strong>
                  <span>{validator.validator_id || "(new validator)"}</span>
                  <span>
                    {formatValidatorType(validator.type)} · {validator.checks.length}{" "}
                    {validator.checks.length === 1 ? "check" : "checks"}
                  </span>
                </button>
              ))}
            </div>
          )}
        </aside>

        <div className="validators-editor-detail">
          {selected === null ? (
            <ValidatorsPreview validators={[]} />
          ) : (
            <>
              <div className="validators-editor-detail-actions">
                <button
                  className="secondary-action"
                  disabled={actionState.jsonUnsafeActionsDisabled}
                  onClick={duplicateSelected}
                  type="button"
                >
                  Duplicate
                </button>
                <button
                  className="secondary-action danger-action"
                  disabled={actionState.jsonUnsafeActionsDisabled}
                  onClick={deleteSelected}
                  type="button"
                >
                  Delete
                </button>
                <div
                  aria-label="Validator edit mode"
                  className="proposal-tabs"
                  role="tablist"
                >
                  <button
                    aria-selected={viewMode === "structured"}
                    className={
                      viewMode === "structured"
                        ? "proposal-tab is-active"
                        : "proposal-tab"
                    }
                    disabled={jsonError !== null}
                    onClick={() => toggleViewMode("structured")}
                    role="tab"
                    type="button"
                  >
                    Structured
                  </button>
                  <button
                    aria-selected={viewMode === "json"}
                    className={
                      viewMode === "json" ? "proposal-tab is-active" : "proposal-tab"
                    }
                    disabled={jsonError !== null}
                    onClick={() => toggleViewMode("json")}
                    role="tab"
                    type="button"
                  >
                    JSON
                  </button>
                </div>
              </div>
              {viewMode === "json" ? (
                <label className="validator-json-field">
                  <span>Validator JSON</span>
                  <textarea
                    aria-label="Validator JSON"
                    className="validator-json-editor"
                    rows={18}
                    value={jsonText}
                    onChange={(event) => updateJson(event.target.value)}
                  />
                </label>
              ) : (
                <ValidatorEditor
                  existingValidatorIds={draft.map(
                    (validator) => validator.validator_id
                  )}
                  onChange={updateSelected}
                  validator={selected}
                />
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
