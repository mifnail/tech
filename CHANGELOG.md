# История изменений

Формат: версия, дата, список изменений. Версия совпадает с тегом релиза
и с номером прогона сборки: `VERSION` перезаписывается CI при сборке APK.

Номер версии = номер прогона GitHub Actions (`github.run_number`), поэтому
не все номера существуют: упавшие прогоны релиз не создают.

## 0.310 — 2026-11-07

Ошибки ботов перестали быть невидимыми, APK перестал тащить инструменты
разработки.

- Логирование ботов: 77 молчаливых `except` в `botcore.py`, `tgbot.py`,
  `maxbot.py` заменены на `logger` (warning — потеря результата, debug —
  ожидаемый fallback); `print` ушли в журнал; `MaxError`/`OSError` больше
  не глотаются молча
- Два потока журналов связаны: «Журнал бота» в настройках показывает
  события из `bot.log` и блок ошибок с трассировками из `flask.log`
- Удалён мёртвый `crash_reporter.py` (не вызывался нигде, умел отправлять
  отчёты в сеть); сторож в тестах не даёт ему вернуться
- `buildozer.spec`: выяснено, что в buildozer 1.6.0 `exclude_dirs` —
  префикс относительного пути, а не имя каталога на любой глубине.
  Добавлены полные пути для `node_modules`, `playwright-report`,
  `test-results`; `exclude_patterns` убирает из APK dev-инструменты и
  исходники CSS. Payload: 27 -> 16 файлов
- Эмуляция в `tests/test_buildozer_spec.py` переписана под реальную
  логику buildozer 1.6.0; новый сторож ловит раздувание APK (проверено
  мутацией: без полного пути уезжает 1677 файлов)

## 0.309 — 2026-11-07

Сопровождение вместо новых функций: приложение выросло до ~14 000 строк,
и дальше решают не «сгенерируй код», а архитектура, тесты, журнал и
версионирование.

- Документация под реальность: AGENT.md (React-стек, актуальная схема БД,
  правила журнала), MEMORY.md
- Удалены четыре папки дизайн-итераций — 18 499 файлов, ~380 МБ
- Правила игнорирования мусора перенесены из локального .git/info/exclude
  в коммитящийся .gitignore: раньше они терялись при клоне
- Автоматическая проверка состава APK: 13 тестов эмулируют отбор файлов
  buildozer и ловят забытые исключения
- Журнал бэкенда: flask.log рядом с базой, logger вместо print и тихих
  except (41 место), необработанные ошибки отдаются JSON, а не HTML
- «Журнал приложения» в настройках рядом с «Журналом бота»
- Прикладной слой вынесен из api.py в services.py: api.py 3111 -> 2650
  строк, conduct_lesson 203 -> 105 строк
- В триггер сборки APK добавлены services.py, log_config.py и фронтенд

## 0.4.0 — 2026-07-11
- Initial commit — LessonTracker (Kivy+SQLite, чистая архитектура)
- v0.4 — LessonScreen: проведение занятия + отметка посещаемости тапом по ФИО (цикл: отсутствует→✓→оценка)
- fix: замена buildozer-action на inline-шаги — сторонний action не проходит подготовку окружения
- fix: accept SDK license, pin p4a, export PATH — buildozer CI
- fix: pin NDK to r25c (r28c+clang 19 breaks Kivy C code with implicit function declaration errors)
- fix: remove duplicate test_database.py (collision with tests/test_database.py)
- wip: local changes
- Initial commit: LessonTracker v0.x — full project
- fix: default lesson status 'scheduled', seed uses 'held', add index, timezone in .ics
- fix CI: delete duplicate test, pin buildozer/Cython, add openpyxl, swap for OOM, arm64-only
- ui: theme system + card layout + grade color fix (5=green)
- ci: bump actions to latest (drop Node 20 deprecation)
- ui: fix layout — padding, spacing, button sizing, empty state, color bug
- ui: rebuild all screens with dp/sp, direct Button widgets, canvas bg, centering
- ui: remove canvas bg, fix padding tuple syntax for Android Kivy 2.3.0
- ui: outer+inner pattern to fix Android Screen sizing during on_pre_enter
- ui: defer all screen builds with Clock.schedule_once to fix Android sizing
- ui: build layout in __init__ (not on_pre_enter) to fix Android sizing
- replace Kivy UI with Flask + HTML/CSS/JS SPA
- fix Android crash: replace pywebview with jnius native WebView
- add crash reporter: file fallback + Telegram/webhook/Sentry transports
- switch to p4a webview bootstrap — zero Kivy, zero jnius

