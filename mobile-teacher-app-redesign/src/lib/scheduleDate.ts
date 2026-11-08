/* Выбранная дата расписания переживает размонтирование экрана.

   Экран «Расписание» рендерится по одному за раз (App.tsx), поэтому при
   переходе в ведомость он размонтируется, а состояние useState теряется.
   Преподаватель, который заполнял занятие задним числом, после свайпа
   назад возвращался на сегодняшнюю дату вместо той, которую открывал.

   Храним дату в sessionStorage: она живёт в рамках сессии приложения
   (переживает размонтирование экрана), но не переносится на следующий
   запуск — там пользователь ожидает увидеть сегодня. */

const KEY = "tech.schedule.date";

export function readScheduleDate(): string | null {
  try {
    return sessionStorage.getItem(KEY);
  } catch {
    return null; // приватный режим / storage недоступен
  }
}

export function saveScheduleDate(value: string): void {
  try {
    sessionStorage.setItem(KEY, value);
  } catch {
    // нет доступа к storage — просто не сохраняем
  }
}

export function clearScheduleDate(): void {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    // игнорируем
  }
}
