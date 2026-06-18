interface JudgeActionInput {
  hasRuns: boolean;
  isBusy: boolean;
}

interface ActionState {
  disabled: boolean;
  disabledReason: string | null;
  label: string;
}

export function getJudgeActionState({
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
    label: "Judge active run"
  };
}
