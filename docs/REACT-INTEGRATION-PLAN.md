# REACT-INTEGRATION-PLAN: текущий функционал main → React-вариант mobile-teacher-app-redesign

> Только план. Код не менять, не пушить. Источник функционала = дерево `D:\tech\tech-redesign`
> (локальный эквивалент main после мержа redesign). Вариант = `mobile-teacher-app-redesign/` (`:5004`, `dist/index.html` 324949 байт ≈ 317KB, singlefile).

## 0. Цель и база

Цель: перенести ВЕСЬ текущий функционал main (Vanilla SPA + Flask `api.py`) на выбранный React-дизайн
без смены контракта API и схемы БД: same-origin `dist/index.html` + fetch-адаптер (решение A, см. §3).

Проверенные SHA (GitHub REST API, только GET; токен из `D:\tech\.gh_token`, не печатается):

- `main` = `c6e4e64a414ec0df9c663de1872e5c5bdc900f22` — `Merge pull request #1 from mifnail/redesign`,
  parents `f5b018df…` + `6a73792b…`; `compare(6a73792b...c6e4e64)` = `ahead 1 / behind 0` → **main содержит redesign**.
- `redesign` = `6a73792b7fad2e46b62aeb4b9f3763b451d795bb`.

Ожидание из задачи подтверждено (main содержит мерж redesign до `6a73792b`).

## 1–2. Инвентаризация main → карта варианта (42 фичи; 16 OK, 26 GAP/частичных, в т.ч. 19 полных GAP)

Источники main: `static/app.js` (`App.Router.handle`, `App.Pages`, `App.API`, `App.Grades.CYCLE`,
`App.Theme`, `App.Download.as`), `templates/index.html` (спрайт 20 иконок, `data-theme`),
`.slim/deepwork/redesign-v2.md` (v2-визуал, Analytics, темы `light|concept`, перестановки кнопок
предмета/группы, general-отчёт, хотфиксы tap/stats/confirm), `api.py` (все Blueprint-роуты).
Вариант: `src/App.tsx` (роуты `today|groups|group|statement|schedule|lesson|more`),
7 экранов `screens/*.tsx`, `lib/store.ts` (Store), `lib/xlsx.ts` (`buildXlsx`/`downloadXlsx`), `lib/router.ts` (hash).

