import type { Experiment } from "../types";

interface ExperimentsListProps {
  experiments: Experiment[];
  selectedExperimentId: string | null;
  onClone?: (experiment: Experiment) => void;
  onCreate?: () => void;
  onDelete?: (experiment: Experiment) => void;
  onSelect: (experiment: Experiment) => void;
}

export function ExperimentsList({
  experiments,
  selectedExperimentId,
  onClone,
  onCreate,
  onDelete,
  onSelect
}: ExperimentsListProps) {
  return (
    <nav className="experiments-panel" aria-label="Experiments">
      <div className="panel-heading experiments-panel-heading">
        <h2>Experiments</h2>
        {onCreate !== undefined ? (
          <button
            className="secondary-action experiment-panel-action"
            onClick={onCreate}
            type="button"
          >
            New
          </button>
        ) : null}
      </div>
      <div className="experiment-nav-list">
        {experiments.map((experiment) => {
          const isSelected = experiment.id === selectedExperimentId;
          return (
            <div
              className={
                isSelected ? "experiment-nav-row is-selected" : "experiment-nav-row"
              }
              key={experiment.id}
            >
              <button
                className={
                  isSelected
                    ? "experiment-nav-item is-selected"
                    : "experiment-nav-item"
                }
                onClick={() => onSelect(experiment)}
                type="button"
              >
                <span className="experiment-nav-title">{experiment.title}</span>
                <span className="experiment-nav-meta">
                  {experiment.output.type} · {experiment.active_version}
                </span>
                <span className="experiment-nav-model">
                  Generator: {experiment.models.generator_model}
                </span>
                <span className="experiment-nav-model">
                  Judge: {experiment.models.judge_model}
                </span>
                <span className="experiment-nav-model">
                  Validator: {experiment.models.validator_model}
                </span>
              </button>
              {isSelected && onClone !== undefined && onDelete !== undefined ? (
                <div className="experiment-nav-actions">
                  <button
                    className="secondary-action"
                    onClick={() => onClone(experiment)}
                    type="button"
                  >
                    Clone
                  </button>
                  <button
                    className="secondary-action danger-action"
                    onClick={() => onDelete(experiment)}
                    type="button"
                  >
                    Delete
                  </button>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </nav>
  );
}
