/* Локальное реактивное хранилище — зеркало REST API бэкенда.
   DEV: персистентность в localStorage и детерминированный сид.
   PROD: fetch к API при старте; мутации — in-memory (запись на сервер — фаза 3). */

import { useSyncExternalStore } from "react";
import type {
  DB, GradeRec, Group, Lesson, LessonStatus,
  ScheduleItem, Settings, Student, Subject, ID,
} from "./types";
import { addDaysISO, todayISO, weekParity, weekdayOf } from "./date";
import { nextGrade, prevGrade } from "./grades";

const LS_KEY = "th4-db-v2";

/* ── DEV-only: Детерминированный PRNG и сид ─────────────────── */
function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function makeCode(rand: () => number, len = 6): string {
  const abc = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  let s = "";
  for (let i = 0; i < len; i++) s += abc[Math.floor(rand() * abc.length)];
  return s;
}

const NAMES = [
  "Андреева Ксения", "Белов Матвей", "Воронцова Дарья", "Громов Артём",
  "Дмитриева Алина", "Егоров Никита", "Жукова Полина", "Зайцев Кирилл",
  "Ильина Софья", "Козлов Даниил", "Лебедева Мария", "Морозов Илья",
  "Николаева Варвара", "Осипов Роман", "Павлова Анна", "Рыбаков Тимофей",
  "Семёнова Ева", "Тарасов Максим", "Ушакова Милана", "Фролов Александр",
  "Харитонова Виктория", "Цветков Егор", "Чернова Ульяна", "Широков Павел",
  "Юдина Кристина", "Яковлев Степан", "Афанасьева Таисия", "Богданов Лев",
  "Власова Анастасия", "Гудков Марк", "Денисова Екатерина", "Ермолаев Глеб",
  "Жданова Алиса", "Зубарев Владимир", "Игнатьева Диана", "Куликов Арсений",
  "Луговой Антон", "Михайлова Серафима", "Новиков Дмитрий", "Орлова Маргарита",
  "Петухов Николай", "Родионова Амелия", "Савельев Ярослав", "Тимофеева Злата",
  "Уваров Фёдор", "Фомина Василиса", "Хохлов Семён",
];

