export type Group = {
  id: number;
  name: string;
  course: string;
  count: number;
  subjects: number;
  color: string;
};
export type Lesson = {
  id: number;
  title: string;
  groupId: number;
  time: string;
  end: string;
  room: string;
  date: string;
  status: "done" | "current" | "planned" | "cancelled";
  type: string;
};
export type Student = { id: number; name: string; groupId: number };
export type Store = {
  groups: Group[];
  lessons: Lesson[];
  students: Student[];
  grades: Record<string, string>;
  teacher: string;
};
export const TODAY = "2026-09-14";
export const initialData: Store = {
  teacher: "Александр Сергеевич",
  groups: [
    {
      id: 1,
      name: "ИС-21",
      course: "Информационные системы",
      count: 25,
      subjects: 3,
      color: "green",
    },
    {
      id: 2,
      name: "ИС-22",
      course: "Информационные системы",
      count: 24,
      subjects: 3,
      color: "purple",
    },
    {
      id: 3,
      name: "ПР-31",
      course: "Программирование",
      count: 23,
      subjects: 2,
      color: "orange",
    },
    {
      id: 4,
      name: "ИС-11",
      course: "Информационные системы",
      count: 26,
      subjects: 2,
      color: "blue",
    },
    {
      id: 5,
      name: "ПР-21",
      course: "Программирование",
      count: 22,
      subjects: 3,
      color: "purple",
    },
    {
      id: 6,
      name: "ИС-12",
      course: "Информационные системы",
      count: 24,
      subjects: 2,
      color: "green",
    },
  ],
  lessons: [
    {
      id: 1,
      title: "Основы программирования",
      groupId: 1,
      time: "08:30",
      end: "10:00",
      room: "204",
      date: TODAY,
      status: "done",
      type: "Практика",
    },
    {
      id: 2,
      title: "Базы данных",
      groupId: 2,
      time: "10:10",
      end: "11:40",
      room: "208",
      date: TODAY,
      status: "current",
      type: "Практика",
    },
    {
      id: 3,
      title: "Разработка веб-приложений",
      groupId: 3,
      time: "12:10",
      end: "13:40",
      room: "204",
      date: TODAY,
      status: "planned",
      type: "Лекция",
    },
    {
      id: 4,
      title: "Основы программирования",
      groupId: 4,
      time: "13:50",
      end: "15:20",
      room: "206",
      date: TODAY,
      status: "planned",
      type: "Практика",
    },
    {
      id: 5,
      title: "Базы данных",
      groupId: 1,
      time: "08:30",
      end: "10:00",
      room: "208",
      date: "2026-09-15",
      status: "planned",
      type: "Лекция",
    },
    {
      id: 6,
      title: "Основы программирования",
      groupId: 3,
      time: "10:10",
      end: "11:40",
      room: "204",
      date: "2026-09-16",
      status: "planned",
      type: "Практика",
    },
  ],
  students: [],
  grades: {},
};
const names = [
  "Александров Артём",
  "Андреева Мария",
  "Белов Максим",
  "Васильева Анна",
  "Волков Дмитрий",
  "Григорьева София",
  "Данилов Иван",
  "Егорова Полина",
  "Жуков Михаил",
  "Зайцева Алиса",
  "Иванов Александр",
  "Козлова Дарья",
  "Кузнецов Никита",
  "Лебедева Виктория",
  "Морозов Даниил",
  "Николаева Ева",
  "Орлов Кирилл",
  "Павлова Анастасия",
  "Петров Матвей",
  "Романова Ксения",
  "Семёнов Илья",
  "Смирнова Валерия",
  "Соколов Андрей",
  "Фёдорова Елизавета",
  "Попов Роман",
  "Макарова Милана",
];
initialData.groups.forEach((g) =>
  names
    .slice(0, g.count)
    .forEach((name, i) =>
      initialData.students.push({ id: g.id * 100 + i, name, groupId: g.id }),
    ),
);
initialData.students
  .filter((s) => s.groupId === 1)
  .forEach(
    (s, i) =>
      (initialData.grades[`1-${s.id}`] =
        i % 13 === 0 ? "Н" : i % 3 === 0 ? "4" : "5"),
  );
export function loadStore(): Store {
  try {
    const stored = localStorage.getItem("teachhelper-v2");
    if (stored) {
      const data = JSON.parse(stored);
      if (
        Array.isArray(data.groups) &&
        Array.isArray(data.lessons) &&
        Array.isArray(data.students) &&
        data.grades
      )
        return data;
    }
  } catch {}
  return initialData;
}
export function formatDate(date: string, long = false) {
  const d = new Date(date + "T12:00:00");
  return d.toLocaleDateString(
    "ru-RU",
    long
      ? { day: "numeric", month: "long" }
      : { day: "2-digit", month: "2-digit" },
  );
}
export const subjects = [
  { name: "Основы программирования", hours: 72, done: 24, color: "green" },
  { name: "Базы данных", hours: 64, done: 18, color: "purple" },
  { name: "Разработка веб-приложений", hours: 96, done: 32, color: "orange" },
  { name: "Информационные технологии", hours: 48, done: 12, color: "blue" },
  { name: "Компьютерные сети", hours: 64, done: 16, color: "purple" },
];
