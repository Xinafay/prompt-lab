interface SuiteMutationState {
  isBusy: boolean;
  caseSuiteCasesDirty: boolean;
}

interface SaveSuiteCasesState {
  isBusy: boolean;
  isDirty: boolean;
  hasPayloadError: boolean;
  selectedSuiteId: string | null;
}

interface ParsedPayloadDraft {
  ok: true;
  payload: Record<string, unknown>;
}

interface InvalidPayloadDraft {
  ok: false;
  error: string;
}

export const SUITE_CASE_SELECTION_BLOCKED_MESSAGE =
  "Save or reset suite case changes before switching suites.";

export function parseCasePayloadDraft(
  text: string
): ParsedPayloadDraft | InvalidPayloadDraft {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text) as unknown;
  } catch {
    return { ok: false, error: "Invalid JSON." };
  }

  if (
    parsed === null ||
    typeof parsed !== "object" ||
    Array.isArray(parsed)
  ) {
    return { ok: false, error: "Payload must be a JSON object." };
  }

  return { ok: true, payload: parsed as Record<string, unknown> };
}

export function isSuiteMutationDisabled({
  isBusy,
  caseSuiteCasesDirty
}: SuiteMutationState): boolean {
  return isBusy || caseSuiteCasesDirty;
}

export function getSuiteSelectionBlockedMessage(
  caseSuiteCasesDirty: boolean
): string | null {
  return caseSuiteCasesDirty ? SUITE_CASE_SELECTION_BLOCKED_MESSAGE : null;
}

export function canSaveSuiteCases({
  isBusy,
  isDirty,
  hasPayloadError,
  selectedSuiteId
}: SaveSuiteCasesState): boolean {
  return !isBusy && selectedSuiteId !== null && !hasPayloadError && isDirty;
}