## 0.196 — 2026-09-09
- add schedule file + loader: 3 subjects/day, odd/even weeks from July 1
- fix: удалён дублирующийся роутер — кнопки навигации работают
- clean slate: keep only AGENT.md, restart project with new schema
- v0.1: initial schema (6 tables) + Flask API + SPA frontend + seed data
- v0.2: schedule parser, reports (Excel/PDF/iCal), crash reporter, CI/CD, tests
- v0.3: lesson status (held/free), substitution dialog, СВОБОДНО, new grade colors (0-green,5-red,4-blue,3-yellow,2-black)
- add SPECIFICATION.md — full system requirements and logic description
- v0.4: new navigation — home→subject→today, lesson journal, prev/next arrows
- v0.5: full test coverage — 103 tests (database API + integration) + fix student UNIQUE constraint + daily report serialization
- refactor: type hints (db), Blueprints + validation (api), modular JS (app.js)
- ux: popup animations, loading spinner, short nav tabs, rename 'пара'→'занятие' everywhere
- ci: add GitHub Actions workflow for APK build (test + buildozer android debug)
- gitignore: add bin/ directory
- ci: trigger build
- ci: fix missing flask in test job; add missing modules (calendar_export, crash_reporter, report_export, schedule_file, schedule.txt, requirements.txt, tests/__init__.py)
- ci: fix apt package names for ubuntu-latest (libncurses-dev instead of libncurses5-dev)
- ci: add Java 17 + caching + verbose for buildozer debug
- ux: remove #today nav tab, fix week types (числитель/знаменатель→нечетная/четная)
- ux: merge #subjects into #home, today card toggles schedule inline, group management on main page
- fix: grade cycle now calls App.Pages.lesson (not renderLesson), empty grade deletes record (fixes unmarking)
- ci: fix exit code masking (remove | tail -50), update actions to latest versions
- ci: fix build-tools license, fix deprecated buildozer keys (android.bootstrap->p4a.bootstrap, android.arch->android.archs, remove android.sdk)
- Fix APK build: update buildozer.spec to use latest python-for-android
- build: комбинированный конфиг из успешной сборки #37 и текущего
- Revert configs to 09c51d2 baseline
- build: merge params from successful run #37 (fullscreen, p4a.port, allow_backup, buildozer 1.6.0, swap)
- build: точная копия рабочего конфига из run #37 (a3c80db) + flask в тесты
- build: улучшения поверх рабочего конфига — package identity, txt include, gradle deps, чистка test deps
- feat: default DB с 3 группами, 5 студентами, 2 предметами по 100ч, 6-дневкой
- fix: skip seed_default for :memory: DB (fixes tests)
- fix: СВОБОДНО→Отмена, замена→replaced+очистка оценок, seed 1 группа
- feat: Начать занятие сразу held, кнопки Заменить/Отменить, ведомость-таблица
- feat: экспорт отчётов (PDF/Excel) + расписание в ICS для Google Calendar
- fix: guarded module-level openpyxl constants (CI без openpyxl/reportlab)
- fix: delete→_delete (reserved word), substitution cancels original + creates new lesson
- fix: avg grades only 2-5, schedule edit (PATCH), today filter by week_type
- chore: hollow push, test CI pipeline
- feat: delete student/group/subject (point 1)
- feat: edit student/group/subject (point 2)
- feat: date format DD.MM.YYYY (point 3)
- feat: delete lesson (point 4)
- feat: allow duplicate lessons per day (point 5)
- feat: download export via fetch+blob (point 6)
- feat: share sheet after download (point 7)
- docs: update SPECIFICATION.md with complete architecture and roadmap
- Update .gitignore
- Update AGENT.md
- Update PLAN.md
- Update PROMPT.md
- Update api.py
- Update buildozer.spec
- Update calendar_export.py
- Update crash_reporter.py
- Update database.py
- Update docs/SPECIFICATION.md
- Update main.py
- Update report_export.py
- Update requirements.txt
- Update schedule.txt
- Update schedule_file.py
- Update seed_db.py
- Update static/app.js
- Update static/style.css
- Update templates/index.html
- Update tests/__init__.py
- Update tests/integration_test.py
- Update tests/test_api.py
- Update tests/test_database.py
- Update build-apk.yml
- Update .coverage
- Update .gitignore
- Update AGENT.md
- Update PLAN.md
- Update PROMPT.md
- Update api.py
- Update buildozer.spec
- Update calendar_export.py
- Update crash_reporter.py
- Update database.py
- Update docs/SPECIFICATION.md
- Update main.py
- Update report_export.py
- Update requirements.txt
- Update schedule.txt
- Update schedule_file.py
- Update seed_db.py
- Update static/app.js
- Update static/style.css
- Update templates/index.html
- Update tests/__init__.py
- Update tests/integration_test.py
- Update tests/test_api.py
- Update tests/test_database.py
- fix: удаления и редактирование (database + app.js) real FK + UI
- fix: удаления и редактирование (database + app.js) real FK + UI
- fix: review - WAL, IntegrityError handling, XSS esc (oracle review)
- fix: review - WAL, IntegrityError handling, XSS esc (oracle review)
- fix: review - WAL, IntegrityError handling, XSS esc (oracle review)
- fix: DB protection + seed guard + gitignore + WAL + push lessons.db (database.py)
- fix: DB protection + seed guard + gitignore + WAL + push lessons.db (api.py)
- fix: DB protection + seed guard + gitignore + WAL + push lessons.db (static/app.js)
- fix: DB protection + seed guard + gitignore + WAL + push lessons.db (.gitignore)
- fix: DB protection + seed guard + gitignore + WAL + push lessons.db (seed_db.py)
- fix: DB protection + seed guard + gitignore + WAL + push lessons.db (lessons.db)
- fix: Android persistent DB path + buildozer.db (database.py)
- fix: Android persistent DB path + buildozer.db (buildozer.spec)
- fix: scroll to student after grade tap (att-static/app.js)
- fix: grades cycle in-place DOM update, no page re-render
- fix: scroll stays in place when tapping student to cycle grade (in-place DOM update)
- feat: 5x5 tile grid for lesson attendance (bypass WebView scroll reset) + revert scroll hacks
- fix: fixed 5x5 tiles, grade as background, fio scales inside tile
- feat: 2-column lesson attendance list, compact header/footer (<=10%), subject name ellipsis truncation
- fix: export deps+CSV fallback, lesson dedup, adjacent/sort by (date,number,id), journal pair numbers + clickable gradebook
- ci: retry buildozer build up to 3 times (savannah 502 workaround)
- ci: trigger rebuild (spec note about savannah 502 + retries)
- ci: 5 build attempts with backoff, workflow triggers on itself
- ci: spec note about 5-attempt retry (triggers rebuild)
- fix: drop reportlab from APK requirements (savannah freetype 502 breaks build); XLSX+CSV stay
- ci: build android release (stable signing key)
- fix: stable release signing key so APK updates install without conflict
- fix: release_artifact=apk so CI uploads installable signed APK, not aab
- ci: trigger build on yandex_publish.py changes
- feat: auto-publish gradebook to teacher Yandex Disk (settings, debounce, copyable link)
- ci: verify APK signature before upload
- ci: convert PKCS12 keystore to JKS before release build (apksigner compat)
- fix: sign release with JKS converted in CI (PKCS12 produced invalid package)
- ci: sign release APK explicitly with apksigner (buildozer skips signing)
- ci: fix apksigner pass syntax (--ks-pass pass:...)
- fix: white screen on launch (flatten pagehide handler nesting that broke JS parsing)
- fix: yandex disk SSL on Android (certifi + fallback to unverified context)
- ci: remove yandex_publish trigger
- revert: cancel yandex publish feature, fix excel sheet title sanitization
- feat: keep only Excel exports, headers number+date, hide PDF/CSV/ICS buttons
- ci: install openpyxl for xlsx export tests
- ci: autobump version 0.N + cache restore-keys
- fix: stored XSS escaping, drop dead export code, cancel-lesson grade count, onerror overlay, quiet share
- diag: include openpyxl import error detail in export message
- fix: bundle et_xmlfile (openpyxl hard dep missing on device)
- feat: auto-share downloaded file via system share sheet (WebView download is unreliable)
- ci: trigger build on tgbot.py changes
- feat: telegram bot read-only grades (polling, bind by surname, settings UI)
- fix: define _maybe_start_bot before use (NameError crashed app on launch)
- fix: bot SSL fallback via shared path; native save-to-Downloads for WebView without share
- fix: pyjnius nested classes via $ (Build$VERSION, MediaStore$Downloads)
- fix: android context via PythonActivity or ActivityThread fallback
- feat: native ACTION_SEND share sheet after saving xlsx to Downloads
- fix: share intent via ClipData (putExtra overload rejected Uri)
- fix: overwrite same-name file in Downloads (Failed to build unique file)
- feat: export test stand (clip/extra/save modes + diag endpoint)
- feat: export stand round 2 (wild mime, handler counts, launch test)
- fix: share via cast(Parcelable) — proven pattern from androidstorage4kivy
- feat: chooser variants matrix (none-title, JString, direct)
- ui: keep H/I share variants + save, drop other test buttons
- ui: Excel button now shares via native sheet (I-variant), test stand removed
- feat: MAX messenger bot (grades push, summary, evening reminders)
- feat: backdated lesson creation (date picker, future rejected)
- ui: grade cycle direction from tap position (left=back, right=forward)
- docs: project README (features, stack, APK, bots, roadmap)
- refactor: keep proven cast+direct share, drop test stand, share report button
- feat: teacher reminder badges for unfilled lessons (needs_attention)
- feat: DB backup/restore + MAX files and buttons (items 4, 6)
- docs: Mermaid diagrams for students + slides links
- docs: brief theory notes under each diagram
- fix: MAX updates path /messages/updates -> /updates (was HTTP 400)
- robustness: retry TG getMe on connection resets (flaky networks)
- ui: lesson date via day steppers + presets (native picker dead in WebView)
- feat: 10s debounce on grade push (only settled grade sent)
- ui: backdate stand (presets, manual DD MM YYYY, stored-date result)
- fix: cache-bust static assets (WebView served stale app.js after update)
- feat: global create-lesson (subject picker + date) and build number footer
- ui: green date-capable buttons replace dateless blue ones, drop unfilled badges
- feat: MAX update_type fix, upload SSL fallback, 5 bot features, calendar entry
- refactor P1: backend helpers (notify, row_get), group_id column, dead lines
- refactor P2: shared botcore transport, thin bot wrappers
- refactor P3: single schedule renderer, single creation entry, dead sweep
- feat: persistent reply keyboard in TG bot (grades/today/help/unbind)
- feat: MAX message-type buttons row (schedule, avg, debts)
- privacy: disable group vedomost file in MAX bot
- feat: personal MAX vedomost (single-student xlsx row)
- fix: read MediaStore backup via fd (stream read() returned int)
- feat: notify teacher on new MAX student bind
- ci: trigger build on maxbot/botcore/tests changes
- feat: group curator (code, 3min grade push, group vedomost)
- docs: refresh README and architecture diagram (bots, curator, backup)
- robustness: supervisor auto-restart for bot polling + busy_timeout
- fix: teacher bare-code bind + teacher post-bind routing (vedomost/help)
- fix: 44px tap targets (WCAG) — attendance, badge, calendar
- fix: curator push group resolution via actual_subject_id + fallback
- feat: in-app updater from GitHub releases (check/download/install banner)
- docs: MIT license, privacy policy, RuStore pack + TG warning + donate (boosty.to/mifnail/donate)

