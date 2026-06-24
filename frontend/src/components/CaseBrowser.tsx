import { type ChangeEvent, useEffect, useMemo, useRef, useState } from "react";

import type { Case, VersionOverview } from "../types";
import { describeValue, ValuePreview } from "./ValuePreview";

interface CaseBrowserProps {
  cases: VersionOverview["cases"];
  isBusy?: boolean;
  onCasesChange?: (cases: Case[]) => void;
}

function normalizeQuery(value: string): string {
  return value.trim().toLocaleLowerCase();
}

function formatJson(value: unknown): string {
  return JSON.stringify(value, null, 2) ?? "undefined";
}

function formatCaseTitle(caseId: string): string {
  return caseId
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toLocaleUpperCase() + part.slice(1))
    .join(" ");
}

function deriveCaseId(fileName: string): string {
  return fileName.replace(/\.json$/i, "").trim();
}

function isJsonObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function caseMatchesQuery(artifactCase: Case, caseQuery: string): boolean {
  if (caseQuery === "") {
    return true;
  }
  return artifactCase.id.toLocaleLowerCase().includes(caseQuery);
}

function caseMatchesPayloadQuery(
  artifactCase: Case,
  payloadQuery: string
): boolean {
  if (payloadQuery === "") {
    return true;
  }
  return Object.keys(artifactCase.payload).some((key) =>
    key.toLocaleLowerCase().includes(payloadQuery)
  );
}

