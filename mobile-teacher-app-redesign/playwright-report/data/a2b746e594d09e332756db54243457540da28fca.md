# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: lesson-run.spec.ts >> грязь → «Есть непроведённые оценки» → «Уйти без сохранения» не фризит навигацию
- Location: e2e\lesson-run.spec.ts:30:1

# Error details

```
TimeoutError: page.waitForResponse: Timeout 10000ms exceeded while waiting for event "response"
```

```
TimeoutError: locator.click: Timeout 10000ms exceeded.
Call log:
  - waiting for getByText('Проведено', { exact: true }).first()
    - locator resolved to <span class="sr-only">Проведено</span>
  - attempting click action
    2 × waiting for element to be visible, enabled and stable
      - element is visible, enabled and stable
      - scrolling into view if needed
      - done scrolling
      - <div class="text-[21px] font-extrabold tabular-nums leading-none text-ink">1</div> from <div class="shrink-0 select-none text-center w-[48px]">…</div> subtree intercepts pointer events
    - retrying click action
    - waiting 20ms
    2 × waiting for element to be visible, enabled and stable
      - element is visible, enabled and stable
      - scrolling into view if needed
      - done scrolling
      - <div class="text-[21px] font-extrabold tabular-nums leading-none text-ink">1</div> from <div class="shrink-0 select-none text-center w-[48px]">…</div> subtree intercepts pointer events
    - retrying click action
      - waiting 100ms
    19 × waiting for element to be visible, enabled and stable
       - element is visible, enabled and stable
       - scrolling into view if needed
       - done scrolling
       - <div class="text-[21px] font-extrabold tabular-nums leading-none text-ink">1</div> from <div class="shrink-0 select-none text-center w-[48px]">…</div> subtree intercepts pointer events
     - retrying click action
       - waiting 500ms

```

# Page snapshot

```yaml
- generic [ref=e3]:
  - generic [ref=e5]:
    - banner [ref=e6]:
      - generic [ref=e7]:
        - generic [ref=e8]: 12.10 – 18.10
        - heading "Расписание" [level=1] [ref=e9]
      - button "Добавить пару" [ref=e11]
    - generic [ref=e13]:
      - button "Предыдущая неделя" [ref=e14]
      - generic [ref=e17]:
        - button "Пн 12" [active] [ref=e18]:
          - generic [ref=e19]: Пн
          - generic [ref=e20]: "12"
        - button "Вт 13" [ref=e22]:
          - generic [ref=e23]: Вт
          - generic [ref=e24]: "13"
        - button "Ср 14" [ref=e26]:
          - generic [ref=e27]: Ср
          - generic [ref=e28]: "14"
        - button "Чт 15" [ref=e30]:
          - generic [ref=e31]: Чт
          - generic [ref=e32]: "15"
        - button "Пт 16" [ref=e34]:
          - generic [ref=e35]: Пт
          - generic [ref=e36]: "16"
        - button "Сб 17" [ref=e38]:
          - generic [ref=e39]: Сб
          - generic [ref=e40]: "17"
        - button "Вс 18" [ref=e42]:
          - generic [ref=e43]: Вс
          - generic [ref=e44]: "18"
      - button "Следующая неделя" [ref=e46]
    - button "Сегодня" [ref=e50]
    - heading "12 октября, понедельник" [level=2] [ref=e52]
    - generic [ref=e53]:
      - heading "ПЗ-21" [level=2] [ref=e55]
      - generic [ref=e56] [cursor=pointer]:
        - generic [ref=e57]:
          - generic [ref=e58]: "1"
          - generic [ref=e59]: ПЗ-21
        - generic [ref=e61]:
          - generic [ref=e62]: Информатика
          - generic [ref=e63]: ПЗ-21
        - generic [ref=e65]: Проведено
        - generic "Проведено" [ref=e66]
        - button "Редактировать пару" [ref=e69]
      - generic [ref=e75] [cursor=pointer]:
        - generic [ref=e76]:
          - generic [ref=e77]: "2"
          - generic [ref=e78]: ПЗ-21
        - generic [ref=e80]:
          - generic [ref=e81]: Компьютерные сети
          - generic [ref=e82]: ПЗ-21
        - generic [ref=e84]: Проведено
        - generic "Проведено" [ref=e85]
        - button "Редактировать пару" [ref=e88]
    - generic [ref=e94]:
      - heading "ПЗ-22" [level=2] [ref=e96]
      - generic [ref=e97] [cursor=pointer]:
        - generic [ref=e98]:
          - generic [ref=e99]: "1"
          - generic [ref=e100]: ПЗ-22
        - generic [ref=e102]:
          - generic [ref=e103]: Базы данных
          - generic [ref=e104]: ПЗ-22
        - generic [ref=e106]: Проведено
        - generic "Проведено" [ref=e107]
        - button "Редактировать пару" [ref=e110]
      - generic [ref=e116] [cursor=pointer]:
        - generic [ref=e117]:
          - generic [ref=e118]: "2"
          - generic [ref=e119]: ПЗ-22
        - generic [ref=e121]:
          - generic [ref=e122]: Операционные системы
          - generic [ref=e123]: ПЗ-22
        - generic [ref=e125]: Проведено
        - generic "Проведено" [ref=e126]
        - button "Редактировать пару" [ref=e129]
    - generic [ref=e135]:
      - heading "СЗ-11" [level=2] [ref=e137]
      - generic [ref=e138] [cursor=pointer]:
        - generic [ref=e139]:
          - generic [ref=e140]: "1"
          - generic [ref=e141]: СЗ-11
        - generic [ref=e143]:
          - generic [ref=e144]: Компьютерные сети
          - generic [ref=e145]: СЗ-11
        - generic [ref=e147]: Проведено
        - generic "Проведено" [ref=e148]
        - button "Редактировать пару" [ref=e151]
      - generic [ref=e157] [cursor=pointer]:
        - generic [ref=e158]:
          - generic [ref=e159]: "2"
          - generic [ref=e160]: СЗ-11
        - generic [ref=e162]:
          - generic [ref=e163]: Базы данных
          - generic [ref=e164]: СЗ-11
        - generic [ref=e166]: Проведено
        - generic "Проведено" [ref=e167]
        - button "Редактировать пару" [ref=e170]
    - generic [ref=e176]:
      - heading "СЗ-12" [level=2] [ref=e178]
      - generic [ref=e179] [cursor=pointer]:
        - generic [ref=e180]:
          - generic [ref=e181]: "1"
          - generic [ref=e182]: СЗ-12
        - generic [ref=e184]:
          - generic [ref=e185]: Операционные системы
          - generic [ref=e186]: СЗ-12
        - generic [ref=e188]: Проведено
        - generic "Проведено" [ref=e189]
        - button "Редактировать пару" [ref=e192]
      - generic [ref=e198] [cursor=pointer]:
        - generic [ref=e199]:
          - generic [ref=e200]: "2"
          - generic [ref=e201]: СЗ-12
        - generic [ref=e203]:
          - generic [ref=e204]: Математика
          - generic [ref=e205]: СЗ-12
        - generic [ref=e207]: Проведено
        - generic "Проведено" [ref=e208]
        - button "Редактировать пару" [ref=e211]
    - button "Начать занятие" [ref=e217]
  - navigation [ref=e220]:
    - generic [ref=e221]:
      - button "Сегодня" [ref=e222]
      - button "Предметы и группы" [ref=e228]
      - button "Расписание" [ref=e235]
      - button "Аналитика" [ref=e240]
      - button "Ещё" [ref=e245]
```

