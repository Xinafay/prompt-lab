import assert from "node:assert/strict";
import test from "node:test";

import { sanitizeJsonPreviewValue, visibleJsonEntries } from "../src/jsonPreview.ts";

test("hides technical object keys from JSON tree previews", () => {
  assert.deepEqual(
    visibleJsonEntries({
      __carmilla_flat_file_node__: "file",
      _internal: "hidden",
      title: "Chapter One",
      nested: { _meta: true, value: 42 }
    }),
    [
      ["title", "Chapter One"],
      ["nested", { _meta: true, value: 42 }]
    ]
  );
});

test("keeps array indexes visible in JSON tree previews", () => {
  assert.deepEqual(visibleJsonEntries(["first", "second"]), [
    ["0", "first"],
    ["1", "second"]
  ]);
});

test("removes technical keys recursively from JSON preview values", () => {
  assert.deepEqual(
    sanitizeJsonPreviewValue({
      __carmilla_flat_file_node__: "file",
      value: {
        _internal: "hidden",
        title: "Chapter One",
        nested: [
          {
            __carmilla_flat_file_node__: "file",
            value: "Visible text"
          }
        ]
      }
    }),
    {
      value: {
        title: "Chapter One",
        nested: [
          {
            value: "Visible text"
          }
        ]
      }
    }
  );
});
