import type { ReactNode } from "react";

import type { Experiment, JobStatus, WorkflowMode } from "../types";

interface WorkflowToolbarProps {
  experiment: Experiment;
  activeVersion: string;
  availableVersions: string[];
  jobStatus: JobStatus | null;
  workflowMessage: string | null;
  workflowMode: WorkflowMode;
  isVersionSwitching: boolean;
  onActiveVersionChange: (version: string) => void;
  onWorkflowModeChange: (mode: WorkflowMode) => void;
  onCancelJob?: () => void;
  primaryAction: ReactNode;
  secondaryAction?: ReactNode;
  showDryRunControls: boolean;
}

export function WorkflowToolbar({
  experiment,
  activeVersion,
  availableVersions = [activeVersion],
  jobStatus,
  workflowMessage,
  workflowMode,
  isVersionSwitching = false,
  onActiveVersionChange = () => undefined,
  onCancelJob,
  onWorkflowModeChange,
  primaryAction,
  secondaryAction = null,
  showDryRunControls
}: WorkflowToolbarProps) {
  const statusMessage =
    jobStatus === null
      ? workflowMessage
      : `${jobStatus.status}: ${jobStatus.message} (${jobStatus.completed_units}/${jobStatus.total_units})`;
  const showCancelAction =
    jobStatus?.status === "running" && onCancelJob !== undefined;
  const showActions =
    showDryRunControls ||
    primaryAction !== null ||
    secondaryAction !== null ||
    showCancelAction;

  return (
    <div className="workflow-toolbar" aria-label="Workflow context">
      <div className="workflow-context">
        <strong>{experiment.title}</strong>
        <label className="version-switcher">
          <span>Version</span>
          <select
            disabled={isVersionSwitching || jobStatus?.status === "running"}
            onChange={(event) => onActiveVersionChange(event.currentTarget.value)}
            value={activeVersion}
          >
            {availableVersions.map((version) => (
              <option key={version} value={version}>
                {version}
              </option>
            ))}
          </select>
        </label>
        {showDryRunControls ? (
          <span className={`workflow-mode-badge mode-${workflowMode}`}>
            {workflowMode === "dry-run" ? "Dry-run" : "Live"}
          </span>
        ) : null}
        {statusMessage !== null ? (
          <span className="workflow-status">{statusMessage}</span>
        ) : null}
      </div>
      {showActions ? (
        <div className="workflow-actions">
          {showDryRunControls ? (
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
          ) : null}
          {secondaryAction}
          {primaryAction}
          {showCancelAction ? (
            <button
              className="secondary-action danger-action"
              onClick={onCancelJob}
              type="button"
            >
              Cancel
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
