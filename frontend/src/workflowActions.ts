interface JudgeActionInput {
  hasReview?: boolean;
  hasRuns: boolean;
  hasUnsavedValidationChanges?: boolean;
  hasValidation?: boolean;
  isBusy: boolean;
}

interface ActionState {
  disabled: boolean;
  disabledReason: string | null;
  label: string;
}

interface CompareActionState extends ActionState {
  emptyMessage: string;
  note: string | null;
}

export function getJudgeActionState({
  hasReview = false,
  hasRuns,
  hasUnsavedValidationChanges = false,
  hasValidation = false,
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
  if (!hasValidation) {
    return {
      disabled: true,
      disabledReason: "Validate the active run before judging.",
      label: "Judge validated run"
    };
  }
  if (hasUnsavedValidationChanges) {
    return {
      disabled: true,
      disabledReason: "Save validation inclusion before judging.",
      label: "Judge validated run"
    };
  }
  return {
    disabled: false,
    disabledReason: null,
    label: hasReview ? "Rejudge validated run" : "Judge validated run"
  };
}

export function getValidateActionState({
  hasRuns,
  hasValidation,
  isBusy
}: {
  hasRuns: boolean;
  hasValidation: boolean;
  isBusy: boolean;
}): ActionState {
  if (isBusy) {
    return {
      disabled: true,
      disabledReason: "Wait for the current workflow action to finish.",
      label: "Validating..."
    };
  }
  if (!hasRuns) {
    return {
      disabled: true,
      disabledReason: "Create a run before validating.",
      label: "Validate active run"
    };
  }
  return {
    disabled: false,
    disabledReason: null,
    label: hasValidation ? "Revalidate active run" : "Validate active run"
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

export function getCompareActionState({
  hasComparison,
  hasUnsavedValidationChanges = false,
  hasValidation,
  isBusy,
  sameVersion,
  versionCount
}: {
  hasComparison: boolean;
  hasUnsavedValidationChanges?: boolean;
  hasValidation: boolean;
  isBusy: boolean;
  sameVersion: boolean;
  versionCount: number;
}): CompareActionState {
  const label = getCompareActionLabel({ hasComparison, isBusy });
  if (isBusy) {
    return {
      disabled: true,
      disabledReason: "Wait for the current workflow action to finish.",
      emptyMessage: "No comparison report.",
      note: null,
      label
    };
  }
  if (versionCount < 2) {
    return {
      disabled: true,
      disabledReason: "Create another version before comparing.",
      emptyMessage: "No comparison report. Create another version before comparing.",
      note: "Create another version before comparing.",
      label
    };
  }
  if (sameVersion) {
    return {
      disabled: true,
      disabledReason: "Choose two different versions before comparing.",
      emptyMessage: "No comparison report. Choose two different versions before comparing.",
      note: "Choose two different versions before comparing.",
      label
    };
  }
  if (hasUnsavedValidationChanges) {
    return {
      disabled: true,
      disabledReason: "Save validation inclusion before comparing.",
      emptyMessage: "No comparison report. Save validation inclusion before comparing.",
      note: null,
      label
    };
  }
  if (!hasValidation) {
    return {
      disabled: true,
      disabledReason: "Validate both versions before comparing.",
      emptyMessage: "No comparison report. Validate both versions before comparing.",
      note: null,
      label
    };
  }
  return {
    disabled: false,
    disabledReason: null,
    emptyMessage: "No comparison report. Compare these versions to create one.",
    note: null,
    label
  };
}
