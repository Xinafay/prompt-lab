import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { CodeViewer, DiffViewer } from "../src/components/CodeViewer.tsx";

test("code viewer SSR fallback renders label, language, and escaped content", () => {
  const html = renderToStaticMarkup(
    React.createElement(CodeViewer, {
      label: "Prompt template",
      language: "markdown-jinja",
      value: "Hello {{ name }}\n<<MODEL>>\n<script>alert('x')</script>"
    })
  );

  assert.match(html, /aria-label="Prompt template"/);
  assert.match(html, /data-language="markdown-jinja"/);
  assert.match(html, /Prompt template/);
  assert.match(html, /Hello \{\{ name \}\}/);
  assert.match(html, /&lt;&lt;MODEL&gt;&gt;/);
  assert.match(html, /&lt;script&gt;alert\(&#x27;x&#x27;\)&lt;\/script&gt;/);
});

test("diff viewer SSR fallback renders label, language, and escaped values", () => {
  const html = renderToStaticMarkup(
    React.createElement(DiffViewer, {
      label: "Validator diff",
      language: "python",
      original: "def score():\n    return '<old>'",
      value: "def score():\n    return '<new>'"
    })
  );

  assert.match(html, /aria-label="Validator diff"/);
  assert.match(html, /data-language="python"/);
  assert.match(html, /Validator diff/);
  assert.match(html, /def score/);
  assert.match(html, /&lt;old&gt;/);
  assert.match(html, /&lt;new&gt;/);
});
