import type {
  ValidationCheckResult,
  ValidationResult,
  ValidationState,
  ValidationVerdict,
  ValidatorDefinition,
  ValidatorType
} from "../types";

export interface ValidationOutputColumn {
  key: string;
  case_id: string;
  repeat_index: number;
  title: string;
}

export interface ValidationMatrixCell {
  key: string;
  columnKey: string;
  result: ValidationResult | null;
  check: ValidationCheckResult | null;
  verdict: ValidationVerdict | "error" | "missing" | "skipped";
  result_included_in_judge: boolean;
  check_included_in_judge: boolean;
  included_in_judge: boolean;
  comment: string;
  status: "ok" | "error" | "missing" | "skipped";
}

export interface ValidationMatrixCheckRow {
  key: string;
  validator_id: string;
  validator_title: string;
  validator_description: string;
  validator_type: ValidatorType;
  check_id: string;
  check_title: string;
  check_description: string;
  cells: ValidationMatrixCell[];
}

export interface ValidationMatrix {
  columns: ValidationOutputColumn[];
  rows: ValidationMatrixCheckRow[];
}

export type InclusionScope =
  | { kind: "cell"; rowKey: string; columnKey: string }
  | { kind: "column"; columnKey: string }
  | { kind: "row"; rowKey: string }
  | { kind: "validator"; validatorId: string };

export function buildValidationMatrix(
  state: ValidationState
): ValidationMatrix {
  const columns = buildColumns(state.results);
  const validators = new Map(
    state.validators.map((validator) => [validator.validator_id, validator])
  );
  const resultByKey = new Map(
    state.results.map((result) => [resultKey(result), result])
  );
  const rows: ValidationMatrixCheckRow[] = [];

  for (const validator of state.validators) {
    for (const definition of validator.checks) {
      const rowKey = checkRowKey(validator.validator_id, definition.check_id);
      rows.push({
        key: rowKey,
        validator_id: validator.validator_id,
        validator_title: validator.title,
        validator_description: validator.description,
        validator_type: validator.type,
        check_id: definition.check_id,
        check_title: definition.title,
        check_description: definition.description,
        cells: columns.map((column) =>
          buildCell({
            column,
            result:
              resultByKey.get(
                resultKeyFromParts(column, validator.validator_id)
              ) ?? null,
            rowKey,
            checkId: definition.check_id
          })
        )
      });
    }
  }

  for (const result of state.results) {
    if (validators.has(result.validator_id)) continue;
    for (const check of result.check_results) {
      const rowKey = checkRowKey(result.validator_id, check.check_id);
      if (rows.some((row) => row.key === rowKey)) continue;
      rows.push({
        key: rowKey,
        validator_id: result.validator_id,
        validator_title: result.validator_id,
        validator_description: "",
        validator_type: result.validator_type,
        check_id: check.check_id,
        check_title: check.check_id,
        check_description: "",
        cells: columns.map((column) =>
          buildCell({
            column,
            result:
              resultByKey.get(
                resultKeyFromParts(column, result.validator_id)
              ) ?? null,
            rowKey,
            checkId: check.check_id
          })
        )
      });
    }
  }

  return { columns, rows };
}

export function setValidationInclusion(
  state: ValidationState,
  scope: InclusionScope,
  included: boolean
): ValidationState {
  const matrix = buildValidationMatrix(state);
  const targetCells = new Set<string>();
  for (const row of matrix.rows) {
    if (!scopeMatchesRow(scope, row)) continue;
    for (const cell of row.cells) {
      if (scope.kind === "column" && cell.columnKey !== scope.columnKey) continue;
      if (scope.kind === "cell" && cell.columnKey !== scope.columnKey) continue;
      if (cell.result === null || cell.check === null) continue;
      targetCells.add(cellKey(row.key, cell.columnKey));
    }
  }

  return {
    ...state,
    results: state.results.map((result) => {
      const hasTargetCell =
        targetCellsForResult(matrix, targetCells, result).length > 0;
      return {
        ...result,
        included_in_judge:
          scope.kind === "column" && hasTargetCell
            ? included
            : included && hasTargetCell
              ? true
              : result.included_in_judge,
        check_results: result.check_results.map((check) => {
          const rowKey = checkRowKey(result.validator_id, check.check_id);
          const key = cellKey(rowKey, resultColumnKey(result));
          return targetCells.has(key)
            ? { ...check, included_in_judge: included }
            : check;
        })
      };
    })
  };
}