## 0.198 — 2026-09-09
- feat: dark concept build on CI (concept+workflow+spec)
- ci: drop stale Chrome repo before apt update (hash mismatch)

## 0.199 — 2026-09-09
- feat: manual dark theme for Android 7+ (tokens, toggle, offline fonts) + CI chrome fix

## 0.200 — 2026-09-10
- feat: mobile redesign frontend wired to Flask API (React/Vite singlefile)

## 0.201 — 2026-09-10
- fix: restore latest scans Download/ dir directly (MediaStore misses index)

## 0.202 — 2026-09-10
- refactor(t1): centralize grade colors into CSS tint classes, drop inline bgColor map
- ui(t2): fixed bottom nav + floating new-lesson FAB (smartphone-first)

## 0.203 — 2026-09-10
- без изменений

## 0.204 — 2026-09-10
- feat: manual backup picker (list + rename restore) for Android

## 0.205 — 2026-09-10
- feat: native Android document picker to restore arbitrary DB file

## 0.206 — 2026-09-10
- fix: native picker — bind+launch on UI thread, direct ACTION_OPEN_DOCUMENT, diag endpoint

## 0.207 — 2026-09-10
- fix: fs fallback glob.join->os.path.join + WAL checkpoint before backup read

## 0.208 — 2026-09-10
- feat: broad backup scan (any *.db in Downloads, paths shown, teachhelper first)
- fix: threaded Flask, URI-only picker callback, Android-aware backup card, skip autobackups in latest

