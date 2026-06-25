import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

test("global settings exposes dirty save state copy", () => {
  const source = readFileSync(
    new URL("../src/components/GlobalSettings.tsx", import.meta.url),
    "utf8"
  );

  assert.match(source, /settings-unsaved-action/);
  assert.match(source, /Unsaved settings changes\./);
});
