import { useEffect, useMemo, useState } from "react";

import type { Case, VersionOverview } from "../types";
import { describeValue, ValuePreview } from "./ValuePreview";

interface CaseBrowserProps {
  cases: VersionOverview["cases"];
}

function normalizeQuery(value: string): string {
  return value.trim().toLocaleLowerCase();
}

function formatJson(value: unknown): string {
  return JSON.stringify(value, null, 2) ?? "undefined";
}

function caseMatchesQuery(artifactCase: Case, caseQuery: string): boolean {
  if (caseQuery === "") {
    return true;
  }
  return (
    artifactCase.title.toLocaleLowerCase().includes(caseQuery) ||
    artifactCase.id.toLocaleLowerCase().includes(caseQuery)
  );
}

function caseMatchesVariableQuery(
  artifactCase: Case,
  variableQuery: string
): boolean {
  if (variableQuery === "") {
    return true;
  }
  return Object.keys(artifactCase.variables).some((key) =>
    key.toLocaleLowerCase().includes(variableQuery)
  );
}

export function CaseBrowser({ cases }: CaseBrowserProps) {
  const [caseQuery, setCaseQuery] = useState("");
  const [variableQuery, setVariableQuery] = useState("");
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(
    cases[0]?.id ?? null
  );

  const filteredCases = useMemo(() => {
    const normalizedCaseQuery = normalizeQuery(caseQuery);
    const normalizedVariableQuery = normalizeQuery(variableQuery);
    return cases.filter(
      (artifactCase) =>
        caseMatchesQuery(artifactCase, normalizedCaseQuery) &&
        caseMatchesVariableQuery(artifactCase, normalizedVariableQuery)
    );
  }, [caseQuery, cases, variableQuery]);

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
  const normalizedVariableQuery = normalizeQuery(variableQuery);
  const selectedVariableEntries =
    selectedCase === null
      ? []
      : Object.entries(selectedCase.variables).filter(
          ([key]) =>
            normalizedVariableQuery === "" ||
            key.toLocaleLowerCase().includes(normalizedVariableQuery)
        );
  const selectedVariableCount =
    selectedCase === null ? 0 : Object.keys(selectedCase.variables).length;

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
            <span>Find variable key</span>
            <input
              onChange={(event) => setVariableQuery(event.target.value)}
              placeholder="Variable key"
              type="search"
              value={variableQuery}
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
                className={
                  artifactCase.id === selectedCase?.id
                    ? "case-browser-item is-selected"
                    : "case-browser-item"
                }
                key={artifactCase.id}
                onClick={() => setSelectedCaseId(artifactCase.id)}
                role="option"
                type="button"
              >
                <strong>{artifactCase.title || "(untitled case)"}</strong>
                <span>{artifactCase.id}</span>
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
                <h3>{selectedCase.title || "(untitled case)"}</h3>
                <p>{selectedCase.id}</p>
              </div>
              <span>
                {selectedVariableEntries.length} of {selectedVariableCount} variable
                {selectedVariableCount === 1 ? "" : "s"}
              </span>
            </div>

            <div className="variables-table" role="table" aria-label="Variables">
              <div className="variables-row variables-row-head" role="row">
                <span role="columnheader">Key</span>
                <span role="columnheader">Type/metadata</span>
                <span role="columnheader">Preview</span>
              </div>
              {selectedVariableEntries.length === 0 ? (
                <div className="variables-empty">
                  {selectedVariableCount === 0
                    ? "No variables in this case."
                    : "No variables match the current key filter."}
                </div>
              ) : (
                selectedVariableEntries.map(([key, value]) => (
                  <div className="variables-row" key={key} role="row">
                    <strong role="cell">{key}</strong>
                    <span className="variable-meta" role="cell">
                      {describeValue(value)}
                    </span>
                    <div role="cell">
                      <ValuePreview value={value} />
                    </div>
                  </div>
                ))
              )}
            </div>

            <details className="case-variables-json">
              <summary>Full variables JSON</summary>
              <pre>{formatJson(selectedCase.variables)}</pre>
            </details>
          </>
        )}
      </div>
    </section>
  );
}