## 0.209 — 2026-09-10
- без изменений

## 0.210 — 2026-09-10
- feat: MANAGE_EXTERNAL_STORAGE access flow for full Download scan (P1)

## 0.211 — 2026-09-10
- fix: picker never raises (503/JSON), detect availability, JSON-safe API client
- chore: bundle working DB snapshot for APK build (temporary)

## 0.213 — 2026-09-10
- feat: bot backup/restore via MAX + current DB (32 students, 143 grades)

## 0.214 — 2026-09-10
- fix: no more silent file-restore paths (db errors + shape mismatch reply)

## 0.215 — 2026-09-10
- ui: visible build number in settings footer

## 0.216 — 2026-09-10
- fix: read file attachments from message body (real MAX shape)

## 0.217 — 2026-09-10
- fix: raw response helper for binary file download (dict has no read)

## 0.218 — 2026-09-10
- fix: persist marker before file restore + preserve bindings across restore

## 0.220 — 2026-09-10
- rename product to Uchet + drop redundant backup buttons
- fix: include P1 api.py/database.py missed in previous push (validate kwarg, group_id)

## 0.221 — 2026-09-11
- Validation hardening: min-size 100B, quick_check, sqlite3.Error->ValueError, clearer restore error

## 0.222 — 2026-09-11
- README: updater, validation hardening, bot invite links, 326 tests
- TEMP DEBUG: curator push delay 180s -> 10s to diagnose missing pushes

