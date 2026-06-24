import { useEffect, useMemo, useState } from "react";
import type { Case, RunArtifact } from "../types";
import { CodeViewer, type CodeViewerProps } from "./CodeViewer";

interface RunsViewProps {
  cases: Case[];
  runBatchId: string | null;
  runs: RunArtifact[];
}

type RunStatusFilter = "all" | RunArtifact["status"];

const RUN_STATUS_FILTERS: RunStatusFilter[] = [
  "all",
  "ok",
  "validation_error",
  "execution_error",
];

function outputBody(run: RunArtifact): string {
  if (run.output_type === "pydantic") {
    if (run.output_json !== undefined) {
      return JSON.stringify(run.output_json, null, 2);
    }
    return "No parsed JSON output.";
  }
  return run.output_text || "No text output.";
}

function hasParsedJsonOutput(run: RunArtifact): boolean {
  return run.output_type === "pydantic" && run.output_json !== undefined;
}

function compactSummary(run: RunArtifact): string {
  if (run.status === "execution_error") {
    return run.execution_error || "Execution error";
  }
  if (run.status === "validation_error") {
    return run.validation_error || "Validation error";
  }
  if (run.output_type === "pydantic") {
    if (run.output_json && typeof run.output_json === "object") {
      const keys = Object.keys(run.output_json);
      if (keys.length > 0) {
        return `JSON object: ${keys.slice(0, 4).join(", ")}${
          keys.length > 4 ? ` +${keys.length - 4}` : ""
        }`;
      }
    }
    return "JSON output";
  }
  const text = run.output_text || run.raw_output || "";
  return text.trim().replace(/\s+/g, " ").slice(0, 140) || "Text output";
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

function filterLabel(filter: RunStatusFilter): string {
  if (filter === "all") {
    return "All";
  }
  if (filter === "ok") {
    return "OK";
  }
  if (filter === "validation_error") {
    return "Validation error";
  }
  return "Execution error";
}

function caseLabel(
  run: RunArtifact,
  caseIds: Set<string>
): { title: string; id: string } {
  const title = run.case_id
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toLocaleUpperCase() + part.slice(1))
    .join(" ");

  return {
    title: caseIds.has(run.case_id) && title ? title : run.case_id,
    id: run.case_id,
  };
}

function ArtifactBlock({
  label,
  value,
  language = "text",
}: {
  label: string;
  value?: string | null;
  language?: CodeViewerProps["language"];
}) {
  if (!value) {
    return null;
  }

  return (
    <div className="run-detail-block">
      <CodeViewer label={label} language={language} value={value} />
    </div>
  );
}