# Test source

```ts
  29  |   return `${d.getDate()} ${MONTHS[d.getMonth()]}, ${WEEKDAYS_LONG[d.getDay()]}`;
  30  | }
  31  | 
  32  | const pad = (n: number) => (n < 10 ? `0${n}` : String(n));
  33  | 
  34  | /** Копия кикера шапки Расписания: «12.10 – 18.10» (en-dash с пробелами). */
  35  | export function weekKicker(monday: Date): string {
  36  |   const end = addDays(monday, 6);
  37  |   return `${pad(monday.getDate())}.${pad(monday.getMonth() + 1)} – ${pad(end.getDate())}.${pad(end.getMonth() + 1)}`;
  38  | }
  39  | 
  40  | /** Загрузить React dist и дождаться ПОЛНОЙ загрузки store.
  41  |     Store тянет batch-2 (gradebook'и всех предметов) ПОСЛЕ batch-1 — без них
  42  |     список занятий дня ещё пуст, и проверки «пустой/непустой день» соврут. */
  43  | export async function gotoApp(page: Page): Promise<void> {
  44  |   const gradebookDone: string[] = [];
  45  |   page.on("response", (r) => {
  46  |     if (/\/api\/subjects\/\d+\/gradebook$/.test(r.url())) gradebookDone.push(r.url());
  47  |   });
  48  |   const subjectsLoaded = page.waitForResponse(
  49  |     (r) => r.url().endsWith("/api/subjects") && r.status() === 200,
  50  |   );
  51  |   await page.goto("/");
  52  |   const subjects = (await (await subjectsLoaded).json()) as Array<{ id: number }>;
  53  |   await expect
  54  |     .poll(() => gradebookDone.length, {
  55  |       timeout: 30_000,
  56  |       message: "gradebook'и batch-2 не догрузились",
  57  |     })
  58  |     .toBe(subjects.length);
  59  | }
  60  | 
  61  | /** Открыть вкладку «Расписание» нижней навигации и убедиться, что это она. */
  62  | export async function openSchedule(page: Page): Promise<void> {
  63  |   await page.getByRole("navigation").getByRole("button", { name: "Расписание" }).click();
  64  |   await expect(page.getByRole("heading", { name: "Расписание" })).toBeVisible();
  65  |   await expect(page.getByText(weekKicker(mondayOf(new Date())))).toBeVisible();
  66  | }
  67  | 
  68  | export async function prevWeek(page: Page): Promise<void> {
  69  |   await page.getByRole("button", { name: "Предыдущая неделя" }).click();
  70  | }
  71  | 
  72  | /** Клик по дню в ленте недели: primary — русский текст («Пн 29»), фолбэк — столбец ленты. */
  73  | export async function selectDay(page: Page, date: Date): Promise<void> {
  74  |   const name = new RegExp(`^\\s*${WEEKDAYS_SHORT[date.getDay()]}\\s+${date.getDate()}\\s*$`);
  75  |   const byName = page.getByRole("button", { name });
  76  |   if ((await byName.count()) > 0) {
  77  |     await byName.first().click();
  78  |   } else {
  79  |     // лента всегда пн→вс: день недели занимает фиксированный столбец
  80  |     await page
  81  |       .locator("div.flex.flex-1.gap-1 > button")
  82  |       .nth((date.getDay() + 6) % 7)
  83  |       .click();
  84  |   }
  85  |   await expect(page.getByRole("heading", { name: formatLong(date) })).toBeVisible();
  86  | }
  87  | 
  88  | /**
  89  |  * Найти дату, удовлетворяющую probe: идём назад по неделям (кнопка ←),
  90  |  * в каждой неделе — по всем 7 дням. Возвращает дату или null.
  91  |  */
  92  | export async function findDay(
  93  |   page: Page,
  94  |   probe: (page: Page) => Promise<boolean>,
  95  | ): Promise<Date | null> {
  96  |   const base = mondayOf(new Date());
  97  |   for (let week = 1; week <= 6; week++) {
  98  |     await prevWeek(page);
  99  |     const monday = addDays(base, -7 * week);
  100 |     await expect(page.getByText(weekKicker(monday))).toBeVisible();
  101 |     for (let i = 0; i < 7; i++) {
  102 |       const day = addDays(monday, i);
  103 |       await selectDay(page, day);
  104 |       if (await probe(page)) return day;
  105 |     }
  106 |   }
  107 |   return null;
  108 | }
  109 | 
  110 | /** Пустая дата: EmptyState «В этот день занятий нет». */
  111 | export const hasEmptyDay = async (page: Page): Promise<boolean> =>
  112 |   (await page.getByText("В этот день занятий нет", { exact: true }).count()) > 0;
  113 | 
  114 | /** Дата с карточками: чип «Проведено» в списке занятий. */
  115 | export const hasHeldChip = async (page: Page): Promise<boolean> =>
  116 |   (await page.getByText("Проведено", { exact: true }).count()) > 0;
  117 | 
  118 | /** Открыть прошедшее занятие (клик по чипу внутри карточки) и дождаться ведомости. */
  119 | export async function openHeldLesson(page: Page): Promise<Date> {
  120 |   const day = await findDay(page, hasHeldChip);
  121 |   expect(day, "за 6 недель назад не нашлась прошедшая дата с чипом «Проведено»").not.toBeNull();
  122 | 
  123 |   const attendance = page.waitForResponse(
  124 |     (r) =>
  125 |       r.request().method() === "GET" &&
  126 |       /\/api\/lessons\/\d+\/attendance$/.test(r.url()) &&
  127 |       r.status() === 200,
  128 |   );
> 129 |   await page.getByText("Проведено", { exact: true }).first().click();
      |                                                              ^ TimeoutError: locator.click: Timeout 10000ms exceeded.
  130 |   await page.waitForURL(/#\/lesson\/\d+/);
  131 |   await attendance;
  132 |   return day as Date;
  133 | }
  134 | 
  135 | /** Первая ячейка ведомости; студент может быть без записи посещаемости — делаем присутствующим. */
  136 | async function firstCell(page: Page) {
  137 |   const cells = page.locator('[role="button"][aria-disabled]');
  138 |   await expect(cells.first()).toBeVisible();
  139 |   const cell = cells.first();
  140 |   const dot = cell.getByRole("button", { name: "Отметить присутствующим" });
  141 |   if ((await dot.count()) > 0) await dot.click();
  142 |   return cell;
  143 | }
  144 | 
  145 | /** Поставить оценку: тап по правой половине ячейки (перебор вперёд). */
  146 | export async function setGrade(page: Page) {
  147 |   const cell = await firstCell(page);
  148 |   const before = (await cell.innerText()).trim();
  149 |   const box = await cell.boundingBox();
  150 |   expect(box, "у ячейки нет габаритов").not.toBeNull();
  151 |   await cell.click({
  152 |     position: { x: Math.round(box!.width * 0.75), y: Math.round(box!.height / 2) },
  153 |   });
  154 |   await expect(cell).not.toHaveText(before);
  155 |   return cell;
  156 | }
  157 | 
```