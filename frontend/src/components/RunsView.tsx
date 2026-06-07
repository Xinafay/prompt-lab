import type { Case, RunArtifact } from "../types";

interface RunsViewProps {
  cases: Case[];
  runBatchId: string | null;
  runs: RunArtifact[];
}

function outputPreview(run: RunArtifact): string {
  if (run.status === "execution_error") {
    return run.execution_error || "Execution error";
  }
  if (run.status === "validation_error") {
    return run.validation_error || "Validation error";
  }
  if (run.output_type === "pydantic") {
    return JSON.stringify(run.output_json, null, 2);
  }
  return run.output_text || run.raw_output || "";
}

function statusLabel(run: RunArtifact): string {
  if (run.status === "ok") {
    return "Valid";
  }
  if (run.status === "validation_error") {
    return "Validation error";
  }
  return "Execution error";
}

export function RunsView({ cases, runBatchId, runs }: RunsViewProps) {
  const caseTitles = new Map(
    cases.map((artifactCase) => [artifactCase.id, artifactCase.title])
  );

  return (
    <section className="runs-panel" aria-label="Run results">
      <div className="section-heading">
        <h3>Runs</h3>
        <span>{runBatchId ?? "No run batch"}</span>
      </div>

      {runs.length === 0 ? (
        <div className="empty-inline">
          No run artifacts yet. Run this version to create run artifacts.
        </div>
      ) : (
        <div className="runs-table-wrap">
          <table className="runs-table">
            <thead>
              <tr>
                <th>Case</th>
                <th>Repeat</th>
                <th>Status</th>
                <th>Validation</th>
                <th>Output preview</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.run_id}>
                  <td>
                    <strong>{caseTitles.get(run.case_id) ?? run.case_id}</strong>
                    <span>{run.case_id}</span>
                  </td>
                  <td>{run.repeat_index}</td>
                  <td>
                    <span className={`status-pill status-${run.status}`}>
                      {run.status}
                    </span>
                  </td>
                  <td>{statusLabel(run)}</td>
                  <td>
                    <pre>{outputPreview(run)}</pre>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
