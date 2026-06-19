import type { ValidationInclusionUpdate, ValidationState } from "../types";

export function buildValidationInclusionUpdate(
  state: ValidationState
): ValidationInclusionUpdate {
  return {
    results: state.results.map((result) => ({
      validation_result_id: result.validation_result_id,
      included_in_judge: result.included_in_judge,
      check_results: result.check_results.map((check) => ({
        check_id: check.check_id,
        included_in_judge: check.included_in_judge
      }))
    }))
  };
}