| # | Фича main | Экран/метод варианта | Эндпоинт | GAP / риск |
|---|---|---|---|---|
| 1 | Главная: группы+предметы+today-сводка | Today + Groups | `GET /api/groups`, `/api/subjects`, `/api/schedule/today` | OK (сводка упрощена) |
| 2 | Группы CRUD | Groups + `addGroup`/`removeGroup` | `GET/POST /api/groups`, `PATCH/DELETE /api/groups/:id` | GAP: rename группы нет |
| 3 | Студенты список + поиск | GroupDetail фильтр | `GET /api/students?group_id=` | OK |
| 4 | Студенты bulk-добавление | `addStudent` (по одному) | `POST /api/students/bulk` | GAP: bulk |
| 5 | Студент edit (ФИО split) | — | `PATCH /api/students/:id` | GAP: ФИО split/склейка |
| 6 | Студент delete | `removeStudent` | `DELETE /api/students/:id` | OK |
| 7 | История оценок студента | — | `GET /api/students/:id/grades` | GAP |
| 8 | Предметы CRUD (+`total_hours`, `group_id`) | `addSubject(name)`+`assign/unassign` | `GET/POST/PATCH/DELETE /api/subjects` | GAP: hours, edit/delete |
| 9 | Ведомость предмета | Statement | `GET /api/subjects/:id/gradebook` | OK (держать фильтр cancelled) |
| 10 | Кликабельные даты ведомости | Statement th-button | тот же gradebook | OK |
| 11 | Занятия предмета | `lessonsOfPair` | `GET /api/subjects/:id/lessons` | OK (map) |
| 12 | Расписание + чётность | Schedule + `scheduleFor` | `GET /api/schedule` | OK |
| 13 | Расписание today | Today `lessonsOn` | `GET /api/schedule/today` | OK (map на клиентский фильтр) |
| 14 | Расписание create | Schedule `saveItem` | `POST /api/schedule` | OK, но time/room СКРЫТЬ (схемы нет) |
| 15 | Расписание edit | — | `PATCH /api/schedule/:id` | GAP |
| 16 | Расписание delete | `removeScheduleItem` | `DELETE /api/schedule/:id` | OK |
| 17 | Создание занятия с календарём (прошлое+сегодня, future-disable, дубли ок) | Schedule-sheet + `createLesson`/`NewLessonSheet` | `POST /api/lessons` | ЧАСТ.: перенести future-guard |
| 18 | Занятие: статы (ср/отмечено/посещ/dist, `_paintStats`) | LessonRun footer | `GET /api/lessons/:id/attendance` | OK (пересчёт на инвалидации) |
| 19 | Двусторонний тап оценок (CYCLE `['','0','5','4','3','2']`) | LessonRun `StudentCell`+`cycleGrade` | `POST /api/lessons/:id/attendance` | OK + дебаунс/bulk (§3.3) |
| 20 | Точка присутствия | `togglePresent` | тот же attendance POST | OK (маппинг present уточнить) |
| 21 | Смежные занятия prev/next | LessonRun siblings | `GET /api/lessons/:id/adjacent` | OK (map на `lessonsOfPair`) |
| 22 | Замены (`actual_subject_id`, все предметы) | — | `GET .../substitution-list` + `PATCH .../substitute` | GAP (статус replaced) |
| 23 | Отмена с счётчиком оценок | LessonRun `cancelConfirm` (graded в body) | `PATCH .../cancel` | ЧАСТ.: сверить серверный счётчик |
| 24 | Удаление занятия | `removeLesson` | `DELETE /api/lessons/:id` | OK |
| 25 | Статус / возврат в расписание | `setLessonStatus` | `PATCH .../status` | OK |
| 26 | Занятия по дате | `lessonsOn` (локально) | `GET /api/lessons/date/:date` | GAP (малый) |
| 27 | Отчёты substitutions/average/daily/neglected | Today-сводка (локальная) | `GET /api/reports/*` | GAP |
| 28 | Экспорт grades ×3 | `exportXlsx` (клиент, `<a download>`) | `GET /api/export/grades/:id.xlsx` + `POST .../to-downloads` + `POST .../share` | GAP → серверные POST (§3.4) |
| 29 | Экспорт report ×3 | — | `GET /api/export/report/:date.*` + to-downloads + share | GAP |
| 30 | Экспорт general ×3 (`shareGeneral`) | — | `GET /api/export/general.xlsx` + to-downloads + share | GAP |
| 31 | ICS lessons/schedule | — | `GET /api/export/lessons.ics`, `schedule.ics` | GAP |
| 32 | Шаринг-шторка (`_save_and_share` → `{path,shared}`) | — (`<a download>`) | `POST */share` | GAP: `<a download>` в WebView не работает |
| 33 | Бэкап SQLite (+WAL-checkpoint) | Settings JSON `exportBackup` | `POST /api/backup`, `/backup/share` | GAP: JSON≠SQLite, депрекейтить |
| 34 | Restore .db (upload/latest/named/pick/diag/access) | Settings JSON `importBackup` | `POST /api/restore*`, `GET /api/backup/list`, `/restore/pick/diag`, `/restore/access`, `/restore/request-access` | GAP: нового JSON-import эндпоинта нет |
| 35 | TG-бот (токен save/check/drop) | Settings tgToken-поле | `GET/POST/DELETE /api/settings/bot`, `GET .../bot/check` | ЧАСТ.: только поле |
| 36 | MAX-бот (токен + teacher unbind) | Settings maxToken-поле | `*/maxbot*`, `POST .../teacher/unbind` | ЧАСТ./GAP: unbind нет |
| 37 | Привязки студентов 📱📨 | GroupDetail иконки tg/max (read-only) | `GET /api/bot|/maxbot/links`, `DELETE .../by-student/:id` | GAP: unbind |
| 38 | Curator-code per-group (copy/unbind) | GroupDetail code+copy | `GET/DELETE /api/groups/:id/curator` | ЧАСТ.: unbind/regenerate нет |
| 39 | Teacher-code + teacherName | Settings code+copy+regenerate, name | серверного поля нет | GAP: teacherName негде хранить |
| 40 | Update-check/banner (`/api/version`, dismiss) | — (статика `2.0/0.121`) | `GET /api/version`, `/api/update/latest|check`, `POST .../download|install` | GAP |
| 41 | Темы `light|concept` (`data-theme`, switch) | Settings `light|dark` (`th-theme`) | localStorage | GAP: `dark→concept` remap; vanilla-CSS удалить (§3.5) |
| 42 | Аналитика (hero/heatmap/по предметам/лидеры+риск, `grades[s][l]`) | — (только Today-сводка) | `GET /api/subjects` + N×gradebook | GAP: экран целиком |

Итого: **42 фичи, 16 OK/маппится, 26 GAP-or-частичных (19 полных GAP: 4,5,7,15,22,26,27,28,29,30,31,32,33,34,37,39,40,41,42)**.
Импеданс (детали в §3): ФИО split/склейка; `assign≠create` (subject-per-group); time/room скрыть;
`actual_subject_id` замен; `GradeRec↔TEXT/null/DELETE` + среднее только 2–5; teacherCode vs per-group
curator codes + teacherName негде хранить; JSON-restore≠SQLite; `<a download>` в WebView не работает.

