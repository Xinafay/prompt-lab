import { Fragment, useMemo, useState } from "react";

import type {
  CompareMatrixCell,
  CompareMatrixResponse,
  CompareMatrixRow
} from "../types";
import { getCompareActionState } from "../workflowActions";
import { MatrixItem } from "./MatrixItem";
import { TooltipButton } from "./TooltipButton";

interface ComparisonViewProps {
  knownVersions: string[];
  baselineVersion: string;
  candidateVersion: string;
  comparison: CompareMatrixResponse | null;
  hasUnsavedValidationChanges: boolean;
  hasValidation: boolean;
  isBusy: boolean;
  showHeader?: boolean;
  onBaselineVersionChange: (version: string) => void;
  onCandidateVersionChange: (version: string) => void;
  onCompare: () => void;
}

interface SelectedCompareCell {
  row: CompareMatrixRow;
  cell: CompareMatrixCell;
}

function emptyCell(version: string): CompareMatrixCell {
  return {
    version,
    status: "empty",
    grade_5: 0,
    grade_4: 0,
    grade_3: 0,
    grade_2: 0,
    grade_1: 0,
    not_assessable: 0,
    missing: 0,
    error: 0,
    total: 0,
    details: []
  };
}

function cellForVersion(row: CompareMatrixRow, version: string): CompareMatrixCell {
  return row.cells.find((cell) => cell.version === version) ?? emptyCell(version);
}

function statusLabel(cell: CompareMatrixCell): string {
  if (cell.total === 0) return "empty";
  if (cell.status === "pass") return "pass";
  if (cell.status === "fail") return `${cell.grade_1 + cell.grade_2} low`;
  if (cell.error > 0) return `${cell.error} error`;
  if (cell.not_assessable > 0) return `${cell.not_assessable} n/a`;
  if (cell.grade_3 > 0) return `${cell.grade_3} mixed`;
  return "mixed";
}

function aggregateCompareStatus(cells: CompareMatrixCell[]): {
  className: string;
  label: string;
} {
  if (cells.length === 0) {
    return { className: "compare-cell-empty", label: "empty" };
  }
  const nonEmpty = cells.filter((cell) => cell.total > 0);
  if (nonEmpty.length === 0) {
    return { className: "compare-cell-empty", label: "empty" };
  }
  const failed = nonEmpty.filter((cell) => cell.status === "fail").length;
  const mixed = nonEmpty.filter((cell) => cell.status === "mixed").length;
  const empty = cells.length - nonEmpty.length;
  if (failed > 0) {
    return { className: "compare-cell-fail", label: `${failed} fail` };
  }
  if (mixed > 0) {
    return { className: "compare-cell-mixed", label: `${mixed} mixed` };
  }
  if (empty > 0) {
    return { className: "compare-cell-mixed", label: `${empty} empty` };
  }
  return { className: "compare-cell-pass", label: "pass" };
}

function detailSnippet(cell: CompareMatrixCell): string {
  const failing = cell.details.find(
    (detail) =>
      detail.status === "error" || detail.grade === 1 || detail.grade === 2
  );
  const mixed = cell.details.find(
    (detail) => detail.grade === 3 || detail.status === "not_assessable"
  );
  const candidate = failing ?? mixed ?? cell.details[0] ?? null;
  if (candidate === null || candidate.comment.trim() === "") {
    if (cell.total === 0) return "No included validation evidence.";
    return "No comment was saved for this evidence.";
  }
  return snippet(candidate.comment);
}

function snippet(value: string, limit = 150): string {
  const compact = value.replace(/\s+/g, " ").trim();
  if (compact.length <= limit) return compact;
  return `${compact.slice(0, limit - 1)}...`;
}

