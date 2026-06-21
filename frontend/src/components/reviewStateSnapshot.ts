import type { ReviewState } from "../types";

export function snapshotReviewState(
  state: ReviewState | null
): ReviewState | null {
  return state === null ? null : structuredClone(state);
}
