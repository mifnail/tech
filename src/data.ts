export type Lesson = { id: number; title: string; group: string; room: string; start: string; end: string; date: string; status: 'done' | 'active' | 'upcoming'; type: string; students: number };
export type Group = { id: number; name: string; course: string; students: number; subjects: number; color: string };
export const TODAY = new Date().toISOString().slice(0, 10);
export const initialGroups: Group[] = [
 {id: 1, name: 'ИС-21', course: '2 курс · Информационные системы', students: 24, subjects: 3, color: 'green'},
 {id: 2, name: 'ИС-22', course: '2 курс · Информационные системы', students: 26, subjects: 2, color: 'blue'},
 {id: 3, name: 'ПР-31', course: '3 курс · Программирование', students: 22, subjects: 4, color: 'purple'},
 {id: 4, name: 'ПР-32', course: '3 курс · Программирование', students: 24, subjects: 3, color: 'orange'},
 {id: 5, name: 'ИС-11', course: '1 курс · Информационные системы', students: 25, subjects: 2, color: 'blue'},
 {id: 6, name: 'ПР-21', course: '2 курс · Программирование', students: 27, subjects: 3, color: 'green'},
];
export const initialLessons: Lesson[] = [
 {id: 1, title: 'Основы программирования', group: 'ИС-21', room: '204', start: '08:30', end: '10:00', date: TODAY, status: 'done', type: 'Практическое занятие', students: 24},
 {id: 2, title: 'Базы данных', group: 'ИС-22', room: '208', start: '10:10', end: '11:40', date: TODAY, status: 'active', type: 'Лекция', students: 26},
 {id: 3, title: 'Разработка веб-приложений', group: 'ПР-31', room: '204', start: '12:10', end: '13:40', date: TODAY, status: 'upcoming', type: 'Практическое занятие', students: 22},
 {id: 4, title: 'Основы программирования', group: 'ИС-21', room: '204', start: '13:50', end: '15:20', date: TODAY, status: 'upcoming', type: 'Лекция', students: 24},
 {id: 5, title: 'Базы данных', group: 'ИС-21', room: '208', start: '08:30', end: '10:00', date: '2026-09-15', status: 'upcoming', type: 'Практическое занятие', students: 24},
 {id: 6, title: 'Разработка веб-приложений', group: 'ПР-32', room: '204', start: '10:10', end: '11:40', date: '2026-09-15', status: 'upcoming', type: 'Лекция', students: 24},
 {id: 7, title: 'Основы программирования', group: 'ИС-22', room: '204', start: '08:30', end: '10:00', date: '2026-09-16', status: 'upcoming', type: 'Лекция', students: 26},
 {id: 8, title: 'Базы данных', group: 'ПР-31', room: '208', start: '10:10', end: '11:40', date: '2026-09-17', status: 'upcoming', type: 'Лекция', students: 22},
 {id: 9, title: 'Разработка веб-приложений', group: 'ПР-32', room: '204', start: '12:10', end: '13:40', date: '2026-09-18', status: 'upcoming', type: 'Практическое занятие', students: 24},
];
export const studentNames = ['Александров Артём', 'Андреева Мария', 'Белов Максим', 'Васильева Анна', 'Волков Дмитрий', 'Гаврилова София', 'Данилов Иван', 'Егорова Полина', 'Жуков Александр', 'Зайцева Алина', 'Иванов Михаил', 'Козлова Екатерина', 'Кузнецов Даниил', 'Лебедева Виктория', 'Макаров Никита', 'Морозова Дарья', 'Николаев Илья', 'Орлова Вероника', 'Павлов Андрей', 'Петрова Анастасия', 'Романов Кирилл', 'Семёнова Елизавета', 'Смирнов Матвей', 'Соколова Валерия', 'Фёдоров Тимофей', 'Яковлева Ксения', 'Новиков Роман'];
export const subjects = ['Основы программирования', 'Базы данных', 'Разработка веб-приложений', 'Компьютерные сети', 'Операционные системы', 'Информационная безопасность', 'Алгоритмы и структуры данных', 'Тестирование ПО'];
export function loadLocal<T>(key: string, fallback: T): T { try { const value = localStorage.getItem('teachhelper-demo-' + key); return value ? JSON.parse(value) : fallback; } catch { return fallback; } }
export function saveLocal(key: string, value: unknown): boolean { try { localStorage.setItem('teachhelper-demo-' + key, JSON.stringify(value)); return true; } catch { return false; } }
export function dateLabel(date: string, options: Intl.DateTimeFormatOptions = {day: 'numeric', month: 'long'}) { return new Date(date + 'T12:00:00').toLocaleDateString('ru-RU', options); }
export function isoDate(date: Date) { return date.getFullYear() + '-' + String(date.getMonth()+1).padStart(2, '0') + '-' + String(date.getDate()).padStart(2, '0'); }
