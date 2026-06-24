import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { RunsView } from "../src/components/RunsView.tsx";
import type { RunArtifact } from "../src/types.ts";

function runArtifact(overrides: Partial<RunArtifact> = {}): RunArtifact {
  return {
    schema_version: "prompt_lab.run/v1",
    run_id: "run-001-case-a-repeat-001",
    run_batch_id: "run-001",
    version: "v001",
    case_id: "case-a",
    repeat_index: 1,
    generator_model: "local/demo",
    status: "ok",
    rendered_prompt: "Hello {{ name }}\n<<MODEL>>",
    raw_output: '{"answer":"ok"}',
    output_type: "pydantic",
    output_json: {
      answer: "ok"
    },
    output_text: null,
    validation_error: null,
    execution_error: null,
    usage: {},
    ...overrides
  };
}

test("runs view renders output JSON and rendered prompt with code viewers", () => {
  const html = renderToStaticMarkup(
    React.createElement(RunsView, {
      cases: [
        {
          id: "case-a",
          payload: {
            value: "hello"
          }
        }
      ],
      runBatchId: "run-001",
      runs: [runArtifact()]
    })
  );

  assert.match(html, /Output JSON/);
  assert.match(html, /data-language="json"/);
  assert.match(html, /Rendered prompt/);
  assert.match(html, /data-language="markdown-jinja"/);
  assert.match(html, /Hello \{\{ name \}\}/);
  assert.match(html, /&lt;&lt;MODEL&gt;&gt;/);
  assert.doesNotMatch(html, /<pre className="code-block">/);
});
