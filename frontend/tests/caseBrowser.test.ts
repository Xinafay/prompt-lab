import assert from "node:assert/strict";
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
