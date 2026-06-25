import assert from "node:assert/strict";
import test from "node:test";

import {
  buildCaseSuitesPath,
  buildGlobalSettingsPath,
  buildExperimentPath,
  isCaseSuitesRoute,
  isGlobalSettingsRoute,
  parseCaseSuitesRoute,
  parseExperimentRoute,
  workbenchTabs
} from "../src/urlState.ts";

test("parses canonical experiment and tab paths", () => {
  assert.deepEqual(
    parseExperimentRoute(
      new URL("http://localhost:5173/experiments/split-scenes/settings")
    ),
    { experimentId: "split-scenes", tab: "settings" }
  );
});

test("keeps legacy experiment paths working", () => {
  assert.deepEqual(
    parseExperimentRoute(new URL("http://localhost:5173/split-scenes/settings")),
    { experimentId: "split-scenes", tab: "settings" }
  );
});

test("keeps old query experiment links working", () => {
  assert.deepEqual(
    parseExperimentRoute(
      new URL("http://localhost:5173/?experiment=split-scenes")
    ),
    { experimentId: "split-scenes", tab: "prompt" }
  );
});

test("defaults invalid tabs to prompt", () => {
  assert.deepEqual(
    parseExperimentRoute(
      new URL("http://localhost:5173/experiments/split-scenes/unknown")
    ),
    { experimentId: "split-scenes", tab: "prompt" }
  );
});

test("parses prompt tab routes", () => {
  assert.deepEqual(
    parseExperimentRoute(new URL("http://localhost:5173/experiments/demo/prompt")),
    { experimentId: "demo", tab: "prompt" }
  );
});

test("parses validation tab routes", () => {
  assert.deepEqual(
    parseExperimentRoute(
      new URL("http://localhost:5173/experiments/demo/validation")
    ),
    { experimentId: "demo", tab: "validation" }
  );
});

test("builds encoded canonical paths", () => {
  assert.equal(
    buildExperimentPath("summarize chapter", "cases"),
    "/experiments/summarize%20chapter/cases"
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

test("parses and builds case suite routes", () => {
  assert.equal(
    isCaseSuitesRoute(new URL("http://localhost:5173/case-suites")),
    true
  );
  assert.equal(
    isCaseSuitesRoute(
      new URL("http://localhost:5173/case-suites/demo-json-briefs")
    ),
    true
  );
  assert.equal(
    isCaseSuitesRoute(new URL("http://localhost:5173/demo-json/cases")),
    false
  );
  assert.deepEqual(
    parseCaseSuitesRoute(
      new URL("http://localhost:5173/case-suites/demo-json-briefs")
    ),
    { suiteId: "demo-json-briefs", tab: "cases" }
  );
  assert.deepEqual(
    parseCaseSuitesRoute(
      new URL("http://localhost:5173/case-suites/demo-json-briefs/settings")
    ),
    { suiteId: "demo-json-briefs", tab: "settings" }
  );
  assert.deepEqual(
    parseCaseSuitesRoute(new URL("http://localhost:5173/case-suites")),
    { suiteId: null, tab: "cases" }
  );
  assert.equal(buildCaseSuitesPath(), "/case-suites");
  assert.equal(
    buildCaseSuitesPath("Demo JSON briefs"),
    "/case-suites/Demo%20JSON%20briefs/cases"
  );
  assert.equal(
    buildCaseSuitesPath("Demo JSON briefs", "settings"),
    "/case-suites/Demo%20JSON%20briefs/settings"
  );
});

test("exports the supported workbench tabs", () => {
  assert.deepEqual(workbenchTabs, [
    "prompt",
    "settings",
    "validators",
    "cases",
    "runs",
    "validation",
    "review",
    "proposal",
    "compare"
  ]);
});
