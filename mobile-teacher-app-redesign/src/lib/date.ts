// Recovered from the tracked a2f9132 production bundle; use local calendar dates.
const monthNames = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"];
const monthTitles = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"];
const weekdays = ["воскресенье", "понедельник", "вторник", "среда", "четверг", "пятница", "суббота"];
const shortWeekdays = ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"];
const pad = (value: number) => value < 10 ? "0" + value : "" + value;

export function fromISO(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function toISO(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function todayISO(): string { return toISO(new Date()); }

export function addDaysISO(value: string, days: number): string {
  const date = fromISO(value);
  date.setDate(date.getDate() + days);
  return toISO(date);
}

export function weekdayOf(value: string): number {
  const day = fromISO(value).getDay();
  return day === 0 ? 7 : day;
}

export function formatDot(value: string): string {
  const [year, month, day] = value.split("-");
  return `${day}.${month}.${year}`;
}

export function formatDotShort(value: string): string {
  const [, month, day] = value.split("-");
  return `${day}.${month}`;
}

export function formatLong(value: string): string {
  const date = fromISO(value);
  return `${date.getDate()} ${monthNames[date.getMonth()]}, ${weekdays[date.getDay()]}`;
}

export function monthYearLabel(value: string): string {
  const date = fromISO(value);
  return `${monthTitles[date.getMonth()]} ${date.getFullYear()}`;
}

export function weekdayShort(value: string): string {
  return shortWeekdays[fromISO(value).getDay()];
}

function isoWeek(date: Date): number {
  const thursday = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  thursday.setDate(thursday.getDate() - (thursday.getDay() + 6) % 7 + 3);
  const first = new Date(thursday.getFullYear(), 0, 4);
  first.setDate(first.getDate() - (first.getDay() + 6) % 7 + 3);
  return 1 + Math.round((thursday.getTime() - first.getTime()) / 604800000);
}

export function weekParity(value: string): 1 | 2 {
  return isoWeek(fromISO(value)) % 2 === 0 ? 1 : 2;
}

export function mondayOfWeek(value: string): string {
  return addDaysISO(value, -(weekdayOf(value) - 1));
}