/* ── Сид: 5 недель журнала + расписание с чёт/неч ─────────── */
function seed(): DB {
  const rand = mulberry32(20260204);
  let seq = 1;
  const id = () => seq++;

  const subjects: Subject[] = [
    { id: id(), name: "Базы данных" },
    { id: id(), name: "Операционные системы" },
    { id: id(), name: "Математический анализ" },
    { id: id(), name: "Иностранный язык" },
    { id: id(), name: "Архитектура ЭВМ" },
  ];
  const [BD, OS, MA, EN, AR] = subjects.map((s) => s.id);

  const groupsRaw = [
    { name: "ИС-21", size: 16, subs: [BD, OS, MA] },
    { name: "ЭК-21", size: 15, subs: [MA, EN] },
    { name: "ТМ-23", size: 14, subs: [EN, AR, MA] },
  ];

  const groups: Group[] = [];
  const students: Student[] = [];
  let n = 0;
  for (const g of groupsRaw) {
    const gid = id();
    groups.push({ id: gid, name: g.name, curatorCode: makeCode(rand), subjectIds: g.subs });
    for (let i = 0; i < g.size; i++, n++) {
      students.push({
        id: id(),
        groupId: gid,
        name: NAMES[n % NAMES.length],
        tg: rand() < 0.55,
        max: rand() < 0.45,
      });
    }
  }
  const [IS, EK, TM] = groups.map((g) => g.id);

  const schedule: ScheduleItem[] = [
    { id: id(), groupId: IS, subjectId: BD, weekday: 1, parity: 0, time: "09:00", room: "204" },
    { id: id(), groupId: EK, subjectId: MA, weekday: 1, parity: 0, time: "10:40", room: "315" },
    { id: id(), groupId: TM, subjectId: EN, weekday: 1, parity: 2, time: "13:00", room: "112" },
    { id: id(), groupId: IS, subjectId: OS, weekday: 2, parity: 0, time: "09:00", room: "421" },
    { id: id(), groupId: TM, subjectId: AR, weekday: 2, parity: 1, time: "10:40", room: "118" },
    { id: id(), groupId: IS, subjectId: MA, weekday: 3, parity: 0, time: "10:40", room: "315" },
    { id: id(), groupId: EK, subjectId: EN, weekday: 3, parity: 0, time: "13:00", room: "112" },
    { id: id(), groupId: TM, subjectId: MA, weekday: 3, parity: 2, time: "09:00", room: "315" },
    { id: id(), groupId: IS, subjectId: BD, weekday: 4, parity: 0, time: "09:00", room: "204" },
    { id: id(), groupId: EK, subjectId: MA, weekday: 4, parity: 1, time: "10:40", room: "315" },
    { id: id(), groupId: TM, subjectId: AR, weekday: 5, parity: 0, time: "10:40", room: "118" },
    { id: id(), groupId: EK, subjectId: EN, weekday: 5, parity: 2, time: "09:00", room: "112" },
    { id: id(), groupId: IS, subjectId: OS, weekday: 6, parity: 2, time: "09:00", room: "421" },
  ];

  // Прошлые занятия — 5 недель назад по расписанию, проведённые, с оценками.
  const lessons: Lesson[] = [];
  const grades: GradeRec[] = [];
  const today = todayISO();

  const gradeFor = (): number => {
    const r = rand();
    return r < 0.32 ? 5 : r < 0.68 ? 4 : r < 0.9 ? 3 : 2;
  };

  for (let back = 34; back >= 1; back--) {
    const date = addDaysISO(today, -back);
    const wd = weekdayOf(date);
    const par = weekParity(date);
    for (const it of schedule) {
      if (it.weekday !== wd) continue;
      if (it.parity !== 0 && it.parity !== par) continue;
      if (rand() < 0.06) continue; // пара выпала
      const lid = id();
      lessons.push({
        id: lid, groupId: it.groupId, subjectId: it.subjectId,
        date, status: "held", time: it.time, room: it.room,
      });
      for (const st of students.filter((s) => s.groupId === it.groupId)) {
        const present = rand() > 0.07;
        grades.push({
          lessonId: lid, studentId: st.id,
          value: present ? gradeFor() : null, present,
        });
      }
    }
  }

  // Сегодня: занятия по расписанию (или пара запасных, если выходной).
  let todayItems = schedule.filter(
    (it) => it.weekday === weekdayOf(today) &&
      (it.parity === 0 || it.parity === weekParity(today)),
  );
  if (!todayItems.length) todayItems = [schedule[0], schedule[3]];
  for (const it of todayItems.slice(0, 3)) {
    lessons.push({
      id: id(), groupId: it.groupId, subjectId: it.subjectId,
      date: today, status: "scheduled", time: it.time, room: it.room,
    });
  }

  return {
    groups, students, subjects, schedule, lessons, grades,
    settings: {
      theme: (typeof localStorage !== "undefined" &&
        localStorage.getItem("th-theme") === "dark") ? "dark" : "light",
      teacherName: "Иванова А. П.",
      tgToken: "",
      maxToken: "",
      teacherCode: makeCode(rand),
    },
    seq,
  };
}

/* ── PROD-only: пустая БД для начального состояния ─────────── */
function emptyDB(): DB {
  return {
    groups: [],
    students: [],
    subjects: [],
    schedule: [],
    lessons: [],
    grades: [],
    settings: {
      theme: (typeof localStorage !== "undefined" &&
        localStorage.getItem("th-theme") === "dark") ? "dark" : "light",
      teacherName: "",
      tgToken: "",
      maxToken: "",
      teacherCode: "",
    },
    seq: 0,
  };
}

/* ── PROD-only: импеданс-маппинг ────────────────────────────── */
function joinName(r: { last_name: string; first_name: string; middle_name?: string }): string {
  return [r.last_name, r.first_name, r.middle_name].filter(Boolean).join(" ");
}

