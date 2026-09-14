// One-time source recovery from the original tracked HTML, never the regenerated dist.
// The normal build does not need Git history or this script.
const fs = require("node:fs");
const path = require("node:path");
const { execFileSync } = require("node:child_process");
const ts = require("typescript");
const root = path.resolve(__dirname, "..");
const targets = ["src/styles.css", "src/utils/cn.js", "index.html"];
if (targets.some((name) => fs.existsSync(path.join(root, name)))) {
  throw new Error("Recovery refuses to overwrite existing source files");
}
const html = execFileSync("git", ["-C", root, "show", "a2f9132:mobile-teacher-app-redesign/dist/index.html"], {
  encoding: "utf8", maxBuffer: 4 * 1024 * 1024,
});
const css = html.match(/<style[^>]*>([\s\S]*?)<\/style>/)[1];
// CSS contains no embedded assets; line breaks after delimiters preserve its rules.
const formattedCss = css.replace(/[{};]/g, "$&\n");
fs.writeFileSync(path.join(root, targets[0]), "/* Recovered unchanged from a2f9132 dist/index.html; original theme and utility rules. */\n" + formattedCss + "\n");
const start = html.indexOf("function tp(c)");
const end = html.indexOf("function Ce(", start);
if (start < 0 || end < 0) throw new Error("Original class utility boundaries changed");
let classes = html.slice(start, end).replace("function Te(...c)", "export function cn(...c)");
if (!classes.includes("export function cn")) throw new Error("Original cn export not found");
classes = ts.createPrinter({ newLine: ts.NewLineKind.LineFeed }).printFile(
  ts.createSourceFile("cn.js", classes, ts.ScriptTarget.Latest, true, ts.ScriptKind.JS),
);
fs.writeFileSync(path.join(root, targets[1]), "// Recovered from a2f9132: the existing bundled clsx and Tailwind merge implementation.\n// Preserve conflict resolution without adding runtime packages.\n" + classes);
const entry = html.replace(/<script type="module"[\s\S]*?<\/script>/, '<script type="module" src="/src/main.tsx"></script>')
  .replace(/\s*<style[^>]*>[\s\S]*?<\/style>/, "");
fs.writeFileSync(path.join(root, targets[2]), entry);
console.log("Recovered stylesheet, class-merging utility and HTML entry from a2f9132.");
