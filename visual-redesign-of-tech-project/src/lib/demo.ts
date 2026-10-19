import { randomUUID } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

type Group = { id: number; name: string };
type Student = { id: number; group_id: number; first_name: string; last_name: string; middle_name: string };
type Subject = { id: number; name: string; group_id: number; total_hours: number; held_lessons: number };
type Lesson = { id: number; subject_id: number; actual_subject_id: number; date: string; status: string; lesson_number: number | null };
type Entry = { id: number; subject_id: number; day_of_week: number; lesson_number: number; week_type: string };
export type Demo = { groups: Group[]; students: Student[]; subjects: Subject[]; lessons: Lesson[]; schedule: Entry[]; grades: Record<string, Record<string, string>> };
export const todayISO = () => new Date().toLocaleDateString('en-CA', { timeZone: 'Europe/Moscow' });
const root = path.join(tmpdir(), 'teachhelper-visual-preview');
export function seed(): Demo {
  const groups = ['ИС-21', 'ИС-22', 'ПИ-31', 'ПИ-32', 'ИС-11', 'ПИ-21'].map((name, i) => ({ id: i + 1, name }));
  const surnames = ['Александров', 'Белов', 'Васильева', 'Волков', 'Григорьева', 'Дмитриев', 'Егорова', 'Жуков', 'Зайцева', 'Иванов', 'Козлов', 'Кузнецова', 'Лебедев', 'Морозова', 'Николаев', 'Орлова', 'Павлов', 'Петрова', 'Романов', 'Семёнова', 'Смирнов', 'Соколова', 'Фёдоров', 'Яковлева'];
  const students = groups.flatMap(g => surnames.map((last_name, i) => ({ id: (g.id - 1) * 24 + i + 1, group_id: g.id, first_name: last_name.endsWith('а') ? ['Анна', 'Мария', 'Елена'][i % 3] : ['Александр', 'Михаил', 'Даниил'][i % 3], last_name, middle_name: '' })));
  const subjects = [
    { id: 1, name: 'Основы программирования', group_id: 1, total_hours: 72, held_lessons: 24 },
    { id: 2, name: 'Базы данных', group_id: 3, total_hours: 64, held_lessons: 28 },
    { id: 3, name: 'Веб-разработка', group_id: 2, total_hours: 96, held_lessons: 32 },
    { id: 4, name: 'Информационные технологии', group_id: 4, total_hours: 72, held_lessons: 18 },
    { id: 5, name: 'Компьютерные сети', group_id: 5, total_hours: 64, held_lessons: 16 },
    { id: 6, name: 'Операционные системы', group_id: 6, total_hours: 48, held_lessons: 12 },
  ];
  const day = new Date(todayISO() + 'T12:00:00').getDay() || 7;
  const schedule = [1, 2, 3, 4].map((subject_id, i) => ({ id: i + 1, subject_id, day_of_week: day, lesson_number: i + 1, week_type: 'all' }));
  for (let d = 1; d <= 5; d++) if (d !== day) schedule.push({ id: schedule.length + 1, subject_id: d % 6 + 1, day_of_week: d, lesson_number: 2, week_type: 'all' });
  const lessons: Lesson[] = [{ id: 1, subject_id: 1, actual_subject_id: 1, date: todayISO(), status: 'held', lesson_number: 1 }];
  for (const subject of subjects) {
    const count = subject.held_lessons - (subject.id === 1 ? 1 : 0);
    for (let i = 0; i < count; i++) {
      const date = new Date(todayISO() + 'T12:00:00Z'); date.setUTCDate(date.getUTCDate() - (count - i));
      lessons.push({ id: lessons.length + 1, subject_id: subject.id, actual_subject_id: subject.id, date: date.toISOString().slice(0, 10), status: 'held', lesson_number: subject.id % 4 + 1 });
    }
  }
  const grades = Object.fromEntries(lessons.map(l => [l.id, Object.fromEntries(students.filter(s => s.group_id === subjects.find(subject => subject.id === l.subject_id)?.group_id).map((s, i) => [s.id, ['5', '4', '5', '0', '3'][(i + l.id - 1) % 5]]))]));
  return { groups, students, subjects, schedule, lessons, grades };
}
export async function getDemo(cookie?: string) {
  const id = cookie && /^[a-f0-9-]{36}$/.test(cookie) ? cookie : randomUUID();
  await mkdir(root, { recursive: true });
  let data: Demo;
  try { data = JSON.parse(await readFile(path.join(root, id + '.json'), 'utf8')); }
  catch { data = seed(); await saveDemo(id, data); }
  return { id, data };
}
export async function saveDemo(id: string, data: Demo) { await writeFile(path.join(root, id + '.json'), JSON.stringify(data)); }
export function demoRequest(data: Demo, method: string, pathname: string, query: URLSearchParams, body: Record<string, unknown>) {
  const p = pathname.split('/').filter(Boolean), resource = p[0], id = Number(p[1]), action = p[2];
  const nextId = (items: { id: number }[]) => Math.max(0, ...items.map(v => v.id)) + 1;
  const subjects = () => data.subjects.map(s => ({ ...s, group_name: data.groups.find(g => g.id === s.group_id)?.name || '', remaining: s.total_hours - s.held_lessons }));
  const lessons = () => data.lessons.map(l => { const s = data.subjects.find(s => s.id === (l.actual_subject_id || l.subject_id)); return { ...l, actual_subject_name: s?.name || '', planned_subject: s?.name || '', group_name: data.groups.find(g => g.id === s?.group_id)?.name || '', group_id: s?.group_id }; });
  const schedule = () => data.schedule.map(e => { const s = subjects().find(s => s.id === e.subject_id); return { ...e, subject_name: s?.name || '', group_name: s?.group_name || '' }; });
  const groupStudents = (groupId: number | undefined) => data.students.filter(s => s.group_id === groupId);
  if (resource === 'version') return { ver: 'visual-preview' };
  if (resource === 'update') return { update_available: false };
  if (resource === 'settings') {
    if (method !== 'GET') throw new Error('Подключите исходный Flask-сервер для настройки ботов. Токены в деморежиме не сохраняются.');
    return { has_token: false, enabled: false, teacher_bound: false };
  }
  if (resource === 'bot' || resource === 'maxbot') return [];
  if (resource === 'backup') throw new Error('Рабочая база не подключена. Резервное копирование доступно в исходном приложении.');
  if (resource === 'groups') {
    if (action === 'curator') return { code: '', bound: false };
    if (method === 'GET') return data.groups;
    if (method === 'POST') { const g = { id: nextId(data.groups), name: String(body.name || '').trim() }; if (!g.name) throw new Error('Введите название группы'); data.groups.push(g); return g; }
    if (method === 'PATCH') { const g = data.groups.find(g => g.id === id); if (g) g.name = String(body.name); }
    if (method === 'DELETE') { const ids = data.subjects.filter(s => s.group_id === id).map(s => s.id); data.groups = data.groups.filter(g => g.id !== id); data.students = data.students.filter(s => s.group_id !== id); data.subjects = data.subjects.filter(s => s.group_id !== id); data.schedule = data.schedule.filter(s => !ids.includes(s.subject_id)); data.lessons = data.lessons.filter(l => !ids.includes(l.subject_id)); }
    return { ok: true };
  }
  if (resource === 'students') {
    if (method === 'GET') return query.has('group_id') ? groupStudents(Number(query.get('group_id'))) : data.students;
    if (method === 'POST' && p[1] === 'bulk') { const entries = Array.isArray(body.students) ? body.students as Record<string, unknown>[] : []; for (const entry of entries) { data.students.push({ id: nextId(data.students), group_id: Number(body.group_id), last_name: String(entry.last_name || ''), first_name: String(entry.first_name || ''), middle_name: String(entry.middle_name || '') }); } return { count: entries.length }; }
    if (method === 'PATCH') { const s = data.students.find(s => s.id === id); if (s) { s.last_name = String(body.last_name || ''); s.first_name = String(body.first_name || ''); s.middle_name = String(body.middle_name || ''); } }
    if (method === 'DELETE') data.students = data.students.filter(s => s.id !== id);
    return { ok: true };
  }
  if (resource === 'subjects') {
    if (action === 'gradebook') { const s = data.subjects.find(s => s.id === id), ls = lessons().filter(l => l.subject_id === id), students = groupStudents(s?.group_id); return { summary: { ...subjects().find(s => s.id === id), total_students: students.length }, lessons: ls, students, grades: Object.fromEntries(students.map(s => [s.id, Object.fromEntries(ls.map(l => [l.id, data.grades[l.id]?.[s.id] || '']))])) }; }
    if (action === 'lessons') return lessons().filter(l => l.subject_id === id);
    if (action === 'substitution-list') return subjects();
    if (method === 'GET') return subjects().filter(s => !query.has('group_id') || s.group_id === Number(query.get('group_id')));
    if (method === 'POST') { const s = { id: nextId(data.subjects), name: String(body.name), total_hours: Number(body.total_hours), group_id: Number(body.group_id), held_lessons: 0 }; if (!s.name || s.total_hours < 1 || !data.groups.some(g => g.id === s.group_id)) throw new Error('Проверьте название, часы и группу'); data.subjects.push(s); return s; }
    if (method === 'PATCH') { const s = data.subjects.find(s => s.id === id); if (s) { s.name = String(body.name); s.total_hours = Number(body.total_hours); } }
    if (method === 'DELETE') { data.subjects = data.subjects.filter(s => s.id !== id); data.schedule = data.schedule.filter(s => s.subject_id !== id); data.lessons = data.lessons.filter(l => l.subject_id !== id); }
    return { ok: true };
  }
  if (resource === 'schedule') {
    if (p[1] === 'today') { const date = todayISO(), day = new Date(date + 'T12:00:00').getDay() || 7; return { date, day_of_week: day, schedule: schedule().filter(e => e.day_of_week === day), lessons: lessons().filter(l => l.date === date) }; }
    if (method === 'GET') return schedule();
    if (method === 'POST') { const e = { id: nextId(data.schedule), subject_id: Number(body.subject_id), day_of_week: Number(body.day_of_week), lesson_number: Number(body.lesson_number), week_type: String(body.week_type || 'all') }; data.schedule.push(e); return e; }
    if (method === 'PATCH') { const e = data.schedule.find(e => e.id === id); if (e) Object.assign(e, { subject_id: Number(body.subject_id), day_of_week: Number(body.day_of_week), lesson_number: Number(body.lesson_number), week_type: String(body.week_type || 'all') }); }
    if (method === 'DELETE') data.schedule = data.schedule.filter(e => e.id !== id);
    return { ok: true };
  }
  if (resource === 'lessons') {
    if (p[1] === 'date') return lessons().filter(l => l.date === action);
    const lesson = lessons().find(l => l.id === id);
    if (action === 'adjacent') { const ls = data.lessons.filter(l => l.subject_id === lesson?.subject_id), index = ls.findIndex(l => l.id === id); return { prev_id: ls[index - 1]?.id || null, next_id: ls[index + 1]?.id || null }; }
    if (action === 'attendance') {
      if (method === 'GET') return { lesson, students: groupStudents(lesson?.group_id), attendance: Object.entries(data.grades[id] || {}).map(([student_id, grade]) => ({ student_id: Number(student_id), grade })) };
      if (!['', '0', '5', '4', '3', '2', 'absent', 'н/я'].includes(String(body.grade))) throw new Error('Недопустимая оценка');
      data.grades[id] ||= {}; data.grades[id][String(body.student_id)] = String(body.grade); return { ok: true };
    }
    if (method === 'POST') { const existing = data.lessons.find(l => l.subject_id === Number(body.subject_id) && l.date === String(body.date || todayISO()) && l.lesson_number === Number(body.lesson_number) && l.status === 'held'); if (body.lesson_number && existing) return { id: existing.id, deduped: true }; if (String(body.date) > todayISO()) throw new Error('Нельзя создавать занятия в будущем'); const s = data.subjects.find(s => s.id === Number(body.subject_id)); if (!s) throw new Error('Предмет не найден'); const l = { id: nextId(data.lessons), subject_id: s.id, actual_subject_id: Number(body.actual_subject_id) || s.id, date: String(body.date || todayISO()), status: String(body.status || 'held'), lesson_number: body.lesson_number ? Number(body.lesson_number) : null }; data.lessons.push(l); s.held_lessons++; return l; }
    if (method === 'DELETE') { data.lessons = data.lessons.filter(l => l.id !== id); const s = data.subjects.find(s => s.id === lesson?.subject_id); if (s && lesson?.status === 'held') s.held_lessons--; delete data.grades[id]; return { ok: true }; }
    if (method === 'PATCH') { const l = data.lessons.find(l => l.id === id); if (l) { if (action === 'substitute') l.actual_subject_id = Number(body.actual_subject_id); else { const next = action === 'cancel' ? 'cancelled' : String(body.status); const s = data.subjects.find(s => s.id === l.subject_id); if (s && l.status !== next) s.held_lessons += next === 'held' ? 1 : -1; l.status = next; if (action === 'cancel') delete data.grades[id]; } } return { ok: true }; }
    return lesson || null;
  }
  if (resource === 'reports') {
    if (p[1] === 'average') { const subject = data.subjects.find(s => s.id === Number(action)), ls = data.lessons.filter(l => l.subject_id === subject?.id); return groupStudents(subject?.group_id).flatMap(s => { const grades = ls.map(l => Number(data.grades[l.id]?.[s.id])).filter(g => g >= 2 && g <= 5); return grades.length ? [{ ...s, average: Number((grades.reduce((a, b) => a + b, 0) / grades.length).toFixed(2)) }] : []; }); }
    return [];
  }
  throw new Error('Этот запрос недоступен в деморежиме. Подключите исходный сервер.');
}
