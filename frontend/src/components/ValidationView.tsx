import { useMemo } from "react";

import type {
  ValidationCheckResult,
  ValidationResult,
  ValidationState,
  ValidatorDefinition
} from "../types";
import { TooltipButton } from "./TooltipButton";
export { buildValidationInclusionUpdate } from "./validationInclusion";

interface ValidationViewProps {
  validationState: ValidationState | null;
  isBusy: boolean;
  hasRuns: boolean;
  hasUnsavedChanges: boolean;
  validateDisabled: boolean;
  validateDisabledReason: string | null;
  validateLabel: string;
  onValidate: () => void;
  onStateChange: (state: ValidationState) => void;
  onSaveInclusion: () => void;
}

function validatorTitle(
  validators: Map<string, ValidatorDefinition>,
  result: ValidationResult
): string {
  return validators.get(result.validator_id)?.title ?? result.validator_id;
}

function checkTitle(
  validators: Map<string, ValidatorDefinition>,
  result: ValidationResult,
  check: ValidationCheckResult
): string {
  const validator = validators.get(result.validator_id);
  const definition = validator?.checks.find(
    (candidate) => candidate.check_id === check.check_id
  );
  return definition?.title ?? check.check_id;
}

function checkDescription(
  validators: Map<string, ValidatorDefinition>,
  result: ValidationResult,
  check: ValidationCheckResult
): string {
  const validator = validators.get(result.validator_id);
  const definition = validator?.checks.find(
    (candidate) => candidate.check_id === check.check_id
  );
  return definition?.description ?? "";
}

function formatTimestamp(value: string | null | undefined): string {
  if (value === null || value === undefined || value.trim() === "") {
    return "not finished";
  }
  return value;
}

export function ValidationView({
  validationState,
  isBusy,
  hasRuns,
  hasUnsavedChanges,
  validateDisabled,
  validateDisabledReason,
  validateLabel,
  onValidate,
  onStateChange,
  onSaveInclusion
}: ValidationViewProps) {
  const validators = useMemo(() => {
    return new Map(
      (validationState?.validators ?? []).map((validator) => [
        validator.validator_id,
        validator
      ])
    );
  }, [validationState]);

  function updateResult(resultId: string, included: boolean) {
    if (validationState === null) return;
    onStateChange({
      ...validationState,
      results: validationState.results.map((result) =>
        result.validation_result_id === resultId
          ? { ...result, included_in_judge: included }
          : result
      )
    });
  }

  function updateCheck(resultId: string, checkId: string, included: boolean) {
    if (validationState === null) return;
    onStateChange({
      ...validationState,
      results: validationState.results.map((result) =>
        result.validation_result_id === resultId
          ? {
              ...result,
              check_results: result.check_results.map((check) =>
                check.check_id === checkId
                  ? { ...check, included_in_judge: included }
                  : check
              )
            }
          : result
      )
    });
  }

  const batch = validationState?.validation_batch ?? null;

  return (
    <section className="validation-panel" aria-label="Validation">
      <div className="section-heading">
        <h3>Validation</h3>
        <div className="section-actions">
          <TooltipButton
            className="secondary-action"
            disabled={validateDisabled}
            disabledReason={validateDisabledReason}
            onClick={onValidate}
            type="button"
          >
            {validateLabel}
          </TooltipButton>
          <TooltipButton
            className="secondary-action"
            disabled={isBusy || !hasUnsavedChanges || validationState === null}
            disabledReason={
              isBusy
                ? "Wait for the current workflow action to finish."
                : "Change validation inclusion before saving."
            }
            onClick={onSaveInclusion}
            type="button"
          >
            Save inclusion
          </TooltipButton>
        </div>
      </div>

      {validationState === null ? (
        <div className="empty-inline">
          {hasRuns
            ? "No validation loaded. Validate the active run to review evidence."
            : "No validation loaded. Run this version before validating."}
        </div>
      ) : (
        <div className="validation-content">
          <div className="validation-summary">
            <div>
              <span>Status</span>
              <strong>{batch?.status}</strong>
            </div>
            <div>
              <span>Results</span>
              <strong>
                {batch?.completed_results}/{batch?.total_results}
              </strong>
            </div>
            <div>
              <span>Validator model</span>
              <strong>{batch?.validator_model}</strong>
            </div>
            <div>
              <span>Finished</span>
              <strong>{formatTimestamp(batch?.finished_at)}</strong>
            </div>
          </div>

          {hasUnsavedChanges ? (
            <div className="validation-unsaved">
              Unsaved validation inclusion changes.
            </div>
          ) : null}

          {validationState.results.length === 0 ? (
            <div className="empty-inline">
              This validation batch has no result artifacts.
            </div>
          ) : (
            <div className="validation-results">
              {validationState.results.map((result) => (
                <article
                  className="validation-card"
                  key={result.validation_result_id}
                >
                  <div className="validation-card-header">
                    <label className="validation-include-control">
                      <input
                        checked={result.included_in_judge}
                        disabled={isBusy}
                        onChange={(event) =>
                          updateResult(
                            result.validation_result_id,
                            event.currentTarget.checked
                          )
                        }
                        type="checkbox"
                      />
                      <span>Include result</span>
                    </label>
                    <div className="validation-card-title">
                      <strong>
                        {validatorTitle(validators, result)}
                      </strong>
                      <span>
                        {result.case_id} · repeat {result.repeat_index} ·{" "}
                        {result.validator_type}
                      </span>
                    </div>
                    <span
                      className={`validation-status validation-status-${result.status}`}
                    >
                      {result.status}
                    </span>
                  </div>

                  {result.execution_error ? (
                    <div className="validation-error">{result.execution_error}</div>
                  ) : null}

                  {result.check_results.length === 0 ? (
                    <div className="validation-empty-checks">
                      No check results were saved for this validator result.
                    </div>
                  ) : (
                    <div className="validation-checks">
                      {result.check_results.map((check) => {
                        const description = checkDescription(
                          validators,
                          result,
                          check
                        );
                        return (
                          <div className="validation-check" key={check.check_id}>
                            <label className="validation-include-control">
                              <input
                                checked={check.included_in_judge}
                                disabled={isBusy}
                                onChange={(event) =>
                                  updateCheck(
                                    result.validation_result_id,
                                    check.check_id,
                                    event.currentTarget.checked
                                  )
                                }
                                type="checkbox"
                              />
                              <span>Include check</span>
                            </label>
                            <div className="validation-check-body">
                              <div className="validation-check-heading">
                                <strong>
                                  {checkTitle(validators, result, check)}
                                </strong>
                                <span
                                  className={`verdict-pill verdict-${check.verdict}`}
                                >
                                  {check.verdict}
                                </span>
                              </div>
                              {description.trim() ? (
                                <p className="validation-check-description">
                                  {description}
                                </p>
                              ) : null}
                              {check.comment.trim() ? (
                                <p className="validation-check-comment">
                                  {check.comment}
                                </p>
                              ) : null}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </article>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
