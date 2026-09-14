const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");
const { root, sourceLoader } = require("./helpers.cjs");

test("production HTML is self-contained, syntactically valid and includes the restore routes", () => {
  const html = fs.readFileSync(path.join(root, "dist/index.html"), "utf8");
  assert.doesNotMatch(html, /<script\b[^>]*\bsrc=|<link\b[^>]*\bhref=|@import\b/i);
  assert.match(html, /id="root"/);
  assert.match(html, /<style>/);
  assert.match(html, /data-theme/);
  for (const route of ["/api/restore/pick/diag", "/api/restore/pick", "/api/restore/named", "/api/backup/list"]) {
    assert.ok(html.includes(route), `Missing ${route}`);
  }
  assert.match(html, /application\/x-sqlite3,\.db/);
  assert.match(html, /safe recovery copy/);
  assert.doesNotMatch(html, /Автобэкап прежней базы сохранён в Загрузки/);
  const scripts = [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)];
  assert.ok(scripts.length >= 1);
  for (const [, script] of scripts) assert.doesNotThrow(() => new vm.Script(script));
  assert.match(html, /--bg:\s*#eceef1/i);
  assert.match(html, /--bg:\s*#0b0f14/i);
  assert.match(html, /\.an-sheet/);
  assert.match(html, /\.restore-file-input/);
  assert.deepEqual(fs.readdirSync(path.join(root, "dist")), ["index.html"]);
});

test("every relative source import resolves and all original screens remain routed", () => {
  function visit(dir) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const filename = path.join(dir, entry.name);
      if (entry.isDirectory()) { visit(filename); continue; }
      if (!/\.[jt]sx?$/.test(filename)) continue;
      const text = fs.readFileSync(filename, "utf8");
      const source = ts.createSourceFile(filename, text, ts.ScriptTarget.Latest);
      for (const statement of source.statements) {
        if (!ts.isImportDeclaration(statement)) continue;
        const name = statement.moduleSpecifier.text;
        if (!name.startsWith(".")) continue;
        const location = path.resolve(dir, name);
        assert.ok(["", ".ts", ".tsx", ".js"].some((ext) => fs.existsSync(location + ext)), `${filename}: unresolved ${name}`);
      }
    }
  }
  visit(path.join(root, "src"));
  const app = fs.readFileSync(path.join(root, "src/App.tsx"), "utf8");
  for (const screen of ["Today", "Groups", "GroupDetail", "Statement", "Schedule", "LessonRun", "Analytics", "Settings"]) {
    assert.ok(app.includes(`./screens/${screen}`));
  }
  const settings = fs.readFileSync(path.join(root, "src/screens/Settings.tsx"), "utf8");
  assert.match(settings, /<RestoreDatabase\s*\/>/);
});

test("recovered date helpers retain local dates, formatting and ISO week parity", () => {
  const date = sourceLoader()("src/lib/date.ts");
  assert.equal(date.toISO(date.fromISO("2026-01-01")), "2026-01-01");
  assert.equal(date.addDaysISO("2024-02-28", 1), "2024-02-29");
  assert.equal(date.addDaysISO("2026-12-31", 1), "2027-01-01");
  assert.equal(date.weekdayOf("2026-09-13"), 7);
  assert.equal(date.mondayOfWeek("2026-09-13"), "2026-09-07");
  assert.equal(date.weekParity("2026-01-01"), 2);
  assert.equal(date.weekParity("2026-01-05"), 1);
  assert.equal(date.weekParity("2027-01-01"), 2);
  assert.equal(date.formatDot("2026-09-13"), "13.09.2026");
  assert.equal(date.formatDotShort("2026-09-13"), "13.09");
  assert.equal(date.weekdayShort("2026-09-13"), "Вс");
  assert.equal(date.monthYearLabel("2026-09-13"), "Сентябрь 2026");
  assert.equal(date.formatLong("2026-09-13"), "13 сентября, воскресенье");
});

test("recovered cn keeps class flattening and Tailwind conflict resolution", () => {
  const { cn } = sourceLoader()("src/utils/cn.js");
  assert.equal(cn("h-11 px-4", "h-9"), "px-4 h-9");
  assert.equal(cn("p-4", "px-2"), "p-4 px-2");
  assert.equal(cn("px-2", "p-4"), "p-4");
  assert.equal(cn(["flex", false, ["gap-2"]], { hidden: false, "font-bold": true }), "flex gap-2 font-bold");
  assert.equal(cn("text-[14px] text-muted", "text-danger"), "text-[14px] text-danger");
  assert.equal(cn("bg-surface", "active:bg-surface2", "bg-accent"), "active:bg-surface2 bg-accent");
});
