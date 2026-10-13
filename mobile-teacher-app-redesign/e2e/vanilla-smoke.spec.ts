import { expect, test } from "@playwright/test";

/** Дымовой тест стенда: сервер отдаёт статику и React dist монтируется. */

test("GET /static/app.js → 200 (JS content-type, непустое тело)", async ({ request }) => {
  const resp = await request.get("/static/app.js");
  expect(resp.status()).toBe(200);
  expect(resp.headers()["content-type"] ?? "").toContain("javascript");
  expect((await resp.body()).length).toBeGreaterThan(0);
});

test("GET / отдаёт React dist, приложение монтируется", async ({ page, request }) => {
  const resp = await request.get("/");
  expect(resp.status()).toBe(200);

  const html = await resp.text();
  expect(html).toContain('id="root"'); // точка входа React
  expect(html).toContain("<!-- static: app.js?v="); // маркер версии из api.index()
  expect(html).not.toContain("/src/main.tsx"); // это сборка, а не dev-сервер Vite

  const pageResp = await page.goto("/");
  expect(pageResp?.status()).toBe(200);

  // React смонтировался и отрисовал корневую вкладку
  await expect(page.getByRole("heading", { name: "Сегодня", exact: true })).toBeVisible();
  await expect(
    page.getByRole("navigation").getByRole("button", { name: "Расписание" }),
  ).toBeVisible();
});
