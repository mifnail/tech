import { expect, test } from "@playwright/test";
import { findDay, gotoApp, hasEmptyDay, hasHeldChip, openSchedule } from "./helpers";

/** Расписание: ретро-лента дат (кнопка ← уводит в прошлое, выбор дня, EmptyState). */

test("пустая дата: EmptyState и активная кнопка «Начать занятие» → Sheet выбора пары", async ({
  page,
}) => {
  await gotoApp(page);
  await openSchedule(page);

  const empty = await findDay(page, hasEmptyDay);
  expect(empty, "за 6 недель назад не нашлась пустая дата").not.toBeNull();

  await expect(page.getByText("В этот день занятий нет", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Начните занятие вручную или выберите другую дату.", { exact: true }),
  ).toBeVisible();

  const start = page.getByRole("button", { name: "Начать занятие" });
  await expect(start).toHaveCount(1);
  await expect(start).toBeEnabled();
  await start.click();

  const dialog = page.getByRole("dialog");
  await expect(dialog).toHaveCount(1);
  await expect(dialog.getByRole("heading", { name: "Начать занятие", exact: true })).toBeVisible();
  await expect(dialog.getByText("Выберите предмет", { exact: true })).toBeVisible();

  await dialog.getByRole("button", { name: "Закрыть" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("дата с проведённым занятием: «Начать занятие» под списком → календарь создания", async ({
  page,
}) => {
  await gotoApp(page);
  await openSchedule(page);

  const busy = await findDay(page, hasHeldChip);
  expect(busy, "за 6 недель назад не нашлась дата с индикатором «Проведено»").not.toBeNull();
  await expect(page.getByLabel("Проведено", { exact: true }).first()).toBeVisible();

  // На непустой дате кнопка ровно одна (muted, под списком занятий)
  const start = page.getByRole("button", { name: "Начать занятие" });
  await expect(start).toHaveCount(1);
  await expect(start).toBeEnabled();
  await start.click();

  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Начать занятие", exact: true })).toBeVisible();
  await expect(dialog.getByText("Выберите предмет", { exact: true })).toBeVisible();

  // Выбор пары → вид «Дата занятия» с календарём-сеткой
  const pair = dialog.getByRole("button", { name: /Математика/ }).first();
  await expect(pair).toBeVisible();
  await pair.click();

  await expect(dialog.getByRole("heading", { name: "Дата занятия", exact: true })).toBeVisible();
  await expect(
    dialog.getByText(/^(Январь|Февраль|Март|Апрель|Май|Июнь|Июль|Август|Сентябрь|Октябрь|Ноябрь|Декабрь) \d{4}$/),
  ).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Создать занятие" })).toBeEnabled();

  await dialog.getByRole("button", { name: "Закрыть" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