## 0.223 — 2026-09-11
- без изменений

## 0.224 — 2026-09-11
- Curator push delay: 60s operating value (was 180, debugged at 10)

## 0.225 — 2026-09-11
- Update README.md
- Fix DB leak into APK: exclude .db from build, fresh init, gitignore; README trimmed for users page
- Remove hardcoded author bot links; TG share is runtime-only, MAX card plain

## 0.226 — 2026-09-11
- без изменений

## 0.237 — 2026-09-12
- redesign: легкий журнал P1-P5 (app.js/style.css/index.html)
- ci(redesign): собирать APK и на ветке redesign
- redesign v2: visual system transfer (app.js, style.css, index.html)
- redesign: экран Аналитики read-only + 4-й таб + CountUp
- redesign: кнопки ✎/✕ с главной внутрь предмета и группы
- redesign hotfix: _renderStats вызывался не у того объекта (вечный спиннер занятия)
- redesign: замена — все предметы преподавателя (аудит кнопок чист)
- redesign: чиню молчание confirm-диалогов + убираю удаление записей расписания
- redesign analytics: чиню ключи grades (риск/лидеры/heatmap)
- redesign: общий отчёт по всем предметам (мульти-лист) на кнопке главной
- redesign: вторая тема concept (тёмный порт) + переключатель

## 0.239 — 2026-09-13
- react phase1: Flask отдаёт dist + read-адаптер (запись сессионная)
- react phase2: write-path мутаций на API (optimistic+debounce+bulk)
- react UX-пакет: flush оценок, предметы, Аналитика, донат, № пары
- react UI-полировка по дефектовке скринов (шит, формы, график, чипы)
- react: среднее только 2–5 + кнопка предмета на главной
- react: чистка настроек, таб Предметы и группы, шит студента, предметы в Начать занятие
- react: шит Начать занятие через портал поверх навбара
- react: Ведомость в Аналитике + сводка расхождений main vs redesign
- react: боты вкл-выкл и отвязки + .db бэкап-рестор
- react: серверный экспорт ведомости + депрекейт JSON-бэкапа
- react: баннер обновлений + О приложении в Настройках
- react: тап по должникам на главной → список