function parseGrade(grade: string): { value: number | null; present: boolean } {
  if (grade === "0") return { value: 0, present: true };
  const n = Number(grade);
  if (!isNaN(n) && n >= 2 && n <= 5) return { value: n, present: true };
  return { value: null, present: false };
}

async function fetchJson(url: string): Promise<unknown> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json();
}

/* ── Хранилище ────────────────────────────────────────────── */
class Store {
  db: DB;
  private listeners = new Set<() => void>();
  version = 0;
  private saveTimer: ReturnType<typeof setTimeout> | null = null;
  /** Обратная карта subjectId → groupId (для маппинга расписания/уроков). */
  private subjectGroup = new Map<ID, ID>();

  constructor() {
    if (import.meta.env.DEV) {
      /* ── DEV: seed + localStorage ──────────────────────── */
      let loaded: DB | null = null;
      try {
        const raw = localStorage.getItem(LS_KEY);
        if (raw) {
          const parsed = JSON.parse(raw) as DB;
          if (parsed && parsed.groups && parsed.lessons && parsed.settings) loaded = parsed;
        }
      } catch (_) { /* битый кэш — пересидим */ }
      this.db = loaded ?? seed();
      this.persist();
    } else {
      /* ── PROD: пустая БД + async загрузка с сервера ───── */
      this.db = emptyDB();
      this.loadFromApi();
    }
  }

  subscribe = (fn: () => void) => {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  };
  getVersion = () => this.version;

  private touch() {
    this.version++;
    this.listeners.forEach((fn) => fn());
    if (import.meta.env.DEV) {
      if (this.saveTimer) clearTimeout(this.saveTimer);
      this.saveTimer = setTimeout(() => this.persist(), 250);
    }
  }

  persist() {
    try { localStorage.setItem(LS_KEY, JSON.stringify(this.db)); } catch (_) {}
  }

  private nextId(): ID {
    return this.db.seq++;
  }

