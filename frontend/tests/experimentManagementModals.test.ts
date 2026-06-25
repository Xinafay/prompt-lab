import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import {
  CloneExperimentModal,
  DeleteExperimentModal,
  NewExperimentModal
} from "../src/components/ExperimentManagementModals.tsx";

const noop = () => undefined;
const noopAsync = async () => undefined;

test("new experiment modal renders title and output fields", () => {
  const html = renderToStaticMarkup(
    React.createElement(NewExperimentModal, {
      error: null,
      isBusy: false,
      onCancel: noop,
      onSubmit: noopAsync
    })
  );

  assert.match(html, /New experiment/);
  assert.match(html, /Title/);
  assert.match(html, /Output type/);
  assert.match(html, /text/);
  assert.match(html, /pydantic/);
  assert.doesNotMatch(html, /window.confirm/);
});

test("clone experiment modal explains full local copy", () => {
  const html = renderToStaticMarkup(
    React.createElement(CloneExperimentModal, {
      error: null,
      isBusy: false,
      onCancel: noop,
      onSubmit: noopAsync,
      sourceTitle: "Demo JSON"
    })
  );

  assert.match(html, /Clone experiment/);
  assert.match(html, /Copy of Demo JSON/);
  assert.match(
    html,
    /copies cases, versions, prompts, models, validators, and artifacts/
  );
});

test("delete experiment modal uses custom destructive copy", () => {
  const html = renderToStaticMarkup(
    React.createElement(DeleteExperimentModal, {
      error: null,
      experimentTitle: "Demo JSON",
      isBusy: false,
      onCancel: noop,
      onConfirm: noopAsync
    })
  );

  assert.match(html, /Delete experiment/);
  assert.match(html, /Demo JSON/);
  assert.match(
    html,
    /runs, validations, reviews, proposals, and comparisons/
  );
  assert.match(html, /Delete experiment/);
  assert.doesNotMatch(html, /window.confirm/);
});
