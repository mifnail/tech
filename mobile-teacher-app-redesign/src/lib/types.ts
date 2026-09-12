/* Доменные модели журнала (зеркалируют схему SQLite-бэкенда). */

export type ID = number;

export interface Group {
  id: ID;
  name: string;
  curatorCode: string;
  subjectIds: ID[];
}

export interface Student {
  id: ID;
  groupId: ID;
  name: string;
  tg?: boolean; // привязан Telegram-бот
  max?: boolean; // привязан MAX-бот
}

export interface Subject {
  id: ID;
  name: string;
}

/** parity: 0 — каждую неделю, 1 — чётная, 2 — нечётная */
export interface ScheduleItem {
  id: ID;
  groupId: ID;
  subjectId: ID;
  weekday: number; // 1..7, понедельник = 1
  parity: 0 | 1 | 2;
  time: string;
  room: string;
  lessonNumber: number; // порядок пары в дне (1, 2, ...)
}

export type LessonStatus = "scheduled" | "held" | "cancelled";

export interface Lesson {
  id: ID;
  groupId: ID;
  subjectId: ID;
  date: string; // YYYY-MM-DD
  status: LessonStatus;
  time: string;
  room: string;
  lessonNumber: number; // номер пары (1..5)
}

export interface GradeRec {
  lessonId: ID;
  studentId: ID;
  value: number | null; // 5/4/3/2/0 или null («—»)
  present: boolean;
}

export interface Settings {
  theme: "light" | "dark";
  teacherName: string;
  tgToken: string;
  maxToken: string;
  teacherCode: string;
}

export interface DB {
  groups: Group[];
  students: Student[];
  subjects: Subject[];
  schedule: ScheduleItem[];
  lessons: Lesson[];
  grades: GradeRec[];
  settings: Settings;
  seq: number;
}
