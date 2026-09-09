import React, { createContext, useContext, useEffect, useMemo, useReducer, useState } from 'react';

/* ================= types ================= */

export type Grade = '5' | '4' | '3' | '2' | '0' | 'absent' | null;
export type LessonStatus = 'held' | 'scheduled' | 'cancelled';
export type WeekType = 'every' | 'odd' | 'even';

export interface Group { id: number; name: string; curatorCode: string; curatorBound: boolean; }
export interface Student { id: number; groupId: number; last: string; first: string; middle: string; tg?: boolean; max?: boolean; }
export interface Subject { id: number; groupId: number; name: string; short: string; totalHours: number; hue: string; }
export interface ScheduleEntry { id: number; subjectId: number; day: number; num: number; week: WeekType; }
export interface Lesson { id: number; subjectId: number; date: string; num: number; status: LessonStatus; }
export interface Toast {
  id: number; title: string; sub?: string; tone?: 'ok' | 'info' | 'warn' | 'push';
  action?: { label: string; fn: () => void };
}

export interface State {
  groups: Group[];
  students: Student[];
  subjects: Subject[];
  schedule: ScheduleEntry[];
  lessons: Lesson[];
  grades: Record<number, Record<number, Grade>>;
  toasts: Toast[];
}

/* ================= grade meta =================
   В оригинале шкала цветов инвертирована (5 — красный, 2 — slate).
   Здесь шкала исправлена на тепловую: 5 → мята … 2 → роза. */

export const GRADE_CYCLE: Exclude<Grade, null>[] = ['0', '5', '4', '3', '2', 'absent'];

export const GRADE_META: Record<string, { c: string; glow?: string; label: string; txt: string; numeric?: number }> = {
  '5':      { c: '#3ddc97', label: '5', txt: 'отлично', numeric: 5 },
  '4':      { c: '#a6e04a', label: '4', txt: 'хорошо', numeric: 4 },
  '3':      { c: '#f5b93f', label: '3', txt: 'удовл.', numeric: 3 },
  '2':      { c: '#f2627a', label: '2', txt: 'неуд.', numeric: 2 },
  '0':      { c: '#8b96ab', label: '·', txt: 'был(а)' },
  'absent': { c: '#f2627a', label: 'н', txt: 'нет' },
};

export const numOf = (g: Grade): number | null =>
  g && GRADE_META[g]?.numeric != null ? GRADE_META[g].numeric! : null;

/* ================= date utils ================= */

export const DAY_SHORT = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];
export const DAY_FULL = ['воскресенье', 'понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота'];
export const MONTH_SHORT = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
export const MONTH_FULL = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
export const LESSON_TIME: Record<number, string> = { 1: '08:30–10:00', 2: '10:15–11:45', 3: '12:10–13:40', 4: '14:00–15:30' };

export const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
export const todayIso = () => iso(new Date());
export const addDays = (d: Date, n: number) => { const c = new Date(d); c.setDate(c.getDate() + n); return c; };
export const fromIso = (s: string) => { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d); };
export const fmtDate = (s: string) => { const d = fromIso(s); return `${d.getDate()} ${MONTH_SHORT[d.getMonth()]}`; };
export const fmtDateFull = (s: string) => { const d = fromIso(s); return `${d.getDate()} ${MONTH_FULL[d.getMonth()]}`; };
export const weekParity = (s: string): 'odd' | 'even' => {
  const d = fromIso(s);
  const start = new Date(d.getFullYear(), 0, 1);
  const w = Math.ceil((((d.getTime() - start.getTime()) / 86400000) + start.getDay() + 1) / 7);
  return w % 2 === 0 ? 'even' : 'odd';
};
export const matchesWeek = (wt: WeekType, dateIso: string) =>
  wt === 'every' || wt === weekParity(dateIso);

/* ================= seed data ================= */

const groups: Group[] = [
  { id: 1, name: 'ИС-31', curatorCode: 'ИС31-7F2K', curatorBound: true },
  { id: 2, name: 'КС-22', curatorCode: 'КС22-9A4Q', curatorBound: false },
];

const S = (id: number, groupId: number, last: string, first: string, middle: string, tg = false, max = false): Student =>
  ({ id, groupId, last, first, middle, tg, max });

