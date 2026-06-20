import {
  Fragment,
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";

import type {
  RunArtifact,
  ValidationResult,
  ValidationState
} from "../types";
import { MatrixItem } from "./MatrixItem";
import { TooltipButton } from "./TooltipButton";
import {
  buildValidationMatrix,
  setValidationInclusion,
  type InclusionScope,
  type ValidationMatrixCell,
  type ValidationMatrixCheckRow
} from "./validationMatrix";
export { buildValidationInclusionUpdate } from "./validationInclusion";

interface ValidationViewProps {
  validationState: ValidationState | null;
  runs: RunArtifact[];
  isBusy: boolean;
  hasRuns: boolean;
  hasUnsavedChanges: boolean;
  onStateChange: (state: ValidationState) => void;
  onSaveInclusion: () => void;
}

interface InclusionState {
  checked: boolean;
  indeterminate: boolean;
  disabled: boolean;
}

interface SelectedCell {
  row: ValidationMatrixCheckRow;
  cell: ValidationMatrixCell;
}

function formatTimestamp(value: string | null | undefined): string {
  if (value === null || value === undefined || value.trim() === "") {
    return "not finished";
  }
  return value;
}

function inclusionState(
  cells: ValidationMatrixCell[],
  isBusy: boolean
): InclusionState {
  const targets = cells.filter(
    (cell) => cell.result !== null && cell.check !== null
  );
  const included = targets.filter((cell) => cell.included_in_judge).length;
  return {
    checked: targets.length > 0 && included === targets.length,
    indeterminate: included > 0 && included < targets.length,
    disabled: isBusy || targets.length === 0
  };
}

function aggregateStatus(cells: ValidationMatrixCell[]): {
  className: string;
  label: string;
} {
  if (cells.length === 0) {
    return { className: "compare-cell-empty", label: "empty" };
  }
  const missingOrError = cells.filter(
    (cell) => cell.verdict === "missing" || cell.verdict === "error"
  ).length;
  const failed = cells.filter((cell) => cell.verdict === "no").length;
  const unknown = cells.filter((cell) => cell.verdict === "unknown").length;
  if (missingOrError > 0 || failed > 0) {
    return {
      className: "compare-cell-fail",
      label: `${missingOrError + failed} fail`
    };
  }
  if (unknown > 0) {
    return {
      className: "compare-cell-mixed",
      label: `${unknown} unknown`
    };
  }
  return { className: "compare-cell-pass", label: "pass" };
}

function outputText(run: RunArtifact | null | undefined): string {
  if (run === null || run === undefined) {
    return "No run artifact is loaded for this validation result.";
  }
  if (run.output_text !== null && run.output_text !== undefined) {
    return run.output_text;
  }
  if (run.output_json !== undefined) {
    return JSON.stringify(run.output_json, null, 2);
  }
  if (run.raw_output !== null && run.raw_output !== undefined) {
    return run.raw_output;
  }
  if (run.validation_error !== null && run.validation_error !== undefined) {
    return run.validation_error;
  }
  if (run.execution_error !== null && run.execution_error !== undefined) {
    return run.execution_error;
  }
  return "This run artifact has no saved output.";
}

function snippet(value: string, limit = 180): string {
  const compact = value.replace(/\s+/g, " ").trim();
  if (compact.length <= limit) return compact;
  return `${compact.slice(0, limit - 1)}...`;
}

function verdictLabel(value: ValidationMatrixCell["verdict"]): string {
  return value === "yes"
    ? "yes"
    : value === "no"
      ? "no"
      : value === "unknown"
        ? "unknown"
        : value;
}

function validatorTypeLabel(
  value: ValidationMatrixCheckRow["validator_type"]
): string {
  if (value === "llm_questionnaire") return "LLM questionnaire";
  if (value === "automatic") return "Automatic";
  return value;
}

function MatrixCheckbox({
  label,
  title,
  state,
  onChange
}: {
  label: string;
  title: string;
  state: InclusionState;
  onChange: (included: boolean) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (inputRef.current !== null) {
      inputRef.current.indeterminate = state.indeterminate;
    }
  }, [state.indeterminate]);

  return (
    <label
      className="validation-matrix-checkbox"
      onClick={(event) => event.stopPropagation()}
      title={title}
    >
      <input
        aria-label={label}
        checked={state.checked}
        disabled={state.disabled}
        onChange={(event) => onChange(event.currentTarget.checked)}
        onClick={(event) => event.stopPropagation()}
        ref={inputRef}
        type="checkbox"
      />
      <span className="validation-checkbox-tooltip" role="tooltip">
        {title}
      </span>
    </label>
  );
}

