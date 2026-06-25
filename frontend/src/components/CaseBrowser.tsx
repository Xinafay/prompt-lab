import { useEffect, useMemo, useState } from "react";

import type { Case, VersionOverview } from "../types";
import { describeValue, ValuePreview } from "./ValuePreview";

interface CaseBrowserProps {
  cases: VersionOverview["cases"];
  isBusy?: boolean;
  onCasesChange?: (cases: Case[]) => void;
  onDeleteCase?: (artifactCase: Case) => void;
  onEditCase?: (artifactCase: Case) => void;
  suiteTitle?: string | null;
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
  onCasesChange,
  onDeleteCase,
  onEditCase,
  suiteTitle = null
}: CaseBrowserProps) {
  const [caseQuery, setCaseQuery] = useState("");
  const [bindingQuery, setBindingQuery] = useState("");
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(
    cases[0]?.id ?? null
  );
  const [caseMessage, setCaseMessage] = useState<string | null>(null);

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

  function handleRunInclusionChange(caseId: string, enabled: boolean): void {
    if (onCasesChange === undefined) {
      return;
    }
    setCaseMessage(
      enabled
        ? `Included ${caseId} in this experiment. Save inclusion to apply changes.`
        : `Excluded ${caseId} from this experiment. Save inclusion to apply changes.`
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
              {suiteTitle === null ? null : <> from {suiteTitle}</>}
            </span>
          </div>
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
                {canEdit ? (
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
                  </div>
                ) : null}
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
                {onEditCase === undefined && onDeleteCase === undefined ? null : (
                  <div className="case-detail-actions">
                    {onEditCase === undefined ? null : (
                      <button
                        className="secondary-action"
                        disabled={isBusy}
                        onClick={() => onEditCase(selectedCase)}
                        type="button"
                      >
                        Edit payload
                      </button>
                    )}
                    {onDeleteCase === undefined ? null : (
                      <button
                        className="secondary-action danger-action"
                        disabled={isBusy}
                        onClick={() => onDeleteCase(selectedCase)}
                        type="button"
                      >
                        Delete case
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
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
