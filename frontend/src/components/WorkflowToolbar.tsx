import type { ReactNode } from "react";

import type { Experiment, JobStatus, WorkflowMode } from "../types";

interface WorkflowToolbarProps {
  experiment: Experiment;
  activeVersion: string;
  jobStatus: JobStatus | null;
  workflowMessage: string | null;
  workflowMode: WorkflowMode;
  onWorkflowModeChange: (mode: WorkflowMode) => void;
  primaryAction: ReactNode;
}

export function WorkflowToolbar({
  experiment,
  activeVersion,
  jobStatus,
  workflowMessage,
  workflowMode,
  onWorkflowModeChange,
  primaryAction
}: WorkflowToolbarProps) {
  const statusMessage =
    jobStatus === null
      ? workflowMessage
      : `${jobStatus.status}: ${jobStatus.message} (${jobStatus.completed_units}/${jobStatus.total_units})`;

  return (
    <div className="workflow-toolbar" aria-label="Workflow context">
      <div className="workflow-context">
        <strong>{experiment.title}</strong>
        <span>{activeVersion}</span>
        <span className={`workflow-mode-badge mode-${workflowMode}`}>
          {workflowMode === "dry-run" ? "Dry-run" : "Live"}
        </span>
        {statusMessage !== null ? (
          <span className="workflow-status">{statusMessage}</span>
        ) : null}
      </div>
      <div className="workflow-actions">
        <label className="dry-run-toggle">
          <input
            checked={workflowMode === "dry-run"}
            onChange={(event) =>
              onWorkflowModeChange(event.target.checked ? "dry-run" : "live")
            }
            type="checkbox"
          />
          <span>Dry-run</span>
        </label>
        {primaryAction}
      </div>
    </div>
  );
}
