import type { ValidationState } from "../types";

export function snapshotValidationState(
  state: ValidationState | null
): ValidationState | null {
  return state === null ? null : structuredClone(state);
}
