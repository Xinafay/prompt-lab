import { useEffect, useState } from "react";

import type { CreatedVersionResponse, ProposalResponse, ReviewState } from "../types";
import { TooltipButton } from "./TooltipButton";

type ProposalSection = "prompt" | "model" | "rationale";

interface ProposalViewProps {
  reviewState: ReviewState | null;
  proposalResponse: ProposalResponse | null;
  createdVersion: CreatedVersionResponse | null;
  isBusy: boolean;
  hasUnsavedReviewChanges: boolean;
  onGenerateProposal: () => void;
  onCreateVersion: () => void;
}

export function ProposalView({
  reviewState,
  proposalResponse,
  createdVersion,
  isBusy,
  hasUnsavedReviewChanges,
  onGenerateProposal,
  onCreateVersion
}: ProposalViewProps) {
  const [activeSection, setActiveSection] = useState<ProposalSection>("prompt");
  const hasModel = Boolean(proposalResponse?.proposal.model_py);
  const visibleSections: ProposalSection[] = hasModel
    ? ["prompt", "model", "rationale"]
    : ["prompt", "rationale"];

  useEffect(() => {
    if (activeSection === "model" && !hasModel) {
      setActiveSection("prompt");
    }
  }, [activeSection, hasModel]);

  return (
    <section className="proposal-panel" aria-label="Proposal">
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
                : "Save review decisions and human notes before generating a proposal."
          }
          onClick={onGenerateProposal}
          type="button"
        >
          {isBusy ? "Generating..." : "Generate proposal"}
        </TooltipButton>
      </div>

      {hasUnsavedReviewChanges ? (
        <div className="empty-inline">
          Save decisions and human notes before generating a proposal.
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
            <div className="proposal-tabs" role="tablist" aria-label="Proposal sections">
              {visibleSections.map((section) => (
                <button
                  aria-selected={activeSection === section}
                  className={
                    activeSection === section
                      ? "proposal-tab is-active"
                      : "proposal-tab"
                  }
                  key={section}
                  onClick={() => setActiveSection(section)}
                  role="tab"
                  type="button"
                >
                  {section === "prompt"
                    ? "Prompt"
                    : section === "model"
                      ? "Model"
                      : "Rationale"}
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

          {activeSection === "prompt" ? (
            <div className="proposal-section">
              <h4>Proposed prompt</h4>
              <pre className="code-block">{proposalResponse.proposal.prompt_md}</pre>
            </div>
          ) : null}

          {activeSection === "model" && proposalResponse.proposal.model_py ? (
            <div className="proposal-section">
              <h4>Proposed model</h4>
              <pre className="code-block">{proposalResponse.proposal.model_py}</pre>
            </div>
          ) : null}

          {activeSection === "rationale" ? (
            <div className="proposal-section">
              <h4>Rationale</h4>
              <pre className="text-block">{proposalResponse.proposal.rationale_md}</pre>
            </div>
          ) : null}

          {createdVersion !== null ? (
            <p className="success-copy">Created {createdVersion.version}</p>
          ) : null}
        </div>
      )}
    </section>
  );
}
