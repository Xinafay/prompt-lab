import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { registerHooks } from "node:module";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { updateVersionValidators } from "../src/api.ts";
import type {
  VersionOverview,
  VersionValidatorsUpdateRequest,
  VersionValidatorsUpdateResponse
} from "../src/types.ts";

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

const { PromptView } = await import("../src/components/PromptView.tsx");
const { ValidatorsView } = await import("../src/components/ValidatorsView.tsx");

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
        case_order: "case-major",
        excluded_case_ids: []
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

test("text output prompt view renders prompt content without model source", () => {
  const html = renderToStaticMarkup(
    React.createElement(PromptView, {
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

test("pydantic output prompt view renders prompt and model source", () => {
  const html = renderToStaticMarkup(
    React.createElement(PromptView, {
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

test("prompt view can hide its local run action for workbench toolbar layouts", () => {
  const html = renderToStaticMarkup(
    React.createElement(PromptView, {
      overview: buildOverview("text"),
      isRunning: false,
      onRunVersion: () => undefined,
      showRunAction: false
    })
  );

  assert.doesNotMatch(html, /Run version/);
});

test("editable prompt view renders source editing actions and diff mode", () => {
  const html = renderToStaticMarkup(
    React.createElement(PromptView, {
      overview: buildOverview("pydantic", {
        model_py: "from pydantic import BaseModel\n\nclass Answer(BaseModel):\n    value: str\n"
      }),
      isRunning: false,
      isSourceEditing: true,
      onRunVersion: () => undefined,
      onSourceDraftChange: () => undefined,
      onSourceEdit: () => undefined,
      onSourceOverwriteCurrent: () => undefined,
      onSourceReset: () => undefined,
      onSourceSaveAsNext: () => undefined,
      onSourceViewModeChange: () => undefined,
      showRunAction: false,
      sourceDraft: {
        prompt: "Write a clearer response for {{ topic }}.",
        model_py:
          "from pydantic import BaseModel\n\nclass Answer(BaseModel):\n    value: str\n    confidence: float\n"
      },
      sourceViewMode: "diff"
    })
  );

  assert.match(html, /Edit/);
  assert.match(html, /Diff/);
  assert.match(html, /Reset/);
  assert.match(html, /Overwrite current version/);
  assert.match(html, /Save as next version/);
  assert.match(html, /Prompt diff/);
  assert.match(html, /Model diff/);
  assert.match(html, /confidence: float/);
});

test("prompt view does not include validators or cases", () => {
  const html = renderToStaticMarkup(
    React.createElement(PromptView, {
      overview: buildOverview("text", {
        cases: [
          {
            id: "case-a",
            enabled: true,
            payload: {
              value: "hello"
            }
          }
        ],
        validators: [
          {
            schema_version: "prompt_lab.validator/v1",
            validator_id: "reply-quality",
            type: "automatic",
            title: "Reply quality",
            description: "Checks the reply.",
            enabled: true,
            input_scope: "output_only",
            checks: [
              {
                check_id: "has-answer",
                title: "Has answer",
                description: "",
                rule: {
                  kind: "word_count",
                  source: "output_text",
                  comparison: { op: "gte", value: 3 }
                }
              }
            ]
          }
        ]
      }),
      isRunning: false,
      onRunVersion: () => undefined
    })
  );

  assert.doesNotMatch(html, /Reply quality/);
  assert.doesNotMatch(html, /Case A/);
});

test("validators view renders validators independently from prompt view", () => {
  const html = renderToStaticMarkup(
    React.createElement(ValidatorsView, {
      validators: [
        {
          schema_version: "prompt_lab.validator/v1",
          validator_id: "reply-quality",
          type: "llm_questionnaire",
          title: "Reply quality",
          description: "Checks the reply.",
          enabled: true,
          input_scope: "output_and_case",
          checks: [
            {
              check_id: "answers-question",
              title: "Answers question",
              description: "The reply answers the user.",
              question: "Does the reply answer the user?"
            }
          ]
        }
      ]
    })
  );

  assert.match(html, /Validators/);
  assert.match(html, /Reply quality/);
  assert.match(html, /LLM questionnaire/);
});

test("production workbench delegates prompt and validators tabs", () => {
  const source = readFileSync(
    new URL("../src/App.tsx", import.meta.url),
    "utf8"
  );

  assert.match(
    source,
    /import \{ PromptView \} from "\.\/components\/PromptView"/
  );
  assert.match(source, /updateVersionValidators/);
  assert.match(source, /VersionValidatorsDraft/);
  assert.match(source, /VersionValidatorsSaveMode/);
  assert.match(source, /validatorsDirty/);
  assert.match(source, /requestValidatorsOverwrite/);
  assert.match(source, /handleSaveVersionValidators/);
  assert.match(
    source,
    /<PromptView\s+overview=\{detailState\.overview\}/
  );
  assert.match(
    source,
    /activeTab === "validators" \? \(\s*<ValidatorsView/
  );
  assert.match(
    source,
    /<ValidatorsView\s+isBusy=\{workflowLocked\}\s+message=\{workflowMessage\}\s+onDraftChange=\{handleValidatorsDraftChange\}/
  );
  assert.match(
    source,
    /onOverwriteCurrent=\{\(\) =>\s+requestValidatorsOverwrite\(\)\s+\}/
  );
  assert.match(source, /onReset=\{handleValidatorsReset\}/);
  assert.match(
    source,
    /onSaveAsNext=\{\(\) =>\s+void handleSaveVersionValidators\("create_next"\)\s+\}/
  );
  assert.match(
    source,
    /validators=\{detailState\.overview\.validators \?\? \[\]\}/
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

test("production workbench keeps dirty-navigation continuation state stable", () => {
  const source = readFileSync(
    new URL("../src/App.tsx", import.meta.url),
    "utf8"
  );

  assert.match(source, /type UnsavedNavigationKind =/);
  assert.match(source, /unsavedKind: UnsavedNavigationKind/);
  assert.match(source, /function buildPendingNavigation/);
  assert.match(source, /const pendingNavigationKind = pendingNavigation\?\.unsavedKind \?\? null/);
  assert.match(source, /async function performPendingNavigation/);
  assert.match(source, /await performActiveVersionChange\(navigation\.version\)/);
  assert.doesNotMatch(source, /void performActiveVersionChange\(navigation\.version\)/);
});

test("validator source API helper posts encoded version update requests", async () => {
  const request: VersionValidatorsUpdateRequest = {
    mode: "create_next",
    validators: []
  };
  const expected: VersionValidatorsUpdateResponse = {
    version: "v2",
    source_version: "v1",
    mode: "create_next",
    version_dir: "/tmp/demo/v2"
  };
  const originalFetch = globalThis.fetch;
  const calls: Array<[RequestInfo | URL, RequestInit | undefined]> = [];
  globalThis.fetch = async (input, init) => {
    calls.push([input, init]);
    return new Response(JSON.stringify(expected), {
      status: 200,
      headers: { "content-type": "application/json" }
    });
  };

  try {
    const response = await updateVersionValidators(
      "demo experiment",
      "v1/edit",
      request
    );

    assert.deepEqual(response, expected);
    assert.equal(
      calls[0]?.[0],
      "/api/experiments/demo%20experiment/versions/v1%2Fedit/validators"
    );
    assert.equal(calls[0]?.[1]?.method, "POST");
    assert.equal(calls[0]?.[1]?.body, JSON.stringify(request));
  } finally {
    globalThis.fetch = originalFetch;
  }
});
