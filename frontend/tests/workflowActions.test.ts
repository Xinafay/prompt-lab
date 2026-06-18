import assert from "node:assert/strict";
import test from "node:test";

import {
  getCompareActionLabel,
  getJudgeActionState,
  getProposalActionLabel,
  getRunActionLabel
} from "../src/workflowActions.ts";

test("judge action is disabled until a run exists", () => {
  assert.deepEqual(getJudgeActionState({ hasRuns: false, isBusy: false }), {
    disabled: true,
    disabledReason: "Create a run before judging the active run.",
    label: "Judge active run"
  });
});

test("judge action is enabled after a run exists", () => {
  assert.deepEqual(getJudgeActionState({ hasRuns: true, isBusy: false }), {
    disabled: false,
    disabledReason: null,
    label: "Judge active run"
  });
});

test("judge action label changes when a review already exists", () => {
  assert.deepEqual(
    getJudgeActionState({ hasReview: true, hasRuns: true, isBusy: false }),
    {
      disabled: false,
      disabledReason: null,
      label: "Rejudge active run"
    }
  );
});

test("judge action explains busy state", () => {
  assert.deepEqual(getJudgeActionState({ hasReview: true, hasRuns: true, isBusy: true }), {
    disabled: true,
    disabledReason: "Wait for the current workflow action to finish.",
    label: "Judging..."
  });
});

test("run action label changes when runs already exist", () => {
  assert.equal(getRunActionLabel({ hasRuns: false, isRunning: false }), "Run version");
  assert.equal(getRunActionLabel({ hasRuns: true, isRunning: false }), "Rerun version");
  assert.equal(getRunActionLabel({ hasRuns: true, isRunning: true }), "Running...");
});

test("proposal action label changes when a proposal already exists", () => {
  assert.equal(
    getProposalActionLabel({ hasProposal: false, isBusy: false }),
    "Generate proposal"
  );
  assert.equal(
    getProposalActionLabel({ hasProposal: true, isBusy: false }),
    "Regenerate proposal"
  );
  assert.equal(
    getProposalActionLabel({ hasProposal: true, isBusy: true }),
    "Generating..."
  );
});

test("compare action label changes when a comparison already exists", () => {
  assert.equal(
    getCompareActionLabel({ hasComparison: false, isBusy: false }),
    "Compare versions"
  );
  assert.equal(
    getCompareActionLabel({ hasComparison: true, isBusy: false }),
    "Recompare versions"
  );
  assert.equal(
    getCompareActionLabel({ hasComparison: true, isBusy: true }),
    "Comparing..."
  );
});
