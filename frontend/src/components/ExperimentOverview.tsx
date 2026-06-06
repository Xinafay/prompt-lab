import type { Case, VersionOverview } from "../types";

interface ExperimentOverviewProps {
  overview: VersionOverview;
  isRunning: boolean;
  onRunVersion: () => void;
}

function formatVariables(artifactCase: Case): string {
  return JSON.stringify(artifactCase.variables, null, 2);
}

export function ExperimentOverview({
  overview,
  isRunning,
  onRunVersion
}: ExperimentOverviewProps) {
  return (
    <section className="overview-grid" aria-label="Experiment overview">
      <div className="overview-header">
        <div>
          <h2>{overview.experiment.title}</h2>
          <p>{overview.experiment.description || "No description provided."}</p>
        </div>
        <button
          className="primary-action"
          disabled={isRunning}
          onClick={onRunVersion}
          type="button"
        >
          {isRunning ? "Running..." : "Run version"}
        </button>
      </div>

      <div className="overview-section">
        <div className="section-heading">
          <h3>Prompt</h3>
          <span>{overview.version}</span>
        </div>
        <pre className="code-block">{overview.prompt}</pre>
      </div>

      <div className="overview-section">
        <div className="section-heading">
          <h3>Rubric</h3>
        </div>
        <pre className="text-block">
          {overview.rubric.trim() || "No rubric found."}
        </pre>
      </div>

      <div className="overview-section overview-section-wide">
        <div className="section-heading">
          <h3>Cases</h3>
          <span>{overview.cases.length}</span>
        </div>
        <div className="case-list">
          {overview.cases.map((artifactCase) => (
            <article className="case-row" key={artifactCase.id}>
              <div>
                <h4>{artifactCase.title}</h4>
                <p>{artifactCase.id}</p>
              </div>
              <pre>{formatVariables(artifactCase)}</pre>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
