import type { ReactNode } from "react";

import type { Experiment, JobStatus, WorkflowMode } from "../types";
import "./WorkflowToolbar.css";

interface WorkflowToolbarProps {
  experiment?: Experiment;
  contextTitle?: string;
  contextMeta?: ReactNode;
  activeTabLabel: string;
  activeVersion?: string;
  availableVersions?: string[];
  jobStatus: JobStatus | null;
  workflowMessage: string | null;
  workflowMode: WorkflowMode;
  isVersionSwitching: boolean;
  onActiveVersionChange?: (version: string) => void;
  onWorkflowModeChange: (mode: WorkflowMode) => void;
  onCancelJob?: () => void;
  primaryAction: ReactNode;
  secondaryAction?: ReactNode;
  tabControl?: ReactNode;
  tabNotice?: ReactNode;
  tabs: ReactNode;
  showDryRunControls: boolean;
}

export function WorkflowToolbar({
  experiment,
  contextTitle,
  contextMeta = null,
  activeTabLabel,
  activeVersion,
  availableVersions,
  jobStatus,
  workflowMessage,
  workflowMode,
  isVersionSwitching = false,
  onActiveVersionChange = () => undefined,
  onCancelJob,
  onWorkflowModeChange,
  primaryAction,
  secondaryAction = null,
  tabControl = null,
  tabNotice = null,
  tabs,
  showDryRunControls
}: WorkflowToolbarProps) {
  const title = contextTitle ?? experiment?.title ?? "";
  const versionOptions =
    activeVersion === undefined ? [] : (availableVersions ?? [activeVersion]);
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
  const showTabMeta = tabNotice !== null || statusMessage !== null;

  return (
    <div className="workflow-toolbar" aria-label="Workflow context">
      <div className="workflow-context-row">
        <strong>{title}</strong>
        {activeVersion === undefined ? null : (
          <label className="version-switcher">
            <span>Version</span>
            <select
              disabled={isVersionSwitching || jobStatus?.status === "running"}
              onChange={(event) => onActiveVersionChange(event.currentTarget.value)}
              value={activeVersion}
            >
              {versionOptions.map((version) => (
                <option key={version} value={version}>
                  {version}
                </option>
              ))}
            </select>
          </label>
        )}
        {contextMeta}
        {showDryRunControls ? (
          <span className={`workflow-mode-badge mode-${workflowMode}`}>
            {workflowMode === "dry-run" ? "Dry-run" : "Live"}
          </span>
        ) : null}
      </div>

      <div className="workflow-tabs-row">{tabs}</div>

      <div className="workflow-tab-actions-row">
        <div className="workflow-tab-heading">
          <h2>{activeTabLabel}</h2>
          {tabControl}
          {showTabMeta ? (
            <div className="workflow-tab-meta">
              {tabNotice}
              {statusMessage !== null ? (
                <span className="workflow-status">{statusMessage}</span>
              ) : null}
            </div>
          ) : null}
        </div>
        {showActions ? (
          <div className="workflow-actions">
            {showDryRunControls ? (
              <label className="dry-run-toggle">
                <input
                  checked={workflowMode === "dry-run"}
                  onChange={(event) =>
                    onWorkflowModeChange(
                      event.target.checked ? "dry-run" : "live"
                    )
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
    </div>
  );
}
