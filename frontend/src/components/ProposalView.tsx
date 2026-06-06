import type { CreatedVersionResponse, ProposalResponse, ReviewState } from "../types";

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
  return (
    <section className="proposal-panel" aria-label="Proposal">
      <div className="section-heading">
        <h3>Proposal</h3>
        <button
          className="secondary-action"
          disabled={isBusy || reviewState === null || hasUnsavedReviewChanges}
          onClick={onGenerateProposal}
          type="button"
        >
          {isBusy ? "Generating..." : "Generate proposal"}
        </button>
      </div>

      {hasUnsavedReviewChanges ? (
        <div className="empty-inline">
          Save decisions and human notes before generating a proposal.
        </div>
      ) : null}

      {proposalResponse === null ? (
        <div className="empty-inline">No proposal generated.</div>
      ) : (
        <div className="proposal-content">
          <div className="proposal-section">
            <h4>Proposed prompt</h4>
            <pre className="code-block">{proposalResponse.proposal.prompt_md}</pre>
          </div>
          {proposalResponse.proposal.model_py ? (
            <div className="proposal-section">
              <h4>Proposed model</h4>
              <pre className="code-block">{proposalResponse.proposal.model_py}</pre>
            </div>
          ) : null}
          <div className="proposal-section">
            <h4>Rationale</h4>
            <pre className="text-block">{proposalResponse.proposal.rationale_md}</pre>
          </div>
          <button
            className="primary-action"
            disabled={isBusy}
            onClick={onCreateVersion}
            type="button"
          >
            Create next version
          </button>
          {createdVersion !== null ? (
            <p className="success-copy">Created {createdVersion.version}</p>
          ) : null}
        </div>
      )}
    </section>
  );
}