function buildColumns(results: ValidationResult[]): ValidationOutputColumn[] {
  const seen = new Map<string, ValidationOutputColumn>();
  for (const result of results) {
    const key = resultColumnKey(result);
    if (seen.has(key)) continue;
    seen.set(key, {
      key,
      case_id: result.case_id,
      repeat_index: result.repeat_index,
      title: `${result.case_id} · r${result.repeat_index}`
    });
  }
  return Array.from(seen.values()).sort(
    (a, b) =>
      a.case_id.localeCompare(b.case_id) || a.repeat_index - b.repeat_index
  );
}

function buildCell({
  column,
  result,
  rowKey,
  checkId
}: {
  column: ValidationOutputColumn;
  result: ValidationResult | null;
  rowKey: string;
  checkId: string;
}): ValidationMatrixCell {
  if (result?.status === "skipped") {
    return {
      key: cellKey(rowKey, column.key),
      columnKey: column.key,
      result,
      check: null,
      verdict: "skipped",
      result_included_in_judge: false,
      check_included_in_judge: false,
      included_in_judge: false,
      comment: result.execution_error ?? "Validation was skipped.",
      status: "skipped"
    };
  }
  const check =
    result?.check_results.find((candidate) => candidate.check_id === checkId) ??
    null;
  if (result === null || check === null) {
    return {
      key: cellKey(rowKey, column.key),
      columnKey: column.key,
      result,
      check,
      verdict: "missing",
      result_included_in_judge: false,
      check_included_in_judge: false,
      included_in_judge: false,
      comment: "No validation result was saved for this check.",
      status: "missing"
    };
  }
  if (result.status === "error") {
    return {
      key: cellKey(rowKey, column.key),
      columnKey: column.key,
      result,
      check,
      verdict: "error",
      result_included_in_judge: result.included_in_judge,
      check_included_in_judge: check.included_in_judge,
      included_in_judge: result.included_in_judge && check.included_in_judge,
      comment: result.execution_error ?? check.comment,
      status: "error"
    };
  }
  return {
    key: cellKey(rowKey, column.key),
    columnKey: column.key,
    result,
    check,
    verdict: check.verdict,
    result_included_in_judge: result.included_in_judge,
    check_included_in_judge: check.included_in_judge,
    included_in_judge: result.included_in_judge && check.included_in_judge,
    comment: check.comment,
    status: "ok"
  };
}

function scopeMatchesRow(
  scope: InclusionScope,
  row: ValidationMatrixCheckRow
): boolean {
  if (scope.kind === "validator") return row.validator_id === scope.validatorId;
  if (scope.kind === "row") return row.key === scope.rowKey;
  if (scope.kind === "cell") return row.key === scope.rowKey;
  return true;
}

function targetCellsForResult(
  matrix: ValidationMatrix,
  targetCells: Set<string>,
  result: ValidationResult
): ValidationMatrixCell[] {
  const columnKey = resultColumnKey(result);
  return matrix.rows
    .flatMap((row) => row.cells)
    .filter(
      (cell) =>
        cell.result?.validation_result_id === result.validation_result_id &&
        cell.columnKey === columnKey &&
        targetCells.has(cell.key)
    );
}

function resultKey(result: ValidationResult): string {
  return `${result.case_id}\u0000${result.repeat_index}\u0000${result.validator_id}`;
}

function resultKeyFromParts(
  column: ValidationOutputColumn,
  validatorId: string
): string {
  return `${column.case_id}\u0000${column.repeat_index}\u0000${validatorId}`;
}

function resultColumnKey(result: ValidationResult): string {
  return `${result.case_id}\u0000${result.repeat_index}`;
}

function checkRowKey(validatorId: string, checkId: string): string {
  return `${validatorId}\u0000${checkId}`;
}

function cellKey(rowKey: string, columnKey: string): string {
  return `${rowKey}\u0000${columnKey}`;
}
