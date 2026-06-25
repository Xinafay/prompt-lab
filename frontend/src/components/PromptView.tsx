import type { VersionOverview, VersionSourceDraft } from "../types";
import { CodeEditor, CodeViewer, DiffViewer } from "./CodeViewer";

type SourceViewMode = "edit" | "diff";

interface PromptViewProps {
  overview: VersionOverview;
  isRunning: boolean;
  isSourceEditing?: boolean;
  onRunVersion: () => void;
  onSourceDraftChange?: (draft: VersionSourceDraft) => void;
  onSourceEdit?: () => void;
  onSourceOverwriteCurrent?: () => void;
  onSourceReset?: () => void;
  onSourceSaveAsNext?: () => void;
  onSourceViewModeChange?: (mode: SourceViewMode) => void;
  showRunAction?: boolean;
  sourceBusy?: boolean;
  sourceDirty?: boolean;
  sourceDraft?: VersionSourceDraft | null;
  sourceViewMode?: SourceViewMode;
}

export function PromptView({
  overview,
  isRunning,
  isSourceEditing = false,
  onRunVersion,
  onSourceDraftChange = () => undefined,
  onSourceEdit = () => undefined,
  onSourceOverwriteCurrent = () => undefined,
  onSourceReset = () => undefined,
  onSourceSaveAsNext = () => undefined,
  onSourceViewModeChange = () => undefined,
  showRunAction = true,
  sourceBusy = false,
  sourceDirty = false,
  sourceDraft = null,
  sourceViewMode = "edit"
}: PromptViewProps) {
  const isPydanticOutput = overview.experiment.output.type === "pydantic";
  const modelFile = overview.model_file ?? "model.py";
  const activeDraft =
    sourceDraft ??
    ({
      prompt: overview.prompt,
      model_py: overview.model_py ?? ""
    } satisfies VersionSourceDraft);
  const actionDisabled = isRunning || sourceBusy;
  const saveDisabled = actionDisabled || !sourceDirty;

  function updatePrompt(prompt: string) {
    onSourceDraftChange({ ...activeDraft, prompt });
  }

  function updateModel(model_py: string) {
    onSourceDraftChange({ ...activeDraft, model_py });
  }

  return (
    <section className="overview-grid" aria-label="Prompt source">
      <div className="overview-header">
        <div>
          <h2>{overview.experiment.title}</h2>
          <p>{overview.experiment.description || "No description provided."}</p>
        </div>
        <div className="overview-header-actions">
          {!isSourceEditing ? (
            <button
              className="secondary-action"
              disabled={actionDisabled}
              onClick={onSourceEdit}
              type="button"
            >
              Edit source
            </button>
          ) : null}
          {showRunAction ? (
            <button
              className="primary-action"
              disabled={isRunning}
              onClick={onRunVersion}
              type="button"
            >
              {isRunning ? "Running..." : "Run version"}
            </button>
          ) : null}
        </div>
      </div>

      {isSourceEditing ? (
        <div className="source-editor-toolbar">
          <div
            className="proposal-tabs"
            role="tablist"
            aria-label="Source editor view"
          >
            {(["edit", "diff"] as const).map((mode) => (
              <button
                aria-selected={sourceViewMode === mode}
                className={
                  sourceViewMode === mode
                    ? "proposal-tab is-active"
                    : "proposal-tab"
                }
                key={mode}
                onClick={() => onSourceViewModeChange(mode)}
                role="tab"
                type="button"
              >
                {mode === "edit" ? "Edit" : "Diff"}
              </button>
            ))}
          </div>
          <div className="source-editor-actions">
            <button
              className="secondary-action"
              disabled={saveDisabled}
              onClick={onSourceReset}
              type="button"
            >
              Reset
            </button>
            <button
              className="secondary-action danger-action"
              disabled={saveDisabled}
              onClick={onSourceOverwriteCurrent}
              type="button"
            >
              Overwrite current version
            </button>
            <button
              className="primary-action"
              disabled={saveDisabled}
              onClick={onSourceSaveAsNext}
              type="button"
            >
              {sourceBusy ? "Saving..." : "Save as next version"}
            </button>
          </div>
        </div>
      ) : null}

      <div
        className={`overview-source-grid${
          isPydanticOutput ? "" : " overview-source-grid-single"
        }`}
      >
        <div className="overview-section">
          <div className="section-heading">
            <h3>Prompt</h3>
            <span>{overview.version}</span>
          </div>
          <div className="overview-code-viewer">
            {isSourceEditing && sourceViewMode === "edit" ? (
              <CodeEditor
                disabled={actionDisabled}
                label="Prompt"
                language="markdown-jinja"
                onChange={updatePrompt}
                value={activeDraft.prompt}
              />
            ) : isSourceEditing && sourceViewMode === "diff" ? (
              <DiffViewer
                label="Prompt diff"
                language="markdown-jinja"
                original={overview.prompt}
                value={activeDraft.prompt}
              />
            ) : (
              <CodeViewer
                label="Prompt"
                language="markdown-jinja"
                value={overview.prompt}
              />
            )}
          </div>
        </div>

        {isPydanticOutput ? (
          <div className="overview-section">
            <div className="section-heading">
              <h3>Model</h3>
              <span>{modelFile}</span>
            </div>
            {overview.model_py ? (
              <div className="overview-code-viewer">
                {isSourceEditing && sourceViewMode === "edit" ? (
                  <CodeEditor
                    disabled={actionDisabled}
                    label={modelFile}
                    language="python"
                    onChange={updateModel}
                    value={activeDraft.model_py ?? ""}
                  />
                ) : isSourceEditing && sourceViewMode === "diff" ? (
                  <DiffViewer
                    label="Model diff"
                    language="python"
                    original={overview.model_py}
                    value={activeDraft.model_py ?? ""}
                  />
                ) : (
                  <CodeViewer
                    label={modelFile}
                    language="python"
                    value={overview.model_py}
                  />
                )}
              </div>
            ) : (
              <p className="overview-inline-empty">Model source unavailable.</p>
            )}
          </div>
        ) : null}
      </div>
    </section>
  );
}
