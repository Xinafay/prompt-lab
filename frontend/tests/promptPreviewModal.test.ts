import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { PromptPreviewModal } from "../src/components/PromptPreviewModal.ts";

test("prompt preview modal renders warnings, metadata, counts, and actions", () => {
  const html = renderToStaticMarkup(
    React.createElement(PromptPreviewModal, {
      isAccepting: false,
      onAccept: () => undefined,
      onReject: () => undefined,
      preview: {
        workflow_kind: "run_version",
        warnings: ["Showing every case and LLM validator for the first repeat only."],
        prompts: [
          {
            kind: "run",
            title: "Run case case-a repeat 1",
            model: "local/demo",
            prompt: "0123456789\nhello world prompt",
            character_count: 29,
            word_count: 4,
            case_id: "case-a",
            repeat_index: 1,
            validator_id: null
          }
        ]
      }
    })
  );

  assert.match(html, /Preview prompts/);
  assert.match(html, /Showing every case and LLM validator/);
  assert.match(html, /prompt-preview-list prompt-preview-list-single/);
  assert.match(html, /Run case case-a repeat 1/);
  assert.match(html, /local\/demo/);
  assert.match(html, /case-a/);
  assert.match(html, /repeat 1/);
  assert.match(html, /29 characters/);
  assert.match(html, /4 words/);
  assert.match(html, /hello world prompt/);
  assert.match(html, /Reject/);
  assert.match(html, /Accept/);
});
