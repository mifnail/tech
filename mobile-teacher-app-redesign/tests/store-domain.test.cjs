const test = require("node:test");
const assert = require("node:assert/strict");
const { sourceLoader, settle, response } = require("./helpers.cjs");

/* Тесты доменной части стора: каскадные удаления, вычитка предмета,
   счётчик проведённых пар и плановые строки расписания.

   Фронт-тестов было 10 файлов на 7 206 строк TS — плотность в 9 раз ниже
   бэкенда. Здесь закрывается самая хрупкая часть: мутации, которые молча
   портят данные (удаление группы тянет за собой оценки, проведение
   увеличивает счётчик часов, закрытый предмет уходит из расписания). */

async function fixture() {
  let fetcher = async () => response({}, 200);
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
    groups: [
      { id: 1, name: "Группа-1", curatorCode: "AAA111", curatorBound: false, subjectIds: [10] },
      { id: 2, name: "Группа-2", curatorCode: "BBB222", curatorBound: false, subjectIds: [20] },
    ],
    students: [
      { id: 11, groupId: 1, name: "Иванов И." },
      { id: 12, groupId: 1, name: "Петров П." },
      { id: 21, groupId: 2, name: "Сидоров С." },
    ],
    subjects: [
      { id: 10, name: "МДК.01", totalHours: 30, heldLessons: 4, closedAt: null },
      { id: 20, name: "ПМ.02", totalHours: 60, heldLessons: 0, closedAt: null },
    ],
    schedule: [
      { id: 100, groupId: 1, subjectId: 10, weekday: 1, parity: 0, time: "08:30", room: "1", lessonNumber: 1 },
      { id: 101, groupId: 2, subjectId: 20, weekday: 1, parity: 0, time: "10:10", room: "2", lessonNumber: 2 },
    ],
    lessons: [
      // 03.11 — вторник: расписание построено по понедельникам, поэтому
      // занятие не занимает слот плана.
      { id: 200, groupId: 1, subjectId: 10, date: "2026-11-03", status: "scheduled", time: "08:30", room: "1", lessonNumber: 1 },
    ],
    grades: [
      { lessonId: 200, studentId: 11, value: 5, present: true },
      { lessonId: 200, studentId: 12, value: null, present: false },
    ],
  };
  return { store, fetchWith(fn) { fetcher = fn; } };
}

/* ── Каскадные удаления ──────────────────────────────────────────────── */

test("removeGroup removes its students, lessons, schedule and grades", async () => {
  const { store } = await fixture();
  store.removeGroup(1);
  assert.equal(store.db.groups.length, 1);
  assert.equal(store.db.students.filter((s) => s.groupId === 1).length, 0);
  assert.equal(store.db.lessons.filter((l) => l.groupId === 1).length, 0);
  assert.equal(store.db.schedule.filter((s) => s.groupId === 1).length, 0);
  // Оценки удалённых студентов и занятий не должны остаться в журнале.
  assert.equal(store.db.grades.filter((g) => g.studentId === 11 || g.lessonId === 200).length, 0);
  // Чужая группа не тронута.
  assert.equal(store.db.students.filter((s) => s.groupId === 2).length, 1);
});

test("removeGroup restores everything when the server refuses", async () => {
  const { store, fetchWith } = await fixture();
  fetchWith(async () => response({}, 500));
  store.removeGroup(1);
  await settle();
  await settle();
  assert.equal(store.db.groups.length, 2);
  assert.equal(store.db.students.length, 3);
  assert.equal(store.db.lessons.length, 1);
  assert.equal(store.db.grades.length, 2);
});

test("removeStudent removes their grades too", async () => {
  const { store } = await fixture();
  store.removeStudent(11);
  assert.equal(store.db.students.filter((s) => s.id === 11).length, 0);
  assert.equal(store.db.grades.filter((g) => g.studentId === 11).length, 0);
  assert.equal(store.db.grades.filter((g) => g.studentId === 12).length, 1);
});

