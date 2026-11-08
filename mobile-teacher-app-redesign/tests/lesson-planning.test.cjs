const test = require("node:test");
const assert = require("node:assert/strict");
const { sourceLoader, settle, response } = require("./helpers.cjs");

/* Регрессы к трём жалобам:
   1. Тап по запланированному занятию открывал лишнее окно выбора даты и
      номера пары. Теперь тап ведёт сразу в ведомость: store.startPlanLesson
      создаёт занятие (или открывает существующее) без промежуточных окон.
   2. Возврат из ведомости свайпом назад сбрасывал дату расписания на
      сегодня: экран размонтируется, useState терялся. Дата теперь лежит
      в sessionStorage (lib/scheduleDate.ts).
   3. Отменённое занятие после перезагрузки снова выглядело как
      «запланировано»: сервер отдавал его как scheduled, слот в расписании
      освобождался. Теперь отменённые приходят с status='cancelled' и
      занимают слот — плановой строки не появляется. */

async function fixture() {
  let fetcher = async () => response({ id: 500 }, 200);
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

  store.db = {
    seq: 100,
    settings: { theme: "light", teacherName: "", tgToken: "", maxToken: "", teacherCode: "",
      tgEnabled: false, maxEnabled: false, tgHasToken: false, maxHasToken: false, teacherBound: false },
    groups: [{ id: 1, name: "АДТ-31", curatorCode: "AAA111", curatorBound: false, subjectIds: [10] }],
    students: [{ id: 11, groupId: 1, name: "Иванов И." }],
    subjects: [{ id: 10, name: "МДК.01", totalHours: 30, heldLessons: 0, closedAt: null }],
    schedule: [
      { id: 100, groupId: 1, subjectId: 10, weekday: 1, parity: 0, time: "08:30", room: "1", lessonNumber: 1 },
    ],
    lessons: [],
    grades: [],
  };
  return { store, fetchWith(fn) { fetcher = fn; } };
}

/* ── Баг 1: тап по плану ведёт сразу в ведомость ────────────────────────── */

test("startPlanLesson creates the lesson for the planned pair and date", async () => {
  const { store } = await fixture();
  const item = store.db.schedule[0];
  const lesson = await store.startPlanLesson(item, "2026-11-02");
  assert.equal(lesson.date, "2026-11-02");
  assert.equal(lesson.groupId, 1);
  assert.equal(lesson.subjectId, 10);
  assert.equal(lesson.lessonNumber, 1);
  assert.equal(lesson.status, "scheduled");
  assert.equal(store.db.lessons.length, 1);
});

test("startPlanLesson does not duplicate an existing lesson", async () => {
  const { store } = await fixture();
  const item = store.db.schedule[0];
  const first = await store.startPlanLesson(item, "2026-11-02");
  const second = await store.startPlanLesson(item, "2026-11-02");
  assert.equal(second.id, first.id);
  assert.equal(store.db.lessons.length, 1);
});

test("startPlanLesson opens a cancelled lesson instead of creating a new one", async () => {
  const { store } = await fixture();
  const item = store.db.schedule[0];
  store.db.lessons.push({
    id: 777, groupId: 1, subjectId: 10, date: "2026-11-02", status: "cancelled",
    time: "08:30", room: "1", lessonNumber: 1,
  });
  const lesson = await store.startPlanLesson(item, "2026-11-02");
  assert.equal(lesson.id, 777);
  assert.equal(store.db.lessons.length, 1);
});

/* ── Баг 2: дата расписания переживает размонтирование экрана ─────────── */

test("schedule date survives screen remount", async () => {
  const backing = new Map();
  const load = sourceLoader({}, {
    sessionStorage: {
      getItem: (k) => (backing.has(k) ? backing.get(k) : null),
      setItem: (k, v) => backing.set(k, v),
      removeItem: (k) => backing.delete(k),
    },
  });
  const { readScheduleDate, saveScheduleDate, clearScheduleDate } =
    load("src/lib/scheduleDate.ts");

  assert.equal(readScheduleDate(), null);
  saveScheduleDate("2026-11-02");
  assert.equal(readScheduleDate(), "2026-11-02");
  // «Экран размонтировался и смонтировался заново» — дата та же.
  assert.equal(readScheduleDate(), "2026-11-02");
  clearScheduleDate();
  assert.equal(readScheduleDate(), null);
});

test("schedule screen restores the saved date instead of today", () => {
  const fs = require("node:fs");
  const path = require("node:path");
  const root = path.resolve(__dirname, "..");
  const source = fs.readFileSync(path.join(root, "src/screens/Schedule.tsx"), "utf8");
  assert.match(source, /readScheduleDate\(\) \?\? today/,
    "экран расписания должен восстанавливать сохранённую дату");
  assert.match(source, /saveScheduleDate\(value\)/,
    "выбранная дата должна сохраняться при смене");
});

/* ── Баг 3: отменённое занятие не выглядит запланированным ─────────────── */

test("cancelled lesson keeps its slot: no planned row appears again", async () => {
  const { store } = await fixture();
  const load = sourceLoader({}, { window: { location: { hash: "" } } });
  const { dayRows } = load("src/components/shell.tsx");

  store.db.lessons.push({
    id: 777, groupId: 1, subjectId: 10, date: "2026-11-02", status: "cancelled",
    time: "08:30", room: "1", lessonNumber: 1,
  });

  const rows = dayRows(store.db, "2026-11-02");
  const planned = rows.filter((r) => r.kind === "plan");
  const lessons = rows.filter((r) => r.kind === "lesson");
  assert.equal(planned.length, 0, "плановая строка не должна возвращаться");
  assert.equal(lessons.length, 1);
  assert.equal(lessons[0].lesson.status, "cancelled");
});
