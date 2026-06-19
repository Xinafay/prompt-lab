import type { ComparisonArtifact } from "../types";
import { getCompareActionState } from "../workflowActions";
import { TooltipButton } from "./TooltipButton";

interface ComparisonViewProps {
  knownVersions: string[];
  baselineVersion: string;
  candidateVersion: string;
  comparison: ComparisonArtifact | null;
  hasValidation: boolean;
  isBusy: boolean;
  onBaselineVersionChange: (version: string) => void;
  onCandidateVersionChange: (version: string) => void;
  onCompare: () => void;
}

export function ComparisonView({
  knownVersions,
  baselineVersion,
  candidateVersion,
  comparison,
  hasValidation,
  isBusy,
  onBaselineVersionChange,
  onCandidateVersionChange,
  onCompare
}: ComparisonViewProps) {
  const sameVersion = baselineVersion === candidateVersion;
  const compareAction = getCompareActionState({
    hasComparison: comparison !== null,
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
        </div>
      )}
    </section>
  );
}
