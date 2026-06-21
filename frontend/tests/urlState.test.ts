import assert from "node:assert/strict";
import test from "node:test";

import {
  buildGlobalSettingsPath,
  buildExperimentPath,
  isGlobalSettingsRoute,
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

test("parses validation tab routes", () => {
  assert.deepEqual(
    parseExperimentRoute(new URL("http://localhost:5173/demo/validation")),
    { experimentId: "demo", tab: "validation" }
  );
});

test("builds encoded canonical paths", () => {
  assert.equal(
    buildExperimentPath("summarize chapter", "cases"),
    "/summarize%20chapter/cases"
  );
});

test("recognizes global settings route", () => {
  assert.equal(
    isGlobalSettingsRoute(new URL("http://localhost:5173/global-settings")),
    true
  );
  assert.equal(
    isGlobalSettingsRoute(new URL("http://localhost:5173/split-scenes/settings")),
    false
  );
  assert.equal(buildGlobalSettingsPath(), "/global-settings");
});

test("exports the supported workbench tabs", () => {
  assert.deepEqual(workbenchTabs, [
    "overview",
    "settings",
    "cases",
    "runs",
    "validation",
    "review",
    "proposal",
    "compare"
  ]);
});
