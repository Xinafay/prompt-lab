import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { CaseBrowser } from "../src/components/CaseBrowser.tsx";

test("case browser renders plain JSON case payloads", () => {
  const html = renderToStaticMarkup(
    React.createElement(CaseBrowser, {
      cases: [
        {
          id: "product-brief",
          enabled: true,
          payload: {
            brief: {
              product: "Atlas Desk Lamp",
              audience: "remote designers"
            }
          }
        }
      ]
    })
  );

  assert.match(html, /product-brief/);
  assert.match(html, /Payload/);
  assert.match(html, /brief/);
  assert.match(html, /Atlas Desk Lamp/);
  assert.doesNotMatch(html, /Full stores JSON/);
});

test("case browser keeps object payload previews compact", () => {
  const html = renderToStaticMarkup(
    React.createElement(CaseBrowser, {
      cases: [
        {
          id: "product-brief",
          enabled: true,
          payload: {
            brief: {
              product: "Atlas Desk Lamp",
              audience: "remote designers",
              requirements: ["summarize benefits", "include three tags"]
            }
          }
        }
      ]
    })
  );

  assert.doesNotMatch(html, /role="columnheader">Type</);
  assert.match(html, /<strong[^>]*>brief<\/strong><span[^>]*>object \| 3 keys<\/span>/);
  assert.match(html, /Explore keys/);
  assert.doesNotMatch(html, /Raw JSON/);
  assert.doesNotMatch(html, /Value JSON/);
  assert.doesNotMatch(html, /\{&quot;product&quot;:&quot;Atlas Desk Lamp&quot;/);
});

test("case browser renders case management controls and excluded state", () => {
  const html = renderToStaticMarkup(
    React.createElement(CaseBrowser, {
      cases: [
        {
          id: "active-case",
          enabled: true,
          payload: { value: "alpha" }
        },
        {
          id: "disabled-case",
          enabled: false,
          payload: { value: "bravo" }
        }
      ],
      onDeleteCase: async () => undefined,
      onRunInclusionChange: async () => undefined,
      onUploadCase: async () => undefined
    })
  );

  assert.match(html, /Upload case JSON/);
  assert.match(html, /Include in runs/);
  assert.match(html, /Delete case/);
  assert.match(html, /Excluded/);
});

test("case browser stacks before the full mobile app breakpoint", () => {
  const css = readFileSync(
    new URL("../src/styles.css", import.meta.url),
    "utf8"
  );

  assert.match(
    css,
    /@media \(max-width: 980px\)[\s\S]*?\.case-browser\s*\{[\s\S]*?grid-template-columns:\s*1fr;/
  );
});