  /* ── PROD: загрузка данных с сервера ─────────────────── */
  private async loadFromApi() {
    try {
      // Batch 1: основные данные (параллельно)
      const [groupsRaw, subjectsRaw, studentsRaw, scheduleRaw, todayRaw, tgLinks, maxLinks] =
        await Promise.all([
          fetchJson("/api/groups") as Promise<Array<{ id: number; name: string }>>,
          fetchJson("/api/subjects") as Promise<Array<{
            id: number; name: string; group_id: number;
            held_lessons: number; average_grade?: number;
          }>>,
          fetchJson("/api/students") as Promise<Array<{
            id: number; group_id: number;
            last_name: string; first_name: string; middle_name: string;
          }>>,
          fetchJson("/api/schedule") as Promise<Array<{
            id: number; day_of_week: number; lesson_number: number;
            subject_id: number; week_type: number;
            subject_name: string; group_name: string;
          }>>,
          fetchJson("/api/schedule/today") as Promise<{
            lessons: Array<{
              id: number; subject_id: number; actual_subject_id: number | null;
              date: string; status: string; lesson_number: number | null;
              group_id: number; group_name: string;
              planned_subject: string; actual_subject_name: string;
            }>;
          }>,
          fetchJson("/api/bot/links") as Promise<Array<{ student_id: number }>>,
          fetchJson("/api/maxbot/links") as Promise<Array<{ student_id: number }>>,
        ]);

      // Обратная карта: subjectId → groupId
      const sg = new Map<ID, ID>();
      for (const s of subjectsRaw) sg.set(s.id, s.group_id);
      this.subjectGroup = sg;

      // Множества привязок ботов
      const tgSet = new Set(tgLinks.map((l) => l.student_id));
      const maxSet = new Set(maxLinks.map((l) => l.student_id));

      // Batch 2: коды кураторов + gradebook'и (параллельно)
      const curatorP = groupsRaw.map((g) =>
        fetchJson(`/api/groups/${g.id}/curator`)
          .then((c) => (c as { code: string }).code || "")
          .catch(() => ""),
      );
      const gbP = subjectsRaw.map((s) =>
        (fetchJson(`/api/subjects/${s.id}/gradebook`) as Promise<{
          lessons: Array<{ id: number; date: string; lesson_number: number | null }>;
          grades: Record<string, Record<string, string>>;
          students: Array<{ id: number }>;
        }>).catch(() => ({ lessons: [], grades: {}, students: [] })),
      );
      const [curators, gradebooks] = await Promise.all([
        Promise.all(curatorP),
        Promise.all(gbP),
      ]);

      // Маппинг групп
      const groups: Group[] = groupsRaw.map((g, i) => {
        const subIds = subjectsRaw.filter((s) => s.group_id === g.id).map((s) => s.id);
        return {
          id: g.id,
          name: g.name,
          curatorCode: curators[i],
          subjectIds: subIds,
        };
      });

      // Маппинг студентов
      const students: Student[] = studentsRaw.map((s) => ({
        id: s.id,
        groupId: s.group_id,
        name: joinName(s),
        tg: tgSet.has(s.id),
        max: maxSet.has(s.id),
      }));

      // Маппинг предметов (только id + name для React-модели)
      const subjects: Subject[] = subjectsRaw.map((s) => ({ id: s.id, name: s.name }));

      // Маппинг расписания
      const schedule: ScheduleItem[] = scheduleRaw.map((s) => ({
        id: s.id,
        groupId: sg.get(s.subject_id) ?? 0,
        subjectId: s.subject_id,
        weekday: s.day_of_week,
        parity: s.week_type as 0 | 1 | 2,
        time: "",
        room: "",
      }));

      // Маппинг уроков и оценок из gradebook'ов
      const lessons: Lesson[] = [];
      const grades: GradeRec[] = [];
      const lessonIds = new Set<ID>();

      for (let i = 0; i < subjectsRaw.length; i++) {
        const subjId = subjectsRaw[i].id;
        const grpId = sg.get(subjId) ?? 0;
        const gb = gradebooks[i];

        for (const l of gb.lessons) {
          if (!lessonIds.has(l.id)) {
            lessonIds.add(l.id);
            lessons.push({
              id: l.id,
              groupId: grpId,
              subjectId: subjId,
              date: l.date,
              status: "held" as LessonStatus,
              time: "",
              room: "",
            });
          }
        }

        // Оценки: {student_id: {lesson_id: grade_text}}
        for (const [sidStr, lmap] of Object.entries(gb.grades)) {
          const sid = Number(sidStr);
          for (const [lidStr, gradeText] of Object.entries(lmap)) {
            const lid = Number(lidStr);
            const g = parseGrade(String(gradeText));
            grades.push({ lessonId: lid, studentId: sid, value: g.value, present: g.present });
          }
        }
      }

      // Сегодняшние уроки (из /api/schedule/today)
      for (const l of todayRaw.lessons) {
        if (!lessonIds.has(l.id)) {
          lessonIds.add(l.id);
          lessons.push({
            id: l.id,
            groupId: l.group_id,
            subjectId: l.actual_subject_id ?? l.subject_id,
            date: l.date,
            status: (l.status === "replaced" ? "cancelled" : l.status) as LessonStatus,
            time: "",
            room: "",
          });
        }
      }

      // Настройки: teacherCode из maxbot settings
      let teacherCode = "";
      try {
        const ms = await fetchJson("/api/settings/maxbot") as { teacher_code?: string };
        teacherCode = ms.teacher_code || "";
      } catch (_) { /* ignore */ }

      // Вычисляем max seq
      const maxId = Math.max(
        ...groups.map((g) => g.id),
        ...students.map((s) => s.id),
        ...subjects.map((s) => s.id),
        ...schedule.map((s) => s.id),
        ...lessons.map((l) => l.id),
        0,
      );

      this.db = {
        groups, students, subjects, schedule, lessons, grades,
        settings: {
          theme: (typeof localStorage !== "undefined" &&
            localStorage.getItem("th-theme") === "dark") ? "dark" : "light",
          teacherName: "",
          tgToken: "",
          maxToken: "",
          teacherCode,
        },
        seq: maxId + 1,
      };
      this.persist();
      this.touch();
    } catch (e) {
      console.error("[store] loadFromApi failed:", e);
    }
  }

