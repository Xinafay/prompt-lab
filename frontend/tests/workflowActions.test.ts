import assert from "node:assert/strict";
import test from "node:test";

import { getJudgeActionState } from "../src/workflowActions.ts";

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

test("judge action explains busy state", () => {
  assert.deepEqual(getJudgeActionState({ hasRuns: true, isBusy: true }), {
    disabled: true,
    disabledReason: "Wait for the current workflow action to finish.",
    label: "Judging..."
  });
});
