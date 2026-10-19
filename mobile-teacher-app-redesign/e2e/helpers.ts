/* Общие хелперы E2E.
   Селекторы — ТОЛЬКО по русскому тексту и aria (data-testid запрещён);
   css-классы используются лишь как фолбэк/скоуп ленты дат. */
import { expect, type Page } from "@playwright/test";

const MONTHS = [
  "января", "февраля", "марта", "апреля", "мая", "июня",
  "июля", "августа", "сентября", "октября", "ноября", "декабря",
];
const WEEKDAYS_LONG = [
  "воскресенье", "понедельник", "вторник", "среда", "четверг", "пятница", "суббота",
];
/** Индекс = Date.getDay(): Вс=0 … Сб=6. */
const WEEKDAYS_SHORT = ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"];

export function addDays(d: Date, days: number): Date {
  const out = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  out.setDate(out.getDate() + days);
  return out;
}

export function mondayOf(d: Date): Date {
  const wd = d.getDay() === 0 ? 7 : d.getDay(); // пн=1 … вс=7
  return addDays(d, -(wd - 1));
}

/** Копия src/lib/date.ts#formatLong: «13 октября, вторник». */
export function formatLong(d: Date): string {
  return `${d.getDate()} ${MONTHS[d.getMonth()]}, ${WEEKDAYS_LONG[d.getDay()]}`;
}

const pad = (n: number) => (n < 10 ? `0${n}` : String(n));

/** Копия кикера шапки Расписания: «12.10 – 18.10» (en-dash с пробелами). */
export function weekKicker(monday: Date): string {
  const end = addDays(monday, 6);
  return `${pad(monday.getDate())}.${pad(monday.getMonth() + 1)} – ${pad(end.getDate())}.${pad(end.getMonth() + 1)}`;
}

/** Загрузить React dist и дождаться ПОЛНОЙ загрузки store.
    Store тянет batch-2 (gradebook'и всех предметов) ПОСЛЕ batch-1 — без них
    список занятий дня ещё пуст, и проверки «пустой/непустой день» соврут. */
export async function gotoApp(page: Page): Promise<void> {
  const gradebookDone: string[] = [];
  page.on("response", (r) => {
    if (/\/api\/subjects\/\d+\/gradebook$/.test(r.url())) gradebookDone.push(r.url());
  });
  const subjectsLoaded = page.waitForResponse(
    (r) => r.url().endsWith("/api/subjects") && r.status() === 200,
  );
  await page.goto("/");
  const subjects = (await (await subjectsLoaded).json()) as Array<{ id: number }>;
  await expect
    .poll(() => gradebookDone.length, {
      timeout: 30_000,
      message: "gradebook'и batch-2 не догрузились",
    })
    .toBe(subjects.length);
}

/** Открыть вкладку «Расписание» нижней навигации и убедиться, что это она. */
export async function openSchedule(page: Page): Promise<void> {
  await page.getByRole("navigation").getByRole("button", { name: "Расписание" }).click();
  await expect(page.getByRole("heading", { name: "Расписание" })).toBeVisible();
  await expect(page.getByText(weekKicker(mondayOf(new Date())))).toBeVisible();
}

export async function prevWeek(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Предыдущая неделя" }).click();
}

/** Клик по дню в ленте недели: primary — русский текст («Пн 29»), фолбэк — столбец ленты. */
export async function selectDay(page: Page, date: Date): Promise<void> {
  const name = new RegExp(`^\\s*${WEEKDAYS_SHORT[date.getDay()]}\\s+${date.getDate()}\\s*$`);
  const byName = page.getByRole("button", { name });
  if ((await byName.count()) > 0) {
    await byName.first().click();
  } else {
    // лента всегда пн→вс: день недели занимает фиксированный столбец
    await page
      .locator("div.flex.flex-1.gap-1 > button")
      .nth((date.getDay() + 6) % 7)
      .click();
  }
  await expect(page.getByRole("heading", { name: formatLong(date) })).toBeVisible();
}

/**
 * Найти дату, удовлетворяющую probe: идём назад по неделям (кнопка ←),
 * в каждой неделе — по всем 7 дням. Возвращает дату или null.
 */
export async function findDay(
  page: Page,
  probe: (page: Page) => Promise<boolean>,
): Promise<Date | null> {
  const base = mondayOf(new Date());
  for (let week = 1; week <= 6; week++) {
    await prevWeek(page);
    const monday = addDays(base, -7 * week);
    await expect(page.getByText(weekKicker(monday))).toBeVisible();
    for (let i = 0; i < 7; i++) {
      const day = addDays(monday, i);
      await selectDay(page, day);
      if (await probe(page)) return day;
    }
  }
  return null;
}

/** Пустая дата: EmptyState «В этот день занятий нет». */
export const hasEmptyDay = async (page: Page): Promise<boolean> =>
  (await page.getByText("В этот день занятий нет", { exact: true }).count()) > 0;

/** Дата с карточками: индикатор «Проведено» в списке занятий.
    Статус компактный (кружок с галочкой), текст живёт в aria-label. */
export const hasHeldChip = async (page: Page): Promise<boolean> =>
  (await page.getByLabel("Проведено", { exact: true }).count()) > 0;

/** Открыть прошедшее занятие (клик по индикатору внутри карточки) и дождаться ведомости. */
export async function openHeldLesson(page: Page): Promise<Date> {
  const day = await findDay(page, hasHeldChip);
  expect(day, "за 6 недель назад не нашлась прошедшая дата с индикатором «Проведено»").not.toBeNull();

  const attendance = page.waitForResponse(
    (r) =>
      r.request().method() === "GET" &&
      /\/api\/lessons\/\d+\/attendance$/.test(r.url()) &&
      r.status() === 200,
  );
  await page.getByLabel("Проведено", { exact: true }).first().click();
  await page.waitForURL(/#\/lesson\/\d+/);
  await attendance;
  return day as Date;
}

/** Первая ячейка ведомости; студент может быть без записи посещаемости — делаем присутствующим. */
async function firstCell(page: Page) {
  const cells = page.locator('[role="button"][aria-disabled]');
  await expect(cells.first()).toBeVisible();
  const cell = cells.first();
  const dot = cell.getByRole("button", { name: "Отметить присутствующим" });
  if ((await dot.count()) > 0) await dot.click();
  return cell;
}

/** Поставить оценку: тап по правой половине ячейки (перебор вперёд). */
export async function setGrade(page: Page) {
  const cell = await firstCell(page);
  const before = (await cell.innerText()).trim();
  const box = await cell.boundingBox();
  expect(box, "у ячейки нет габаритов").not.toBeNull();
  await cell.click({
    position: { x: Math.round(box!.width * 0.75), y: Math.round(box!.height / 2) },
  });
  await expect(cell).not.toHaveText(before);
  return cell;
}
