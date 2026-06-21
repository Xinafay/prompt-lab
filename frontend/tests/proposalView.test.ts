import assert from "node:assert/strict";
import test, { after, before } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer, type ViteDevServer } from "vite";

import type { ProposalResponse } from "../src/types.ts";

const noop = () => {};

type ProposalViewComponent =
  typeof import("../src/components/ProposalView.tsx").ProposalView;

let server: ViteDevServer | null = null;
let ProposalView: ProposalViewComponent;

before(async () => {
  server = await createServer({
    appType: "custom",
    logLevel: "silent",
    server: { middlewareMode: true }
  });

  const module = await server.ssrLoadModule("/src/components/ProposalView.tsx");
  ProposalView = module.ProposalView as ProposalViewComponent;
});

after(async () => {
  await server?.close();
});

function renderProposal(props: {
  currentModel?: string | null;
  currentModelFile?: string | null;
  proposalResponse: ProposalResponse;
}) {
  return renderToStaticMarkup(
    React.createElement(ProposalView, {
      createdVersion: null,
      currentModel: props.currentModel ?? null,
      currentModelFile: props.currentModelFile ?? null,
      currentPrompt: "Existing prompt",
      hasUnsavedReviewChanges: false,
      isBusy: false,
      onCreateVersion: noop,
      onGenerateProposal: noop,
      proposalResponse: props.proposalResponse,
      reviewState: null
    })
  );
}

test("text proposal renders new version controls, rationale, and prompt without model panel", () => {
  const html = renderProposal({
    proposalResponse: {
      proposal_dir: "proposal-1",
      proposal: {
        prompt_md: "Proposed text prompt",
        rationale_md: "This prompt is clearer."
      },
      source: {}
    }
  });

  assert.match(html, /New version/);
  assert.match(html, /Diff/);
  assert.match(html, /Rationale/);
  assert.match(html, /This prompt is clearer\./);
  assert.match(html, /Proposed prompt/);
  assert.match(html, /Proposed text prompt/);
  assert.doesNotMatch(html, /Proposed model/);
});

test("pydantic proposal renders prompt and model panels with model file fallback", () => {
  const html = renderProposal({
    currentModel: "class ExistingAnswer(BaseModel):\n    old: str",
    currentModelFile: null,
    proposalResponse: {
      proposal_dir: "proposal-2",
      proposal: {
        prompt_md: "Proposed pydantic prompt",
        model_py: "class ProposedAnswer(BaseModel):\n    answer: str",
        rationale_md: "The model captures the answer explicitly."
      },
      source: {}
    }
  });

  assert.match(html, /New version/);
  assert.match(html, /Diff/);
  assert.match(html, /Rationale/);
  assert.match(html, /Proposed prompt/);
  assert.match(html, /Proposed pydantic prompt/);
  assert.match(html, /Proposed model/);
  assert.match(html, /model\.py/);
  assert.match(html, /class ProposedAnswer\(BaseModel\)/);
});
