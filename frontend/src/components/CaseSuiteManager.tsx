import { useEffect, useMemo, useState, type FormEvent } from "react";

import type {
  Case,
  CaseSuite,
  CaseSuiteCreateRequest,
  CaseSuiteUpdateRequest
} from "../types";
import {
  canSaveSuiteCases,
  isSuiteMutationDisabled,
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
  onSelectSuite: (suiteId: string) => void;
  onCreateSuite: (request: CaseSuiteCreateRequest) => void | Promise<void>;
  onUpdateSuite: (
    suiteId: string,
    request: CaseSuiteUpdateRequest
  ) => void | Promise<void>;
  onDeleteSuite: (suiteId: string) => void | Promise<void>;
  onCasesChange: (cases: Case[]) => void;
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
  onCreateSuite,
  onDeleteSuite,
  onResetCases,
  onSaveCases,
  onSelectSuite,
  onUpdateSuite
}: CaseSuiteManagerProps) {
  const selectedSuite = useMemo(
    () => suites.find((suite) => suite.id === selectedSuiteId) ?? null,
    [selectedSuiteId, suites]
  );
  const [createTitle, setCreateTitle] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [suiteTitle, setSuiteTitle] = useState(selectedSuite?.title ?? "");
  const [suiteDescription, setSuiteDescription] = useState(
    selectedSuite?.description ?? ""
  );
  const [selectedCaseId, setSelectedCaseId] = useState(cases[0]?.id ?? "");
  const selectedCase =
    cases.find((artifactCase) => artifactCase.id === selectedCaseId) ??
    cases[0] ??
    null;
  const [addCaseId, setAddCaseId] = useState("");
  const [addPayloadText, setAddPayloadText] = useState("{\n  \n}");
  const [payloadText, setPayloadText] = useState(
    selectedCase === null ? "" : formatPayload(selectedCase.payload)
  );
  const [error, setError] = useState<string | null>(null);
  const [payloadError, setPayloadError] = useState<string | null>(null);
  const referencedBy = selectedSuite?.experiment_ids ?? [];
  const hasCasePayloadError = payloadError !== null;
  const suiteMutationDisabled = isSuiteMutationDisabled({
    isBusy,
    caseSuiteCasesDirty
  });
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

  async function handleCreateSuite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const title = createTitle.trim();
    if (title.length === 0) {
      setError("Suite title is required.");
      return;
    }
    setError(null);
    try {
      await onCreateSuite({
        title,
        description: createDescription.trim()
      });
      setCreateTitle("");
      setCreateDescription("");
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Unknown error");
    }
  }

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

  function handleAddCase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const caseId = addCaseId.trim();
    if (caseId.length === 0) {
      setError("Case ID is required.");
      return;
    }
    if (cases.some((artifactCase) => artifactCase.id === caseId)) {
      setError(`Case ${caseId} already exists.`);
      return;
    }
    const parsed = parseCasePayloadDraft(addPayloadText);
    if (parsed.ok) {
      setError(null);
      onCasesChange([
        ...cases,
        { id: caseId, enabled: true, payload: parsed.payload }
      ]);
      setSelectedCaseId(caseId);
      setAddCaseId("");
      setAddPayloadText("{\n  \n}");
    } else {
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
    <section className="case-suite-manager">
      <aside className="case-suite-sidebar" aria-label="Case suite list">
        <div className="case-suite-header">
          <div>
            <h2>Case Suites</h2>
            <p>{suites.length} suite{suites.length === 1 ? "" : "s"}</p>
          </div>
          {isBusy ? <span>Loading suite changes</span> : null}
        </div>

        <div className="case-suite-list">
          {suites.map((suite) => {
            const experimentIds = suite.experiment_ids ?? [];
            return (
              <button
                className={
                  suite.id === selectedSuiteId
                    ? "case-suite-list-item is-selected"
                    : "case-suite-list-item"
                }
                disabled={suiteMutationDisabled}
                key={suite.id}
                onClick={() => onSelectSuite(suite.id)}
                type="button"
              >
                <strong>{suite.title}</strong>
                <span>{suite.id}</span>
                <span>{formatCaseCount(suite.case_count)}</span>
                {experimentIds.length > 0 ? (
                  <span>Referenced by {experimentIds.join(", ")}</span>
                ) : null}
              </button>
            );
          })}
        </div>

        <form className="case-suite-panel-form" onSubmit={handleCreateSuite}>
          <h3>Create suite</h3>
          <label>
            <span>Title</span>
            <input
              disabled={suiteMutationDisabled}
              onChange={(event) => setCreateTitle(event.target.value)}
              value={createTitle}
            />
          </label>
          <label>
            <span>Description</span>
            <textarea
              disabled={suiteMutationDisabled}
              onChange={(event) => setCreateDescription(event.target.value)}
              rows={3}
              value={createDescription}
            />
          </label>
          <button
            className="secondary-action"
            disabled={suiteMutationDisabled}
            type="submit"
          >
            Create suite
          </button>
        </form>
      </aside>

      <div className="case-suite-detail">
        {message !== null ? <div className="settings-message">{message}</div> : null}
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
                  <span>{formatCaseCount(cases.length)}</span>
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
                <form className="case-suite-add-case" onSubmit={handleAddCase}>
                  <h3>Add case</h3>
                  <label>
                    <span>Case ID</span>
                    <input
                      disabled={isBusy}
                      onChange={(event) => setAddCaseId(event.target.value)}
                      value={addCaseId}
                    />
                  </label>
                  <label>
                    <span>JSON object</span>
                    <textarea
                      disabled={isBusy}
                      onChange={(event) => setAddPayloadText(event.target.value)}
                      rows={5}
                      value={addPayloadText}
                    />
                  </label>
                  <button className="secondary-action" disabled={isBusy} type="submit">
                    Add case
                  </button>
                </form>

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
