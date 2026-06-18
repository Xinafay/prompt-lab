import assert from "node:assert/strict";
import test from "node:test";

import {
  buildExperimentPath,
  parseExperimentRoute,
  workbenchTabs
} from "../src/urlState.ts";

test("parses canonical experiment and tab paths", () => {
  assert.deepEqual(
    parseExperimentRoute(
      new URL("http://localhost:5173/split-scenes/settings")
    ),
    { experimentId: "split-scenes", tab: "settings" }
  );
});

test("keeps old query experiment links working", () => {
  assert.deepEqual(
    parseExperimentRoute(
      new URL("http://localhost:5173/?experiment=split-scenes")
    ),
    { experimentId: "split-scenes", tab: "overview" }
  );
});

test("defaults invalid tabs to overview", () => {
  assert.deepEqual(
    parseExperimentRoute(new URL("http://localhost:5173/split-scenes/unknown")),
    { experimentId: "split-scenes", tab: "overview" }
  );
});

test("builds encoded canonical paths", () => {
  assert.equal(
    buildExperimentPath("summarize chapter", "cases"),
    "/summarize%20chapter/cases"
  );
});

test("exports the supported workbench tabs", () => {
  assert.deepEqual(workbenchTabs, [
    "overview",
    "settings",
    "cases",
    "runs",
    "review",
    "proposal",
    "compare"
  ]);
});
