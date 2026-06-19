import type { Experiment } from "../types";

interface ExperimentsListProps {
  experiments: Experiment[];
  selectedExperimentId: string | null;
  onSelect: (experiment: Experiment) => void;
}

export function ExperimentsList({
  experiments,
  selectedExperimentId,
  onSelect
}: ExperimentsListProps) {
  return (
    <nav className="experiments-panel" aria-label="Experiments">
      <div className="panel-heading">
        <h2>Experiments</h2>
      </div>
      <div className="experiment-nav-list">
        {experiments.map((experiment) => (
          <button
            className={
              experiment.id === selectedExperimentId
                ? "experiment-nav-item is-selected"
                : "experiment-nav-item"
            }
            key={experiment.id}
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
          </button>
        ))}
      </div>
    </nav>
  );
}
