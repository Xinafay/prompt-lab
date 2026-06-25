import {
  useEffect,
  useMemo,
  type Ref,
  useRef,
  useState,
  type KeyboardEvent
} from "react";

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
import { ValidatorCard } from "./ValidatorCard";

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

function validatorModalTitle(state: ValidatorModalState): string {
  const label =
    state.validator.title || state.validator.validator_id || "new validator";
  return state.mode === "create" ? "Add validator" : `Edit validator: ${label}`;
}

function validatorsEqual(
  left: ValidatorDefinition[],
  right: ValidatorDefinition[]
): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

type ValidatorJsonParseResult =
  | { ok: true; validator: ValidatorDefinition }
  | { ok: false; error: string };

type ValidatorModalMode = "create" | "edit";
type ValidatorEditMode = "structured" | "json";

interface ValidatorModalState {
  mode: ValidatorModalMode;
  sourceIndex: number | null;
  initialValidator: ValidatorDefinition;
  validator: ValidatorDefinition;
  viewMode: ValidatorEditMode;
  jsonText: string;
  jsonError: string | null;
  discardConfirming: boolean;
}

export function updateValidatorModalStructuredState(
  state: ValidatorModalState,
  validator: ValidatorDefinition
): ValidatorModalState {
  return {
    ...state,
    validator,
    viewMode: "structured",
    jsonText: JSON.stringify(validator, null, 2),
    jsonError: null,
    discardConfirming: false
  };
}

export function switchValidatorModalViewModeState(
  state: ValidatorModalState,
  mode: ValidatorEditMode
): ValidatorModalState {
  if (state.jsonError !== null) return state;
  return {
    ...state,
    viewMode: mode,
    jsonText: JSON.stringify(state.validator, null, 2),
    jsonError: null,
    discardConfirming: false
  };
}

interface ValidatorEditModalProps {
  closeButtonRef?: Ref<HTMLButtonElement> | null;
  draftValidatorIds: string[];
  isBusy: boolean;
  modalState: ValidatorModalState;
  modalValidationErrors: string[];
  onClose: () => void;
  onDiscardEdits: () => void;
  onKeepEditing: () => void;
  onSave: () => void;
  onSwitchMode: (mode: ValidatorEditMode) => void;
  onUpdateJson: (value: string) => void;
  onUpdateValidator: (validator: ValidatorDefinition) => void;
}

