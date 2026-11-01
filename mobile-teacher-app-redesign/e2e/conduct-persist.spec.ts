import { expect, test } from "@playwright/test";
import { gotoApp, setGrade } from "./helpers";

/** Главное правило: до «Провести» на сервере не меняется ничего.
    Раньше тап по студенту молча писал ведомость и поднимал статус до held. */

const pad = (n: number) => (n < 10 ? `0${n}` : String(n));

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

test("оценки уходят только по «Провести»: до — пусто, после — held и оценки", async ({ page }) => {
  await gotoApp(page);

  // Непроведённое занятие на прошлую дату — создаём через API, чтобы тест
  // не зависел от того, какие слоты есть в шаблоне расписания.
  const subjects = (await (await page.request.get("/api/subjects")).json()) as Array<{
    id: number;
  }>;
  expect(subjects.length).toBeGreaterThan(0);
  const created = (await (
    await page.request.post("/api/lessons", {
      data: {
        subject_id: subjects[0].id,
        date: isoDaysAgo(21),
        status: "scheduled",
        lesson_number: 2,
      },
    })
  ).json()) as { id: number };
  const lessonId = created.id;

  const readAttendance = async () =>
    ((await (await page.request.get(`/api/lessons/${lessonId}/attendance`)).json()) as {
      attendance: unknown[];
    }).attendance;
  const readStatus = async () =>
    ((await (await page.request.get(`/api/lessons/${lessonId}`)).json()) as {
      status: string;
    }).status;

  expect(await readAttendance()).toHaveLength(0);
  expect(await readStatus()).toBe("scheduled");

  const loaded = page.waitForResponse(
    (r) =>
      r.request().method() === "GET" &&
      r.url().endsWith(`/api/lessons/${lessonId}/attendance`) &&
      r.status() === 200,
  );
  await page.goto(`/#/lesson/${lessonId}`);
  await loaded;

  await setGrade(page);

  // Ключевая проверка: тап ничего не отправил.
  expect(await readAttendance()).toHaveLength(0);
  expect(await readStatus()).toBe("scheduled");

  const conduct = page.getByRole("button", { name: "Провести" });
  await expect(conduct).toBeEnabled();
  await conduct.click();
  await expect(page.getByText(/^Проведено · уведомлений: \d+$/)).toBeVisible();

  expect(await readStatus()).toBe("held");
  expect((await readAttendance()).length).toBeGreaterThan(0);
});
