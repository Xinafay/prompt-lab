import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { registerHooks } from "node:module";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import type { GlobalSettings as GlobalSettingsModel } from "../src/types.ts";

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

const { GlobalSettings } = await import("../src/components/GlobalSettings.tsx");

const settings: GlobalSettingsModel = {
  schema_version: "prompt_lab.settings/v1",
  default_generator_model: "local/generator",
  default_validator_model: "local/validator",
  default_judge_model: "local/judge",
  default_repeat_count: 1
};

test("global settings exposes dirty save state copy", () => {
  const source = readFileSync(
    new URL("../src/components/GlobalSettings.tsx", import.meta.url),
    "utf8"
  );

  assert.match(source, /settings-unsaved-action/);
  assert.match(source, /Unsaved settings changes\./);
});

test("global settings clears saved message after new dirty edits", () => {
  const source = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");

  assert.match(
    source,
    /function handleGlobalSettingsDirtyChange\(isDirty: boolean\)[\s\S]*setGlobalSettingsDirty\(isDirty\);[\s\S]*if \(isDirty\) \{[\s\S]*setGlobalSettingsMessage\(null\);/
  );
  assert.match(source, /onDirtyChange=\{handleGlobalSettingsDirtyChange\}/);
});

test("global settings shows saved message beside form actions", () => {
  const html = renderToStaticMarkup(
    React.createElement(GlobalSettings, {
      isBusy: false,
      message: "Global settings saved.",
      onDirtyChange: () => undefined,
      onDraftChange: () => undefined,
      onReset: () => undefined,
      onSave: async () => undefined,
      settings
    })
  );

  assert.match(
    html,
    /<div class="settings-actions">[\s\S]*<span class="settings-message">Global settings saved\.<\/span>[\s\S]*<\/div>/
  );
  assert.doesNotMatch(
    html,
    /<\/div><div class="settings-message">Global settings saved\.<\/div><section/
  );
});
