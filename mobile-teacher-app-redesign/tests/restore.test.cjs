const test = require("node:test");
const assert = require("node:assert/strict");
const { deferred, response, restoreHarness, settle } = require("./helpers.cjs");

const native = { android: true, picker_available: true };
const posts = (h) => h.events.filter((event) => Array.isArray(event) && event[1]?.method === "POST");

test("the real Android restore button confirms before native POST, drains attendance, and reloads once", async () => {
  const flushing = deferred(), picking = deferred();
  const h = restoreHarness({
    flush: () => flushing.promise,
    fetch: (url) => url.endsWith("/diag") ? response(native) : picking.promise,
  });
  await h.ready();
  assert.equal(h.all((n) => n.type === "input" && n.props.type === "file").length, 0);
  h.click("Restore database");
  assert.match(h.content(), /immediately replace/);
  assert.equal(posts(h).length, 0);
  const confirm = h.button("Choose and restore");
  confirm.props.onClick();
  confirm.props.onClick();
  h.render();
  assert.equal(posts(h).length, 0);
  assert.equal(h.events.filter((event) => event === "flush").length, 1);
  assert.equal(h.button("Restore database").props.disabled, true);
  flushing.resolve();
  await settle();
  assert.deepEqual(posts(h).map((event) => event[0]), ["/api/restore/pick"]);
  picking.resolve(response({ ok: true }));
  await settle();
  h.render();
  assert.equal(h.events.at(-1), "reload");
  assert.equal(h.session.get("th-restore-success"), "1");
  assert.match(h.messages[0], /safe recovery copy/);
  assert.doesNotMatch(h.messages[0], /Downloads/);
  assert.equal(h.button("Restore database").props.disabled, true);
});

test("confirmation cancellation sends no restore request", async () => {
  const h = restoreHarness({ fetch: () => response(native) });
  await h.ready();
  h.click("Restore database");
  h.click("Отмена");
  assert.equal(posts(h).length, 0);
  assert.match(h.content(), /Restore cancelled/);
});

test("picker cancellation and server errors unlock controls without reporting success", async () => {
  for (const result of [response({ error: "Выбор файла отменён" }, 404), response({ error: "Recovery copy failed" }, 500), response({ ok: false }, 200)]) {
    const h = restoreHarness({ fetch: (url) => url.endsWith("/diag") ? response(native) : result });
    await h.ready();
    h.click("Restore database");
    h.click("Choose and restore");
    await settle();
    h.render();
    assert.equal(h.button("Restore database").props.disabled, false);
    assert.equal(h.messages.length, 0);
    assert.equal(h.events.includes("reload"), false);
    assert.match(h.content(), /cancelled|Recovery copy failed|did not complete/);
  }
});

test("attendance failure prevents all restore requests", async () => {
  const h = restoreHarness({ fetch: () => response(native), flush: async () => { throw new Error("Attendance save failed"); } });
  await h.ready();
  h.click("Restore database");
  h.click("Choose and restore");
  await settle();
  h.render();
  assert.equal(posts(h).length, 0);
  assert.match(h.content(), /Attendance save failed/);
  assert.equal(h.all((node) => node.props.role === "alert").length, 1);
});

test("unavailable Android picker uses backup list, explicit selection and named confirmation", async () => {
  const h = restoreHarness({ fetch: (url) => {
    if (url.endsWith("/diag")) return response({ android: true, picker_available: false });
    if (url === "/api/backup/list") return response({ backups: [{ name: "teachhelper_test.db" }] });
    return response({ ok: true });
  } });
  await h.ready();
  assert.equal(h.button("Restore database").props.disabled, true);
  await h.click("Restore from saved backup");
  h.render();
  assert.equal(h.button("Continue").props.disabled, true);
  h.all((node) => node.type === "select")[0].props.onChange({ target: { value: "teachhelper_test.db" } });
  h.render();
  h.click("Continue");
  assert.equal(posts(h).length, 0);
  assert.match(h.content(), /teachhelper_test.db/);
  h.click("Replace database");
  await settle();
  assert.deepEqual(posts(h).map((event) => event[0]), ["/api/restore/named"]);
  assert.deepEqual(JSON.parse(posts(h)[0][1].body), { name: "teachhelper_test.db" });
});

test("desktop file input has an explicit accessible label, SQLite accept types and reselection reset", async () => {
  const h = restoreHarness({ fetch: (url) => url.endsWith("/diag") ? response({ android: false }) : response({ error: "Invalid SQLite database" }, 400) });
  await h.ready();
  const input = h.all((node) => node.type === "input")[0];
  assert.equal(input.props.accept, "application/x-sqlite3,.db");
  assert.equal(h.all((node) => node.type === "label" && node.props.htmlFor === input.props.id).length, 1);
  assert.doesNotMatch(input.props.className, /hidden/);
  const file = new File(["synthetic test only"], "test.db", { type: "application/x-sqlite3" });
  for (let attempt = 0; attempt < 2; attempt++) {
    const event = { currentTarget: { files: [file], value: "test.db" } };
    input.props.onChange(event);
    assert.equal(event.currentTarget.value, "");
    h.render();
    h.click("Replace database");
    await settle();
    h.render();
  }
  assert.equal(posts(h).length, 2);
  assert.equal(posts(h)[0][0], "/api/restore");
  assert.equal(posts(h)[0][1].body.get("file").name, "test.db");
  assert.match(h.content(), /Invalid SQLite database/);
});

test("diagnostic failure, empty lists, network errors and malformed responses stay visible", async () => {
  for (const listResult of [response({ backups: [] }), response({ error: "List unavailable" }, 500)]) {
    const h = restoreHarness({ fetch: (url) => {
      if (url.endsWith("/diag")) throw new Error("offline");
      return listResult;
    } });
    await h.ready();
    assert.match(h.content(), /Could not check the file picker/);
    await h.click("Restore from saved backup");
    h.render();
    assert.match(h.content(), /No saved backups|List unavailable/);
    assert.equal(h.button("Continue").props.disabled, true);
  }
  for (const failure of [() => { throw new Error("Network unavailable"); }, () => ({ ok: true, status: 200, json: async () => { throw new Error("not JSON"); } })]) {
    const h = restoreHarness({ fetch: (url) => url.endsWith("/diag") ? response(native) : failure() });
    await h.ready();
    h.click("Restore database");
    h.click("Choose and restore");
    await settle();
    h.render();
    assert.match(h.content(), /Network unavailable|did not complete/);
    assert.equal(h.events.includes("reload"), false);
  }
});
