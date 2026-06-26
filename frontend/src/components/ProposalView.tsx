import { useState } from "react";

import type { CreatedVersionResponse, ProposalResponse, ReviewState } from "../types";
import { CodeViewer, DiffViewer } from "./CodeViewer";
import { TooltipButton } from "./TooltipButton";

type ProposalViewMode = "new" | "diff";

interface ProposalViewProps {
  reviewState: ReviewState | null;
  proposalResponse: ProposalResponse | null;
  createdVersion: CreatedVersionResponse | null;
  currentPrompt: string;
  currentModel: string | null;
  currentModelFile: string | null;
  initialViewMode?: ProposalViewMode;
  isBusy: boolean;
  hasUnsavedReviewChanges: boolean;
  showHeader?: boolean;
  onGenerateProposal: () => void;
  onCreateVersion: () => void;
}

export function ProposalView({
  reviewState,
  proposalResponse,
  createdVersion,
  currentPrompt,
  currentModel,
  currentModelFile,
  initialViewMode = "new",
  isBusy,
  hasUnsavedReviewChanges,
  showHeader = true,
  onGenerateProposal,
  onCreateVersion
}: ProposalViewProps) {
  const [viewMode, setViewMode] = useState<ProposalViewMode>(initialViewMode);
  const hasModel = Boolean(proposalResponse?.proposal.model_py);
  const modelFile = currentModelFile?.trim() || "model.py";

  return (
    <section className="proposal-panel" aria-label="Proposal">
      {showHeader ? (
        <div className="section-heading">
          <h3>Proposal</h3>
          <TooltipButton
            className="secondary-action"
            disabled={isBusy || reviewState === null || hasUnsavedReviewChanges}
            disabledReason={
              isBusy
                ? "Wait for the current workflow action to finish."
                : reviewState === null
                  ? "Judge the active run before generating a proposal."
                  : "Save review changes before generating a proposal."
            }
            onClick={onGenerateProposal}
            type="button"
          >
            {isBusy ? "Generating..." : "Generate proposal"}
          </TooltipButton>
        </div>
      ) : null}

      {hasUnsavedReviewChanges ? (
        <div className="empty-inline">
          Save review changes before generating a proposal.
        </div>
      ) : null}

      {proposalResponse === null ? (
        <div className="empty-inline">
          {reviewState === null
            ? "Judge the active run before generating a proposal."
            : "No proposal generated."}
        </div>
      ) : (
        <div className="proposal-content">
          <div className="proposal-toolbar">
            <div className="proposal-tabs" role="tablist" aria-label="Proposal view">
              {(["new", "diff"] as const).map((mode) => (
                <button
                  aria-selected={viewMode === mode}
                  className={
                    viewMode === mode
                      ? "proposal-tab is-active"
                      : "proposal-tab"
                  }
                  key={mode}
                  onClick={() => setViewMode(mode)}
                  role="tab"
                  type="button"
                >
                  {mode === "new" ? "New version" : "Diff"}
                </button>
              ))}
            </div>
            <TooltipButton
              className="primary-action"
              disabled={isBusy}
              disabledReason="Wait for the current workflow action to finish."
              onClick={onCreateVersion}
              type="button"
            >
              Create next version
            </TooltipButton>
          </div>

          <div
            className={
              hasModel
                ? "proposal-artifact-grid"
                : "proposal-artifact-grid proposal-artifact-grid-single"
            }
          >
            <div className="proposal-section">
              <div className="artifact-caption">prompt.md</div>
              {viewMode === "new" ? (
                <CodeViewer
                  label="Proposed prompt"
                  language="markdown-jinja"
                  value={proposalResponse.proposal.prompt_md}
                />
              ) : (
                <DiffViewer
                  label="Prompt diff"
                  language="markdown-jinja"
                  original={currentPrompt}
                  value={proposalResponse.proposal.prompt_md}
                />
              )}
            </div>

            {proposalResponse.proposal.model_py ? (
              <div className="proposal-section">
                <div className="artifact-caption">{modelFile}</div>
                {viewMode === "new" ? (
                  <CodeViewer
                    label="Proposed model"
                    language="python"
                    value={proposalResponse.proposal.model_py}
                  />
                ) : currentModel === null ? (
                  <div className="empty-inline">
                    Current model source unavailable; diff cannot be shown.
                  </div>
                ) : (
                  <DiffViewer
                    label="Model diff"
                    language="python"
                    original={currentModel}
                    value={proposalResponse.proposal.model_py}
                  />
                )}
              </div>
            ) : null}
          </div>

          <div className="proposal-rationale">
            <h4>Rationale</h4>
            <pre className="text-block">{proposalResponse.proposal.rationale_md}</pre>
          </div>

          {createdVersion !== null ? (
            <p className="success-copy">Created {createdVersion.version}</p>
          ) : null}
        </div>
      )}
    </section>
  );
}
