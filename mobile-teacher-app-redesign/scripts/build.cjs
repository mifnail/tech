const path = require("node:path");
const { pathToFileURL } = require("node:url");
const ts = require("typescript");
const root = path.resolve(__dirname, "..");

async function main() {
  const config = ts.readConfigFile(path.join(root, "tsconfig.json"), ts.sys.readFile);
  if (config.error) throw new Error(ts.flattenDiagnosticMessageText(config.error.messageText, "\n"));
  const parsed = ts.parseJsonConfigFileContent(config.config, ts.sys, root);
  const reactTypes = path.dirname(require.resolve("@types/react/package.json"));
  const domTypes = path.dirname(require.resolve("@types/react-dom/package.json"));
  const lucideDir = path.dirname(require.resolve("lucide-react/package.json"));
  const lucide = require(path.join(lucideDir, "package.json"));
  const program = ts.createProgram(parsed.fileNames, {
    ...parsed.options,
    baseUrl: root,
    typeRoots: [path.dirname(reactTypes)],
    paths: {
      react: [path.join(reactTypes, "index.d.ts")],
      "react/*": [path.join(reactTypes, "*")],
      "react-dom": [path.join(domTypes, "index.d.ts")],
      "react-dom/*": [path.join(domTypes, "*")],
      "lucide-react": [path.join(lucideDir, lucide.types || lucide.typings)],
    },
  });
  const diagnostics = [...parsed.errors, ...ts.getPreEmitDiagnostics(program)];
  if (diagnostics.length) {
    console.error(ts.formatDiagnosticsWithColorAndContext(diagnostics, {
      getCurrentDirectory: () => root,
      getCanonicalFileName: (name) => name,
      getNewLine: () => "\n",
    }));
    process.exitCode = 1;
    return;
  }
  const { build } = await import(pathToFileURL(require.resolve("vite")).href);
  const options = require("../vite.config.cjs");
  await build({ ...options, configFile: false, mode: "production" });
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
