import { expect, test } from "@playwright/test";
import { gotoApp, openSchedule, setGrade } from "./helpers";

/** Вычитка предмета: последняя пара предупреждает, после подтверждения
    предмет уходит из будущего расписания. */

const pad = (n: number) => (n < 10 ? `0${n}` : String(n));

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

test("последняя пара: предупреждение → закрытие → исчезает из расписания", async ({ page }) => {
  // Данные готовим ДО загрузки приложения: стор тянет снимок один раз
  // и созданное после загрузки не увидит.
  const groups = (await (await page.request.get("/api/groups")).json()) as Array<{ id: number }>;
  const subject = (await (
    await page.request.post("/api/subjects", {
      data: { name: "МДК тест-вычитка", total_hours: 1, group_id: groups[0].id },
    })
  ).json()) as { id: number };
  const lesson = (await (
    await page.request.post("/api/lessons", {
      data: {
        subject_id: subject.id,
        date: isoDaysAgo(7),
        status: "scheduled",
        lesson_number: 7,
      },
    })
  ).json()) as { id: number };

  // Плановая строка на сегодня: до закрытия видна, после — нет.
  const weekday = new Date().getDay() === 0 ? 7 : new Date().getDay();
  await page.request.post("/api/schedule", {
    data: { day_of_week: weekday, lesson_number: 6, subject_id: subject.id, week_type: 0 },
  });

  await gotoApp(page);

  const subjectState = async () =>
    ((
      (await (await page.request.get("/api/subjects")).json()) as Array<{
        id: number;
        closed_at?: string | null;
      }>
    ).find((s) => s.id === subject.id)?.closed_at ?? null);

  expect(await subjectState()).toBeNull();
  await openSchedule(page);
  await expect(page.getByText("МДК тест-вычитка").first()).toBeVisible();

  const loaded = page.waitForResponse(
    (r) =>
      r.request().method() === "GET" &&
      r.url().endsWith(`/api/lessons/${lesson.id}/attendance`) &&
      r.status() === 200,
  );
  await page.goto(`/#/lesson/${lesson.id}`);
  await loaded;
  await setGrade(page);

  await page.getByRole("button", { name: "Провести", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByText("Последняя пара по предмету")).toBeVisible();
  await expect(page.getByText(/исчезнет из будущего расписания/)).toBeVisible();

  await page.getByRole("button", { name: "Провести и закрыть" }).click();
  await expect(page.getByText(/Предмет убран из расписания/)).toBeVisible();

  expect(await subjectState()).not.toBeNull();
  const status = ((await (await page.request.get(`/api/lessons/${lesson.id}`)).json()) as {
    status: string;
  }).status;
  expect(status).toBe("held");

  // Экран занятия без нижней навигации — идём в расписание прямым адресом.
  await page.goto("/#/schedule");
  await expect(page.getByRole("heading", { name: "Расписание" })).toBeVisible();
  await expect(page.getByText("МДК тест-вычитка")).toHaveCount(0);
});
