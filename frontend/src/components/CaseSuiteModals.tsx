import { useState, type FormEvent } from "react";

import type { Case, CaseSuiteCreateRequest } from "../types";
import { parseCasePayloadDraft } from "./caseSuiteDrafts";

interface NewCaseSuiteModalProps {
  error: string | null;
  isBusy: boolean;
  onCancel: () => void;
  onSubmit: (request: CaseSuiteCreateRequest) => Promise<void>;
}

interface AddCaseModalProps {
  existingCases: Case[];
  isBusy: boolean;
  onCancel: () => void;
  onSubmit: (artifactCase: Case) => void;
}

async function ignoreHandledRejection(action: () => Promise<void>): Promise<void> {
  try {
    await action();
  } catch {
    // Parent handlers own user-visible errors.
  }
}

export function NewCaseSuiteModal({
  error,
  isBusy,
  onCancel,
  onSubmit
}: NewCaseSuiteModalProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const trimmedTitle = title.trim();
  const submitDisabled = isBusy || trimmedTitle === "";

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitDisabled) return;
    void ignoreHandledRejection(() =>
      onSubmit({ title: trimmedTitle, description: description.trim() })
    );
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <form
        aria-labelledby="new-case-suite-title"
        aria-modal="true"
        className="settings-navigation-modal experiment-management-modal"
        onSubmit={handleSubmit}
        role="dialog"
      >
        <div>
          <h2 id="new-case-suite-title">New Case Suite</h2>
          <p>Create a reusable suite of case payloads for experiments.</p>
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
          <span>Description</span>
          <textarea
            disabled={isBusy}
            onChange={(event) => setDescription(event.target.value)}
            rows={3}
            value={description}
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
            {isBusy ? "Creating..." : "Create suite"}
          </button>
        </div>
      </form>
    </div>
  );
}

export function AddCaseModal({
  existingCases,
  isBusy,
  onCancel,
  onSubmit
}: AddCaseModalProps) {
  const [caseId, setCaseId] = useState("");
  const [payloadText, setPayloadText] = useState("{\n  \n}");
  const [error, setError] = useState<string | null>(null);
  const trimmedCaseId = caseId.trim();
  const submitDisabled = isBusy || trimmedCaseId === "";

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitDisabled) return;
    if (existingCases.some((artifactCase) => artifactCase.id === trimmedCaseId)) {
      setError(`Case ${trimmedCaseId} already exists.`);
      return;
    }
    const parsed = parseCasePayloadDraft(payloadText);
    if (!parsed.ok) {
      setError(parsed.error);
      return;
    }
    setError(null);
    onSubmit({ id: trimmedCaseId, enabled: true, payload: parsed.payload });
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <form
        aria-labelledby="add-case-title"
        aria-modal="true"
        className="settings-navigation-modal experiment-management-modal"
        onSubmit={handleSubmit}
        role="dialog"
      >
        <div>
          <h2 id="add-case-title">Add case</h2>
          <p>Add a JSON object payload to the selected Case Suite.</p>
        </div>

        <label className="settings-field">
          <span>Case ID</span>
          <input
            autoFocus
            disabled={isBusy}
            onChange={(event) => setCaseId(event.target.value)}
            required
            value={caseId}
          />
        </label>

        <label className="settings-field">
          <span>JSON object</span>
          <textarea
            disabled={isBusy}
            onChange={(event) => setPayloadText(event.target.value)}
            rows={8}
            value={payloadText}
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
            Add case
          </button>
        </div>
      </form>
    </div>
  );
}
