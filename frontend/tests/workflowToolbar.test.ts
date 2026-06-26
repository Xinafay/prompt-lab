import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import {
  classifyWorkflowStatusTone,
  WorkflowToolbar
} from "../src/components/WorkflowToolbar.tsx";
import type { Experiment } from "../src/types.ts";

const experiment: Experiment = {
  schema_version: "prompt_lab.experiment/v1",
  id: "demo-json",
  title: "Demo JSON",
  description: "Demo experiment",
  active_version: "v001",
  output: { type: "pydantic", model_file: "model.py" },
  template: {
    engine: "jinja2",
    path: "prompt.md"
  },
  models: {
    generator_model: "local/generator",
    validator_model: "local/validator",
    judge_model: "local/judge"
  },
  run_defaults: {
    repeat_count: 1,
    llm_cache: "disabled",
    case_order: "case-major",
    excluded_case_ids: []
  }
};

test("workflow toolbar renders three persistent workbench header rows", () => {
  const html = renderToStaticMarkup(
    React.createElement(WorkflowToolbar, {
      activeTabLabel: "Settings",
      activeVersion: "v001",
      availableVersions: ["v001", "v002"],
      experiment,
      isVersionSwitching: false,
      jobStatus: null,
      onActiveVersionChange: () => undefined,
      onWorkflowModeChange: () => undefined,
      primaryAction: React.createElement("button", { type: "button" }, "Save"),
      secondaryAction: React.createElement(
        "button",
        { type: "button" },
        "Reset"
      ),
      showDryRunControls: false,
      tabs: React.createElement(
        "div",
        { className: "workbench-tabs", role: "tablist" },
        "Tabs"
      ),
      tabNotice: React.createElement("span", null, "Unsaved settings changes."),
      workflowMessage: "Saved",
      workflowMode: "live"
    })
  );

  assert.match(html, /workflow-context-row/);
  assert.match(html, /workflow-tabs-row/);
  assert.match(html, /workflow-tab-actions-row/);
  assert.match(html, /Demo JSON/);
  assert.match(html, /Version/);
  assert.match(html, /Tabs/);
  assert.match(html, /<h2>Settings<\/h2>/);
  assert.match(html, /Unsaved settings changes\./);
  assert.match(html, /Saved/);
  assert.match(html, /Reset/);
  assert.match(html, /Save/);
});

test("workflow toolbar can place tab controls beside the active tab title", () => {
  const html = renderToStaticMarkup(
    React.createElement(WorkflowToolbar, {
      activeTabLabel: "Prompt",
      activeVersion: "v001",
      availableVersions: ["v001"],
      experiment,
      isVersionSwitching: false,
      jobStatus: null,
      onActiveVersionChange: () => undefined,
      onWorkflowModeChange: () => undefined,
      primaryAction: null,
      secondaryAction: null,
      showDryRunControls: false,
      tabControl: React.createElement(
        "div",
        { "aria-label": "Source editor view", role: "tablist" },
        React.createElement("button", { type: "button" }, "Edit"),
        React.createElement("button", { type: "button" }, "Diff")
      ),
      tabs: React.createElement(
        "div",
        { className: "workbench-tabs", role: "tablist" },
        "Tabs"
      ),
      workflowMessage: null,
      workflowMode: "live"
    })
  );

  assert.match(
    html,
    /<div class="workflow-tab-heading"><h2>Prompt<\/h2><div aria-label="Source editor view" role="tablist">/
  );
  assert.match(html, /Edit/);
  assert.match(html, /Diff/);
});

test("workflow toolbar marks saved workflow messages as success", () => {
  assert.equal(classifyWorkflowStatusTone("Case inclusion saved."), "success");
  assert.equal(
    classifyWorkflowStatusTone("Validation inclusion saved."),
    "success"
  );
  assert.equal(classifyWorkflowStatusTone("Review changes saved."), "success");
  assert.equal(
    classifyWorkflowStatusTone("Created v003 and switched to it."),
    "success"
  );
  assert.equal(classifyWorkflowStatusTone("Preparing prompt preview..."), "info");
  assert.equal(classifyWorkflowStatusTone("Unknown error"), "error");
});

test("workflow toolbar renders success workflow status with green class", () => {
  const html = renderToStaticMarkup(
    React.createElement(WorkflowToolbar, {
      activeTabLabel: "Cases",
      activeVersion: "v001",
      availableVersions: ["v001"],
      experiment,
      isVersionSwitching: false,
      jobStatus: null,
      onActiveVersionChange: () => undefined,
      onWorkflowModeChange: () => undefined,
      primaryAction: null,
      secondaryAction: null,
      showDryRunControls: false,
      tabs: React.createElement(
        "div",
        { className: "workbench-tabs", role: "tablist" },
        "Tabs"
      ),
      workflowMessage: "Case inclusion saved.",
      workflowMode: "live"
    })
  );

  assert.match(
    html,
    /<span class="workflow-status workflow-status-success">Case inclusion saved\.<\/span>/
  );
});

test("workflow toolbar styles keep the whole header sticky", () => {
  const styles = readFileSync(
    new URL("../src/styles.css", import.meta.url),
    "utf8"
  );

  assert.match(
    styles,
    /\.workflow-toolbar\s*\{[\s\S]*?position: sticky;[\s\S]*?\.workflow-context-row/
  );
  assert.match(styles, /\.workflow-tabs-row/);
  assert.match(styles, /\.workflow-tab-actions-row/);
  assert.match(styles, /\.workflow-status-success/);
});
