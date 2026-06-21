import { readFileSync } from "node:fs";
import { createRequire, registerHooks } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const viteRequire = createRequire(require.resolve("vite/package.json"));
const { transformSync } = viteRequire("esbuild");

registerHooks({
  resolve(specifier, context, nextResolve) {
    const isRelative = specifier.startsWith("./") || specifier.startsWith("../");
    const hasExtension = /\.[a-z]+$/i.test(specifier);
    const parent = context.parentURL ?? "";
    if (
      isRelative &&
      !hasExtension &&
      (parent.endsWith(".ts") || parent.endsWith(".tsx"))
    ) {
      try {
        return nextResolve(`${specifier}.tsx`, context);
      } catch {
        try {
          return nextResolve(`${specifier}.ts`, context);
        } catch {
          return nextResolve(specifier, context);
        }
      }
    }

    return nextResolve(specifier, context);
  },

  load(url, context, nextLoad) {
    if (url.endsWith(".css")) {
      return {
        format: "module",
        shortCircuit: true,
        source: ""
      };
    }

    if (url.endsWith(".tsx")) {
      const sourcefile = fileURLToPath(url);
      const source = readFileSync(sourcefile, "utf8");
      const result = transformSync(source, {
        format: "esm",
        jsx: "automatic",
        loader: "tsx",
        sourcefile,
        target: "node24"
      });

      return {
        format: "module",
        shortCircuit: true,
        source: result.code
      };
    }

    return nextLoad(url, context);
  }
});
