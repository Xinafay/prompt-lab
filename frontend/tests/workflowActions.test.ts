import assert from "node:assert/strict";
import test from "node:test";

import {
  getCompareActionLabel,
  getCompareActionState,
  getJudgeActionState,
  getProposalActionLabel,
  getValidateActionState,
  getRunActionLabel
} from "../src/workflowActions.ts";

test("judge action is disabled until a run exists", () => {
  assert.deepEqual(
    getJudgeActionState({ hasRuns: false, hasValidation: false, isBusy: false }),
    {
      disabled: true,
      disabledReason: "Create a run before judging the active run.",
      label: "Judge active run"
    }
  );
});

test("validate action is disabled until a run exists", () => {
  assert.deepEqual(
    getValidateActionState({ hasRuns: false, hasValidation: false, isBusy: false }),
    {
      disabled: true,
      disabledReason: "Create a run before validating.",
      label: "Validate active run"
    }
  );
});

test("validate action explains busy state", () => {
  assert.deepEqual(
    getValidateActionState({ hasRuns: true, hasValidation: false, isBusy: true }),
    {
      disabled: true,
      disabledReason: "Wait for the current workflow action to finish.",
      label: "Validating..."
    }
  );
});

test("validate action label changes when validation already exists", () => {
  assert.deepEqual(
    getValidateActionState({ hasRuns: true, hasValidation: true, isBusy: false }),
    {
      disabled: false,
      disabledReason: null,
      label: "Revalidate active run"
    }
  );
});

test("judge action is disabled until validation exists", () => {
  assert.deepEqual(
    getJudgeActionState({ hasRuns: true, hasValidation: false, isBusy: false }),
    {
      disabled: true,
      disabledReason: "Validate the active run before judging.",
      label: "Judge validated run"
    }
  );
});

test("judge action is enabled after validation exists", () => {
  assert.deepEqual(
    getJudgeActionState({ hasRuns: true, hasValidation: true, isBusy: false }),
    {
      disabled: false,
      disabledReason: null,
      label: "Judge validated run"
    }
  );
});

test("judge action label changes when a review already exists", () => {
  assert.deepEqual(
    getJudgeActionState({
      hasReview: true,
      hasRuns: true,
      hasValidation: true,
      isBusy: false
    }),
    {
      disabled: false,
      disabledReason: null,
      label: "Rejudge validated run"
    }
  );
});

test("judge action explains busy state", () => {
  assert.deepEqual(
    getJudgeActionState({
      hasReview: true,
      hasRuns: true,
      hasValidation: false,
      isBusy: true
    }),
    {
      disabled: true,
      disabledReason: "Wait for the current workflow action to finish.",
      label: "Judging..."
    }
  );
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

test("compare action explains when only one version exists", () => {
  assert.deepEqual(
    getCompareActionState({
      hasComparison: false,
      hasValidation: false,
      isBusy: false,
      sameVersion: true,
      versionCount: 1
    }),
    {
      disabled: true,
      disabledReason: "Create another version before comparing.",
      emptyMessage: "No comparison report. Create another version before comparing.",
      note: "Create another version before comparing.",
      label: "Compare versions"
    }
  );
});

test("compare action asks for validation before comparing different versions", () => {
  assert.deepEqual(
    getCompareActionState({
      hasComparison: false,
      hasValidation: false,
      isBusy: false,
      sameVersion: false,
      versionCount: 2
    }),
    {
      disabled: true,
      disabledReason: "Validate both versions before comparing.",
      emptyMessage: "No comparison report. Validate both versions before comparing.",
      note: null,
      label: "Compare versions"
    }
  );
});

test("compare action asks to save validation inclusion before comparing", () => {
  assert.deepEqual(
    getCompareActionState({
      hasComparison: false,
      hasUnsavedValidationChanges: true,
      hasValidation: true,
      isBusy: false,
      sameVersion: false,
      versionCount: 2
    }),
    {
      disabled: true,
      disabledReason: "Save validation inclusion before comparing.",
      emptyMessage: "No comparison report. Save validation inclusion before comparing.",
      note: null,
      label: "Compare versions"
    }
  );
});

test("compare action invites comparison when prerequisites are ready", () => {
  assert.deepEqual(
    getCompareActionState({
      hasComparison: false,
      hasValidation: true,
      isBusy: false,
      sameVersion: false,
      versionCount: 2
    }),
    {
      disabled: false,
      disabledReason: null,
      emptyMessage: "No comparison report. Compare these versions to create one.",
      note: null,
      label: "Compare versions"
    }
  );
});
