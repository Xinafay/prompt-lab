import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { CaseSuiteManager } from "../src/components/CaseSuiteManager.tsx";
import {
  AddCaseModal,
  EditCasePayloadModal,
  NewCaseSuiteModal
} from "../src/components/CaseSuiteModals.tsx";
import { CaseSuitesList } from "../src/components/CaseSuitesList.tsx";
import {
  canSaveSuiteCases,
  getSuiteSelectionBlockedMessage,
  isSuiteMutationDisabled,
  parseCasePayloadDraft
} from "../src/components/caseSuiteDrafts.ts";
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
      activeTab: "cases",
      suites,
      selectedSuiteId: "suite-regression",
      cases,
      caseSuiteCasesDirty: false,
      isBusy: false,
      message: null,
      onCasesChange: () => undefined,
      onAddCase: () => undefined,
      onDeleteSuite: async () => undefined,
      onResetCases: () => undefined,
      onSaveCases: async () => undefined,
      onTabChange: () => undefined,
      onUpdateSuite: async () => undefined,
      ...props
    })
  );
}

test("case suites list renders suite rail metadata and create action", () => {
  const html = renderToStaticMarkup(
    React.createElement(CaseSuitesList, {
      isBusy: false,
      isSelectionBlocked: false,
      onCreate: () => undefined,
      onSelect: () => undefined,
      selectedSuiteId: "suite-regression",
      suites
    })
  );

  assert.match(html, /Case Suites/);
  assert.match(html, /Regression Suite/);
  assert.match(html, /suite-regression/);
  assert.match(html, /2 cases/);
  assert.match(html, /Referenced by demo-json/);
  assert.match(html, /Empty Suite/);
  assert.match(html, />New<\/button>/);
});

test("case suite manager renders management controls and disables referenced delete", () => {
  const html = renderManager({ activeTab: "settings" });

  assert.match(html, /Case Suite settings/);
  assert.match(html, />Save<\/button>/);
  assert.match(html, /Delete suite/);
  assert.match(html, /Danger zone/);
  assert.match(html, /data-tooltip="Cannot delete a suite referenced by experiments: demo-json\."/);
  assert.doesNotMatch(html, /Cannot delete a suite referenced by experiments\./);
  assert.match(html, /<button[^>]*disabled=""[^>]*>Delete suite<\/button>/);
});

test("case suite manager renders cases with browser layout and suite actions", () => {
  const html = renderManager();

  assert.match(html, /Case Suite workspace/);
  assert.match(html, /Cases/);
  assert.match(html, /alpha/);
  assert.match(html, /bravo/);
  assert.match(html, /Add case/);
  assert.match(html, /Edit payload/);
  assert.match(html, /Delete case/);
  assert.match(html, /bindings-table/);
  assert.doesNotMatch(html, /Delete selected case/);
  assert.doesNotMatch(html, /Suite cases/);
  assert.doesNotMatch(html, /Delete suite/);
  assert.doesNotMatch(html, /case-suite-payload-editor/);
  assert.doesNotMatch(html, /Save suite cases/);
  assert.match(html, />Save<\/button>/);
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

test("case suite creation, add case, and edit case render as modals", () => {
  const createHtml = renderToStaticMarkup(
    React.createElement(NewCaseSuiteModal, {
      error: null,
      isBusy: false,
      onCancel: () => undefined,
      onSubmit: async () => undefined
    })
  );
  const addCaseHtml = renderToStaticMarkup(
    React.createElement(AddCaseModal, {
      existingCases: cases,
      isBusy: false,
      onCancel: () => undefined,
      onSubmit: () => undefined
    })
  );
  const editCaseHtml = renderToStaticMarkup(
    React.createElement(EditCasePayloadModal, {
      artifactCase: cases[0],
      isBusy: false,
      onCancel: () => undefined,
      onSubmit: () => undefined
    })
  );

  assert.match(createHtml, /role="dialog"/);
  assert.match(createHtml, /New Case Suite/);
  assert.match(createHtml, /Create suite/);
  assert.match(addCaseHtml, /role="dialog"/);
  assert.match(addCaseHtml, /Add case/);
  assert.match(addCaseHtml, /Case ID/);
  assert.match(addCaseHtml, /Upload case JSON/);
  assert.match(addCaseHtml, /Choose JSON file/);
  assert.match(addCaseHtml, /No file selected/);
  assert.match(addCaseHtml, /case-file-picker/);
  assert.match(addCaseHtml, /case-file-input/);
  assert.match(addCaseHtml, /Payload JSON/);
  assert.match(addCaseHtml, /modal-card-large-code/);
  assert.match(addCaseHtml, /code-editor/);
  assert.match(editCaseHtml, /role="dialog"/);
  assert.match(editCaseHtml, /Edit case payload/);
  assert.match(editCaseHtml, /Payload JSON/);
  assert.match(editCaseHtml, /modal-card-large-code/);
  assert.match(editCaseHtml, /code-editor/);
});

test("production app wires a dedicated case suites view", () => {
  const source = readFileSync(
    new URL("../src/App.tsx", import.meta.url),
    "utf8"
  );

  assert.match(source, /type AppView = "experiment" \| "globalSettings" \| "caseSuites"/);
  assert.match(source, /CaseSuiteManager/);
  assert.match(source, /CaseSuitesList/);
  assert.match(source, /NewCaseSuiteModal/);
  assert.match(source, /AddCaseModal/);
  assert.match(source, /Case Suites/);
  assert.match(source, /saveCaseSuiteCases/);
  assert.match(source, /getCaseSuiteCases/);
  assert.match(source, /Case Suite cases saved\./);
});

test("case suite draft helpers reject invalid payloads and block saving", () => {
  const invalidSyntax = parseCasePayloadDraft('{"customer": ');
  assert.equal(invalidSyntax.ok, false);
  if (!invalidSyntax.ok) {
    assert.match(invalidSyntax.error, /JSON/);
  }

  assert.deepEqual(parseCasePayloadDraft("[]"), {
    ok: false,
    error: "Payload must be a JSON object."
  });

  assert.equal(
    canSaveSuiteCases({
      isBusy: false,
      isDirty: true,
      hasPayloadError: true,
      selectedSuiteId: "suite-regression"
    }),
    false
  );
  assert.equal(
    canSaveSuiteCases({
      isBusy: false,
      isDirty: true,
      hasPayloadError: false,
      selectedSuiteId: "suite-regression"
    }),
    true
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

test("case suite draft helpers block suite selection and mutations while dirty", () => {
  assert.equal(
    getSuiteSelectionBlockedMessage(true),
    "Save or reset suite case changes before switching suites."
  );
  assert.equal(getSuiteSelectionBlockedMessage(false), null);

  assert.equal(
    isSuiteMutationDisabled({ isBusy: false, caseSuiteCasesDirty: true }),
    true
  );
  assert.equal(
    isSuiteMutationDisabled({ isBusy: true, caseSuiteCasesDirty: false }),
    true
  );
  assert.equal(
    isSuiteMutationDisabled({ isBusy: false, caseSuiteCasesDirty: false }),
    false
  );
});

test("case suite manager stacks below the shared mobile breakpoint", () => {
  const css = readFileSync(
    new URL("../src/styles.css", import.meta.url),
    "utf8"
  );

  assert.match(
    css,
    /@media \(max-width: 760px\)[\s\S]*?\.settings-section-danger \.disabled-tooltip-wrapper\s*\{[\s\S]*?grid-column:\s*1;/
  );
});
