import { build } from "esbuild";
await build({
  entryPoints: ["src/legacy.tsx"],
  bundle: true,
  outfile: "public/legacy.js",
  format: "iife",
  target: ["chrome51"],
  minify: true,
  define: { "process.env.NODE_ENV": '"production"' },
  legalComments: "none",
});
console.log("Legacy bundle built for Chromium 51 (Android 7).");
