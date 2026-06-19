import { useEffect, useMemo, useState, type FormEvent } from "react";

import type { GlobalSettings as GlobalSettingsModel } from "../types";
import { TooltipButton } from "./TooltipButton";

interface GlobalSettingsProps {
  isBusy: boolean;
  message: string | null;
  onDirtyChange: (isDirty: boolean) => void;
  onDraftChange: (draft: GlobalSettingsModel | null) => void;
  onReset: () => void;
  onSave: (settings: GlobalSettingsModel) => Promise<void>;
  settings: GlobalSettingsModel;
}

function cloneSettings(settings: GlobalSettingsModel): GlobalSettingsModel {
  return { ...settings };
}

function prepareForSave(settings: GlobalSettingsModel): GlobalSettingsModel {
  return {
    schema_version: "prompt_lab.settings/v1",
    default_generator_model: settings.default_generator_model.trim(),
    default_validator_model: settings.default_validator_model.trim(),
    default_judge_model: settings.default_judge_model.trim(),
    default_repeat_count: settings.default_repeat_count
  };
}

export function GlobalSettings({
  isBusy,
  message,
  onDirtyChange,
  onDraftChange,
  onReset,
  onSave,
  settings
}: GlobalSettingsProps) {
  const [draft, setDraft] = useState<GlobalSettingsModel>(() =>
    cloneSettings(settings)
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDraft(cloneSettings(settings));
    setError(null);
  }, [settings]);

  const preparedDraft = useMemo(() => prepareForSave(draft), [draft]);
  const preparedSettings = useMemo(
    () => prepareForSave(settings),
    [settings]
  );
  const isDirty = useMemo(
    () => JSON.stringify(preparedDraft) !== JSON.stringify(preparedSettings),
    [preparedDraft, preparedSettings]
  );

  useEffect(() => {
    onDirtyChange(isDirty);
    onDraftChange(isDirty ? preparedDraft : null);
  }, [isDirty, onDirtyChange, onDraftChange, preparedDraft]);

  function updateDraft(updater: (current: GlobalSettingsModel) => GlobalSettingsModel) {
    setDraft((current) => updater(current));
    setError(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (preparedDraft.default_generator_model.length === 0) {
      setError("Default generator model is required.");
      return;
    }
    if (preparedDraft.default_validator_model.length === 0) {
      setError("Default validator model is required.");
      return;
    }
    if (preparedDraft.default_judge_model.length === 0) {
      setError("Default judge model is required.");
      return;
    }
    if (preparedDraft.default_repeat_count < 1) {
      setError("Default repeat count must be at least 1.");
      return;
    }
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
          <h2>Global settings</h2>
          <p>Edit application-level settings stored in config/settings.json.</p>
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
              setDraft(cloneSettings(settings));
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
        <h3>Experiment defaults</h3>
        <label className="settings-field">
          <span>Default generator model</span>
          <input
            required
            value={draft.default_generator_model}
            onChange={(event) =>
              updateDraft((current) => ({
                ...current,
                default_generator_model: event.target.value
              }))
            }
          />
        </label>
        <label className="settings-field">
          <span>Default judge model</span>
          <input
            required
            value={draft.default_judge_model}
            onChange={(event) =>
              updateDraft((current) => ({
                ...current,
                default_judge_model: event.target.value
              }))
            }
          />
        </label>
        <label className="settings-field">
          <span>Default repeat count</span>
          <input
            min={1}
            required
            type="number"
            value={draft.default_repeat_count}
            onChange={(event) =>
              updateDraft((current) => ({
                ...current,
                default_repeat_count: Number(event.target.value)
              }))
            }
          />
        </label>
      </section>
    </form>
  );
}