## 0.240 — 2026-09-13
- react: фикс версий mtime vs semver + VERSION
- react: порог должников <3 + подпись версии внизу Настроек

## 0.241 — 2026-09-13
- react: блок По предметам в Сводке Сегодня с прогрессом
- react: прогресс По предметам held/total_hours + должники без оценок или ср<3
- ci: триггерить сборку APK также на VERSION и mobile-teacher-app-redesign

## 0.242 — 2026-09-13
- react: баннер не показывается повторно после Установить (запоминает версию)
- react: Н для отсутствующих, . для не выставленных (ведомости и оценивание)
- react: 0 убран из цикла оценок, Н серая невзрачная
- react: 0 в БД показывается как . в интерфейсе и отчетах, Н для отсутствовавших

## 0.243 — 2026-09-13
- без изменений

## 0.244 — 2026-09-13
- без изменений

## 0.245 — 2026-09-13
- react: баннер лаконично Доступно обновление X, тап → описание изменений

## 0.246 — 2026-09-13
- без изменений

## 0.247 — 2026-09-13
- react: баннер не показывается повторно после Скачать, VERSION 0.241
- revert VERSION to 0.237, keep banner via markInstalled

## 0.248 — 2026-09-13
- без изменений

## 0.249 — 2026-09-13
- react: расписание без чёт/нечёт, ручные занятия с пометкой

## 0.250 — 2026-09-13
- react: вернуть ленту дат в Расписание (тап → занятия дня)

## 0.251 — 2026-09-13
- react: Среднее в ведомости после ФИО + фикс тап Восстановить БД
- react: тап по дате в расписании → список занятий дня по группам

## 0.252 — 2026-09-13
- react: расписание контент по выбранной дате (без Sheet)
- react: главный экран статистика по предметам вместо последних занятий

## 0.253 — 2026-09-13
- без изменений

## 0.254 — 2026-09-13
- без изменений

## 0.255 — 2026-09-13
- react: Восстановить базу через label (фикс тап в WebView)

## 0.258 — 2026-09-14
- Учёт занятий: локальный API, строгая валидация БД, pipeline restore, React-восстановление базы, тесты
- merge e94ef48: чиню main.tsx/restore-input/tsconfig + пересобранный dist
- tests: чиню 24 старых теста под новый бэкенд e94ef48, CI зелёный

