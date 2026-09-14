const test = require("node:test");
const assert = require("node:assert/strict");
const { sourceLoader, settle, response, deferred } = require("./helpers.cjs");

async function fixture() {
  let fetcher = async () => response([], 503);
  const timers = new Map(), listeners = {};
  let nextTimer = 0;
  const load = sourceLoader({}, {
    fetch: (...args) => fetcher(...args),
    console: { error() {} },
    localStorage: { getItem: () => null, setItem() {} },
    window: { addEventListener: (name, fn) => { listeners[name] = fn; } },
    document: { addEventListener: (name, fn) => { listeners[name] = fn; }, visibilityState: "hidden" },
    setTimeout: (fn) => { timers.set(++nextTimer, fn); return nextTimer; },
    clearTimeout: (id) => timers.delete(id),
  });
  const store = load("src/lib/store.ts").store;
  await settle();
  store.db.grades = [{ lessonId: 1, studentId: 11, present: true, value: null }];
  return { store, timers, listeners, fetchWith(fn) { fetcher = fn; } };
}

for (const mutation of ["cycleGrade", "togglePresent"]) {
  test(`${mutation} rolls back to the snapshot before mutation on failure`, async () => {
    const { store, fetchWith } = await fixture();
    fetchWith(async () => response({}, 500));
    const before = JSON.stringify(store.db.grades);
    store[mutation](1, 11, 1);
    assert.notEqual(JSON.stringify(store.db.grades), before);
    await assert.rejects(store.flushAttendance(), /500/);
    assert.equal(JSON.stringify(store.db.grades), before);
  });
}

test("concurrent flush callers share one request and drain new edits serially", async () => {
  const { store, fetchWith, timers } = await fixture();
  const first = deferred(), second = deferred(), bodies = [];
  fetchWith((url, options) => {
    bodies.push(JSON.parse(options.body));
    return bodies.length === 1 ? first.promise : second.promise;
  });
  store.cycleGrade(1, 11, 1);
  const a = store.flushAttendance();
  store.cycleGrade(1, 11, 1);
  const b = store.flushAttendance();
  assert.equal(a, b);
  assert.equal(bodies.length, 1);
  first.resolve(response({ ok: true }));
  await settle();
  assert.equal(bodies.length, 2);
  assert.equal(bodies[0][0].grade, "5");
  assert.equal(bodies[1][0].grade, "4");
  second.resolve(response({ ok: true }));
  await Promise.all([a, b]);
  assert.equal(timers.size, 0);
  await store.flushAttendance();
  assert.equal(bodies.length, 2);
});

test("a failed in-flight batch preserves newer edits and their original rollback baseline", async () => {
  const { store, fetchWith } = await fixture();
  const first = deferred();
  fetchWith(() => first.promise);
  store.cycleGrade(1, 11, 1);
  const pending = store.flushAttendance();
  store.cycleGrade(1, 11, 1);
  const rejected = assert.rejects(pending, /500/);
  first.resolve(response({}, 500));
  await rejected;
  assert.equal(store.gradeOf(1, 11).value, 4);
  const payloads = [];
  fetchWith(async (_, options) => { payloads.push(JSON.parse(options.body)); return response({}, 500); });
  await assert.rejects(store.flushAttendance(), /500/);
  assert.equal(payloads[0][0].grade, "4");
  assert.equal(store.gradeOf(1, 11).value, null);
});

test("all lesson payloads are frozen before a batch awaits network", async () => {
  const { store, fetchWith } = await fixture();
  store.db.grades.push({ lessonId: 2, studentId: 22, present: true, value: null });
  const first = deferred(), payloads = [];
  fetchWith((url, options) => {
    payloads.push([url, JSON.parse(options.body)]);
    return payloads.length === 1 ? first.promise : Promise.resolve(response({ ok: true }));
  });
  store.cycleGrade(1, 11, 1);
  store.cycleGrade(2, 22, 1);
  const pending = store.flushAttendance();
  store.cycleGrade(2, 22, 1);
  first.resolve(response({ ok: true }));
  await pending;
  assert.deepEqual(payloads.map((entry) => entry[1][0].grade), ["5", "5", "4"]);
});

test("lifecycle flush after a completed pre-restore drain sends no stale attendance", async () => {
  const { store, fetchWith, listeners, timers } = await fixture();
  const writes = [];
  fetchWith(async (url) => { writes.push(url); return response({ ok: true }); });
  store.cycleGrade(1, 11, 1);
  await store.flushAttendance();
  assert.equal(timers.size, 0);
  listeners.pagehide();
  listeners.visibilitychange();
  await settle();
  assert.equal(writes.length, 1);
});

function apiData(url) {
  if (url === "/api/groups") return [{ id: 1, name: "Synthetic group" }];
  if (url === "/api/subjects") return [{ id: 2, group_id: 1, name: "Synthetic subject" }];
  if (url === "/api/schedule/today") return { lessons: [] };
  if (url.endsWith("/curator")) return { code: "TEST", bound: false };
  if (url.endsWith("/gradebook")) return { lessons: [], grades: {}, students: [] };
  if (url.startsWith("/api/settings/")) return { has_token: false, enabled: false };
  return [];
}

for (const failing of ["/api/groups", "/api/subjects/2/gradebook", "/api/groups/1/curator", "/api/settings/bot"]) {
  test(`reloadAll propagates ${failing} failure and retains the existing database`, async () => {
    const { store, fetchWith } = await fixture();
    const before = store.db;
    fetchWith(async (url) => response(apiData(url), url === failing ? 500 : 200));
    await assert.rejects(store.reloadAll(), /500/);
    assert.equal(store.db, before);
  });
}

test("reloadAll replaces state on complete success", async () => {
  const { store, fetchWith } = await fixture();
  fetchWith(async (url) => response(apiData(url)));
  await store.reloadAll();
  assert.equal(store.db.groups[0].name, "Synthetic group");
  assert.equal(store.db.grades.length, 0);
});
