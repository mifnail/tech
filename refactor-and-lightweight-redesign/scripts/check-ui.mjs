import { chromium } from "@playwright/test";
import assert from "node:assert/strict";
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.goto("http://localhost:4173");
await page.screenshot({ path: "/tmp/teachhelper-desktop.png", fullPage: true });
console.log(
  "Desktop dimensions",
  await page.evaluate(() => ({
    width: innerWidth,
    content: document.documentElement.scrollWidth,
    height: document.documentElement.scrollHeight,
  })),
);
await page.getByRole("button", { name: "Перейти к занятию" }).click();
await page
  .getByRole("button", { name: "Все присутствуют", exact: true })
  .click();
await page.getByRole("button", { name: /Оценка 0, Александров Артём/ }).click();
await page.getByRole("button", { name: "Закрыть", exact: true }).click();
await page.reload();
await page.getByRole("button", { name: "Перейти к занятию" }).click();
assert.equal(
  await page
    .getByRole("button", { name: /Оценка 5, Александров Артём/ })
    .count(),
  1,
);
await page.getByRole("button", { name: "Закрыть", exact: true }).click();
await page.getByRole("button", { name: "Все группы", exact: true }).click();
await page
  .getByRole("button", { name: "Добавить группу", exact: true })
  .click();
await page.getByRole("textbox", { name: "Название группы" }).fill("ТЕСТ-01");
await page
  .getByRole("textbox", { name: "Направление" })
  .fill("Тестирование интерфейса");
await page.getByRole("button", { name: "Создать группу", exact: true }).click();
await page.getByRole("textbox", { name: "Найти группу" }).fill("ТЕСТ-01");
assert.equal(await page.locator(".group-card").count(), 1);
await page.getByRole("button", { name: "Отчёты", exact: true }).click();
const downloadPromise = page.waitForEvent("download");
await page
  .getByRole("button", { name: "Экспорт в Excel", exact: true })
  .click();
const download = await downloadPromise;
assert.ok(download.suggestedFilename().endsWith(".xlsx"));
await download.saveAs("/tmp/teachhelper-test.xlsx");
console.log("Excel exported:", download.suggestedFilename());
const mobile = await browser.newPage({
  viewport: { width: 390, height: 844 },
  isMobile: true,
  hasTouch: true,
});
mobile.on("pageerror", (e) => errors.push(e.message));
await mobile.goto("http://localhost:4173");
await mobile.screenshot({
  path: "/tmp/teachhelper-mobile.png",
  fullPage: true,
});
assert.equal(
  await mobile.evaluate(
    () => document.documentElement.scrollWidth <= innerWidth,
  ),
  true,
);
await mobile.getByRole("button", { name: "Открыть меню" }).click();
await mobile
  .getByRole("button", { name: "Группы", exact: false })
  .first()
  .click();
assert.ok((await mobile.locator("h1").innerText()) === "Группы");
for (const width of [320, 360, 620, 768, 1024, 1440]) {
  await page.setViewportSize({ width, height: 900 });
  await page.goto("http://localhost:4173");
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > innerWidth,
  );
  assert.equal(overflow, false, "Overflow at " + width);
}
const legacy = await browser.newPage({
  viewport: { width: 360, height: 740 },
  userAgent:
    "Mozilla/5.0 (Linux; Android 7.0) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/51.0.2704.81 Mobile Safari/537.36",
});
legacy.on("pageerror", (e) => errors.push(e.message));
await legacy.goto("http://localhost:4173");
await legacy.locator("h1").waitFor();
assert.equal(await legacy.evaluate(() => window.__teachHelperLegacy), true);
assert.equal(await legacy.locator(".app-shell").count(), 1);
await legacy.getByRole("button", { name: "Перейти к занятию" }).click();
assert.equal(await legacy.getByRole("dialog").count(), 1);
console.log(
  "Legacy loader and journal passed (simulated Android 7 user-agent).",
);
assert.deepEqual(errors, []);
console.log(
  "PASS: grades persisted, group created, search filtered, Excel downloaded, mobile navigation, six viewport widths; no runtime errors.",
);
await browser.close();