const students: Student[] = [
  S(1, 1, 'Иванов', 'Артём', 'Игоревич', true, true),
  S(2, 1, 'Петрова', 'Дарья', 'Олеговна', false, true),
  S(3, 1, 'Сидоров', 'Максим', 'Андреевич', true, false),
  S(4, 1, 'Козлова', 'Анна', 'Сергеевна', false, true),
  S(5, 1, 'Морозов', 'Илья', 'Дмитриевич'),
  S(6, 1, 'Волкова', 'Ева', 'Артёмовна', true, true),
  S(7, 1, 'Соколов', 'Тимур', 'Романович', false, true),
  S(8, 1, 'Лебедева', 'Мия', 'Павловна'),
  S(9, 1, 'Новиков', 'Роман', 'Егорович', true, false),
  S(10, 1, 'Орлова', 'Софья', 'Максимовна', false, true),
  S(11, 2, 'Захаров', 'Даниил', 'Ильич', true, true),
  S(12, 2, 'Романова', 'Варвара', 'Олеговна', false, true),
  S(13, 2, 'Гусев', 'Марк', 'Тимофеевич', true, false),
  S(14, 2, 'Титова', 'Алиса', 'Денисовна'),
  S(15, 2, 'Беляев', 'Егор', 'Миронович', false, true),
  S(16, 2, 'Фролова', 'Ульяна', 'Львовна', true, true),
];

const subjects: Subject[] = [
  { id: 1, groupId: 1, name: 'Базы данных', short: 'БД', totalHours: 64, hue: '#7c8cff' },
  { id: 2, groupId: 1, name: 'Проектирование интерфейсов', short: 'UX', totalHours: 48, hue: '#a78bfa' },
  { id: 3, groupId: 2, name: 'Сетевые технологии', short: 'Сети', totalHours: 56, hue: '#5cd6f0' },
];

const schedule: ScheduleEntry[] = [
  { id: 11, subjectId: 1, day: 1, num: 1, week: 'every' },
  { id: 12, subjectId: 1, day: 4, num: 2, week: 'every' },
  { id: 13, subjectId: 2, day: 2, num: 1, week: 'every' },
  { id: 14, subjectId: 2, day: 5, num: 3, week: 'even' },
  { id: 15, subjectId: 3, day: 3, num: 2, week: 'every' },
  { id: 16, subjectId: 3, day: 6, num: 1, week: 'odd' },
];

/* детерминированный псевдо-рандом, чтобы демо было стабильным */
const hashN = (n: number) => {
  let x = n * 2654435761 % 4294967296;
  x = (x ^ (x >> 15)) * 2246822519 % 4294967296;
  x = x ^ (x >> 13);
  return (x >>> 0) / 4294967296;
};

const pickGrade = (r: number): Grade => {
  if (r < 0.30) return '5';
  if (r < 0.62) return '4';
  if (r < 0.80) return '3';
  if (r < 0.87) return '2';
  if (r < 0.94) return 'absent';
  return '0';
};

function buildSeed(): { lessons: Lesson[]; grades: Record<number, Record<number, Grade>> } {
  const lessons: Lesson[] = [];
  const grades: Record<number, Record<number, Grade>> = {};
  const today = new Date();
  let lid = 100;

  for (const subj of subjects) {
    const entries = schedule.filter(e => e.subjectId === subj.id);
    const past: { d: Date; num: number }[] = [];
    const todayEntries: ScheduleEntry[] = [];
    for (let back = 1; back <= 30 && past.length < 6; back++) {
      const d = addDays(today, -back);
      const dIso = iso(d);
      const dow = d.getDay();
      for (const e of entries) {
        if (e.day === dow && matchesWeek(e.week, dIso)) past.push({ d, num: e.num });
      }
    }
    past.reverse().forEach((p, i) => {
      const cancelled = i === 1 && subj.id === 2;
      lessons.push({ id: lid, subjectId: subj.id, date: iso(p.d), num: p.num, status: cancelled ? 'cancelled' : 'held' });
      if (!cancelled) {
        const gg: Record<number, Grade> = {};
        for (const st of students.filter(s => s.groupId === subj.groupId)) {
          const r = hashN(lid * 31 + st.id * 7);
          if (r < 0.9) gg[st.id] = pickGrade(hashN(lid * 131 + st.id * 17));
        }
        grades[lid] = gg;
      }
      lid++;
    });

    /* сегодняшние занятия — частично заполненные, чтобы протыкать */
    const dow = today.getDay();
    const tIso = iso(today);
    for (const e of entries) {
      if (e.day === dow && matchesWeek(e.week, tIso)) todayEntries.push(e);
    }
    for (const e of todayEntries) {
      lessons.push({ id: lid, subjectId: subj.id, date: tIso, num: e.num, status: 'held' });
      const gg: Record<number, Grade> = {};
      const sts = students.filter(s => s.groupId === subj.groupId);
      sts.slice(0, Math.ceil(sts.length * 0.35)).forEach(st => {
        gg[st.id] = pickGrade(hashN(lid * 733 + st.id * 29 + 5));
      });
      grades[lid] = gg;
      lid++;
    }
  }
  return { lessons, grades };
}

