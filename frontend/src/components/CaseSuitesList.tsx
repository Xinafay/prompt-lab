import type { CaseSuite } from "../types";

interface CaseSuitesListProps {
  isBusy: boolean;
  isSelectionBlocked: boolean;
  onCreate: () => void;
  onSelect: (suiteId: string) => void;
  selectedSuiteId: string | null;
  suites: CaseSuite[];
}

function formatCaseCount(count: number | undefined): string {
  const safeCount = count ?? 0;
  return `${safeCount} case${safeCount === 1 ? "" : "s"}`;
}

export function CaseSuitesList({
  isBusy,
  isSelectionBlocked,
  onCreate,
  onSelect,
  selectedSuiteId,
  suites
}: CaseSuitesListProps) {
  return (
    <nav className="experiments-panel" aria-label="Case Suites">
      <div className="panel-heading experiments-panel-heading">
        <h2>Case Suites</h2>
        <button
          className="secondary-action experiment-panel-action"
          disabled={isBusy || isSelectionBlocked}
          onClick={onCreate}
          type="button"
        >
          New
        </button>
      </div>
      <div className="experiment-nav-list">
        {suites.map((suite) => {
          const isSelected = suite.id === selectedSuiteId;
          const experimentIds = suite.experiment_ids ?? [];
          return (
            <div
              className={
                isSelected ? "experiment-nav-row is-selected" : "experiment-nav-row"
              }
              key={suite.id}
            >
              <button
                className={
                  isSelected
                    ? "experiment-nav-item is-selected"
                    : "experiment-nav-item"
                }
                disabled={isBusy || isSelectionBlocked}
                onClick={() => onSelect(suite.id)}
                type="button"
              >
                <span className="experiment-nav-title">{suite.title}</span>
                <span className="experiment-nav-meta">{suite.id}</span>
                <span className="experiment-nav-model">
                  {formatCaseCount(suite.case_count)}
                </span>
                {experimentIds.length > 0 ? (
                  <span className="experiment-nav-model">
                    Referenced by {experimentIds.join(", ")}
                  </span>
                ) : (
                  <span className="experiment-nav-model">No experiment references</span>
                )}
              </button>
            </div>
          );
        })}
      </div>
    </nav>
  );
}
