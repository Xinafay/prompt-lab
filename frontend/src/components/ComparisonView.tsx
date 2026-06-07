import type { ComparisonArtifact } from "../types";

interface ComparisonViewProps {
  knownVersions: string[];
  baselineVersion: string;
  candidateVersion: string;
  comparison: ComparisonArtifact | null;
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
  isBusy,
  onBaselineVersionChange,
  onCandidateVersionChange,
  onCompare
}: ComparisonViewProps) {
  return (
    <section className="comparison-panel" aria-label="Comparison">
      <div className="section-heading">
        <h3>Comparison</h3>
        <button className="secondary-action" disabled={isBusy} onClick={onCompare} type="button">
          {isBusy ? "Comparing..." : "Compare versions"}
        </button>
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

      {comparison === null ? (
        <div className="empty-inline">
          No comparison report. Run both versions before comparing.
        </div>
      ) : (
        <div className="comparison-report">
          <div className="review-summary">
            <h4>Recommendation</h4>
            <p>{comparison.recommendation}</p>
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
