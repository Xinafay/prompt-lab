import { useEffect, useMemo, useState, type FormEvent } from "react";

import type { Experiment, OutputType } from "../types";

interface ExperimentSettingsProps {
  experiment: Experiment;
  isBusy: boolean;
  message: string | null;
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
  return draft;
}

export function ExperimentSettings({
  experiment,
  isBusy,
  message,
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

  function handleOutputTypeChange(type: OutputType) {
    updateDraft((current) => {
      if (type === "text") {
        return { ...current, output: { type: "text" } };
      }
      return {
        ...current,
        output: {
          type: "pydantic",
          model_file: current.output.model_file ?? "model.py",
          model_entrypoint: current.output.model_entrypoint ?? "",
          validation_context_from_case:
            current.output.validation_context_from_case ?? null
        }
      };
    });
  }

  return (
    <form className="settings-form" onSubmit={handleSubmit}>
      <div className="settings-header">
        <div>
          <h2>Experiment settings</h2>
          <p>Edit the manifest stored in the runtime experiments workspace.</p>
        </div>
        <div className="settings-actions">
          <button
            className="secondary-action"
            disabled={isBusy || !isDirty}
            onClick={() => {
              setDraft(cloneExperiment(experiment));
              setError(null);
              onReset();
            }}
            type="button"
          >
            Reset
          </button>
          <button className="primary-action" disabled={isBusy || !isDirty} type="submit">
            {isBusy ? "Saving..." : "Save"}
          </button>
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
        <h3>Version</h3>
        <label className="settings-field">
          <span>Active version</span>
          <input
            required
            value={draft.active_version}
            onChange={(event) =>
              updateDraft((current) => ({
                ...current,
                active_version: event.target.value
              }))
            }
          />
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
          <select
            value={draft.output.type}
            onChange={(event) => handleOutputTypeChange(event.target.value as OutputType)}
          >
            <option value="text">text</option>
            <option value="pydantic">pydantic</option>
          </select>
        </label>
        {draft.output.type === "pydantic" ? (
          <>
            <label className="settings-field">
              <span>Model file</span>
              <input
                required
                value={draft.output.model_file ?? ""}
                onChange={(event) =>
                  updateDraft((current) => ({
                    ...current,
                    output: { ...current.output, model_file: event.target.value }
                  }))
                }
              />
            </label>
            <label className="settings-field">
              <span>Model entrypoint</span>
              <input
                required
                value={draft.output.model_entrypoint ?? ""}
                onChange={(event) =>
                  updateDraft((current) => ({
                    ...current,
                    output: {
                      ...current.output,
                      model_entrypoint: event.target.value
                    }
                  }))
                }
              />
            </label>
            <label className="settings-field">
              <span>Validation context field</span>
              <input
                value={draft.output.validation_context_from_case ?? ""}
                onChange={(event) =>
                  updateDraft((current) => ({
                    ...current,
                    output: {
                      ...current.output,
                      validation_context_from_case:
                        event.target.value.trim() === ""
                          ? null
                          : event.target.value
                    }
                  }))
                }
              />
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
          <input
            required
            value={draft.template.path}
            onChange={(event) =>
              updateDraft((current) => ({
                ...current,
                template: { ...current.template, path: event.target.value }
              }))
            }
          />
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
