import type { ComparisonArtifact } from "../types";
import { getCompareActionState } from "../workflowActions";
import { TooltipButton } from "./TooltipButton";

interface ComparisonViewProps {
  knownVersions: string[];
  baselineVersion: string;
  candidateVersion: string;
  comparison: ComparisonArtifact | null;
  hasRuns: boolean;
  isBusy: boolean;
  onBaselineVersionChange: (version: string) => void;
  onCandidateVersionChange: (version: string) => void;
  onCompare: () => void;
}

function ComparisonList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="comparison-list">
      <h4>{title}</h4>
      {items.length === 0 ? (
        <p className="muted-copy">None.</p>
      ) : (
        <ul>
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function ComparisonView({
  knownVersions,
  baselineVersion,
  candidateVersion,
  comparison,
  hasRuns,
  isBusy,
  onBaselineVersionChange,
  onCandidateVersionChange,
  onCompare
}: ComparisonViewProps) {
  const sameVersion = baselineVersion === candidateVersion;
  const compareAction = getCompareActionState({
    hasComparison: comparison !== null,
    hasRuns,
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
            <h4>Recommendation</h4>
            <p>
              <span className="recommendation-pill">
                {comparison.recommendation}
              </span>
            </p>
            <p>{comparison.summary}</p>
          </div>
          <ComparisonList title="Improvements" items={comparison.improvements} />
          <ComparisonList title="Regressions" items={comparison.regressions} />
          <ComparisonList
            title="Unchanged problems"
            items={comparison.unchanged_problems}
          />
          <ComparisonList title="New problems" items={comparison.new_problems} />
          <ComparisonList
            title="Stability changes"
            items={comparison.stability_changes}
          />
        </div>
      )}
    </section>
  );
}
