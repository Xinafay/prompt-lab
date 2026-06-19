import { useEffect, useMemo, useState } from "react";

import type { Case, PromptBinding, StoreScopeBinding, VersionOverview } from "../types";
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

function caseMatchesBindingQuery(
  artifactCase: Case,
  bindingQuery: string
): boolean {
  if (bindingQuery === "") {
    return true;
  }
  return Object.keys(artifactCase.bindings).some((key) =>
    key.toLocaleLowerCase().includes(bindingQuery)
  );
}

function displayPath(path: string): string {
  const normalized = path.trim().replace(/^\/+|\/+$/g, "");
  return normalized === "" ? "." : normalized;
}

function resolveStoreScopePreview(
  artifactCase: Case,
  binding: StoreScopeBinding
): unknown {
  const store = artifactCase.stores[binding.store];
  if (store === undefined) {
    return `Missing store: ${binding.store}`;
  }

  const normalizedPath = binding.path.trim().replace(/^\/+|\/+$/g, "");
  if (normalizedPath === "") {
    return store.values;
  }

  let current: unknown = store.values;
  for (const segment of normalizedPath.split("/")) {
    if (
      current === null ||
      typeof current !== "object" ||
      !(segment in current)
    ) {
      return `Missing store path: ${binding.path}`;
    }
    current = (current as Record<string, unknown>)[segment];
  }
  return unwrapFlatFileNodePreview(current);
}

function unwrapFlatFileNodePreview(value: unknown): unknown {
  if (
    value !== null &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    Object.keys(value).length === 2 &&
    (value as Record<string, unknown>).__carmilla_flat_file_node__ === "file" &&
    "value" in value
  ) {
    return (value as Record<string, unknown>).value;
  }
  return value;
}

function describeBinding(binding: PromptBinding): string {
  if (binding.kind === "value") {
    return `value | ${describeValue(binding.value)}`;
  }
  return `store_scope | store: ${binding.store} | path: ${displayPath(
    binding.path
  )}`;
}

function bindingPreview(artifactCase: Case, binding: PromptBinding): unknown {
  if (binding.kind === "value") {
    return binding.value;
  }
  return resolveStoreScopePreview(artifactCase, binding);
}

export function CaseBrowser({ cases }: CaseBrowserProps) {
  const [caseQuery, setCaseQuery] = useState("");
  const [bindingQuery, setBindingQuery] = useState("");
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(
    cases[0]?.id ?? null
  );

  const filteredCases = useMemo(() => {
    const normalizedCaseQuery = normalizeQuery(caseQuery);
    const normalizedBindingQuery = normalizeQuery(bindingQuery);
    return cases.filter(
      (artifactCase) =>
        caseMatchesQuery(artifactCase, normalizedCaseQuery) &&
        caseMatchesBindingQuery(artifactCase, normalizedBindingQuery)
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
  const selectedBindingEntries =
    selectedCase === null
      ? []
      : Object.entries(selectedCase.bindings).filter(
          ([key]) =>
            normalizedBindingQuery === "" ||
            key.toLocaleLowerCase().includes(normalizedBindingQuery)
        );
  const selectedBindingCount =
    selectedCase === null ? 0 : Object.keys(selectedCase.bindings).length;

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
            <span>Find binding key</span>
            <input
              onChange={(event) => setBindingQuery(event.target.value)}
              placeholder="Binding key"
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
                {selectedBindingEntries.length} of {selectedBindingCount} binding
                {selectedBindingCount === 1 ? "" : "s"}
              </span>
            </div>

            <div className="bindings-table" role="table" aria-label="Bindings">
              <div className="bindings-row bindings-row-head" role="row">
                <span role="columnheader">Key</span>
                <span role="columnheader">Type/metadata</span>
                <span role="columnheader">Preview</span>
              </div>
              {selectedBindingEntries.length === 0 ? (
                <div className="bindings-empty">
                  {selectedBindingCount === 0
                    ? "No bindings in this case."
                    : "No bindings match the current key filter."}
                </div>
              ) : (
                selectedBindingEntries.map(([key, binding]) => (
                  <div className="bindings-row" key={key} role="row">
                    <strong role="cell">{key}</strong>
                    <span className="binding-meta" role="cell">
                      {describeBinding(binding)}
                    </span>
                    <div role="cell">
                      <ValuePreview value={bindingPreview(selectedCase, binding)} />
                      <details className="binding-json">
                        <summary>Binding JSON</summary>
                        <pre>{formatJson(binding)}</pre>
                      </details>
                    </div>
                  </div>
                ))
              )}
            </div>

            <details className="case-bindings-json">
              <summary>Full bindings JSON</summary>
              <pre>{formatJson(selectedCase.bindings)}</pre>
            </details>

            <details className="case-bindings-json">
              <summary>Full stores JSON</summary>
              <pre>{formatJson(selectedCase.stores)}</pre>
            </details>
          </>
        )}
      </div>
    </section>
  );
}
