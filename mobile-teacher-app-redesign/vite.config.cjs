const path = require("node:path");

const packageDir = (name) => path.dirname(require.resolve(`${name}/package.json`));
const lucideDir = packageDir("lucide-react");
const lucide = require(path.join(lucideDir, "package.json"));

module.exports = {
  root: __dirname,
  base: "./",
  publicDir: false,
  resolve: {
    alias: [
      { find: /^react(?=\/|$)/, replacement: packageDir("react") },
      { find: /^react-dom(?=\/|$)/, replacement: packageDir("react-dom") },
      { find: "lucide-react", replacement: path.join(lucideDir, lucide.module || lucide.main) },
    ],
  },
  esbuild: { jsx: "automatic" },
  build: {
    target: "es2017",
    cssTarget: "chrome61",
    modulePreload: false,
    cssCodeSplit: false,
    assetsInlineLimit: Number.MAX_SAFE_INTEGER,
    emptyOutDir: false,
    rollupOptions: { output: { inlineDynamicImports: true } },
  },
  plugins: [{
    name: "single-html-for-flask",
    generateBundle(_, bundle) {
      const html = bundle["index.html"];
      if (!html || html.type !== "asset") throw new Error("Missing HTML entry");
      let source = String(html.source);
      for (const [name, asset] of Object.entries(bundle)) {
        if (name === "index.html") continue;
        const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        if (asset.type === "chunk") {
          const tag = new RegExp(`<script\\b[^>]*src=["'](?:\\./|/)?${escaped}["'][^>]*><\\/script>`);
          if (!tag.test(source)) throw new Error(`Unreferenced script: ${name}`);
          source = source.replace(tag, () => `<script type="module">${asset.code.replace(/<\/script/gi, "<\\/script")}</script>`);
        } else if (name.endsWith(".css")) {
          const tag = new RegExp(`<link\\b[^>]*href=["'](?:\\./|/)?${escaped}["'][^>]*>`);
          if (!tag.test(source)) throw new Error(`Unreferenced stylesheet: ${name}`);
          source = source.replace(tag, () => `<style>${asset.source}</style>`);
        } else {
          throw new Error(`Asset must be inlined: ${name}`);
        }
        delete bundle[name];
      }
      if (/<script\b[^>]*\bsrc=|<link\b[^>]*\bhref=/i.test(source)) {
        throw new Error("The Flask frontend must not reference external assets");
      }
      html.source = source;
    },
  }],
};