const seed = buildSeed();

const initialState: State = {
  groups, students, subjects, schedule,
  lessons: seed.lessons,
  grades: seed.grades,
  toasts: [],
};

/* ================= selectors ================= */

export const groupOf = (st: State, subjectId: number) => {
  const subj = st.subjects.find(s => s.id === subjectId);
  return st.groups.find(g => g.id === subj?.groupId);
};
export const studentsOfSubject = (st: State, subjectId: number) => {
  const subj = st.subjects.find(s => s.id === subjectId);
  return st.students.filter(s => s.groupId === subj?.groupId);
};
export const lessonsOfSubject = (st: State, subjectId: number) =>
  st.lessons.filter(l => l.subjectId === subjectId).sort((a, b) => a.date.localeCompare(b.date));

export const avgOfGrades = (vals: Grade[]): number | null => {
  const nums = vals.map(numOf).filter((n): n is number => n != null);
  if (!nums.length) return null;
  return nums.reduce((a, b) => a + b, 0) / nums.length;
};
export const fmtAvg = (a: number | null) => (a == null ? '—' : (Math.round(a * 10) / 10).toString().replace('.', ','));

export const subjectStats = (st: State, subjectId: number) => {
  const subj = st.subjects.find(s => s.id === subjectId)!;
  const held = st.lessons.filter(l => l.subjectId === subjectId && l.status === 'held').length;
  const vals: Grade[] = [];
  for (const l of st.lessons.filter(l => l.subjectId === subjectId && l.status === 'held')) {
    vals.push(...Object.values(st.grades[l.id] || {}));
  }
  return {
    held,
    remaining: Math.max(0, subj.totalHours / 2 - held),
    avg: avgOfGrades(vals),
    students: studentsOfSubject(st, subjectId).length,
  };
};

export const studentStatsInSubject = (st: State, subjectId: number, studentId: number) => {
  const held = st.lessons.filter(l => l.subjectId === subjectId && l.status === 'held');
  const vals: Grade[] = [];
  let abs = 0, marks = 0;
  for (const l of held) {
    const g = st.grades[l.id]?.[studentId];
    if (g) { marks++; vals.push(g); if (g === 'absent') abs++; }
  }
  return { avg: avgOfGrades(vals), abs, marks, total: held.length };
};

/* ================= store ================= */

type Action =
  | { type: 'grade'; lessonId: number; studentId: number; grade: Grade }
  | { type: 'addLesson'; lesson: Lesson }
  | { type: 'setStatus'; lessonId: number; status: LessonStatus }
  | { type: 'removeLesson'; lessonId: number }
  | { type: 'toast'; toast: Toast }
  | { type: 'dismissToast'; id: number };

function reducer(st: State, a: Action): State {
  switch (a.type) {
    case 'grade': {
      const lg = { ...(st.grades[a.lessonId] || {}) };
      if (a.grade == null) delete lg[a.studentId]; else lg[a.studentId] = a.grade;
      return { ...st, grades: { ...st.grades, [a.lessonId]: lg } };
    }
    case 'addLesson': return { ...st, lessons: [...st.lessons, a.lesson] };
    case 'setStatus':
      return { ...st, lessons: st.lessons.map(l => (l.id === a.lessonId ? { ...l, status: a.status } : l)) };
    case 'removeLesson': {
      const grades = { ...st.grades };
      delete grades[a.lessonId];
      return { ...st, lessons: st.lessons.filter(l => l.id !== a.lessonId), grades };
    }
    case 'toast': return { ...st, toasts: [...st.toasts.slice(-2), a.toast] };
    case 'dismissToast': return { ...st, toasts: st.toasts.filter(t => t.id !== a.id) };
    default: return st;
  }
}