## 0.259 — 2026-09-14
- react: UI замены занятия в LessonRun (#22)

## 0.260 — 2026-09-14
- react: правки группы/студента/пары (#2/#5/#15)

## 0.261 — 2026-09-14
- react: bulk-студенты списком + future-guard

## 0.262 — 2026-09-14
- react: предмет edit/delete + VERSION авто из CI

## 0.263 — 2026-09-14
- apk: иконка приложения icon-512.png в buildozer.spec

## 0.264 — 2026-09-15
- react: проверка обновлений из главной в Настройки

## 0.265 — 2026-09-15
- react: двусторонняя лента дат в расписании

## 0.266 — 2026-09-16
- bot: громкий лог поллинга + /check без 500; README упаковка

## 0.267 — 2026-09-16
- bot: возврат SSL-fallback как 11.09 + статус ботов в Настройках

## 0.268 — 2026-09-16
- bot: проверка и сброс webhook в Настройках

## 0.269 — 2026-09-16
- tests: tz-robust recent_grades + docs REPO-SETUP

## 0.270 — 2026-09-16
- risk=debtor rule; убрать REQUEST_INSTALL_PACKAGES для модерации

## 0.271 — 2026-09-16
- react: убраны приветствие и имя препода

## 0.272 — 2026-09-16
- conduct: кнопка Провести + немедленные пуши с дедупом

## 0.273 — 2026-09-17
- ios: фаза 0 спайк (1/5)
- ios: фаза 0 спайк (2/5)
- ios: фаза 0 спайк (3/5)
- ios: фаза 0 спайк (4/5)
- ios: фаза 0 workflow сборки IPA
- ios фаза 1: Briefcase-скелет реального приложения

## 0.275 — 2026-09-17
- ios фаза 2: иконки, версия, гейт апдейта
- ios: чинить YAML workflow (кавычки в name)
- tests: PIL-гейт для CI без Pillow (чинить APK-сборку)
- ios: Pillow до валидации иконок

## 0.276 — 2026-10-12
- react: тап по предмету с главной сразу в ведомость

## 0.277 — 2026-10-12
- react: убрать молчаливый фриз навигации при грязных оценках

## 0.278 — 2026-10-13
- Расписание: кнопка Начать занятие при непустом дне (ретро-ввод проведенных)
- CI: отключены iPhone-сборки (build-ios.yml), только Android

## 0.279 — 2026-10-13
- Тесты: фикс 4 pre-existing fail (vm-realm Error, extensionless cn, style-атрибут)
- Стенд: stand.py/stand_seed.py (фазы static/backend/api/e2e, tripwire lessons.db), Playwright e2e (6 сценариев), фронт-файлы для CI
- CI: test-stand.yml — полный прогон стенда (static/backend/api/e2e) на windows-latest

## 0.280 — 2026-10-13
- без изменений

## 0.281 — 2026-10-14
- CI: build-apk пишет VERSION из run_number — футeр версии в приложении совпадает со сборкой

## 0.282 — 2026-10-19
- curator: batch notification after 'conduct' with new format (date/subject/lesson number/list of students-grade/absent list)

## 0.283 — 2026-10-19
- reconcile: held status + pair cards + group colors

## 0.284 — 2026-10-19
- Журнал: прошедшие пары проведены, вторая пара дня видна
- Убрать базы с реальными данными из репозитория
- e2e: догнать компактный статус и новый текст тоста

## 0.285 — 2026-10-19
- без изменений

## 0.286 — 2026-10-19
- APK: не тащить в сборку отчёты тестов и чужие дизайн-итерации

## 0.287 — 2026-10-19
- Расписание: пара действует с даты создания; тап по слоту ведёт в ведомость

## 0.288 — 2026-10-20
- Куратору — полный состав пары: присутствующие и отсутствующие
- Сводка куратору: цветовые маркеры состояния студента

## 0.289 — 2026-10-20
- без изменений

## 0.290 — 2026-10-20
- Test stand: починен UnicodeEncodeError на Windows-раннере

## 0.291 — 2026-10-20
- Расписание: плоский список дня вместо группировки по группам
- Группа под номером пары читается: отдельный цвет для нейтрального фона

## 0.292 — 2026-10-20
- без изменений

## 0.293 — 2026-10-20
- Подпись группы под номером пары крупнее: 9.5 → 10.5px

## 0.294 — 2026-10-20
- Интерфейс: четыре мелких визуальных правки

## 0.295 — 2026-10-20
- Аналитика: график идёт по датам, а не в порядке загрузки

## 0.296 — 2026-10-22
- reconcile: held status + pair cards + group colors

## 0.297 — 2026-10-23
- Откат мусора из чужого коммита f7d6ac0

## 0.298 — 2026-10-23
- Проведённым делает ведомость, а не прошедшая дата
- Резервная копия базы перед установкой обновления

## 0.299 — 2026-10-23
- без изменений

## 0.300 — 2026-10-23
- Оценки уходят только по «Провести»; напоминание о незаполненных занятиях
- Уведомления о проведении: единый формат куратору и студентам

## 0.301 — 2026-10-23
- без изменений

## 0.302 — 2026-10-23
- Стенд: тест фоновой записи переписан под новое поведение

## 0.303 — 2026-10-25
- Повторное «Провести» без изменений молчит

## 0.304 — 2026-10-26
- MAX-бот: видно, живой ли он, и можно перезапустить

## 0.305 — 2026-11-01
- Завершение миграции: удалён legacy Vanilla JS, остаётся React

## 0.306 — 2026-11-01
- Дайджест с незаполненными парами, журнал бота, экспорт в календарь, чистка доков, e2e

## 0.307 — 2026-11-01
- Вычитка предмета: предупреждение перед последней парой и уход из расписания

## 0.308 — 2026-11-02
- Предупреждение о паре сверх часов