function resultTitle(result: ValidationResult | null): string {
  if (result === null) return "Missing validation result";
  return `${result.case_id} / repeat ${result.repeat_index}`;
}

function validationComment(cell: ValidationMatrixCell): string {
  return cell.comment.trim()
    ? cell.comment
    : "No validation comment was saved for this check.";
}

export function ValidationView({
  validationState,
  runs,
  isBusy,
  hasRuns,
  hasUnsavedChanges,
  onStateChange,
  onSaveInclusion
}: ValidationViewProps) {
  const [selectedCell, setSelectedCell] = useState<SelectedCell | null>(null);
  const matrix = useMemo(
    () => (validationState === null ? null : buildValidationMatrix(validationState)),
    [validationState]
  );
  const runsById = useMemo(
    () => new Map(runs.map((run) => [run.run_id, run])),
    [runs]
  );
  const batch = validationState?.validation_batch ?? null;

  function updateInclusion(scope: InclusionScope, included: boolean) {
    if (validationState === null) return;
    onStateChange(setValidationInclusion(validationState, scope, included));
  }

  const allCells = matrix?.rows.flatMap((row) => row.cells) ?? [];
  const allStatus = aggregateStatus(allCells);

  return (
    <section className="validation-panel" aria-label="Validation">
      <div className="section-heading">
        <h3>Validation</h3>
        <div className="section-actions">
          <span
            className={
              hasUnsavedChanges
                ? "validation-unsaved-inline"
                : "validation-unsaved-inline validation-unsaved-inline-hidden"
            }
          >
            Unsaved inclusion changes.
          </span>
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

      {validationState === null || matrix === null ? (
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

          {matrix.rows.length === 0 || matrix.columns.length === 0 ? (
            <div className="empty-inline">
              This validation batch has no result artifacts.
            </div>
          ) : (
            <div className="validation-matrix-wrap">
              <table className="validation-matrix">
                <thead>
                  <tr>
                    <th className="validation-matrix-corner" scope="col">
                      <MatrixItem
                        badge={
                          <span
                            className={`validation-aggregate-pill ${allStatus.className}`}
                          >
                            {allStatus.label}
                          </span>
                        }
                        meta={`${matrix.rows.length} checks · ${matrix.columns.length} outputs`}
                        title="Validation matrix"
                      />
                    </th>
                    {matrix.columns.map((column) => {
                      const columnCells = matrix.rows.map(
                        (row) =>
                          row.cells.find((cell) => cell.columnKey === column.key)!
                      );
                      const columnStatus = aggregateStatus(columnCells);
                      return (
                        <th key={column.key} scope="col">
                          <MatrixItem
                            badge={
                              <span
                                className={`validation-aggregate-pill ${columnStatus.className}`}
                              >
                                {columnStatus.label}
                              </span>
                            }
                            checkbox={
                              <MatrixCheckbox
                                label={`Include ${column.title} in judge`}
                                onChange={(included) =>
                                  updateInclusion(
                                    { kind: "column", columnKey: column.key },
                                    included
                                  )
                                }
                                state={inclusionState(columnCells, isBusy)}
                                title="Include or exclude this case/run in judge"
                              />
                            }
                            meta={`repeat ${column.repeat_index}`}
                            title={column.case_id}
                          />
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {matrix.rows.map((row, rowIndex) => {
                    const previous = matrix.rows[rowIndex - 1];
                    const startsValidator =
                      previous === undefined ||
                      previous.validator_id !== row.validator_id;
                    const validatorRows = matrix.rows.filter(
                      (candidate) =>
                        candidate.validator_id === row.validator_id
                    );
                    const validatorCells = validatorRows.flatMap(
                      (candidate) => candidate.cells
                    );
                    const validatorStatus = aggregateStatus(validatorCells);
                    return (
                      <Fragment key={row.key}>
                        {startsValidator ? (
                          <tr
                            className="validation-validator-row"
                            key={`${row.validator_id}-group`}
                          >
                            <th scope="row">
                              <MatrixItem
                                badge={
                                  <span
                                    className={`validation-aggregate-pill ${validatorStatus.className}`}
                                  >
                                    {validatorStatus.label}
                                  </span>
                                }
                                checkbox={
                                  <MatrixCheckbox
                                    label={`Include ${row.validator_title} validator in judge`}
                                    onChange={(included) =>
                                      updateInclusion(
                                        {
                                          kind: "validator",
                                          validatorId: row.validator_id
                                        },
                                        included
                                      )
                                    }
                                    state={inclusionState(
                                      validatorCells,
                                      isBusy
                                    )}
                                    title="Include or exclude all checks from this validator in judge"
                                  />
                                }
                                meta={validatorTypeLabel(row.validator_type)}
                                title={row.validator_title}
                              />
                            </th>
                            <td colSpan={matrix.columns.length}>
                              <MatrixItem
                                description={row.validator_description}
                                meta={`${validatorRows.length} checks`}
                              />
                            </td>
                          </tr>
                        ) : null}
                        <tr className="validation-check-row" key={row.key}>
                          <th scope="row">
                            <MatrixItem
                              badge={
                                <span
                                  className={`validation-aggregate-pill ${
                                    aggregateStatus(row.cells).className
                                  }`}
                                >
                                  {aggregateStatus(row.cells).label}
                                </span>
                              }
                              checkbox={
                                <MatrixCheckbox
                                  label={`Include ${row.check_title} check in judge`}
                                  onChange={(included) =>
                                    updateInclusion(
                                      { kind: "row", rowKey: row.key },
                                      included
                                    )
                                  }
                                  state={inclusionState(row.cells, isBusy)}
                                  title="Include or exclude this check in judge"
                                />
                              }
                              description={row.check_description}
                              title={row.check_title}
                            />
                          </th>
                          {row.cells.map((cell) => {
                            return (
                              <td
                                className={
                                  cell.included_in_judge
                                    ? "validation-matrix-cell"
                                    : "validation-matrix-cell validation-matrix-cell-excluded"
                                }
                                key={cell.key}
                                onClick={() => setSelectedCell({ row, cell })}
                                onKeyDown={(event) => {
                                  if (
                                    event.key === "Enter" ||
                                    event.key === " "
                                  ) {
                                    event.preventDefault();
                                    setSelectedCell({ row, cell });
                                  }
                                }}
                                role="button"
                                tabIndex={0}
                                title="Click to view run output and validation details"
                              >
                                <MatrixItem
                                  badge={
                                    <span
                                      className={`verdict-pill verdict-${cell.verdict}`}
                                    >
                                      {verdictLabel(cell.verdict)}
                                    </span>
                                  }
                                  checkbox={
                                    <MatrixCheckbox
                                      label={`Include ${row.check_title} for ${resultTitle(
                                        cell.result
                                      )} in judge`}
                                      onChange={(included) =>
                                        updateInclusion(
                                          {
                                            kind: "cell",
                                            rowKey: row.key,
                                            columnKey: cell.columnKey
                                          },
                                          included
                                        )
                                      }
                                      state={{
                                        checked: cell.included_in_judge,
                                        indeterminate: false,
                                        disabled:
                                          isBusy ||
                                          cell.result === null ||
                                          cell.check === null
                                      }}
                                      title="Include or exclude this check result in judge"
                                    />
                                  }
                                  description={snippet(validationComment(cell))}
                                />
                              </td>
                            );
                          })}
                        </tr>
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
              <p className="validation-matrix-note">
                Click a cell to view run output and validation details.
              </p>
            </div>
          )}
        </div>
      )}

      {selectedCell !== null ? (
        <ValidationCellModal
          cell={selectedCell.cell}
          onClose={() => setSelectedCell(null)}
          row={selectedCell.row}
          run={
            selectedCell.cell.result === null
              ? null
              : runsById.get(selectedCell.cell.result.run_id) ?? null
          }
        />
      ) : null}
    </section>
  );
}

function ValidationCellModal({
  row,
  cell,
  run,
  onClose
}: {
  row: ValidationMatrixCheckRow;
  cell: ValidationMatrixCell;
  run: RunArtifact | null;
  onClose: () => void;
}) {
  const text = outputText(run);
  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div
        aria-modal="true"
        className="validation-detail-modal"
        onMouseDown={(event) => event.stopPropagation()}
        role="dialog"
      >
        <div className="validation-detail-header">
          <div>
            <h2>{row.check_title}</h2>
            <p>
              {row.validator_title} · {resultTitle(cell.result)}
            </p>
          </div>
          <span className={`verdict-pill verdict-${cell.verdict}`}>
            {verdictLabel(cell.verdict)}
          </span>
        </div>

        <section>
          <h3>Run output</h3>
          <pre>{text}</pre>
        </section>

        <section>
          <h3>Validation comment</h3>
          <p>{validationComment(cell)}</p>
        </section>

        <section>
          <h3>Check</h3>
          <p>{row.check_description || "No check description was saved."}</p>
        </section>

        <div className="modal-actions">
          <button className="secondary-action" onClick={onClose} type="button">
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