export function ValidatorEditModal({
  closeButtonRef = null,
  draftValidatorIds,
  isBusy,
  modalState,
  modalValidationErrors,
  onClose,
  onDiscardEdits,
  onKeepEditing,
  onSave,
  onSwitchMode,
  onUpdateJson,
  onUpdateValidator
}: ValidatorEditModalProps) {
  const modeSwitchDisabled = isBusy || modalState.jsonError !== null;

  return (
    <div
      aria-labelledby="validators-editor-modal-title"
      aria-modal="true"
      className="validation-detail-modal validators-editor-modal"
      role="dialog"
    >
      <div className="validation-detail-header validators-editor-modal-header">
        <div>
          <h2 id="validators-editor-modal-title">{validatorModalTitle(modalState)}</h2>
          <p>
            {modalState.discardConfirming
              ? "Discard validator edits or return to the editor."
              : "Save changes here to update the local validators draft, then use the version actions to persist it."}
          </p>
        </div>
        {modalState.discardConfirming ? null : (
          <button
            ref={closeButtonRef}
            className="secondary-action"
            onClick={onClose}
            type="button"
          >
            Close
          </button>
        )}
      </div>

      {modalState.discardConfirming ? (
        <div
          className="settings-navigation-modal validators-editor-discard-confirm"
          role="alert"
        >
          <div>
            <h2>Discard unsaved validator edits?</h2>
            <p>These changes have not been applied to the local draft.</p>
          </div>
          <div className="modal-actions">
            <button className="secondary-action" onClick={onKeepEditing} type="button">
              Keep editing
            </button>
            <button
              className="secondary-action danger-action"
              onClick={onDiscardEdits}
              type="button"
            >
              Discard edits
            </button>
          </div>
        </div>
      ) : (
        <>
          <div aria-label="Validator edit mode" className="proposal-tabs" role="tablist">
            <button
              aria-selected={modalState.viewMode === "structured"}
              className={
                modalState.viewMode === "structured"
                  ? "proposal-tab is-active"
                  : "proposal-tab"
              }
              disabled={modeSwitchDisabled}
              onClick={() => onSwitchMode("structured")}
              role="tab"
              type="button"
            >
              Structured
            </button>
            <button
              aria-selected={modalState.viewMode === "json"}
              className={
                modalState.viewMode === "json"
                  ? "proposal-tab is-active"
                  : "proposal-tab"
              }
              disabled={modeSwitchDisabled}
              onClick={() => onSwitchMode("json")}
              role="tab"
              type="button"
            >
              JSON
            </button>
          </div>

          {modalState.jsonError !== null ? (
            <div className="settings-error">
              Invalid validator JSON: {modalState.jsonError}
            </div>
          ) : null}
          {modalValidationErrors.length > 0 ? (
            <div className="settings-error">{modalValidationErrors.join(" ")}</div>
          ) : null}

          <div className="validators-editor-modal-body">
            {modalState.viewMode === "json" ? (
              <label className="validator-json-field">
                <span>Validator JSON</span>
                <textarea
                  aria-label="Validator JSON"
                  className="validator-json-editor"
                  rows={18}
                  value={modalState.jsonText}
                  onChange={(event) => onUpdateJson(event.target.value)}
                />
              </label>
            ) : (
              <ValidatorEditor
                existingValidatorIds={draftValidatorIds}
                onChange={onUpdateValidator}
                validator={modalState.validator}
              />
            )}
          </div>

          <div className="modal-actions validators-editor-modal-actions">
            <button className="secondary-action" onClick={onClose} type="button">
              Cancel
            </button>
            <button
              className="primary-action"
              disabled={
                isBusy ||
                modalState.jsonError !== null ||
                modalValidationErrors.length > 0
              }
              onClick={onSave}
              type="button"
            >
              Save changes
            </button>
          </div>
        </>
      )}
    </div>
  );
}

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
  const [modalState, setModalState] = useState<ValidatorModalState | null>(null);
  const lastDraftEmissionRef = useRef(JSON.stringify(null));
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const modalReturnFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    setDraft(cloneValidators(validators));
    setModalState(null);
  }, [validators]);

  function nextDraftWithModalValidator(
    state: ValidatorModalState
  ): ValidatorDefinition[] {
    if (state.sourceIndex === null) return [...draft, state.validator];
    return draft.map((validator, index) =>
      index === state.sourceIndex ? state.validator : validator
    );
  }

  const isDirty = useMemo(() => !validatorsEqual(draft, validators), [
    draft,
    validators
  ]);
  const validationErrors = useMemo(() => validateValidatorDraft(draft), [draft]);
  const modalValidationErrors = useMemo(
    () =>
      modalState === null
        ? []
        : validateValidatorDraft(nextDraftWithModalValidator(modalState)),
    [draft, modalState]
  );
  const actionState = getValidatorEditorActionState({
    isBusy,
    isDirty,
    jsonError: null,
    validationErrorCount: validationErrors.length
  });
  const isModalOpen = modalState !== null;

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
    if (!isModalOpen) {
      if (modalReturnFocusRef.current?.isConnected) {
        modalReturnFocusRef.current.focus();
      }
      modalReturnFocusRef.current = null;
      return;
    }
    window.requestAnimationFrame(() => closeButtonRef.current?.focus());
  }, [isModalOpen]);

  function openModal(
    state: Omit<
      ValidatorModalState,
      | "initialValidator"
      | "viewMode"
      | "jsonText"
      | "jsonError"
      | "discardConfirming"
    >,
    eventTarget?: EventTarget | null
  ) {
    modalReturnFocusRef.current =
      eventTarget instanceof HTMLElement ? eventTarget : null;
    setModalState({
      ...state,
      initialValidator: cloneValidators([state.validator])[0],
      viewMode: "structured",
      jsonText: JSON.stringify(state.validator, null, 2),
      jsonError: null,
      discardConfirming: false
    });
  }

  function openCreateValidator(eventTarget?: EventTarget | null) {
    const nextValidator = createDefaultValidator(
      "llm_questionnaire",
      draft.map((validator) => validator.validator_id)
    );
    openModal(
      { mode: "create", sourceIndex: null, validator: nextValidator },
      eventTarget
    );
  }

  function openEditValidator(index: number, eventTarget?: EventTarget | null) {
    const validator = draft[index];
    if (validator === undefined) return;
    openModal(
      {
        mode: "edit",
        sourceIndex: index,
        validator: cloneValidators([validator])[0]
      },
      eventTarget
    );
  }

  function duplicateValidatorFromCard(
    index: number,
    eventTarget?: EventTarget | null
  ) {
    const validator = draft[index];
    if (validator === undefined) return;
    const copy = duplicateValidator(
      validator,
      draft.map((candidate) => candidate.validator_id)
    );
    openModal({ mode: "create", sourceIndex: null, validator: copy }, eventTarget);
  }

  function deleteValidatorFromCard(index: number) {
    if (actionState.jsonUnsafeActionsDisabled) return;
    setDraft((current) =>
      current.filter((_validator, validatorIndex) => validatorIndex !== index)
    );
  }

  function updateModalValidator(validator: ValidatorDefinition) {
    setModalState((current) =>
      current === null
        ? null
        : updateValidatorModalStructuredState(current, validator)
    );
  }

  function updateModalJson(value: string) {
    setModalState((current) => {
      if (current === null) return null;
      const result = parseValidatorJsonDraft(value);
      if (!result.ok) {
        return {
          ...current,
          jsonText: value,
          jsonError: result.error,
          discardConfirming: false
        };
      }
      return {
        ...current,
        validator: result.validator,
        jsonText: value,
        jsonError: null,
        discardConfirming: false
      };
    });
  }

  function switchModalViewMode(mode: ValidatorEditMode) {
    setModalState((current) => {
      if (current === null || current.viewMode === mode) return current;
      return switchValidatorModalViewModeState(current, mode);
    });
  }

  function saveModalValidator() {
    if (modalState === null || modalState.jsonError !== null) return;
    const nextDraft = nextDraftWithModalValidator(modalState);
    if (validateValidatorDraft(nextDraft).length > 0) return;
    setDraft(nextDraft);
    setModalState(null);
  }

  function closeModal() {
    setModalState(null);
  }

  function isModalDirty(state: ValidatorModalState): boolean {
    const initialJsonText = JSON.stringify(state.initialValidator, null, 2);
    return (
      !validatorsEqual([state.validator], [state.initialValidator]) ||
      state.jsonText !== initialJsonText
    );
  }

  function requestCloseModal() {
    if (modalState !== null && isModalDirty(modalState)) {
      setModalState({ ...modalState, discardConfirming: true });
      return;
    }
    closeModal();
  }

  function handleModalKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      requestCloseModal();
    }
    if (event.key !== "Tab") return;

    const container = event.currentTarget;
    const focusable = Array.from(
      container.querySelectorAll<HTMLElement>(
        'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [href], [tabindex]:not([tabindex="-1"])'
      )
    );
    if (focusable.length === 0) return;

    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
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
      {validationErrors.length > 0 ? (
        <div className="settings-error">{validationErrors.join(" ")}</div>
      ) : null}

      <div className="validators-overview-toolbar">
        <button
          className="secondary-action"
          disabled={actionState.jsonUnsafeActionsDisabled}
          onClick={(event) => openCreateValidator(event.currentTarget)}
          type="button"
        >
          Add validator
        </button>
      </div>

      {draft.length === 0 ? (
        <div className="empty-state compact-empty-state">
          <h2>No validators configured</h2>
          <p>Add validator definitions before running validation.</p>
        </div>
      ) : (
        <div className="validators-card-list">
          {draft.map((validator, validatorIndex) => (
            <ValidatorCard
              showActions={true}
              disabled={actionState.jsonUnsafeActionsDisabled}
              key={validatorIndex}
              onDelete={() => deleteValidatorFromCard(validatorIndex)}
              onDuplicate={(event) =>
                duplicateValidatorFromCard(validatorIndex, event.currentTarget)
              }
              onEdit={(event) =>
                openEditValidator(validatorIndex, event.currentTarget)
              }
              validator={validator}
            />
          ))}
        </div>
      )}

      {modalState !== null ? (
        <div
          className="modal-backdrop validators-editor-modal-backdrop"
          onMouseDown={requestCloseModal}
          role="presentation"
        >
          <div
            onKeyDown={handleModalKeyDown}
            onMouseDown={(event) => event.stopPropagation()}
          >
            <ValidatorEditModal
              closeButtonRef={closeButtonRef}
              draftValidatorIds={draft.map((validator) => validator.validator_id)}
              isBusy={isBusy}
              modalState={modalState}
              modalValidationErrors={modalValidationErrors}
              onClose={requestCloseModal}
              onDiscardEdits={closeModal}
              onKeepEditing={() =>
                setModalState((current) =>
                  current === null ? null : { ...current, discardConfirming: false }
                )
              }
              onSave={saveModalValidator}
              onSwitchMode={switchModalViewMode}
              onUpdateJson={updateModalJson}
              onUpdateValidator={updateModalValidator}
            />
          </div>
        </div>
      ) : null}
    </section>
  );

  function resetDraft() {
    setDraft(cloneValidators(validators));
    setModalState(null);
    onReset();
  }
}