interface Ctx {
  st: State;
  cycleGrade: (lessonId: number, studentId: number, dir: 1 | -1) => void;
  setGrade: (lessonId: number, studentId: number, g: Grade) => void;
  startLesson: (subjectId: number, date: string, num: number) => number;
  cancelLesson: (id: number) => void;
  restoreLesson: (id: number) => void;
  removeLesson: (id: number) => void;
  toast: (t: Omit<Toast, 'id'>) => void;
  dismissToast: (id: number) => void;
}

const StoreCtx = createContext<Ctx>(null as unknown as Ctx);
export const useStore = () => useContext(StoreCtx);

let toastSeq = 1;

export function StoreProvider({ children }: { children: React.ReactNode }) {
  const [st, dispatch] = useReducer(reducer, initialState);

  const api = useMemo<Ctx>(() => ({
    st,
    toast: (t) => {
      const id = toastSeq++;
      dispatch({ type: 'toast', toast: { ...t, id } });
      window.setTimeout(() => dispatch({ type: 'dismissToast', id }), t.action ? 5200 : 3400);
    },
    dismissToast: (id) => dispatch({ type: 'dismissToast', id }),
    setGrade: (lessonId, studentId, g) => dispatch({ type: 'grade', lessonId, studentId, grade: g }),
    cycleGrade: (lessonId, studentId, dir) => {
      // направление от места тапа: правая половина — вперёд, левая — назад
      const cur = st.grades[lessonId]?.[studentId] ?? null;
      const cyc: (Grade | '')[] = ['', ...GRADE_CYCLE];
      const idx = cyc.indexOf(cur ?? '');
      const n = cyc.length;
      const next = cyc[(((idx + dir) % n) + n) % n] as Grade | '';
      const g: Grade = next === '' ? null : (next as Grade);
      dispatch({ type: 'grade', lessonId, studentId, grade: g });

      const stt = st.students.find(s => s.id === studentId);
      const name = stt ? `${stt.last} ${stt.first[0]}.` : '';
      if (g && g !== cur) {
        const revert = () => dispatch({ type: 'grade', lessonId, studentId, grade: cur ?? null });
        const meta = GRADE_META[g];
        api.toast({
          title: `${name} — ${meta.txt}`,
          sub: `оценка «${meta.label === '·' ? 'присутствие' : meta.label}»`,
          tone: 'ok',
          action: { label: 'Отменить', fn: revert },
        });
        /* симуляция дебаунс-пуша MAX-бота (в проде — 10 с, редми maxbot.py) */
        if (stt?.max) {
          window.setTimeout(() => {
            api.toast({ title: 'MAX → пуш отправлен', sub: `${name}: новая оценка (дебаунс 10 с)`, tone: 'push' });
          }, 1500);
        }
      }
    },
    startLesson: (subjectId, date, num) => {
      const id = Date.now() % 100000000;
      dispatch({ type: 'addLesson', lesson: { id, subjectId, date, num, status: 'held' } });
      return id;
    },
    cancelLesson: (id) => dispatch({ type: 'setStatus', lessonId: id, status: 'cancelled' }),
    restoreLesson: (id) => dispatch({ type: 'setStatus', lessonId: id, status: 'held' }),
    removeLesson: (id) => dispatch({ type: 'removeLesson', lessonId: id }),
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [st]);

  return <StoreCtx.Provider value={api}>{children}</StoreCtx.Provider>;
}

/* ================= hash router ================= */

export const nav = (to: string) => { window.location.hash = to; };

export function useHashRoute(): string {
  const [h, setH] = useState(() => window.location.hash || '#home');
  useEffect(() => {
    const f = () => {
      setH(window.location.hash || '#home');
      const sc = document.getElementById('screen');
      if (sc) sc.scrollTo({ top: 0 });
    };
    window.addEventListener('hashchange', f);
    return () => window.removeEventListener('hashchange', f);
  }, []);
  return h;
}
