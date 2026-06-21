import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { registerHooks } from "node:module";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import type { VersionOverview } from "../src/types.ts";

registerHooks({
  resolve(specifier, context, nextResolve) {
    const isRelative = specifier.startsWith("./") || specifier.startsWith("../");
    const hasExtension = /\.[a-z]+$/i.test(specifier);
    if (isRelative && !hasExtension && context.parentURL?.endsWith(".tsx")) {
      try {
        return nextResolve(`${specifier}.tsx`, context);
      } catch {
        return nextResolve(specifier, context);
      }
    }
    return nextResolve(specifier, context);
  }
});

const { ExperimentOverview } = await import(
  "../src/components/ExperimentOverview.tsx"
);

function buildOverview(
  outputType: "text" | "pydantic",
  overrides: Partial<VersionOverview> = {}
): VersionOverview {
  return {
    experiment: {
      schema_version: "prompt_lab.experiment/v1",
      id: "demo",
      title: "Demo experiment",
      description: "Demo description",
      active_version: "v1",
      output:
        outputType === "text"
          ? { type: "text" }
          : { type: "pydantic", model_file: "custom_model.py" },
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
        case_order: "case-major"
      }
    },
    version: "v1",
    prompt: "Write a concise response for {{ topic }}.",
    rubric: "",
    cases: [],
    validators: [],
    ...overrides
  };
}

test("text output overview renders prompt content without model source", () => {
  const html = renderToStaticMarkup(
    React.createElement(ExperimentOverview, {
      overview: buildOverview("text"),
      isRunning: false,
      onRunVersion: () => undefined
    })
  );

  assert.match(html, /Prompt/);
  assert.match(html, /Write a concise response for \{\{ topic \}\}\./);
  assert.doesNotMatch(html, /Model/);
  assert.doesNotMatch(html, /model\.py/);
});

test("pydantic output overview renders prompt and model source", () => {
  const html = renderToStaticMarkup(
    React.createElement(ExperimentOverview, {
      overview: buildOverview("pydantic", {
        model_py: "from pydantic import BaseModel\n\nclass Answer(BaseModel):\n    value: str\n"
      }),
      isRunning: false,
      onRunVersion: () => undefined
    })
  );

  assert.match(html, /Prompt/);
  assert.match(html, /Write a concise response for \{\{ topic \}\}\./);
  assert.match(html, /Model/);
  assert.match(html, /model\.py/);
  assert.match(html, /from pydantic import BaseModel/);
  assert.match(html, /class Answer\(BaseModel\)/);
});

test("overview can hide its local run action for workbench toolbar layouts", () => {
  const html = renderToStaticMarkup(
    React.createElement(ExperimentOverview, {
      overview: buildOverview("text"),
      isRunning: false,
      onRunVersion: () => undefined,
      showRunAction: false
    })
  );

  assert.doesNotMatch(html, /Run version/);
});

test("production workbench overview delegates to ExperimentOverview", () => {
  const source = readFileSync(
    new URL("../src/App.tsx", import.meta.url),
    "utf8"
  );

  assert.match(
    source,
    /import \{ ExperimentOverview \} from "\.\/components\/ExperimentOverview"/
  );
  assert.match(
    source,
    /<ExperimentOverview\s+overview=\{detailState\.overview\}/
  );
  assert.match(source, /isRunning=\{workflowLocked\}/);
  assert.match(source, /onRunVersion=\{handleRunVersion\}/);
  assert.doesNotMatch(
    source,
    /<pre className="code-block">\{detailState\.overview\.prompt\}<\/pre>/
  );
  assert.doesNotMatch(
    source,
    /import \{ ValidatorsPreview \} from "\.\/components\/ValidatorsPreview"/
  );
});