## 3. Архитектурное решение: A принято, B/C отклонены

**A (принято): полная замена фронта**, same-origin singlefile (`vite-plugin-singlefile` уже в `vite.config.ts`)
+ fetch-адаптер поверх `api.py`. Hash-роутер без rewrite (вариант `lib/router.ts` уже hash-based — оставить).
**B/C (отклонены):** iframe-гибрид / постепенный mount рядом с Vanilla (двойной CSS/стейт, рассинхрон кэшей, WebView-риски).

- (1) `api.py:index` отдаёт `dist/index.html` + `_static_ver` по **mtime dist** + `no-store`;
  hash-роутер без rewrite. Вход: `dist/index.html` собран. Выход: `GET /` → dist с `?v=STATIC_VER`.
- (2) api-client + инвалидация вместо `useSyncExternalStore/version`-счётчика и persist `th4-db-v2`;
  прод-флаг отключает seed/`mulberry32` и localStorage-кэш. Вход: клиент готов. Выход: ни одного чтения `th4-db-v2`/seed в прод-билде.
- (3) Write-path: оптимистичный UI с откатом; дебаунс тапов **длиннее серверных 10с/60с**
  (`GRADE_PUSH_DELAY=10`, `CURATOR_PUSH_DELAY=60`); bulk `POST attendance`; dedupe `find_held_lesson`.
  Вход: адаптер есть. Выход: шторм тапов = 1 settled-POST, откат при 4xx/5xx.
- (4) `xlsx.ts` удалить → `POST to-downloads|share` + тост про путь; JSON-бэкап депрекейтить
  (нового JSON-import эндпоинта нет — только SQLite restore). Выход: ни одного `<a download>`/client-xlsx.
- (5) Темы: только механика React (`th-theme`→`concept` remap); vanilla-CSS удалить со старым фронтом.
  Выход: один механизм тем, `prefers-color-scheme`-медиаблоков нет.
- (6) CI: Node `npm ci+build` **перед** buildozer; триггеры `main+redesign`; `?v=STATIC_VER`;
  смоук `minapi24` + тег отката. Выход: зелёный пайплайн + откат revert-ом одного файла.
- (7) В прод-дерево едет **ТОЛЬКО `dist/index.html`** (точечный `--include`, без `--include-untracked`).
  Выход: APK содержит dist, мусора (`node_modules`, `mobile-teacher-app-redesign (1)/(2)`, `*.db-wal`) нет.

## 4. Гейты приёмки (каждая фаза)

Вход фазы = выход предыдущей. Выход = все четыре гейта:

1. `pytest tests -q` — **239+ passed** (эталон v2: 327 passed);
2. `esprima parseScript` / `tsc` — без ошибок (пока жив старый фронт — esprima app.js; после замены — `tsc --noEmit` + `vite build`);
3. живой функц. тест против демо-стенда (расписание 8/8, PATCH-цепочки cancel/substitute, general.xlsx-сверка) — PASS, TEST-сущности зачищены;
4. ручная проверка **360×800**: двусторонний тап, календарь, bottom-sheet, тосты, тёмная тема.

## 5. Доставка файлов

- Новый фронт: `mobile-teacher-app-redesign/dist/index.html` (singlefile) → раздаётся из `api.py:index`.
- `api.py`: только `index` (`dist` + mtime-`_static_ver` + `no-store`); контракт/роуты/бот-таймеры (10с/60с) не трогать.
- В прод-дерево: только `dist/index.html` (точечный `--include`, без `--include-untracked`).
- Этот план: `docs/REACT-INTEGRATION-PLAN.md` (единственный новый файл) + короткая запись в `.slim/deepwork/redesign-v2.md`.

## 6. Топ-риски

1. **Импеданс моделей** (ФИО, `assign≠create`, `actual_subject_id`, `GradeRec↔TEXT/null/DELETE`, среднее только 2–5, коды) → фикстурные тесты маппинга до кода.
2. **Шторм тапов → боты** (каждый тап будит 10с/60с таймеры + пуши TG/MAX) → дебаунс длиннее серверного + bulk POST + откат.
3. **Вес 317KB + холодный старт + откат** → singlefile уже 317KB, бюджет держать, откат = revert одного файла + тег CI.

## 7. НЕ-цели

Схема БД, контракт API, логика ботов (таймеры/пуши), JSON-restore (эндпоинта нет — только SQLite),
time/room в новом UI (схемы нет — скрыть), новые отчёты/ICS, редизайн дизайна варианта.
