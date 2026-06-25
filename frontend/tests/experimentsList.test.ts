import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { ExperimentsList } from "../src/components/ExperimentsList.tsx";
import type { Experiment } from "../src/types.ts";

const experiment: Experiment = {
  schema_version: "prompt_lab.experiment/v1",
  id: "demo-json",
  title: "Demo JSON",
  description: "",
  active_version: "v001",
  output: {
    type: "pydantic",
    model_file: "model.py",
    model_entrypoint: "model.Output"
  },
  template: {
    engine: "jinjax",
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

test("experiments list renders navigation without management actions", () => {
  const html = renderToStaticMarkup(
    React.createElement(ExperimentsList, {
      experiments: [experiment],
      onCreate: () => undefined,
      onSelect: () => undefined,
      selectedExperimentId: "demo-json"
    })
  );

  assert.match(html, /New/);
  assert.match(html, /Demo JSON/);
  assert.doesNotMatch(html, /Clone/);
  assert.doesNotMatch(html, /Delete/);
  assert.doesNotMatch(html, /danger-action/);
});

test("experiments list remains navigation when no experiment is selected", () => {
  const html = renderToStaticMarkup(
    React.createElement(ExperimentsList, {
      experiments: [experiment],
      onCreate: () => undefined,
      onSelect: () => undefined,
      selectedExperimentId: null
    })
  );

  assert.match(html, /New/);
  assert.doesNotMatch(html, /Clone/);
  assert.doesNotMatch(html, /Delete/);
});

test("app wires experiment management API calls and modals", () => {
  const source = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");

  assert.match(source, /createExperiment/);
  assert.match(source, /cloneExperiment/);
  assert.match(source, /deleteExperiment/);
  assert.match(source, /NewExperimentModal/);
  assert.match(source, /CloneExperimentModal/);
  assert.match(source, /DeleteExperimentModal/);
  assert.match(source, /routeAfterExperimentMutation/);
});
