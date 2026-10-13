import { defineConfig } from "@playwright/test";

/**
 * E2E TeachHelper4 — против СОБРАННОГО dist через живой Flask на 127.0.0.1:5111.
 *
 * Сервер: webServer гоняет `python e2e_server.py` (sid во временную БД + main.py)
 * и ждёт baseURL. Если внешний раннер (stand.py/stand_seed.py) уже поднял 5111 —
 * reuseExistingServer:true, Playwright подхватывает живой сервер и свой не стартует.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 8_000 },
  fullyParallel: false, // общий сервер и общая БД — только последовательно
  workers: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:5111",
    headless: true,
    viewport: { width: 430, height: 900 },
    locale: "ru-RU",
    actionTimeout: 10_000,
    navigationTimeout: 20_000,
    trace: "retain-on-failure",
  },
  // только chromium
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
  webServer: {
    command: "python e2e_server.py",
    url: "http://127.0.0.1:5111/",
    reuseExistingServer: true,
    timeout: 120_000,
    stdout: "pipe",
    stderr: "pipe",
  },
});
