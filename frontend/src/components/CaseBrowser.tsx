import { type ChangeEvent, useEffect, useMemo, useRef, useState } from "react";

import type { Case, VersionOverview } from "../types";
import { describeValue, ValuePreview } from "./ValuePreview";

interface CaseBrowserProps {
  cases: VersionOverview["cases"];
  isBusy?: boolean;
  onDeleteCase?: (caseId: string) => Promise<void>;
  onRunInclusionChange?: (caseId: string, enabled: boolean) => Promise<void>;
  onUploadCase?: (
    caseId: string,
    payload: Record<string, unknown>
  ) => Promise<void>;
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
  onDeleteCase,
  onRunInclusionChange,
  onUploadCase
}: CaseBrowserProps) {
  const [caseQuery, setCaseQuery] = useState("");
  const [bindingQuery, setBindingQuery] = useState("");
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(
    cases[0]?.id ?? null
  );
  const [busyAction, setBusyAction] = useState<string | null>(null);
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
  const isActionBusy = isBusy || busyAction !== null;

  async function runCaseAction(
    action: string,
    callback: () => Promise<void>,
    successMessage: string
  ): Promise<void> {
    setBusyAction(action);
    setCaseMessage(null);
    setCaseError(null);
    try {
      await callback();
      setCaseMessage(successMessage);
    } catch (error) {
      setCaseError(error instanceof Error ? error.message : "Unknown error");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleFileInputChange(
    event: ChangeEvent<HTMLInputElement>
  ): Promise<void> {
    const file = event.currentTarget.files?.[0] ?? null;
    event.currentTarget.value = "";
    if (file === null || onUploadCase === undefined) {
      return;
    }
    const caseId = deriveCaseId(file.name);
    if (caseId.length === 0) {
      setCaseMessage(null);
      setCaseError("Case file name must include a case id.");
      return;
    }
    await runCaseAction(
      "upload",
      async () => {
        const parsed = JSON.parse(await file.text()) as unknown;
        if (!isJsonObject(parsed)) {
          throw new Error("Case file must contain a JSON object.");
        }
        await onUploadCase(caseId, parsed);
      },
      `Uploaded ${caseId}.`
    );
  }

  async function handleDeleteSelectedCase(): Promise<void> {
    if (selectedCase === null || onDeleteCase === undefined) {
      return;
    }
    if (
      !window.confirm(
        `Delete case "${selectedCase.id}"? Generated artifacts will be cleared.`
      )
    ) {
      return;
    }
    await runCaseAction(
      "delete",
      () => onDeleteCase(selectedCase.id),
      `Deleted ${selectedCase.id}.`
    );
  }

  async function handleRunInclusionChange(
    event: ChangeEvent<HTMLInputElement>
  ): Promise<void> {
    if (selectedCase === null || onRunInclusionChange === undefined) {
      return;
    }
    const enabled = event.currentTarget.checked;
    await runCaseAction(
      "inclusion",
      () => onRunInclusionChange(selectedCase.id, enabled),
      enabled
        ? `Included ${selectedCase.id} in runs.`
        : `Excluded ${selectedCase.id} from runs.`
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
          {onUploadCase === undefined ? null : (
            <div className="case-browser-actions">
              <button
                className="secondary-action"
                disabled={isActionBusy}
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
              <button
                aria-selected={artifactCase.id === selectedCase?.id}
                className={[
                  "case-browser-item",
                  artifactCase.id === selectedCase?.id ? "is-selected" : null,
                  artifactCase.enabled ? null : "is-disabled"
                ]
                  .filter(Boolean)
                  .join(" ")}
                key={artifactCase.id}
                onClick={() => setSelectedCaseId(artifactCase.id)}
                role="option"
                type="button"
              >
                <strong>{formatCaseTitle(artifactCase.id)}</strong>
                <span>{artifactCase.id}</span>
                {artifactCase.enabled ? null : (
                  <span className="case-state-badge">Excluded</span>
                )}
              </button>
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
            <div className="case-detail-actions">
              {onRunInclusionChange === undefined ? null : (
                <label className="case-run-toggle">
                  <input
                    checked={selectedCase.enabled}
                    disabled={isActionBusy}
                    onChange={(event) => void handleRunInclusionChange(event)}
                    type="checkbox"
                  />
                  <span>Include in runs</span>
                </label>
              )}
              {onDeleteCase === undefined ? null : (
                <button
                  className="secondary-action danger-action"
                  disabled={isActionBusy}
                  onClick={() => void handleDeleteSelectedCase()}
                  type="button"
                >
                  Delete case
                </button>
              )}
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
