import { useEffect, useMemo, useState } from "react";

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
  const saveDisabled =
    isBusy || !isDirty || validationErrors.length > 0 || jsonError !== null;

  useEffect(() => {
    onDraftChange(isDirty ? { validators: draft } : null);
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
    if (selected === null) return;
    const copy = duplicateValidator(
      selected,
      draft.map((validator) => validator.validator_id)
    );
    setDraftAndSelect([...draft, copy], draft.length);
  }

  function deleteSelected() {
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
    setDraft(cloneValidators(validators));
    setSelectedIndex(validators.length > 0 ? 0 : -1);
    setJsonError(null);
    setJsonText("");
    onReset();
  }

  function toggleViewMode(mode: "structured" | "json") {
    setViewMode(mode);
    setJsonError(null);
    setJsonText(selected === null ? "" : JSON.stringify(selected, null, 2));
  }

  function updateJson(value: string) {
    setJsonText(value);
    try {
      const parsed = JSON.parse(value) as ValidatorDefinition;
      updateSelected(parsed);
      setJsonError(null);
    } catch (error) {
      setJsonError(error instanceof Error ? error.message : "Invalid JSON.");
    }
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
            disabled={isBusy || !isDirty}
            onClick={resetDraft}
            type="button"
          >
            Reset
          </button>
          <button
            className="secondary-action danger-action"
            disabled={saveDisabled}
            onClick={onOverwriteCurrent}
            type="button"
          >
            Overwrite current version
          </button>
          <button
            className="primary-action"
            disabled={saveDisabled}
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
              disabled={isBusy}
              onClick={() => addValidator("llm_questionnaire")}
              type="button"
            >
              Add validator
            </button>
            <button
              className="secondary-action"
              disabled={isBusy}
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
                  onClick={() => {
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
                  disabled={isBusy}
                  onClick={duplicateSelected}
                  type="button"
                >
                  Duplicate
                </button>
                <button
                  className="secondary-action danger-action"
                  disabled={isBusy}
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
