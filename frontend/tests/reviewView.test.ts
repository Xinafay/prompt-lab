import assert from "node:assert/strict";
import test from "node:test";

import { snapshotReviewState } from "../src/components/reviewStateSnapshot.ts";
import type { ReviewState } from "../src/types.ts";

function reviewState(): ReviewState {
  return {
    review_id: "review-001",
    judgment: {
      schema_version: "prompt_lab.judgment/v1",
      judgment_id: "judgment-001",
      version: "v001",
      run_batch_ids: ["run-001"],
      judge_model: "openai/judge",
      summary: "Good overall.",
      what_looks_correct: [],
      findings: [
        {
          finding_id: "finding-001",
          severity: "medium",
          area: "output",
          category: "coverage",
          description: "Needs more detail.",
          evidence: ["Evidence"],
          suggested_change: "Add details."
        }
      ],
      decision_points: []
    },
    decisions: {
      schema_version: "prompt_lab.decisions/v1",
      finding_decisions: {
        "finding-001": { decision: "accepted", reason: null }
      }
    },
    human_notes: "Saved note.",
    judgment_markdown: "# Review",
    rubric_snapshot: "Rubric"
  };
}

test("snapshotReviewState preserves saved review when draft changes", () => {
  const saved = reviewState();
  const snapshot = snapshotReviewState(saved);
  saved.decisions.finding_decisions["finding-001"] = {
    decision: "rejected",
    reason: "Draft reason"
  };
  saved.human_notes = "Draft note.";

  assert.equal(
    snapshot?.decisions.finding_decisions["finding-001"].decision,
    "accepted"
  );
  assert.equal(snapshot?.human_notes, "Saved note.");
});
