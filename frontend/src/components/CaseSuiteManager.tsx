import { useEffect, useMemo, useState, type FormEvent } from "react";

import type { Case, CaseSuite, CaseSuiteUpdateRequest } from "../types";
import type { CaseSuiteTab } from "../urlState";
import { CaseBrowser } from "./CaseBrowser";
import { EditCasePayloadModal } from "./CaseSuiteModals";
import { TooltipButton } from "./TooltipButton";
import {
  canSaveSuiteCases,
  SUITE_CASE_SELECTION_BLOCKED_MESSAGE
} from "./caseSuiteDrafts";

interface CaseSuiteManagerProps {
  activeTab: CaseSuiteTab;
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
  onTabChange: (tab: CaseSuiteTab) => void;
}

function formatCaseCount(count: number | undefined): string {
  const safeCount = count ?? 0;
  return `${safeCount} case${safeCount === 1 ? "" : "s"}`;
}

export function CaseSuiteManager({
  activeTab,
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
  onTabChange,
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
  const saveSettingsDisabled = isBusy || selectedSuite === null || !suiteDraftDirty;
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
  const resetCasesDisabled = isBusy || !caseSuiteCasesDirty;
  const resetCasesDisabledReason = isBusy
    ? "Wait for the suite case save to finish."
    : "Change suite cases before resetting.";
  const saveCasesDisabledReason =
    selectedSuite === null
      ? "Select a case suite before saving cases."
      : isBusy
        ? "Wait for the suite case save to finish."
        : !caseSuiteCasesDirty
          ? "Change suite cases before saving."
          : null;
  const resetSettingsDisabled = isBusy || !suiteDraftDirty;
  const resetSettingsDisabledReason = isBusy
    ? "Wait for the settings save to finish."
    : "Change suite settings before resetting.";
  const saveSettingsDisabledReason =
    selectedSuite === null
      ? "Select a case suite before saving settings."
      : isBusy
        ? "Wait for the settings save to finish."
        : !suiteDraftDirty
          ? "Change suite settings before saving."
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

  function handleResetSettings() {
    if (selectedSuite === null) return;
    setSuiteTitle(selectedSuite.title);
    setSuiteDescription(selectedSuite.description ?? "");
    setError(null);
  }

  async function handleSaveSettings(event: FormEvent<HTMLFormElement>) {
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
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unknown error");
    }
  }

  async function handleSaveCases() {
    if (saveSuiteCasesDisabled) return;
    setError(null);
    try {
      await onSaveCases();
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
    <section className="case-suite-workbench" aria-label="Case Suite workspace">
      {selectedSuite === null ? (
        <>
          {message !== null ? <div className="settings-message">{message}</div> : null}
          {isBusy ? <div className="settings-message">Loading suite changes</div> : null}
          {error !== null ? <div className="settings-error">{error}</div> : null}
          <div className="case-browser-empty">Select a case suite.</div>
        </>
      ) : (
        <>
          <div className="settings-header case-suite-workbench-header">
            <div>
              <h2>{selectedSuite.title}</h2>
              <p>{selectedSuite.id}</p>
            </div>
            <div className="settings-actions">
              {activeTab === "cases" ? (
                <>
                  <TooltipButton
                    className="secondary-action"
                    disabled={resetCasesDisabled}
                    disabledReason={resetCasesDisabledReason}
                    onClick={onResetCases}
                    type="button"
                  >
                    Reset
                  </TooltipButton>
                  <TooltipButton
                    className="primary-action"
                    disabled={saveSuiteCasesDisabled}
                    disabledReason={saveCasesDisabledReason}
                    onClick={handleSaveCases}
                    type="button"
                  >
                    {isBusy ? "Saving..." : "Save"}
                  </TooltipButton>
                </>
              ) : (
                <>
                  <TooltipButton
                    className="secondary-action"
                    disabled={resetSettingsDisabled}
                    disabledReason={resetSettingsDisabledReason}
                    onClick={handleResetSettings}
                    type="button"
                  >
                    Reset
                  </TooltipButton>
                  <TooltipButton
                    className="primary-action"
                    disabled={saveSettingsDisabled}
                    disabledReason={saveSettingsDisabledReason}
                    form="case-suite-settings-form"
                    type="submit"
                  >
                    {isBusy ? "Saving..." : "Save"}
                  </TooltipButton>
                </>
              )}
            </div>
          </div>

          <div
            className="workbench-tabs"
            role="tablist"
            aria-label="Case Suite sections"
          >
            <button
              aria-selected={activeTab === "cases"}
              className={
                activeTab === "cases" ? "workbench-tab is-active" : "workbench-tab"
              }
              onClick={() => onTabChange("cases")}
              role="tab"
              type="button"
            >
              Cases
            </button>
            <button
              aria-selected={activeTab === "settings"}
              className={
                activeTab === "settings"
                  ? "workbench-tab is-active"
                  : "workbench-tab"
              }
              onClick={() => onTabChange("settings")}
              role="tab"
              type="button"
            >
              Settings
            </button>
          </div>

          {activeTab === "cases" ? (
            <div className="case-suite-cases-view">
              {message !== null ? (
                <div className="settings-message">{message}</div>
              ) : null}
              {isBusy ? (
                <div className="settings-message">Loading suite changes</div>
              ) : null}
              {error !== null ? <div className="settings-error">{error}</div> : null}
              {caseSuiteCasesDirty ? (
                <div className="settings-message">
                  Unsaved suite case changes. {SUITE_CASE_SELECTION_BLOCKED_MESSAGE}
                </div>
              ) : null}
              <div className="settings-header case-suite-cases-toolbar">
                <div>
                  <h2>Cases</h2>
                  <p>{formatCaseCount(cases.length)} in this suite</p>
                </div>
                <button
                  className="secondary-action"
                  disabled={isBusy}
                  onClick={onAddCase}
                  type="button"
                >
                  Add case
                </button>
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
          ) : (
            <form
              className="settings-form"
              id="case-suite-settings-form"
              onSubmit={handleSaveSettings}
            >
              <h2 className="case-suite-settings-title">Case Suite settings</h2>
              {message !== null ? (
                <div className="settings-message">{message}</div>
              ) : null}
              {isBusy ? (
                <div className="settings-message">Loading suite changes</div>
              ) : null}
              {error !== null ? <div className="settings-error">{error}</div> : null}

              <section className="settings-section">
                <h3>Identity</h3>
                <label className="settings-field">
                  <span>ID</span>
                  <input readOnly value={selectedSuite.id} />
                </label>
                <label className="settings-field">
                  <span>Title</span>
                  <input
                    disabled={suiteControlsDisabled}
                    onChange={(event) => {
                      setSuiteTitle(event.target.value);
                      setError(null);
                    }}
                    required
                    value={suiteTitle}
                  />
                </label>
                <label className="settings-field settings-field-wide">
                  <span>Description</span>
                  <textarea
                    disabled={suiteControlsDisabled}
                    onChange={(event) => {
                      setSuiteDescription(event.target.value);
                      setError(null);
                    }}
                    rows={3}
                    value={suiteDescription}
                  />
                </label>
              </section>

              <section className="settings-section">
                <h3>Usage</h3>
                <p className="settings-section-description">
                  {referencedBy.length === 0
                    ? "No references."
                    : `Referenced by ${referencedBy.join(", ")}.`}
                </p>
              </section>

              <section className="settings-section settings-section-danger">
                <h3>Danger zone</h3>
                <p className="settings-section-description">
                  Delete this case suite from the local workspace.
                </p>
                <TooltipButton
                  className="secondary-action danger-action"
                  disabled={deleteDisabled}
                  disabledReason={deleteDisabledReason}
                  onClick={handleDeleteSuite}
                  type="button"
                >
                  Delete suite
                </TooltipButton>
              </section>
            </form>
          )}
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
    </section>
  );
}
