import type { FindingDecisionValue, ReviewState } from "../types";

interface ReviewViewProps {
  reviewState: ReviewState | null;
  isBusy: boolean;
  onJudge: () => void;
  onDecisionChange: (
    findingId: string,
    decision: FindingDecisionValue,
    reason: string | null
  ) => void;
  onSaveDecisions: () => void;
  onHumanNotesChange: (notes: string) => void;
  onSaveHumanNotes: () => void;
}

const decisionOptions: FindingDecisionValue[] = [
  "accepted",
  "rejected",
  "deferred"
];

function labelDecision(value: FindingDecisionValue): string {
  if (value === "accepted") return "Accepted";
  if (value === "rejected") return "Rejected";
  return "Deferred";
}

export function ReviewView({
  reviewState,
  isBusy,
  onJudge,
  onDecisionChange,
  onSaveDecisions,
  onHumanNotesChange,
  onSaveHumanNotes
}: ReviewViewProps) {
  return (
    <section className="review-panel" aria-label="Review">
      <div className="section-heading">
        <h3>Review</h3>
        <button className="secondary-action" disabled={isBusy} onClick={onJudge} type="button">
          {isBusy ? "Judging..." : "Judge latest runs"}
        </button>
      </div>

      {reviewState === null ? (
        <div className="empty-inline">
          No judgment loaded. Run and judge the latest run batch.
        </div>
      ) : (
        <div className="review-content">
          <div className="review-summary">
            <h4>Summary</h4>
            <p>{reviewState.judgment.summary}</p>
          </div>

          <div className="review-section">
            <h4>What looks correct</h4>
            {reviewState.judgment.what_looks_correct.map((finding) => (
              <article className="review-card" key={finding.finding_id}>
                <strong>{finding.description}</strong>
                <ul>
                  {finding.evidence.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </article>
            ))}
          </div>

          <div className="review-section">
            <h4>Findings</h4>
            {reviewState.judgment.findings.map((finding) => {
              const savedDecision =
                reviewState.decisions.finding_decisions[finding.finding_id] ??
                { decision: "accepted", reason: "" };
              return (
                <article className="finding-card" key={finding.finding_id}>
                  <div className="finding-header">
                    <div>
                      <strong>{finding.description}</strong>
                      <span>
                        {finding.severity} · {finding.area} · {finding.category}
                      </span>
                    </div>
                  </div>
                  <p>{finding.suggested_change}</p>
                  <ul>
                    {finding.evidence.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                  <div className="decision-controls">
                    {decisionOptions.map((option) => (
                      <label key={option}>
                        <input
                          checked={savedDecision.decision === option}
                          disabled={isBusy}
                          name={`decision-${finding.finding_id}`}
                          onChange={() =>
                            onDecisionChange(
                              finding.finding_id,
                              option,
                              option === "accepted"
                                ? null
                                : savedDecision.reason ?? null
                            )
                          }
                          type="radio"
                        />
                        {labelDecision(option)}
                      </label>
                    ))}
                  </div>
                  {savedDecision.decision !== "accepted" ? (
                    <input
                      className="reason-input"
                      disabled={isBusy}
                      onChange={(event) =>
                        onDecisionChange(
                          finding.finding_id,
                          savedDecision.decision,
                          event.currentTarget.value
                        )
                      }
                      placeholder="Reason"
                      type="text"
                      value={savedDecision.reason ?? ""}
                    />
                  ) : null}
                </article>
              );
            })}
            <button
              className="secondary-action"
              disabled={isBusy}
              onClick={onSaveDecisions}
              type="button"
            >
              Save decisions
            </button>
          </div>

          <div className="review-section">
            <h4>Decision points</h4>
            {reviewState.judgment.decision_points.length === 0 ? (
              <p className="muted-copy">No decision points.</p>
            ) : (
              reviewState.judgment.decision_points.map((decision) => (
                <article className="review-card" key={decision.decision_id}>
                  <strong>{decision.description}</strong>
                  <p>Recommended: {decision.recommended_option}</p>
                </article>
              ))
            )}
          </div>

          <div className="review-section">
            <h4>Human notes</h4>
            <textarea
              className="notes-input"
              disabled={isBusy}
              onChange={(event) => onHumanNotesChange(event.currentTarget.value)}
              rows={5}
              value={reviewState.human_notes}
            />
            <button
              className="secondary-action"
              disabled={isBusy}
              onClick={onSaveHumanNotes}
              type="button"
            >
              Save notes
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