function countSummary(cell: CompareMatrixCell): string {
  if (cell.total === 0) return "0 included checks";
  const parts: string[] = [];
  if (cell.grade_5 > 0) parts.push(`${cell.grade_5} grade 5`);
  if (cell.grade_4 > 0) parts.push(`${cell.grade_4} grade 4`);
  if (cell.grade_3 > 0) parts.push(`${cell.grade_3} grade 3`);
  if (cell.grade_2 > 0) parts.push(`${cell.grade_2} grade 2`);
  if (cell.grade_1 > 0) parts.push(`${cell.grade_1} grade 1`);
  if (cell.not_assessable > 0) parts.push(`${cell.not_assessable} n/a`);
  if (cell.error > 0) parts.push(`${cell.error} error`);
  if (cell.missing > 0) parts.push(`${cell.missing} missing`);
  return parts.join(" · ");
}

function detailLabel(
  detail: CompareMatrixCell["details"][number]
): string {
  if (detail.status === "error") return "error";
  if (detail.grade === null) return "n/a";
  return `grade ${detail.grade}`;
}

export function ComparisonView({
  knownVersions,
  baselineVersion,
  candidateVersion,
  comparison,
  hasUnsavedValidationChanges,
  hasValidation,
  isBusy,
  showHeader = true,
  onBaselineVersionChange,
  onCandidateVersionChange,
  onCompare
}: ComparisonViewProps) {
  const [selectedCell, setSelectedCell] = useState<SelectedCompareCell | null>(
    null
  );
  const sameVersion = baselineVersion === candidateVersion;
  const compareAction = getCompareActionState({
    hasComparison: comparison !== null,
    hasUnsavedValidationChanges,
    hasValidation,
    isBusy,
    sameVersion,
    versionCount: knownVersions.length
  });
  const allCells = useMemo(
    () => comparison?.rows.flatMap((row) => row.cells) ?? [],
    [comparison]
  );
  const allStatus = aggregateCompareStatus(allCells);

  return (
    <section className="comparison-panel" aria-label="Comparison">
      {showHeader ? (
        <div className="section-heading">
          <h3>Comparison</h3>
          <TooltipButton
            className="secondary-action"
            disabled={compareAction.disabled}
            disabledReason={compareAction.disabledReason}
            onClick={onCompare}
            type="button"
          >
            {compareAction.label}
          </TooltipButton>
        </div>
      ) : null}
      <div className="comparison-controls">
        <label>
          Baseline
          <select
            disabled={isBusy}
            onChange={(event) => onBaselineVersionChange(event.currentTarget.value)}
            value={baselineVersion}
          >
            {knownVersions.map((version) => (
              <option key={version} value={version}>
                {version}
              </option>
            ))}
          </select>
        </label>
        <label>
          Candidate
          <select
            disabled={isBusy}
            onChange={(event) => onCandidateVersionChange(event.currentTarget.value)}
            value={candidateVersion}
          >
            {knownVersions.map((version) => (
              <option key={version} value={version}>
                {version}
              </option>
            ))}
          </select>
        </label>
      </div>

      {compareAction.note !== null ? (
        <div className="comparison-note">{compareAction.note}</div>
      ) : null}

      {comparison === null ? (
        <div className="empty-inline">{compareAction.emptyMessage}</div>
      ) : (
        <div className="comparison-report">
          <div className="review-summary">
            <h4>Compare matrix</h4>
            <p>
              Compared {comparison.versions.length} version
              {comparison.versions.length === 1 ? "" : "s"} across{" "}
              {comparison.rows.length} validation check
              {comparison.rows.length === 1 ? "" : "s"}.
            </p>
            <p className="muted-copy">{comparison.versions.join(" vs ")}</p>
          </div>
          {comparison.rows.length === 0 ? (
            <div className="empty-inline">
              No included validation checks were available for comparison.
            </div>
          ) : (
            <div className="validation-matrix-wrap comparison-matrix-wrap">
              <table className="validation-matrix comparison-matrix">
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
                        meta={`${comparison.rows.length} checks · ${comparison.versions.length} versions`}
                        title="Compare matrix"
                      />
                    </th>
                    {comparison.versions.map((version) => {
                      const columnCells = comparison.rows.map((row) =>
                        cellForVersion(row, version)
                      );
                      const columnStatus = aggregateCompareStatus(columnCells);
                      const evidenceCount = columnCells.reduce(
                        (sum, cell) => sum + cell.total,
                        0
                      );
                      return (
                        <th key={version} scope="col">
                          <MatrixItem
                            badge={
                              <span
                                className={`validation-aggregate-pill ${columnStatus.className}`}
                              >
                                {columnStatus.label}
                              </span>
                            }
                            meta={`${evidenceCount} included results`}
                            title={version}
                          />
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {comparison.rows.map((row, rowIndex) => {
                    const previous = comparison.rows[rowIndex - 1];
                    const startsValidator =
                      previous === undefined ||
                      previous.validator_id !== row.validator_id;
                    const validatorRows = comparison.rows.filter(
                      (candidate) => candidate.validator_id === row.validator_id
                    );
                    const validatorCells = validatorRows.flatMap(
                      (candidate) => candidate.cells
                    );
                    const validatorStatus =
                      aggregateCompareStatus(validatorCells);
                    const validatorEvidenceCount = validatorCells.reduce(
                      (sum, cell) => sum + cell.total,
                      0
                    );
                    return (
                      <Fragment key={`${row.validator_id}:${row.check_id}`}>
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
                                meta={`${validatorRows.length} checks`}
                                title={row.validator_title}
                              />
                            </th>
                            <td colSpan={comparison.versions.length}>
                              <MatrixItem
                                meta={`${validatorEvidenceCount} included results across versions`}
                              />
                            </td>
                          </tr>
                        ) : null}
                        <tr className="validation-check-row">
                          <th scope="row">
                            <MatrixItem
                              badge={
                                <span
                                  className={`validation-aggregate-pill ${
                                    aggregateCompareStatus(row.cells).className
                                  }`}
                                >
                                  {aggregateCompareStatus(row.cells).label}
                                </span>
                              }
                              description={row.check_description}
                              title={row.check_title}
                            />
                          </th>
                          {comparison.versions.map((version) => {
                            const cell = cellForVersion(row, version);
                            return (
                              <td
                                className={`validation-matrix-cell comparison-matrix-cell comparison-matrix-cell-${cell.status}`}
                                key={version}
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
                                title="Click to view comparison evidence"
                              >
                                <MatrixItem
                                  badge={
                                    <span
                                      className={`verdict-pill compare-cell-${cell.status}`}
                                    >
                                      {statusLabel(cell)}
                                    </span>
                                  }
                                  description={detailSnippet(cell)}
                                  meta={countSummary(cell)}
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
                Click a cell to view included case/repeat evidence.
              </p>
            </div>
          )}
        </div>
      )}

      {selectedCell !== null ? (
        <CompareCellModal
          cell={selectedCell.cell}
          onClose={() => setSelectedCell(null)}
          row={selectedCell.row}
        />
      ) : null}
    </section>
  );
}

function CompareCellModal({
  row,
  cell,
  onClose
}: {
  row: CompareMatrixRow;
  cell: CompareMatrixCell;
  onClose: () => void;
}) {
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
              {row.validator_title} · {cell.version}
            </p>
          </div>
          <span className={`verdict-pill compare-cell-${cell.status}`}>
            {statusLabel(cell)}
          </span>
        </div>

        <section>
          <h3>Summary</h3>
          <p>{countSummary(cell)}</p>
        </section>

        <section>
          <h3>Evidence</h3>
          {cell.details.length === 0 ? (
            <p>No included validation evidence was available for this cell.</p>
          ) : (
            <div className="compare-cell-details">
              {cell.details.map((detail, index) => (
                <div
                  className="compare-cell-detail"
                  key={`${detail.validation_result_id}:${detail.case_id}:${detail.repeat_index}:${detail.status}:${detail.grade ?? "na"}:${index}`}
                >
                  <strong>{detailLabel(detail)}</strong>
                  <span>
                    {detail.case_id} · repeat {detail.repeat_index}
                  </span>
                  {detail.comment.trim() ? <p>{detail.comment}</p> : null}
                </div>
              ))}
            </div>
          )}
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
