import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { ExperimentSettings } from "../src/components/ExperimentSettings.tsx";
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

test("experiment settings renders creation-time structural fields read-only", () => {
  const html = renderToStaticMarkup(
    React.createElement(ExperimentSettings, {
      experiment,
      isBusy: false,
      message: null,
      onDirtyChange: () => undefined,
      onDraftChange: () => undefined,
      onReset: () => undefined,
      onSave: async () => undefined
    })
  );

  assert.match(html, /<input readOnly="" value="v001"\/>/);
  assert.match(html, /<input readOnly="" value="pydantic"\/>/);
  assert.match(html, /<input readOnly="" value="model.py"\/>/);
  assert.match(html, /<input readOnly="" value="model.Output"\/>/);
  assert.match(html, /<input readOnly="" value="prompt.md"\/>/);
  assert.doesNotMatch(html, /<select[^>]*><option value="text"/);
});
