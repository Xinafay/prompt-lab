interface JudgeActionInput {
  hasReview?: boolean;
  hasRuns: boolean;
  isBusy: boolean;
}

interface ActionState {
  disabled: boolean;
  disabledReason: string | null;
  label: string;
}

export function getJudgeActionState({
  hasReview = false,
  hasRuns,
  isBusy
}: JudgeActionInput): ActionState {
  if (isBusy) {
    return {
      disabled: true,
      disabledReason: "Wait for the current workflow action to finish.",
      label: "Judging..."
    };
  }
  if (!hasRuns) {
    return {
      disabled: true,
      disabledReason: "Create a run before judging the active run.",
      label: "Judge active run"
    };
  }
  return {
    disabled: false,
    disabledReason: null,
    label: hasReview ? "Rejudge active run" : "Judge active run"
  };
}

export function getRunActionLabel({
  hasRuns,
  isRunning
}: {
  hasRuns: boolean;
  isRunning: boolean;
}): string {
  if (isRunning) return "Running...";
  return hasRuns ? "Rerun version" : "Run version";
}

export function getProposalActionLabel({
  hasProposal,
  isBusy
}: {
  hasProposal: boolean;
  isBusy: boolean;
}): string {
  if (isBusy) return "Generating...";
  return hasProposal ? "Regenerate proposal" : "Generate proposal";
}

export function getCompareActionLabel({
  hasComparison,
  isBusy
}: {
  hasComparison: boolean;
  isBusy: boolean;
}): string {
  if (isBusy) return "Comparing...";
  return hasComparison ? "Recompare versions" : "Compare versions";
}
