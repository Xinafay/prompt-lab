import { useEffect, useMemo, useState, type FormEvent } from "react";

import type { Case, CaseSuite, CaseSuiteUpdateRequest } from "../types";
import { CaseBrowser } from "./CaseBrowser";
import { EditCasePayloadModal } from "./CaseSuiteModals";
import { TooltipButton } from "./TooltipButton";
import {
  canSaveSuiteCases,
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
  const [editingCase, setEditingCase] = useState<Case | null>(null);
  const [error, setError] = useState<string | null>(null);
  const referencedBy = selectedSuite?.experiment_ids ?? [];
  const suiteTitleDirty =
    selectedSuite !== null && suiteTitle.trim() !== selectedSuite.title;
  const suiteDescriptionDirty =
    selectedSuite !== null &&
    suiteDescription.trim() !== (selectedSuite.description ?? "");
  const suiteDraftDirty = suiteTitleDirty || suiteDescriptionDirty;
  const suiteControlsDisabled = isBusy;
  const saveSuiteCasesDisabled = !canSaveSuiteCases({
    isBusy,
    isDirty: caseSuiteCasesDirty,
    hasPayloadError: false,
    selectedSuiteId: selectedSuite?.id ?? null
  });
  const saveChangesDisabled =
    isBusy ||
    selectedSuite === null ||
    (!suiteDraftDirty && saveSuiteCasesDisabled);
  const deleteDisabled =
    selectedSuite === null || referencedBy.length > 0 || isBusy || caseSuiteCasesDirty;
  const deleteDisabledReason =
    selectedSuite === null
      ? "Select a case suite before deleting."
      : referencedBy.length > 0
        ? `Cannot delete a suite referenced by experiments: ${referencedBy.join(", ")}.`
        : caseSuiteCasesDirty
          ? "Save or reset suite case changes before deleting this suite."
          : isBusy
            ? "Wait for the current suite action to finish."
            : null;

  useEffect(() => {
    setSuiteTitle(selectedSuite?.title ?? "");
    setSuiteDescription(selectedSuite?.description ?? "");
    setEditingCase(null);
    setError(null);
  }, [selectedSuite]);

  useEffect(() => {
    if (
      editingCase !== null &&
      !cases.some((artifactCase) => artifactCase.id === editingCase.id)
    ) {
      setEditingCase(null);
    }
  }, [cases, editingCase]);

  function handleEditCasePayload(updatedCase: Case) {
    onCasesChange(
      cases.map((artifactCase) =>
        artifactCase.id === updatedCase.id ? updatedCase : artifactCase
      )
    );
    setEditingCase(null);
    setError(null);
  }

  function handleDeleteCase(artifactCase: Case) {
    if (isBusy) {
      return;
    }
    onCasesChange(cases.filter((item) => item.id !== artifactCase.id));
    setError(null);
  }

  async function handleSaveChanges(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedSuite === null) return;
    const title = suiteTitle.trim();
    if (title.length === 0) {
      setError("Suite title is required.");
      return;
    }
    setError(null);
    try {
      if (suiteDraftDirty) {
        await onUpdateSuite(selectedSuite.id, {
          title,
          description: suiteDescription.trim()
        });
      }
      if (!saveSuiteCasesDisabled) {
        await onSaveCases();
      }
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unknown error");
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
            <form className="case-suite-editor" onSubmit={handleSaveChanges}>
              <div className="case-suite-editor-heading">
                <div>
                  <h3>{selectedSuite.title}</h3>
                  <p>{selectedSuite.id}</p>
                </div>
                <div className="case-suite-actions">
                  <button
                    className="primary-action"
                    disabled={saveChangesDisabled}
                    type="submit"
                  >
                    Save changes
                  </button>
                  <TooltipButton
                    className="secondary-action danger-action"
                    disabled={deleteDisabled}
                    disabledReason={deleteDisabledReason}
                    onClick={handleDeleteSuite}
                    type="button"
                  >
                    Delete suite
                  </TooltipButton>
                </div>
              </div>
              <div className="case-suite-fields">
                <label>
                  <span>Title</span>
                  <input
                    disabled={suiteControlsDisabled}
                    onChange={(event) => setSuiteTitle(event.target.value)}
                    value={suiteTitle}
                  />
                </label>
                <label>
                  <span>Description</span>
                  <textarea
                    disabled={suiteControlsDisabled}
                    onChange={(event) => setSuiteDescription(event.target.value)}
                    rows={3}
                    value={suiteDescription}
                  />
                </label>
              </div>
            </form>

            <div className="case-suite-cases">
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
              {cases.length === 0 ? (
                <div className="case-browser-empty">No cases in this suite.</div>
              ) : (
                <CaseBrowser
                  cases={cases}
                  isBusy={isBusy}
                  onDeleteCase={handleDeleteCase}
                  onEditCase={setEditingCase}
                  suiteTitle={selectedSuite.title}
                />
              )}
            </div>
            {editingCase === null ? null : (
              <EditCasePayloadModal
                artifactCase={editingCase}
                isBusy={isBusy}
                onCancel={() => setEditingCase(null)}
                onSubmit={handleEditCasePayload}
              />
            )}
          </>
        )}
      </div>
    </section>
  );
}
