import { readdirSync } from "node:fs";
import { spawnSync } from "node:child_process";

const nodeOptions = ["--import", "./scripts/register-tsx-loader.mjs", "--test"];

const testArgs =
  process.argv.length > 2
    ? process.argv
        .slice(2)
        .filter((arg) => arg !== "--")
        .map((arg) =>
          arg.includes("/") || arg.includes("\\") ? arg : `tests/${arg}`
        )
    : readdirSync("tests")
        .filter((name) => name.endsWith(".test.ts"))
        .sort()
        .map((name) => `tests/${name}`);

const result = spawnSync(process.execPath, [...nodeOptions, ...testArgs], {
  stdio: "inherit"
});

process.exit(result.status ?? 1);
