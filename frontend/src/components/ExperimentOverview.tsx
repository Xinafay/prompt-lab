import type { Case, VersionOverview } from "../types";
import { ValidatorsPreview } from "./ValidatorsPreview";

interface ExperimentOverviewProps {
  overview: VersionOverview;
  isRunning: boolean;
  onRunVersion: () => void;
}

function formatCaseContract(artifactCase: Case): string {
  return JSON.stringify(
    {
      bindings: artifactCase.bindings,
      stores: artifactCase.stores
    },
    null,
    2
  );
}

function summarizeCaseContract(artifactCase: Case): string {
  const bindingCount = Object.keys(artifactCase.bindings).length;
  const storeCount = Object.keys(artifactCase.stores).length;
  return `${bindingCount} binding${bindingCount === 1 ? "" : "s"} · ${storeCount} store${
    storeCount === 1 ? "" : "s"
  }`;
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

      <div className="overview-section overview-section-wide">
        <div className="section-heading">
          <h3>Validators</h3>
          <span>{(overview.validators ?? []).length}</span>
        </div>
        <ValidatorsPreview validators={overview.validators ?? []} />
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
                <p>{summarizeCaseContract(artifactCase)}</p>
              </div>
              <pre>{formatCaseContract(artifactCase)}</pre>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
