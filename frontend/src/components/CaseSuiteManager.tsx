import { useEffect, useMemo, useState, type FormEvent } from "react";

import type { Case, CaseSuite, CaseSuiteUpdateRequest } from "../types";
import {
  canSaveSuiteCases,
  parseCasePayloadDraft,
  SUITE_CASE_SELECTION_BLOCKED_MESSAGE
} from "./caseSuiteDrafts";

interface CaseSuiteManagerProps {
  suites: CaseSuite[];
  selectedSuiteId: string | null;
  cases: Case[];
  isBusy: boolean;
  message: string | null;
  caseSuiteCasesDirty: boolean;
  onUpdateSuite: (
    suiteId: string,
    request: CaseSuiteUpdateRequest
  ) => void | Promise<void>;
  onDeleteSuite: (suiteId: string) => void | Promise<void>;
  onCasesChange: (cases: Case[]) => void;
  onAddCase: () => void;
  onResetCases: () => void;
  onSaveCases: () => void | Promise<void>;
}

function formatCaseCount(count: number | undefined): string {
  const safeCount = count ?? 0;
  return `${safeCount} case${safeCount === 1 ? "" : "s"}`;
}

function formatPayload(payload: Record<string, unknown>): string {
  return JSON.stringify(payload, null, 2);
}