/* ── Вычитка предмета ─────────────────────────────────────────────────── */

test("closeSubject marks the subject as closed and keeps the date", async () => {
  const { store, fetchWith } = await fixture();
  const calls = [];
  fetchWith(async (url, options) => { calls.push([url, options]); return response({}, 200); });
  await store.closeSubject(10, "2026-11-07");
  assert.equal(store.subject(10).closedAt, "2026-11-07");
  assert.equal(calls[0][0], "/api/subjects/10/close");
});

test("closeSubject rolls back the date when the server fails", async () => {
  const { store, fetchWith } = await fixture();
  fetchWith(async () => response({}, 500));
  await store.closeSubject(10, "2026-11-07");
  assert.equal(store.subject(10).closedAt, null);
});

test("reopenSubject clears the closing date", async () => {
  const { store } = await fixture();
  store.subject(10).closedAt = "2026-11-07";
  await store.reopenSubject(10);
  assert.equal(store.subject(10).closedAt, null);
});

test("reopenSubject restores the date when the server fails", async () => {
  const { store, fetchWith } = await fixture();
  store.subject(10).closedAt = "2026-11-07";
  fetchWith(async () => response({}, 500));
  await store.reopenSubject(10);
  assert.equal(store.subject(10).closedAt, "2026-11-07");
});

/* ── Проведение занятия ───────────────────────────────────────────────── */

test("conductLesson counts the pair only once", async () => {
  const { store, fetchWith } = await fixture();
  fetchWith(async () => response({ notified: 2 }, 200));
  await store.conductLesson(200);
  assert.equal(store.lesson(200).status, "held");
  assert.equal(store.subject(10).heldLessons, 5);
  // Повторное проведение не должно удваивать счётчик.
  await store.conductLesson(200);
  assert.equal(store.subject(10).heldLessons, 5);
});

test("conductLesson reports hours exhausted from the server", async () => {
  const { store, fetchWith } = await fixture();
  fetchWith(async () => response({
    notified: 1, hours_exhausted: true, hours_message: "Пары по предмету «МДК.01» вычитаны: 30 из 30.",
  }, 200));
  const res = await store.conductLesson(200);
  assert.equal(res.notified, 1);
  assert.equal(res.hoursExhausted, true);
  assert.match(res.hoursMessage, /вычитаны/);
});

test("conductLesson keeps the pair pending when the server fails", async () => {
  const { store, fetchWith } = await fixture();
  fetchWith(async () => response({}, 500));
  await assert.rejects(store.conductLesson(200), /500/);
  assert.equal(store.lesson(200).status, "scheduled");
  assert.equal(store.subject(10).heldLessons, 4);
});

/* ── Плановые строки расписания ──────────────────────────────────────── */

function dayRowsOf(store, db) {
  const load = sourceLoader({}, { window: { location: { hash: "" } } });
  return load("src/components/shell.tsx").dayRows;
}

test("a closed subject leaves the schedule but stays in the journal", async () => {
  const { store } = await fixture();
  const dayRows = dayRowsOf(store, store.db);
  store.subject(10).closedAt = "2026-11-07";

  const before = dayRows(store.db, "2026-11-02");  // понедельник до закрытия
  const after = dayRows(store.db, "2026-11-09");   // понедельник после закрытия
  const journal = dayRows(store.db, "2026-11-03"); // вторник: само занятие

  const planned = (rows) => rows.filter((r) => r.kind === "plan");
  assert.equal(planned(before).filter((p) => p.item.subjectId === 10).length, 1);
  assert.equal(planned(after).filter((p) => p.item.subjectId === 10).length, 0);
  // Чужой предмет в этом же расписании остаётся.
  assert.equal(planned(after).filter((p) => p.item.subjectId === 20).length, 1);
  // Само занятие вычитанного предмета в журнале остаётся.
  assert.equal(journal.filter((r) => r.kind === "lesson" && r.lesson.id === 200).length, 1);
});