  /* ── PROD: загрузка данных конкретного урока (attendance + adjacent) ── */
  async loadLesson(id: ID) {
    if (import.meta.env.DEV) return;
    try {
      const [att, adj] = await Promise.all([
        fetchJson(`/api/lessons/${id}/attendance`) as Promise<{
          lesson: { id: number; subject_id: number; actual_subject_id: number | null;
                    date: string; status: string; group_id?: number } | null;
          attendance: Array<{ student_id: number; grade: string }>;
          students: Array<{ id: number; group_id: number }>;
        }>,
        fetchJson(`/api/lessons/${id}/adjacent`) as Promise<{ prev_id: number | null; next_id: number | null }>,
      ]);

      if (!att.lesson) return;
      const srv = att.lesson;
      const grpId = srv.group_id ?? this.subjectGroup.get(srv.subject_id) ?? 0;
      const subjId = srv.actual_subject_id ?? srv.subject_id;
      const mapped: Lesson = {
        id: srv.id,
        groupId: grpId,
        subjectId: subjId,
        date: srv.date,
        status: (srv.status === "replaced" ? "cancelled" : srv.status) as LessonStatus,
        time: "",
        room: "",
      };

      // Upsert урока
      const existing = this.db.lessons.find((l) => l.id === id);
      if (existing) Object.assign(existing, mapped);
      else {
        this.db.lessons.push(mapped);
        this.db.seq = Math.max(this.db.seq, id + 1);
      }

      // Заменяем оценки для этого урока
      this.db.grades = this.db.grades.filter((g) => g.lessonId !== id);
      const gradedIds = new Set<number>();
      for (const rec of att.attendance) {
        const g = parseGrade(rec.grade);
        this.db.grades.push({ lessonId: id, studentId: rec.student_id, value: g.value, present: g.present });
        gradedIds.add(rec.student_id);
      }
      // Студенты без оценки → отсутствуют
      for (const st of att.students) {
        if (!gradedIds.has(st.id)) {
          this.db.grades.push({ lessonId: id, studentId: st.id, value: null, present: false });
        }
      }

      // Обновляем смежные уроки (prev/next) — подсказки для навигации
      // Храним как overlay на уроке (не ломая тип Lesson)
      if (adj.prev_id != null) this.ensureLessonStub(adj.prev_id, grpId, subjId);
      if (adj.next_id != null) this.ensureLessonStub(adj.next_id, grpId, subjId);

      this.persist();
      this.touch();
    } catch (e) {
      console.error("[store] loadLesson failed:", e);
    }
  }

  /** Заглушка урока, чтобы LessonRun мог перейти на prev/next. */
  private ensureLessonStub(id: ID, groupId: ID, subjectId: ID) {
    if (this.db.lessons.some((l) => l.id === id)) return;
    this.db.lessons.push({
      id, groupId, subjectId, date: "", status: "scheduled", time: "", room: "",
    });
    this.db.seq = Math.max(this.db.seq, id + 1);
  }

