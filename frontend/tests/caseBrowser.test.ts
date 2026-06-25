import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { caseInclusionMatchesCases } from "../src/App.tsx";
import { CaseBrowser } from "../src/components/CaseBrowser.tsx";

function functionSource(source: string, name: string): string {
  const start = source.search(new RegExp(`(?:async )?function ${name}\\b`));
  assert.notEqual(start, -1, `${name} should exist`);
  const rest = source.slice(start + 1);
  const next = rest.search(/\n  (?:async )?function \w+/);
  return source.slice(start, next === -1 ? undefined : start + 1 + next);
}

test("case browser renders plain JSON case payloads", () => {
  const html = renderToStaticMarkup(
    React.createElement(CaseBrowser, {
      cases: [
        {
          id: "product-brief",
          enabled: true,
          payload: {
            brief: {
              product: "Atlas Desk Lamp",
              audience: "remote designers"
            }
          }
        }
      ]
    })
  );

  assert.match(html, /product-brief/);
  assert.match(html, /Payload/);
  assert.match(html, /brief/);
  assert.match(html, /Atlas Desk Lamp/);
  assert.doesNotMatch(html, /Full stores JSON/);
});

test("case browser keeps object payload previews compact", () => {
  const html = renderToStaticMarkup(
    React.createElement(CaseBrowser, {
      cases: [
        {
          id: "product-brief",
          enabled: true,
          payload: {
            brief: {
              product: "Atlas Desk Lamp",
              audience: "remote designers",
              requirements: ["summarize benefits", "include three tags"]
            }
          }
        }
      ]
    })
  );

  assert.doesNotMatch(html, /role="columnheader">Type</);
  assert.match(html, /<strong[^>]*>brief<\/strong><span[^>]*>object \| 3 keys<\/span>/);
  assert.match(html, /Explore keys/);
  assert.doesNotMatch(html, /Raw JSON/);
  assert.doesNotMatch(html, /Value JSON/);
  assert.doesNotMatch(html, /\{&quot;product&quot;:&quot;Atlas Desk Lamp&quot;/);
});

test("case browser renders experiment inclusion controls and suite title", () => {
  const html = renderToStaticMarkup(
    React.createElement(CaseBrowser, {
      cases: [
        {
          id: "active-case",
          enabled: true,
          payload: { value: "alpha" }
        },
        {
          id: "disabled-case",
          enabled: false,
          payload: { value: "bravo" }
        }
      ],
      onCasesChange: () => undefined,
      suiteTitle: "Marketing Demo Suite"
    })
  );

  assert.match(html, /2 of 2 from Marketing Demo Suite/);
  assert.match(html, /Include in runs/);
  assert.match(html, /Excluded/);
  assert.match(html, /case-browser-item-actions/);
  assert.doesNotMatch(html, /case-detail-actions/);
  assert.doesNotMatch(html, /Upload case JSON/);
  assert.doesNotMatch(html, /Delete case/);
});

test("production workbench treats case edits as unsaved navigation state", () => {
  const source = readFileSync(
    new URL("../src/App.tsx", import.meta.url),
    "utf8"
  );

  assert.match(source, /const \[casesDirty, setCasesDirty\]/);
  assert.match(source, /activeTab === "cases"[\s\S]*casesDirty/);
  assert.match(source, /Unsaved case inclusion changes/);
  assert.match(source, /handleSaveCaseInclusion/);
});

test("production workbench resets run-derived state after saving case inclusion", () => {
  const source = readFileSync(
    new URL("../src/App.tsx", import.meta.url),
    "utf8"
  );
  const saveCaseInclusionSource = functionSource(
    source,
    "handleSaveCaseInclusion"
  );

  assert.match(
    saveCaseInclusionSource,
    /setCommittedValidationState\(null\);[\s\S]*setCompareValidationByVersion\(\{\}\);[\s\S]*setCommittedReviewState\(null\);[\s\S]*setProposalResponse\(null\);[\s\S]*setCreatedVersion\(null\);[\s\S]*setComparison\(null\);/
  );
});

test("production workbench only marks case inclusion dirty when it differs", () => {
  const source = readFileSync(
    new URL("../src/App.tsx", import.meta.url),
    "utf8"
  );
  const draftChangeSource = functionSource(source, "handleCasesDraftChange");

  assert.match(source, /function caseInclusionMatchesOverview/);
  assert.match(
    draftChangeSource,
    /const isDirty = !caseInclusionMatchesOverview\(nextCases\);[\s\S]*setCasesDraft\(isDirty \? nextCases : null\);[\s\S]*setCasesDirty\(isDirty\);/
  );
});

test("case inclusion matcher compares committed enabled states by case id", () => {
  const committedCases = [
    { id: "alpha", enabled: true, payload: { value: "one" } },
    { id: "bravo", enabled: false, payload: { value: "two" } }
  ];

  assert.equal(
    caseInclusionMatchesCases(
      [
        { id: "bravo", enabled: false, payload: { value: "changed" } },
        { id: "alpha", enabled: true, payload: { value: "changed" } }
      ],
      committedCases
    ),
    true
  );
  assert.equal(
    caseInclusionMatchesCases(
      [
        { id: "alpha", enabled: false, payload: { value: "one" } },
        { id: "bravo", enabled: false, payload: { value: "two" } }
      ],
      committedCases
    ),
    false
  );
  assert.equal(
    caseInclusionMatchesCases(
      [{ id: "alpha", enabled: true, payload: { value: "one" } }],
      committedCases
    ),
    false
  );
  assert.equal(
    caseInclusionMatchesCases(
      [
        { id: "alpha", enabled: true, payload: { value: "one" } },
        { id: "bravo", enabled: false, payload: { value: "two" } },
        { id: "charlie", enabled: true, payload: { value: "three" } }
      ],
      committedCases
    ),
    false
  );
});

test("production workbench disables run and preview controls for unsaved case inclusion", () => {
  const source = readFileSync(
    new URL("../src/App.tsx", import.meta.url),
    "utf8"
  );
  const runDisabledMatches = source.match(/disabled=\{runActionDisabled\}/g) ?? [];
  const runDisabledReasonMatches =
    source.match(/disabledReason=\{runActionDisabledReason\}/g) ?? [];

  assert.match(source, /const runActionDisabled = workflowLocked \|\| casesDirty;/);
  assert.match(
    source,
    /const runActionDisabledReason = workflowLocked[\s\S]*Save case inclusion before running or previewing/
  );
  assert.equal(runDisabledMatches.length, 2);
  assert.equal(runDisabledReasonMatches.length, 2);
  assert.match(
    source,
    /secondaryAction=[\s\S]*?activeTab === "runs"[\s\S]*?disabled=\{runActionDisabled\}[\s\S]*?disabledReason=\{runActionDisabledReason\}[\s\S]*?onClick=\{handlePreviewRunPrompts\}/
  );
  assert.match(
    source,
    /primaryAction=[\s\S]*?activeTab === "runs"[\s\S]*?disabled=\{runActionDisabled\}[\s\S]*?disabledReason=\{runActionDisabledReason\}[\s\S]*?onClick=\{handleRunVersion\}/
  );
});

test("case browser stacks before the full mobile app breakpoint", () => {
  const css = readFileSync(
    new URL("../src/styles.css", import.meta.url),
    "utf8"
  );

  assert.match(
    css,
    /@media \(max-width: 980px\)[\s\S]*?\.case-browser,\s*[\s\S]*?\.case-suite-manager\s*\{[\s\S]*?grid-template-columns:\s*1fr;/
  );
});