export function CaseSuiteManager({
  suites,
  selectedSuiteId,
  cases,
  caseSuiteCasesDirty,
  isBusy,
  message,
  onCasesChange,
  onDeleteSuite,
  onAddCase,
  onResetCases,
  onSaveCases,
  onUpdateSuite
}: CaseSuiteManagerProps) {
  const selectedSuite = useMemo(
    () => suites.find((suite) => suite.id === selectedSuiteId) ?? null,
    [selectedSuiteId, suites]
  );
  const [suiteTitle, setSuiteTitle] = useState(selectedSuite?.title ?? "");
  const [suiteDescription, setSuiteDescription] = useState(
    selectedSuite?.description ?? ""
  );
  const [selectedCaseId, setSelectedCaseId] = useState(cases[0]?.id ?? "");
  const selectedCase =
    cases.find((artifactCase) => artifactCase.id === selectedCaseId) ??
    cases[0] ??
    null;
  const [payloadText, setPayloadText] = useState(
    selectedCase === null ? "" : formatPayload(selectedCase.payload)
  );
  const [error, setError] = useState<string | null>(null);
  const [payloadError, setPayloadError] = useState<string | null>(null);
  const referencedBy = selectedSuite?.experiment_ids ?? [];
  const hasCasePayloadError = payloadError !== null;
  const suiteMutationDisabled = isBusy || caseSuiteCasesDirty;
  const saveSuiteCasesDisabled = !canSaveSuiteCases({
    isBusy,
    isDirty: caseSuiteCasesDirty,
    hasPayloadError: hasCasePayloadError,
    selectedSuiteId: selectedSuite?.id ?? null
  });
  const deleteDisabled =
    selectedSuite === null || referencedBy.length > 0 || suiteMutationDisabled;

  useEffect(() => {
    setSuiteTitle(selectedSuite?.title ?? "");
    setSuiteDescription(selectedSuite?.description ?? "");
    setError(null);
    setPayloadError(null);
  }, [selectedSuite]);

  useEffect(() => {
    if (cases.length === 0) {
      setSelectedCaseId("");
      setPayloadText("");
      setPayloadError(null);
      return;
    }
    const nextSelected =
      cases.find((artifactCase) => artifactCase.id === selectedCaseId) ??
      cases[0];
    setSelectedCaseId(nextSelected.id);
    setPayloadText(formatPayload(nextSelected.payload));
    setPayloadError(null);
  }, [cases, selectedCaseId]);

  async function handleUpdateSuite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedSuite === null) return;
    const title = suiteTitle.trim();
    if (title.length === 0) {
      setError("Suite title is required.");
      return;
    }
    setError(null);
    try {
      await onUpdateSuite(selectedSuite.id, {
        title,
        description: suiteDescription.trim()
      });
    } catch (updateError) {
      setError(updateError instanceof Error ? updateError.message : "Unknown error");
    }
  }

  async function handleDeleteSuite() {
    if (selectedSuite === null || deleteDisabled) return;
    setError(null);
    try {
      await onDeleteSuite(selectedSuite.id);
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Unknown error");
    }
  }

  function handlePayloadTextChange(nextText: string) {
    setPayloadText(nextText);
    if (selectedCase === null) return;
    const parsed = parseCasePayloadDraft(nextText);
    if (parsed.ok) {
      setPayloadError(null);
      setError(null);
      onCasesChange(
        cases.map((artifactCase) =>
          artifactCase.id === selectedCase.id
            ? { ...artifactCase, payload: parsed.payload }
            : artifactCase
        )
      );
    } else {
      setPayloadError(parsed.error);
      setError(parsed.error);
    }
  }

  function handleDeleteSelectedCase() {
    if (selectedCase === null) return;
    const nextCases = cases.filter(
      (artifactCase) => artifactCase.id !== selectedCase.id
    );
    onCasesChange(nextCases);
    setSelectedCaseId(nextCases[0]?.id ?? "");
    setPayloadError(null);
    setError(null);
  }

  async function handleSaveCases() {
    if (hasCasePayloadError) {
      setError(payloadError);
      return;
    }
    setError(null);
    try {
      await onSaveCases();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unknown error");
    }
  }

  return (
    <section className="case-suite-manager" aria-label="Case Suite details">
      <div className="case-suite-detail">
        {message !== null ? <div className="settings-message">{message}</div> : null}
        {isBusy ? <div className="settings-message">Loading suite changes</div> : null}
        {error !== null ? <div className="settings-error">{error}</div> : null}
        {caseSuiteCasesDirty ? (
          <div className="settings-message">
            Unsaved suite case changes. {SUITE_CASE_SELECTION_BLOCKED_MESSAGE}
          </div>
        ) : null}

        {selectedSuite === null ? (
          <div className="case-browser-empty">Select a case suite.</div>
        ) : (
          <>
            <form className="case-suite-editor" onSubmit={handleUpdateSuite}>
              <div className="case-suite-editor-heading">
                <div>
                  <h3>{selectedSuite.title}</h3>
                  <p>{selectedSuite.id}</p>
                </div>
                <div className="case-suite-actions">
                  <button
                    className="secondary-action"
                    disabled={suiteMutationDisabled}
                    type="submit"
                  >
                    Save suite
                  </button>
                  <button
                    className="secondary-action danger-action"
                    disabled={deleteDisabled}
                    onClick={handleDeleteSuite}
                    type="button"
                  >
                    Delete suite
                  </button>
                </div>
              </div>
              {referencedBy.length > 0 ? (
                <p className="case-suite-reference">
                  Cannot delete a suite referenced by experiments. Referenced by{" "}
                  {referencedBy.join(", ")}.
                </p>
              ) : null}
              <div className="case-suite-fields">
                <label>
                  <span>Title</span>
                  <input
                    disabled={suiteMutationDisabled}
                    onChange={(event) => setSuiteTitle(event.target.value)}
                    value={suiteTitle}
                  />
                </label>
                <label>
                  <span>Description</span>
                  <textarea
                    disabled={suiteMutationDisabled}
                    onChange={(event) => setSuiteDescription(event.target.value)}
                    rows={3}
                    value={suiteDescription}
                  />
                </label>
              </div>
            </form>

            <div className="case-suite-cases">
              <div className="case-suite-cases-list">
                <div className="case-suite-cases-heading">
                  <h3>Suite cases</h3>
                  <div>
                    <span>{formatCaseCount(cases.length)}</span>
                    <button
                      className="secondary-action"
                      disabled={isBusy || selectedSuite === null}
                      onClick={onAddCase}
                      type="button"
                    >
                      Add case
                    </button>
                  </div>
                </div>
                {cases.length === 0 ? (
                  <div className="case-browser-empty">No cases in this suite.</div>
                ) : (
                  cases.map((artifactCase) => (
                    <button
                      className={
                        artifactCase.id === selectedCase?.id
                          ? "case-suite-case-item is-selected"
                          : "case-suite-case-item"
                      }
                      disabled={isBusy}
                      key={artifactCase.id}
                      onClick={() => setSelectedCaseId(artifactCase.id)}
                      type="button"
                    >
                      <strong>{artifactCase.id}</strong>
                      <span>{Object.keys(artifactCase.payload).length} keys</span>
                    </button>
                  ))
                )}
              </div>

              <div className="case-suite-payload-panel">
                <div className="case-suite-payload-editor">
                  <div className="case-suite-payload-heading">
                    <h3>Payload JSON</h3>
                    <button
                      className="secondary-action danger-action"
                      disabled={isBusy || selectedCase === null}
                      onClick={handleDeleteSelectedCase}
                      type="button"
                    >
                      Delete selected case
                    </button>
                  </div>
                  <textarea
                    disabled={isBusy || selectedCase === null}
                    onChange={(event) => handlePayloadTextChange(event.target.value)}
                    rows={14}
                    value={payloadText}
                  />
                  <button
                    className="primary-action"
                    disabled={saveSuiteCasesDisabled}
                    onClick={() => void handleSaveCases()}
                    type="button"
                  >
                    Save suite cases
                  </button>
                  <button
                    className="secondary-action"
                    disabled={isBusy || !caseSuiteCasesDirty}
                    onClick={onResetCases}
                    type="button"
                  >
                    Reset suite case changes
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