export function CaseBrowser({
  cases,
  isBusy = false,
  onCasesChange
}: CaseBrowserProps) {
  const [caseQuery, setCaseQuery] = useState("");
  const [bindingQuery, setBindingQuery] = useState("");
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(
    cases[0]?.id ?? null
  );
  const [caseMessage, setCaseMessage] = useState<string | null>(null);
  const [caseError, setCaseError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const filteredCases = useMemo(() => {
    const normalizedCaseQuery = normalizeQuery(caseQuery);
    const normalizedBindingQuery = normalizeQuery(bindingQuery);
    return cases.filter(
      (artifactCase) =>
        caseMatchesQuery(artifactCase, normalizedCaseQuery) &&
        caseMatchesPayloadQuery(artifactCase, normalizedBindingQuery)
    );
  }, [bindingQuery, caseQuery, cases]);

  useEffect(() => {
    if (filteredCases.length === 0) {
      return;
    }
    if (
      selectedCaseId === null ||
      !filteredCases.some((artifactCase) => artifactCase.id === selectedCaseId)
    ) {
      setSelectedCaseId(filteredCases[0].id);
    }
  }, [filteredCases, selectedCaseId]);

  const selectedCase =
    filteredCases.find((artifactCase) => artifactCase.id === selectedCaseId) ??
    null;
  const normalizedBindingQuery = normalizeQuery(bindingQuery);
  const selectedPayloadEntries =
    selectedCase === null
      ? []
      : Object.entries(selectedCase.payload).filter(
          ([key]) =>
            normalizedBindingQuery === "" ||
            key.toLocaleLowerCase().includes(normalizedBindingQuery)
        );
  const selectedPayloadCount =
    selectedCase === null ? 0 : Object.keys(selectedCase.payload).length;
  const canEdit = onCasesChange !== undefined;

  async function handleFileInputChange(
    event: ChangeEvent<HTMLInputElement>
  ): Promise<void> {
    const file = event.currentTarget.files?.[0] ?? null;
    event.currentTarget.value = "";
    if (file === null || onCasesChange === undefined) {
      return;
    }
    const caseId = deriveCaseId(file.name);
    if (caseId.length === 0) {
      setCaseMessage(null);
      setCaseError("Case file name must include a case id.");
      return;
    }
    if (cases.some((artifactCase) => artifactCase.id === caseId)) {
      setCaseMessage(null);
      setCaseError("Case already exists.");
      return;
    }
    try {
      const parsed = JSON.parse(await file.text()) as unknown;
      if (!isJsonObject(parsed)) {
        throw new Error("Case file must contain a JSON object.");
      }
      setCaseError(null);
      setCaseMessage(`Added ${caseId}. Save cases to apply changes.`);
      setSelectedCaseId(caseId);
      onCasesChange([
        ...cases,
        { id: caseId, payload: parsed, enabled: true }
      ].sort((left, right) => left.id.localeCompare(right.id)));
    } catch (error) {
      setCaseMessage(null);
      setCaseError(error instanceof Error ? error.message : "Unknown error");
    }
  }

  function handleDeleteCase(caseId: string): void {
    if (onCasesChange === undefined) {
      return;
    }
    setCaseError(null);
    setCaseMessage(`Removed ${caseId}. Save cases to apply changes.`);
    onCasesChange(cases.filter((artifactCase) => artifactCase.id !== caseId));
  }

  function handleRunInclusionChange(caseId: string, enabled: boolean): void {
    if (onCasesChange === undefined) {
      return;
    }
    setCaseError(null);
    setCaseMessage(
      enabled
        ? `Included ${caseId} in runs. Save cases to apply changes.`
        : `Excluded ${caseId} from runs. Save cases to apply changes.`
    );
    onCasesChange(
      cases.map((artifactCase) =>
        artifactCase.id === caseId ? { ...artifactCase, enabled } : artifactCase
      )
    );
  }

  return (
    <section className="case-browser" aria-label="Cases">
      <div className="case-browser-sidebar">
        <div className="case-browser-header">
          <div>
            <h3>Cases</h3>
            <span>
              {filteredCases.length} of {cases.length}
            </span>
          </div>
          {!canEdit ? null : (
            <div className="case-browser-actions">
              <button
                className="secondary-action"
                disabled={isBusy}
                onClick={() => fileInputRef.current?.click()}
                type="button"
              >
                Upload case JSON
              </button>
              <input
                accept="application/json,.json"
                className="case-file-input"
                onChange={(event) => void handleFileInputChange(event)}
                ref={fileInputRef}
                type="file"
              />
            </div>
          )}
          <label>
            <span>Find case</span>
            <input
              onChange={(event) => setCaseQuery(event.target.value)}
              placeholder="Title or id"
              type="search"
              value={caseQuery}
            />
          </label>
          <label>
            <span>Find payload key</span>
            <input
              onChange={(event) => setBindingQuery(event.target.value)}
              placeholder="Payload key"
              type="search"
              value={bindingQuery}
            />
          </label>
        </div>

        {filteredCases.length === 0 ? (
          <div className="case-browser-empty">
            No cases match the current filters.
          </div>
        ) : (
          <div className="case-browser-list" role="listbox" aria-label="Case list">
            {filteredCases.map((artifactCase) => (
              <div
                aria-selected={artifactCase.id === selectedCase?.id}
                className={[
                  "case-browser-item",
                  artifactCase.id === selectedCase?.id ? "is-selected" : null,
                  artifactCase.enabled ? null : "is-disabled"
                ]
                  .filter(Boolean)
                  .join(" ")}
                key={artifactCase.id}
                role="option"
              >
                <button
                  className="case-browser-item-main"
                  onClick={() => setSelectedCaseId(artifactCase.id)}
                  type="button"
                >
                  <strong>{formatCaseTitle(artifactCase.id)}</strong>
                  <span>{artifactCase.id}</span>
                  {artifactCase.enabled ? null : (
                    <span className="case-state-badge">Excluded</span>
                  )}
                </button>
                {!canEdit ? null : (
                  <div className="case-browser-item-actions">
                    <label
                      className="case-run-toggle"
                      onClick={(event) => event.stopPropagation()}
                    >
                      <input
                        checked={artifactCase.enabled}
                        disabled={isBusy}
                        onChange={(event) =>
                          handleRunInclusionChange(
                            artifactCase.id,
                            event.currentTarget.checked
                          )
                        }
                        type="checkbox"
                      />
                      <span>Include in runs</span>
                    </label>
                    <button
                      className="secondary-action danger-action"
                      disabled={isBusy}
                      onClick={() => handleDeleteCase(artifactCase.id)}
                      type="button"
                    >
                      Delete case
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="case-browser-detail">
        {selectedCase === null ? (
          <div className="case-browser-empty">
            Select a case or adjust the filters.
          </div>
        ) : (
          <>
            <div className="case-detail-heading">
              <div>
                <h3>{formatCaseTitle(selectedCase.id)}</h3>
                <p>{selectedCase.id}</p>
              </div>
              <div className="case-detail-summary">
                <span>
                  {selectedPayloadEntries.length} of {selectedPayloadCount} payload
                  key{selectedPayloadCount === 1 ? "" : "s"}
                </span>
                {selectedCase.enabled ? null : (
                  <span className="case-state-badge">Excluded</span>
                )}
              </div>
            </div>
            {caseError === null ? null : (
              <p className="case-management-message is-error">{caseError}</p>
            )}
            {caseMessage === null ? null : (
              <p className="case-management-message">{caseMessage}</p>
            )}

            <div className="bindings-table" role="table" aria-label="Payload">
              <div className="bindings-row bindings-row-head" role="row">
                <span role="columnheader">Key</span>
                <span role="columnheader">Preview</span>
              </div>
              {selectedPayloadEntries.length === 0 ? (
                <div className="bindings-empty">
                  {selectedPayloadCount === 0
                    ? "No payload keys in this case."
                    : "No payload keys match the current key filter."}
                </div>
              ) : (
                selectedPayloadEntries.map(([key, value]) => (
                  <div className="bindings-row" key={key} role="row">
                    <div className="payload-key-cell" role="cell">
                      <strong>{key}</strong>
                      <span className="binding-meta">
                        {describeValue(value)}
                      </span>
                    </div>
                    <div role="cell">
                      <ValuePreview value={value} />
                    </div>
                  </div>
                ))
              )}
            </div>

            <details className="case-bindings-json">
              <summary>Full payload JSON</summary>
              <pre>{formatJson(selectedCase.payload)}</pre>
            </details>
          </>
        )}
      </div>
    </section>
  );
}
