import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { CaseSuiteManager } from "../src/components/CaseSuiteManager.tsx";
import type { Case, CaseSuite } from "../src/types.ts";

const suites: CaseSuite[] = [
  {
    schema_version: "prompt_lab.case_suite/v1",
    id: "suite-regression",
    title: "Regression Suite",
    description: "Shared regression cases",
    case_count: 2,
    experiment_ids: ["demo-json"]
  },
  {
    schema_version: "prompt_lab.case_suite/v1",
    id: "suite-empty",
    title: "Empty Suite",
    description: "",
    case_count: 0,
    experiment_ids: []
  }
];

const cases: Case[] = [
  {
    id: "alpha",
    enabled: true,
    payload: {
      customer: "Ada",
      tier: "enterprise"
    }
  },
  {
    id: "bravo",
    enabled: true,
    payload: {
      customer: "Linus",
      tier: "starter"
    }
  }
];

function renderManager(props: Partial<React.ComponentProps<typeof CaseSuiteManager>> = {}) {
  return renderToStaticMarkup(
    React.createElement(CaseSuiteManager, {
      suites,
      selectedSuiteId: "suite-regression",
      cases,
      caseSuiteCasesDirty: false,
      isBusy: false,
      message: null,
      onCasesChange: () => undefined,
      onCreateSuite: async () => undefined,
      onDeleteSuite: async () => undefined,
      onResetCases: () => undefined,
      onSaveCases: async () => undefined,
      onSelectSuite: () => undefined,
      onUpdateSuite: async () => undefined,
      ...props
    })
  );
}

test("case suite manager renders suite list with selected suite metadata", () => {
  const html = renderManager();

  assert.match(html, /Case Suites/);
  assert.match(html, /Regression Suite/);
  assert.match(html, /suite-regression/);
  assert.match(html, /2 cases/);
  assert.match(html, /Referenced by demo-json/);
  assert.match(html, /Empty Suite/);
});

test("case suite manager renders management controls and disables referenced delete", () => {
  const html = renderManager();

  assert.match(html, /Create suite/);
  assert.match(html, /Save suite/);
  assert.match(html, /Delete suite/);
  assert.match(html, /Cannot delete a suite referenced by experiments/);
  assert.match(html, /<button[^>]*disabled=""[^>]*>Delete suite<\/button>/);
});

test("case suite manager renders selected cases, payload editor, and save controls", () => {
  const html = renderManager();

  assert.match(html, /Suite cases/);
  assert.match(html, /alpha/);
  assert.match(html, /bravo/);
  assert.match(html, /Add case/);
  assert.match(html, /Case ID/);
  assert.match(html, /JSON object/);
  assert.match(html, /Payload JSON/);
  assert.match(html, /Delete selected case/);
  assert.match(html, /Save suite cases/);
  assert.match(html, /&quot;customer&quot;: &quot;Ada&quot;/);
});

test("case suite manager renders busy and empty states", () => {
  const html = renderManager({
    cases: [],
    isBusy: true,
    message: "Case Suite cases saved.",
    selectedSuiteId: "suite-empty"
  });

  assert.match(html, /Case Suite cases saved\./);
  assert.match(html, /Loading suite changes/);
  assert.match(html, /No cases in this suite/);
});

test("production app wires a dedicated case suites view", () => {
  const source = readFileSync(
    new URL("../src/App.tsx", import.meta.url),
    "utf8"
  );

  assert.match(source, /type AppView = "experiment" \| "globalSettings" \| "caseSuites"/);
  assert.match(source, /CaseSuiteManager/);
  assert.match(source, /Case Suites/);
  assert.match(source, /saveCaseSuiteCases/);
  assert.match(source, /getCaseSuiteCases/);
  assert.match(source, /Case Suite cases saved\./);
});

test("case suite manager blocks saving while payload JSON is invalid", () => {
  const source = readFileSync(
    new URL("../src/components/CaseSuiteManager.tsx", import.meta.url),
    "utf8"
  );

  assert.match(source, /const hasCasePayloadError = payloadError !== null;/);
  assert.match(source, /if \(hasCasePayloadError\) \{[\s\S]*setError\(payloadError\);[\s\S]*return;[\s\S]*\}/);
  assert.match(
    source,
    /disabled=\{[\s\S]*?isBusy \|\|[\s\S]*?selectedSuite === null \|\|[\s\S]*?hasCasePayloadError/
  );
});

test("production app tracks dirty case suite drafts before switching suites", () => {
  const source = readFileSync(
    new URL("../src/App.tsx", import.meta.url),
    "utf8"
  );

  assert.match(source, /const \[caseSuiteCasesDirty, setCaseSuiteCasesDirty\]/);
  assert.match(source, /function handleResetCaseSuiteCases/);
  assert.match(source, /caseSuiteCasesDirty=\{caseSuiteCasesDirty\}/);
  assert.match(source, /onResetCases=\{handleResetCaseSuiteCases\}/);
});

test("case suite manager disables suite mutations while case changes are dirty", () => {
  const source = readFileSync(
    new URL("../src/components/CaseSuiteManager.tsx", import.meta.url),
    "utf8"
  );

  assert.match(source, /caseSuiteCasesDirty: boolean;/);
  assert.match(source, /const suiteMutationDisabled = isBusy \|\| caseSuiteCasesDirty;/);
  assert.match(source, /disabled=\{suiteMutationDisabled\}/);
  assert.match(source, /Save or reset case changes before switching\s*suites\./);
  assert.match(source, /Reset case changes/);
});

test("case suite manager stacks below the shared mobile breakpoint", () => {
  const css = readFileSync(
    new URL("../src/styles.css", import.meta.url),
    "utf8"
  );

  assert.match(
    css,
    /@media \(max-width: 980px\)[\s\S]*?\.case-suite-manager\s*\{[\s\S]*?grid-template-columns:\s*1fr;/
  );
});
