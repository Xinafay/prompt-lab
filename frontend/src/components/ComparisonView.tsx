import type {
  CompareMatrixCell,
  CompareMatrixResponse,
  CompareMatrixRow,
} from "../types";
import { getCompareActionState } from "../workflowActions";
import { TooltipButton } from "./TooltipButton";

interface ComparisonViewProps {
  knownVersions: string[];
  baselineVersion: string;
  candidateVersion: string;
  comparison: CompareMatrixResponse | null;
  hasUnsavedValidationChanges: boolean;
  hasValidation: boolean;
  isBusy: boolean;
  onBaselineVersionChange: (version: string) => void;
  onCandidateVersionChange: (version: string) => void;
  onCompare: () => void;
}

function cellForVersion(row: CompareMatrixRow, version: string): CompareMatrixCell {
  return (
    row.cells.find((cell) => cell.version === version) ?? {
      version,
      status: "empty",
      yes: 0,
      no: 0,
      unknown: 0,
      missing: 0,
      error: 0,
      total: 0,
      details: []
    }
  );
}

export function ComparisonView({
  knownVersions,
  baselineVersion,
  candidateVersion,
  comparison,
  hasUnsavedValidationChanges,
  hasValidation,
  isBusy,
  onBaselineVersionChange,
  onCandidateVersionChange,
  onCompare
}: ComparisonViewProps) {
  const sameVersion = baselineVersion === candidateVersion;
  const compareAction = getCompareActionState({
    hasComparison: comparison !== null,
    hasUnsavedValidationChanges,
    hasValidation,
    isBusy,
    sameVersion,
    versionCount: knownVersions.length
  });

  return (
    <section className="comparison-panel" aria-label="Comparison">
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
            <div className="compare-matrix-wrap">
              <table className="compare-matrix">
                <thead>
                  <tr>
                    <th scope="col">Validator / check</th>
                    {comparison.versions.map((version) => (
                      <th key={version} scope="col">
                        {version}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {comparison.rows.map((row) => (
                    <tr key={`${row.validator_id}:${row.check_id}`}>
                      <th scope="row">
                        <strong>{row.validator_title}</strong>
                        <span>{row.check_title}</span>
                        {row.check_description.trim() ? (
                          <p>{row.check_description}</p>
                        ) : null}
                      </th>
                      {comparison.versions.map((version) => {
                        const cell = cellForVersion(row, version);
                        return (
                          <td
                            className={`compare-cell compare-cell-${cell.status}`}
                            key={version}
                          >
                            <strong>
                              {cell.yes}/{cell.total} yes
                            </strong>
                            <span>
                              {cell.no} no · {cell.unknown} unknown ·{" "}
                              {cell.error} error
                              {cell.missing > 0 ? ` · ${cell.missing} missing` : ""}
                            </span>
                            {cell.details.length > 0 ? (
                              <details>
                                <summary>Details</summary>
                                <div className="compare-cell-details">
                                  {cell.details.map((detail) => (
                                    <div
                                      className="compare-cell-detail"
                                      key={`${detail.validation_result_id}:${detail.case_id}:${detail.repeat_index}:${detail.verdict}`}
                                    >
                                      <strong>{detail.verdict}</strong>
                                      <span>
                                        {detail.case_id} · repeat{" "}
                                        {detail.repeat_index}
                                      </span>
                                      {detail.comment.trim() ? (
                                        <p>{detail.comment}</p>
                                      ) : null}
                                    </div>
                                  ))}
                                </div>
                              </details>
                            ) : null}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