  /* ── Селекторы ─────────────────────────────────────────── */
  group(id: ID): Group | undefined { return this.db.groups.find((g) => g.id === id); }
  subject(id: ID): Subject | undefined { return this.db.subjects.find((s) => s.id === id); }
  lesson(id: ID): Lesson | undefined { return this.db.lessons.find((l) => l.id === id); }
  studentsOf(groupId: ID): Student[] {
    return this.db.students.filter((s) => s.groupId === groupId);
  }
  gradeOf(lessonId: ID, studentId: ID): GradeRec | undefined {
    return this.db.grades.find((g) => g.lessonId === lessonId && g.studentId === studentId);
  }
  gradesOfLesson(lessonId: ID): GradeRec[] {
    return this.db.grades.filter((g) => g.lessonId === lessonId);
  }
  gradesOfStudent(studentId: ID): GradeRec[] {
    return this.db.grades.filter((g) => g.studentId === studentId);
  }
  /** Занятия пары «группа+предмет», по дате и времени. */
  lessonsOfPair(groupId: ID, subjectId: ID): Lesson[] {
    return this.db.lessons
      .filter((l) => l.groupId === groupId && l.subjectId === subjectId)
      .sort((a, b) => (a.date + a.time).localeCompare(b.date + b.time));
  }
  lessonsOn(date: string): Lesson[] {
    return this.db.lessons
      .filter((l) => l.date === date)
      .sort((a, b) => a.time.localeCompare(b.time));
  }
  /** Пары «предмет—группа» из расписания (для «Начать занятие»). */
  scheduledPairs(): { groupId: ID; subjectId: ID }[] {
    const seen = new Set<string>();
    const out: { groupId: ID; subjectId: ID }[] = [];
    for (const it of this.db.schedule) {
      const k = it.groupId + "/" + it.subjectId;
      if (seen.has(k)) continue;
      seen.add(k);
      out.push({ groupId: it.groupId, subjectId: it.subjectId });
    }
    return out;
  }
  scheduleFor(weekday: number, parity: 1 | 2): ScheduleItem[] {
    return this.db.schedule
      .filter((it) => it.weekday === weekday && (it.parity === 0 || it.parity === parity))
      .sort((a, b) => a.time.localeCompare(b.time));
  }
  scheduleItemFor(lesson: Pick<Lesson, "groupId" | "subjectId">, date: string): ScheduleItem | undefined {
    const wd = weekdayOf(date);
    const par = weekParity(date);
    return this.db.schedule.find(
      (it) =>
        it.groupId === lesson.groupId && it.subjectId === lesson.subjectId &&
        it.weekday === wd && (it.parity === 0 || it.parity === par),
    );
  }

