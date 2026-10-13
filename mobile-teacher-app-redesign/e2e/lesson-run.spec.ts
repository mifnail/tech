import { expect, test } from "@playwright/test";
import { gotoApp, openHeldLesson, openSchedule, setGrade } from "./helpers";

/** Занятие: оценка тапом → «Провести», и защита от ухода с грязью. */

test("провести занятие: тап-оценка → «Провести» → тост «Проведено, отправлено N»", async ({
  page,
}) => {
  await gotoApp(page);
  await openSchedule(page);
  await openHeldLesson(page);

  // До правок кнопка неактивна — «грязи» нет
  const conduct = page.getByRole("button", { name: "Провести" });
  await expect(conduct).toHaveCount(1);
  await expect(conduct).toBeDisabled();

  // Тап по правой половине ячейки = оценка вперёд (не требует dirty)
  await setGrade(page);
  await expect(page.getByText("не проведено", { exact: true })).toBeVisible();
  await expect(conduct).toBeEnabled();

  await conduct.click();

  await expect(page.getByText(/^Проведено, отправлено \d+$/)).toBeVisible();
  await expect(page.getByText("не проведено", { exact: true })).toHaveCount(0);
  await expect(conduct).toBeDisabled(); // грязь снята
});

test("грязь → «Есть непроведённые оценки» → «Уйти без сохранения» не фризит навигацию", async ({
  page,
}) => {
  await gotoApp(page);
  await openSchedule(page);
  await openHeldLesson(page);

  await setGrade(page);
  await expect(page.getByText("не проведено", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Назад" }).click();

  const sheet = page.getByRole("dialog");
  await expect(sheet).toHaveCount(1);
  await expect(
    sheet.getByRole("heading", { name: "Есть непроведённые оценки", exact: true }),
  ).toBeVisible();
  await expect(sheet.getByRole("button", { name: "Провести" })).toBeVisible();
  await sheet.getByRole("button", { name: "Уйти без сохранения" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  // Экран занятия закрылся, навигация живая
  await expect(page.getByRole("button", { name: "Провести" })).toHaveCount(0);
  await expect(page.getByRole("navigation")).toBeVisible();
  await page.getByRole("navigation").getByRole("button", { name: "Сегодня" }).click();
  await expect(page.getByRole("heading", { name: "Сегодня", exact: true })).toBeVisible();
});
