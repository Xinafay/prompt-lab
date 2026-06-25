import { useState, type FormEvent } from "react";

import type {
  ExperimentCloneRequest,
  ExperimentCreateRequest,
  OutputType
} from "../types";

interface NewExperimentModalProps {
  error: string | null;
  isBusy: boolean;
  onCancel: () => void;
  onSubmit: (request: ExperimentCreateRequest) => Promise<void>;
}

interface CloneExperimentModalProps {
  error: string | null;
  isBusy: boolean;
  onCancel: () => void;
  onSubmit: (request: ExperimentCloneRequest) => Promise<void>;
  sourceTitle: string;
}

interface DeleteExperimentModalProps {
  error: string | null;
  experimentTitle: string;
  isBusy: boolean;
  onCancel: () => void;
  onConfirm: () => Promise<void>;
}

async function ignoreHandledRejection(action: () => Promise<void>): Promise<void> {
  try {
    await action();
  } catch {
    // Parent handlers own user-visible errors so modal submissions do not leak
    // unhandled promise rejections during failed API calls.
  }
}

export function NewExperimentModal({
  error,
  isBusy,
  onCancel,
  onSubmit
}: NewExperimentModalProps) {
  const [title, setTitle] = useState("");
  const [outputType, setOutputType] = useState<OutputType>("text");
  const [modelEntrypoint, setModelEntrypoint] = useState("model.Output");

  const trimmedTitle = title.trim();
  const trimmedModelEntrypoint = modelEntrypoint.trim();
  const submitDisabled =
    isBusy ||
    trimmedTitle === "" ||
    (outputType === "pydantic" && trimmedModelEntrypoint === "");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitDisabled) return;
    void ignoreHandledRejection(() =>
      onSubmit({
        title: trimmedTitle,
        output_type: outputType,
        model_entrypoint:
          outputType === "pydantic" ? trimmedModelEntrypoint : null
      })
    );
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <form
        aria-labelledby="new-experiment-title"
        aria-modal="true"
        className="modal-card modal-card-compact"
        onSubmit={handleSubmit}
        role="dialog"
      >
        <div>
          <h2 id="new-experiment-title">New experiment</h2>
          <p>
            Create a local experiment. The title is used to generate a unique
            slug, and prompt.md is created for the first version.
          </p>
        </div>

        <label className="settings-field">
          <span>Title</span>
          <input
            autoFocus
            disabled={isBusy}
            onChange={(event) => setTitle(event.target.value)}
            required
            value={title}
          />
        </label>

        <label className="settings-field">
          <span>Output type</span>
          <select
            disabled={isBusy}
            onChange={(event) => setOutputType(event.target.value as OutputType)}
            value={outputType}
          >
            <option value="text">text</option>
            <option value="pydantic">pydantic</option>
          </select>
        </label>

        {outputType === "pydantic" ? (
          <label className="settings-field">
            <span>Model entrypoint</span>
            <input
              disabled={isBusy}
              onChange={(event) => setModelEntrypoint(event.target.value)}
              required
              value={modelEntrypoint}
            />
          </label>
        ) : null}

        {error !== null ? <div className="settings-error">{error}</div> : null}

        <div className="modal-actions">
          <button
            className="secondary-action"
            disabled={isBusy}
            onClick={onCancel}
            type="button"
          >
            Cancel
          </button>
          <button className="primary-action" disabled={submitDisabled} type="submit">
            {isBusy ? "Creating..." : "Create experiment"}
          </button>
        </div>
      </form>
    </div>
  );
}

export function CloneExperimentModal({
  error,
  isBusy,
  onCancel,
  onSubmit,
  sourceTitle
}: CloneExperimentModalProps) {
  const [title, setTitle] = useState(`Copy of ${sourceTitle}`);
  const trimmedTitle = title.trim();
  const submitDisabled = isBusy || trimmedTitle === "";

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitDisabled) return;
    void ignoreHandledRejection(() => onSubmit({ title: trimmedTitle }));
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <form
        aria-labelledby="clone-experiment-title"
        aria-modal="true"
        className="modal-card modal-card-compact"
        onSubmit={handleSubmit}
        role="dialog"
      >
        <div>
          <h2 id="clone-experiment-title">Clone experiment</h2>
          <p>
            This creates a full local copy of {sourceTitle}. It copies cases,
            versions, prompts, models, validators, and artifacts.
          </p>
        </div>

        <label className="settings-field">
          <span>Title</span>
          <input
            autoFocus
            disabled={isBusy}
            onChange={(event) => setTitle(event.target.value)}
            required
            value={title}
          />
        </label>

        {error !== null ? <div className="settings-error">{error}</div> : null}

        <div className="modal-actions">
          <button
            className="secondary-action"
            disabled={isBusy}
            onClick={onCancel}
            type="button"
          >
            Cancel
          </button>
          <button className="primary-action" disabled={submitDisabled} type="submit">
            {isBusy ? "Cloning..." : "Clone experiment"}
          </button>
        </div>
      </form>
    </div>
  );
}

export function DeleteExperimentModal({
  error,
  experimentTitle,
  isBusy,
  onCancel,
  onConfirm
}: DeleteExperimentModalProps) {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isBusy) return;
    void ignoreHandledRejection(onConfirm);
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <form
        aria-labelledby="delete-experiment-title"
        aria-modal="true"
        className="modal-card modal-card-compact"
        onSubmit={handleSubmit}
        role="dialog"
      >
        <div>
          <h2 id="delete-experiment-title">Delete experiment</h2>
          <p>
            Delete {experimentTitle} from the local workspace. This removes its
            experiment manifest, cases, versions, prompts, models, validators,
            runs, validations, reviews, proposals, and comparisons.
          </p>
        </div>

        {error !== null ? <div className="settings-error">{error}</div> : null}

        <div className="modal-actions">
          <button
            className="secondary-action"
            disabled={isBusy}
            onClick={onCancel}
            type="button"
          >
            Cancel
          </button>
          <button
            className="secondary-action danger-action"
            disabled={isBusy}
            type="submit"
          >
            {isBusy ? "Deleting..." : "Delete experiment"}
          </button>
        </div>
      </form>
    </div>
  );
}