  /* ── Мутации ───────────────────────────────────────────── */
  addGroup(name: string): Group {
    const g: Group = {
      id: this.nextId(), name: name.trim(),
      curatorCode: makeCode(Math.random), subjectIds: [],
    };
    this.db.groups.push(g);
    this.touch();
    return g;
  }
  removeGroup(id: ID) {
    const studentIds = this.studentsOf(id).map((s) => s.id);
    const lessonIds = this.db.lessons.filter((l) => l.groupId === id).map((l) => l.id);
    this.db.grades = this.db.grades.filter(
      (g) => !studentIds.includes(g.studentId) && !lessonIds.includes(g.lessonId),
    );
    this.db.lessons = this.db.lessons.filter((l) => l.groupId !== id);
    this.db.schedule = this.db.schedule.filter((s) => s.groupId !== id);
    this.db.students = this.db.students.filter((s) => s.groupId !== id);
    this.db.groups = this.db.groups.filter((g) => g.id !== id);
    this.touch();
  }
  addStudent(groupId: ID, name: string): Student {
    const st: Student = { id: this.nextId(), groupId, name: name.trim() };
    this.db.students.push(st);
    this.touch();
    return st;
  }
  removeStudent(id: ID) {
    this.db.students = this.db.students.filter((s) => s.id !== id);
    this.db.grades = this.db.grades.filter((g) => g.studentId !== id);
    this.touch();
  }
  addSubject(name: string): Subject {
    const existing = this.db.subjects.find(
      (s) => s.name.toLowerCase() === name.trim().toLowerCase(),
    );
    if (existing) return existing;
    const s: Subject = { id: this.nextId(), name: name.trim() };
    this.db.subjects.push(s);
    this.touch();
    return s;
  }
  assignSubject(groupId: ID, subjectId: ID) {
    const g = this.group(groupId);
    if (g && !g.subjectIds.includes(subjectId)) {
      g.subjectIds.push(subjectId);
      this.touch();
    }
  }
  unassignSubject(groupId: ID, subjectId: ID) {
    const g = this.group(groupId);
    if (!g) return;
    g.subjectIds = g.subjectIds.filter((x) => x !== subjectId);
    this.touch();
  }
  addScheduleItem(item: Omit<ScheduleItem, "id">): ScheduleItem {
    const it: ScheduleItem = { ...item, id: this.nextId() };
    this.db.schedule.push(it);
    const g = this.group(item.groupId);
    if (g && !g.subjectIds.includes(item.subjectId)) g.subjectIds.push(item.subjectId);
    this.touch();
    return it;
  }
  removeScheduleItem(id: ID) {
    this.db.schedule = this.db.schedule.filter((s) => s.id !== id);
    this.touch();
  }
  /** Создание занятия с датой (прошлое + сегодня). Дубли разрешены. */
  createLesson(groupId: ID, subjectId: ID, date: string): Lesson {
    const fromSchedule = this.scheduleItemFor({ groupId, subjectId }, date);
    const lesson: Lesson = {
      id: this.nextId(), groupId, subjectId, date,
      status: "scheduled",
      time: fromSchedule?.time ?? "—",
      room: fromSchedule?.room ?? "—",
    };
    this.db.lessons.push(lesson);
    for (const st of this.studentsOf(groupId)) {
      this.db.grades.push({ lessonId: lesson.id, studentId: st.id, value: null, present: true });
    }
    this.touch();
    return lesson;
  }
  setLessonStatus(id: ID, status: LessonStatus) {
    const l = this.lesson(id);
    if (l) { l.status = status; this.touch(); }
  }
  removeLesson(id: ID) {
    this.db.lessons = this.db.lessons.filter((l) => l.id !== id);
    this.db.grades = this.db.grades.filter((g) => g.lessonId !== id);
    this.touch();
  }
  /** Досоздать записи оценок для студентов, добавленных после создания занятия. */
  ensureGrades(lessonId: ID) {
    const lesson = this.lesson(lessonId);
    if (!lesson) return;
    let changed = false;
    for (const st of this.studentsOf(lesson.groupId)) {
      if (!this.gradeOf(lessonId, st.id)) {
        this.db.grades.push({ lessonId, studentId: st.id, value: null, present: true });
        changed = true;
      }
    }
    if (changed) this.touch();
  }
  cycleGrade(lessonId: ID, studentId: ID, dir: 1 | -1) {
    const rec = this.gradeOf(lessonId, studentId);
    if (!rec || !rec.present) return;
    rec.value = dir === 1 ? nextGrade(rec.value) : prevGrade(rec.value);
    this.touch();
  }
  togglePresent(lessonId: ID, studentId: ID) {
    const rec = this.gradeOf(lessonId, studentId);
    if (!rec) return;
    rec.present = !rec.present;
    this.touch();
  }
  updateSettings(patch: Partial<Settings>) {
    Object.assign(this.db.settings, patch);
    if (patch.theme) {
      try {
        localStorage.setItem("th-theme", patch.theme);
        document.documentElement.setAttribute("data-theme", patch.theme);
        const meta = document.querySelector('meta[name="theme-color"]');
        if (meta) meta.setAttribute("content", patch.theme === "dark" ? "#0B0F14" : "#ECEEF1");
      } catch (_) {}
    }
    this.touch();
  }
  regenerateTeacherCode() {
    this.db.settings.teacherCode = makeCode(Math.random);
    this.touch();
  }
  exportBackup(): string {
    return JSON.stringify(this.db, null, 2);
  }
  importBackup(json: string): boolean {
    try {
      const parsed = JSON.parse(json) as DB;
      if (!parsed.groups || !parsed.students || !parsed.lessons || !parsed.settings) return false;
      this.db = parsed;
      this.persist();
      this.touch();
      return true;
    } catch (_) {
      return false;
    }
  }
  resetDemo() {
    this.db = seed();
    this.persist();
    this.touch();
  }
}

export const store = new Store();

/** Реактивный доступ к БД (перерендер при любой мутации). */
export function useDB(): DB {
  useSyncExternalStore(store.subscribe, store.getVersion);
  return store.db;
}

/** Номер версии БД — использовать в зависимостях useMemo,
    т.к. данные мутируются in-place и identity БД не меняется. */
export function useVersion(): number {
  return useSyncExternalStore(store.subscribe, store.getVersion);
}

export { store as default };

/* Утилита для подсчёта среднего по занятию */
export function lessonAvg(recs: GradeRec[]): number | null {
  const vals = recs.filter((r) => r.present && r.value !== null).map((r) => r.value as number);
  if (!vals.length) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}
