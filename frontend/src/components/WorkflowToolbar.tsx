import type { ReactNode } from "react";

import type { Experiment, JobStatus } from "../types";

interface WorkflowToolbarProps {
  experiment: Experiment;
  activeVersion: string;
  jobStatus: JobStatus | null;
  workflowMessage: string | null;
  primaryAction: ReactNode;
}

export function WorkflowToolbar({
  experiment,
  activeVersion,
  jobStatus,
  workflowMessage,
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
        {statusMessage !== null ? (
          <span className="workflow-status">{statusMessage}</span>
        ) : null}
      </div>
      <div className="workflow-actions">{primaryAction}</div>
    </div>
  );
}