export function RunsView({ cases, runBatchId, runs }: RunsViewProps) {
  const [statusFilter, setStatusFilter] = useState<RunStatusFilter>("all");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const caseIds = useMemo(
    () => new Set(cases.map((artifactCase) => artifactCase.id)),
    [cases]
  );

  const counts = useMemo(
    () => ({
      all: runs.length,
      ok: runs.filter((run) => run.status === "ok").length,
      validation_error: runs.filter((run) => run.status === "validation_error")
        .length,
      execution_error: runs.filter((run) => run.status === "execution_error")
        .length,
    }),
    [runs]
  );

  const filteredRuns = useMemo(
    () =>
      statusFilter === "all"
        ? runs
        : runs.filter((run) => run.status === statusFilter),
    [runs, statusFilter]
  );

  const selectedRun = useMemo(
    () =>
      filteredRuns.find((run) => run.run_id === selectedRunId) ??
      filteredRuns[0] ??
      null,
    [filteredRuns, selectedRunId]
  );

  useEffect(() => {
    if (selectedRun && selectedRun.run_id !== selectedRunId) {
      setSelectedRunId(selectedRun.run_id);
    }
    if (!selectedRun && selectedRunId !== null) {
      setSelectedRunId(null);
    }
  }, [selectedRun, selectedRunId]);

  return (
    <section className="runs-panel" aria-label="Run results">
      <div className="section-heading">
        <h3>Active run</h3>
        <span>
          {runs.length === 0
            ? "No active run"
            : `${runs.length} artifact${runs.length === 1 ? "" : "s"}`}
        </span>
      </div>

      {runs.length === 0 ? (
        <div className="empty-inline">
          No active run yet. Run this version to create one active run.
        </div>
      ) : (
        <div className="runs-workspace">
          <div className="runs-filterbar" aria-label="Filter runs by status">
            {RUN_STATUS_FILTERS.map((filter) => (
              <button
                aria-pressed={statusFilter === filter}
                className="runs-filter-button"
                key={filter}
                onClick={() => setStatusFilter(filter)}
                type="button"
              >
                <span>{filterLabel(filter)}</span>
                <strong>{counts[filter]}</strong>
              </button>
            ))}
          </div>

          <div className="runs-drilldown">
            <div className="runs-table-wrap">
              <table className="runs-table">
                <thead>
                  <tr>
                    <th>Case</th>
                    <th>Repeat</th>
                    <th>Status</th>
                    <th>Output summary</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRuns.map((run) => {
                    const label = caseLabel(run, caseIds);
                    const isSelected = selectedRun?.run_id === run.run_id;

                    return (
                      <tr
                        aria-selected={isSelected}
                        className={isSelected ? "runs-row-selected" : undefined}
                        key={run.run_id}
                        onClick={() => setSelectedRunId(run.run_id)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            setSelectedRunId(run.run_id);
                          }
                        }}
                        tabIndex={0}
                      >
                        <td>
                          <strong>{label.title}</strong>
                          <span>{label.id}</span>
                        </td>
                        <td>{run.repeat_index}</td>
                        <td>
                          <span className={`status-pill status-${run.status}`}>
                            {run.status}
                          </span>
                          <span>{statusLabel(run)}</span>
                        </td>
                        <td className="runs-summary-cell">{compactSummary(run)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>

              {filteredRuns.length === 0 ? (
                <div className="runs-filter-empty">
                  No runs match this status filter.
                </div>
              ) : null}
            </div>

            {selectedRun ? (
              <aside className="run-detail-panel" aria-label="Selected run detail">
                <div className="run-detail-heading">
                  <div>
                    <h4>{caseLabel(selectedRun, caseIds).title}</h4>
                    <span>{caseLabel(selectedRun, caseIds).id}</span>
                  </div>
                  <span className={`status-pill status-${selectedRun.status}`}>
                    {selectedRun.status}
                  </span>
                </div>

                <dl className="run-detail-meta">
                  <div>
                    <dt>Repeat</dt>
                    <dd>{selectedRun.repeat_index}</dd>
                  </div>
                  <div>
                    <dt>Output type</dt>
                    <dd>{selectedRun.output_type}</dd>
                  </div>
                  {runBatchId !== null ? (
                    <div>
                      <dt>Artifact id</dt>
                      <dd>{runBatchId}</dd>
                    </div>
                  ) : null}
                  <div>
                    <dt>Run id</dt>
                    <dd>{selectedRun.run_id}</dd>
                  </div>
                </dl>

                <ArtifactBlock
                  label={
                    selectedRun.output_type === "pydantic"
                      ? "Output JSON"
                      : "Output text"
                  }
                  value={outputBody(selectedRun)}
                  language={
                    hasParsedJsonOutput(selectedRun) ? "json" : "text"
                  }
                />
                <ArtifactBlock
                  label="Raw output"
                  language={
                    selectedRun.output_type === "pydantic" ? "json" : "text"
                  }
                  value={selectedRun.raw_output}
                />
                <ArtifactBlock
                  label="Rendered prompt"
                  language="markdown-jinja"
                  value={selectedRun.rendered_prompt}
                />
                <ArtifactBlock
                  label="Validation error"
                  value={selectedRun.validation_error}
                />
                <ArtifactBlock
                  label="Execution error"
                  value={selectedRun.execution_error}
                />
              </aside>
            ) : null}
          </div>
        </div>
      )}
    </section>
  );
}
