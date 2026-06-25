import { useEffect, useMemo, useState, type FormEvent } from "react";

import type { CaseSuite, Experiment } from "../types";
import { TooltipButton } from "./TooltipButton";

interface ExperimentSettingsProps {
  caseSuites: CaseSuite[];
  experiment: Experiment;
  isBusy: boolean;
  message: string | null;
  onDirtyChange: (isDirty: boolean) => void;
  onDraftChange: (draft: Experiment | null) => void;
  onReset: () => void;
  onSave: (experiment: Experiment) => Promise<void>;
}

function cloneExperiment(experiment: Experiment): Experiment {
  return JSON.parse(JSON.stringify(experiment)) as Experiment;
}

function prepareForSave(draft: Experiment): Experiment {
  if (draft.output.type === "text") {
    return {
      ...draft,
      output: { type: "text" }
    };
  }
  return {
    ...draft,
    output: {
      type: "pydantic",
      model_file: draft.output.model_file,
      model_entrypoint: draft.output.model_entrypoint
    }
  };
}

export function ExperimentSettings({
  caseSuites,
  experiment,
  isBusy,
  message,
  onDirtyChange,
  onDraftChange,
  onReset,
  onSave
}: ExperimentSettingsProps) {
  const [draft, setDraft] = useState<Experiment>(() => cloneExperiment(experiment));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDraft(cloneExperiment(experiment));
    setError(null);
  }, [experiment]);

  const preparedDraft = useMemo(() => prepareForSave(draft), [draft]);
  const preparedExperiment = useMemo(
    () => prepareForSave(experiment),
    [experiment]
  );
  const isDirty = useMemo(
    () => JSON.stringify(preparedDraft) !== JSON.stringify(preparedExperiment),
    [preparedDraft, preparedExperiment]
  );

  useEffect(() => {
    onDirtyChange(isDirty);
    onDraftChange(isDirty ? preparedDraft : null);
  }, [isDirty, onDirtyChange, onDraftChange, preparedDraft]);

  function updateDraft(updater: (current: Experiment) => Experiment) {
    setDraft((current) => updater(current));
    setError(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      await onSave(preparedDraft);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unknown error");
    }
  }

  return (
    <form className="settings-form" onSubmit={handleSubmit}>
      <div className="settings-header">
        <div>
          <h2>Experiment settings</h2>
          <p>Edit the manifest stored in the runtime experiments workspace.</p>
        </div>
        <div className="settings-actions">
          <TooltipButton
            className="secondary-action"
            disabled={isBusy || !isDirty}
            disabledReason={
              isBusy
                ? "Wait for the settings save to finish."
                : "Change a setting before resetting the form."
            }
            onClick={() => {
              setDraft(cloneExperiment(experiment));
              setError(null);
              onDirtyChange(false);
              onDraftChange(null);
              onReset();
            }}
            type="button"
          >
            Reset
          </TooltipButton>
          <TooltipButton
            className="primary-action"
            disabled={isBusy || !isDirty}
            disabledReason={
              isBusy
                ? "Wait for the settings save to finish."
                : "Change a setting before saving."
            }
            type="submit"
          >
            {isBusy ? "Saving..." : "Save"}
          </TooltipButton>
        </div>
      </div>

      {message !== null ? <div className="settings-message">{message}</div> : null}
      {error !== null ? <div className="settings-error">{error}</div> : null}

      <section className="settings-section">
        <h3>Identity</h3>
        <label className="settings-field">
          <span>ID</span>
          <input readOnly value={draft.id} />
        </label>
        <label className="settings-field">
          <span>Title</span>
          <input
            required
            value={draft.title}
            onChange={(event) =>
              updateDraft((current) => ({ ...current, title: event.target.value }))
            }
          />
        </label>
        <label className="settings-field settings-field-wide">
          <span>Description</span>
          <textarea
            rows={3}
            value={draft.description}
            onChange={(event) =>
              updateDraft((current) => ({
                ...current,
                description: event.target.value
              }))
            }
          />
        </label>
      </section>

      <section className="settings-section">
        <h3>Case Suite</h3>
        <label className="settings-field">
          <span>Case Suite</span>
          <select
            value={draft.case_suite_id ?? ""}
            onChange={(event) =>
              updateDraft((current) => ({
                ...current,
                case_suite_id:
                  event.target.value === "" ? null : event.target.value
              }))
            }
          >
            <option value="">No Case Suite assigned</option>
            {caseSuites.map((suite) => (
              <option key={suite.id} value={suite.id}>
                {suite.title} ({suite.id})
              </option>
            ))}
          </select>
        </label>
      </section>

      <section className="settings-section">
        <h3>Version</h3>
        <label className="settings-field">
          <span>Active version</span>
          <input readOnly value={draft.active_version} />
        </label>
      </section>

      <section className="settings-section">
        <h3>Models</h3>
        <label className="settings-field">
          <span>Generator model</span>
          <input
            required
            value={draft.models.generator_model}
            onChange={(event) =>
              updateDraft((current) => ({
                ...current,
                models: {
                  ...current.models,
                  generator_model: event.target.value
                }
              }))
            }
          />
        </label>
        <label className="settings-field">
          <span>Validator model</span>
          <input
            required
            value={draft.models.validator_model}
            onChange={(event) =>
              updateDraft((current) => ({
                ...current,
                models: {
                  ...current.models,
                  validator_model: event.target.value
                }
              }))
            }
          />
        </label>
        <label className="settings-field">
          <span>Judge model</span>
          <input
            required
            value={draft.models.judge_model}
            onChange={(event) =>
              updateDraft((current) => ({
                ...current,
                models: {
                  ...current.models,
                  judge_model: event.target.value
                }
              }))
            }
          />
        </label>
      </section>

      <section className="settings-section">
        <h3>Output</h3>
        <label className="settings-field">
          <span>Type</span>
          <input readOnly value={draft.output.type} />
        </label>
        {draft.output.type === "pydantic" ? (
          <>
            <label className="settings-field">
              <span>Model file</span>
              <input readOnly value={draft.output.model_file ?? ""} />
            </label>
            <label className="settings-field">
              <span>Model entrypoint</span>
              <input readOnly value={draft.output.model_entrypoint ?? ""} />
            </label>
          </>
        ) : null}
      </section>

      <section className="settings-section">
        <h3>Template</h3>
        <label className="settings-field">
          <span>Engine</span>
          <input readOnly value={draft.template.engine} />
        </label>
        <label className="settings-field">
          <span>Path</span>
          <input readOnly value={draft.template.path} />
        </label>
      </section>

      <section className="settings-section">
        <h3>Run defaults</h3>
        <label className="settings-field">
          <span>Repeat count</span>
          <input
            min={1}
            required
            type="number"
            value={draft.run_defaults.repeat_count}
            onChange={(event) =>
              updateDraft((current) => ({
                ...current,
                run_defaults: {
                  ...current.run_defaults,
                  repeat_count: Number(event.target.value)
                }
              }))
            }
          />
        </label>
        <label className="settings-field">
          <span>LLM cache</span>
          <input readOnly value={draft.run_defaults.llm_cache} />
        </label>
        <label className="settings-field">
          <span>Case order</span>
          <input readOnly value={draft.run_defaults.case_order} />
        </label>
      </section>
    </form>
  );
}
