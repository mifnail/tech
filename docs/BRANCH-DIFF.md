# BRANCH-DIFF: что видит пользователь — main vs redesign

> Только чтение + этот файл. Код не менять, не пушить.
> `main` = Vanilla SPA (`static/app.js` + `api.py`). `redesign` = React-вариант
> (`mobile-teacher-app-redesign/`, 8 экранов incl. `Analytics.tsx`, `dist/index.html` ≈ 317KB).

## 1. Факты веток (GitHub REST API, только GET; токен из `D:\tech\.gh_token`, не печатается)

- `main` = `c6e4e64a414ec0df9c663de1872e5c5bdc900f22` (Merge PR #1 from redesign).
- `redesign` = `af9b075870cf04df4a4dce9b4f971695af6bfd8e` (ушла вперёд после мержа).
- `compare(main...redesign)`: `diverged`, `ahead 7 / behind 1`
  (behind 1 = мерж-коммит `c6e4e64a` на main; ahead 7 = работа после мержа):

| SHA | Коммит |
|---|---|
| `bcd6e88` | react phase1: Flask отдаёт dist + read-адаптер (запись сессионная) |
| `cb8ce31` | react phase2: write-path мутаций на API (optimistic+debounce+bulk) |
| `93afe15` | react UX-пакет: flush оценок, предметы, Аналитика, донат, № пары |
| `2d16e8c` | react UI-полировка по дефектовке скринов (шит, формы, график, чипы) |
| `52cc942` | react: среднее только 2–5 + кнопка предмета на главной |
| `7fbd54c` | react: чистка настроек, таб Предметы и группы, шит студента, предметы в «Начать занятие» |
| `af9b075` | react: шит «Начать занятие» через портал поверх навбара |

Файлы: `api.py` modified (+12/−8); добавлен `docs/REACT-INTEGRATION-PLAN.md` (+125);
добавлен React-фронт (19 файлов: `App`, `NewLessonSheet/shell/ui`, `lib/*` без `xlsx.ts`,
8 экранов incl. `Analytics.tsx`, `vite-env`) + `dist/index.html` (+48).

**Дельта бэкенда main→redesign — только выдача:** `_static_ver` теперь mtime
`mobile-teacher-app-redesign/dist/index.html`; `index()` отдаёт dist + `no-store`
(+ doctype-правка и комментарий вместо `/static/*`). Контракт/роуты/таймеры ботов (10с/60с)
не тронуты. General-отчёт (`/api/export/general*`) — **до мержа**, уже в main
(проверено: есть в main-эквивалентном дереве, в этих 7 коммитах бэкенд-дельты нет).

## 2. Таблица пользовательских отличий (27 строк)

Формат: фича | main (vanilla) | redesign (React) | статус.

| Фича | main (vanilla) | redesign (React) | Статус |
|---|---|---|---|
| Фронт/выдача | Vanilla SPA: `app.js`+`style.css`, `?v=` по mtime | Singlefile `dist/index.html`, `?v=` по mtime dist, `no-store` | ПОКРЫТО (замена) |
| Темы | `light\|concept`, ручной тоггл (`data-theme`, meta theme-color) | `light\|dark` (`th-theme`), Segmented | ЧАСТИЧНО (нужен remap `dark→concept`) |
| Сегодня/Главная | Группы+предметы+today+сводка, «Поделиться отчётом» (general) | Приветствие, пары дня, вчерашние, сводка, «Начать занятие» (шит через портал) | ПОКРЫТО |
| Группы | CRUD incl. rename (ряд Назад/Изменить/Удалить) | Список+поиск, add/remove | ЧАСТИЧНО (rename нет) |
| Студенты | Bulk-добавление, edit ФИО, delete, поиск | По одному, delete, фильтр | ЧАСТИЧНО (bulk/edit — GAP) |
| Предметы | CRUD + `total_hours`, таб «Предметы», ряд Ведомость/Редактировать/Удалить | Add + assign/unassign, таб «Предметы и группы», кнопка предмета на главной | ЧАСТИЧНО (hours/edit/delete — GAP) |
| Расписание | CRUD (✕ убран, только edit), чётность, today, занятие из записи | Лента недели, чёт/неч, add/remove, занятие из пары | ЧАСТИЧНО (edit записи — GAP) |
| Создание занятия | Календарь (future-disable), дубли ок, FAB | Шит «Начать занятие» (+предметы), future-guard — проверить | ПОКРЫТО |
| Проведение/тап | Двусторонний тап (CYCLE), живые статы, adjacent | Двусторонний тап, живые статы, prev/next; запись: optimistic+debounce+bulk | ПОКРЫТО |
| Замены | Все предметы, `PATCH substitute`, `actual_subject_id` | Нет UI | GAP |
| Отмена/удаление | Confirm-цепочки, счётчик оценок | ConfirmSheet, graded в тексте, возврат в расписание | ПОКРЫТО |
| № пары | `lesson_number` в карточках/ведомости | `lessonNumber` в шапке занятия | ПОКРЫТО |
| Ведомость | Gradebook + кликабельные даты + average | Сетка + кликабельные даты + тренд + распределение | ПОКРЫТО |
| Среднее | Сервер (`average_grade`) | Только 2–5 (`52cc942`) | ПОКРЫТО (паритет) |
| Аналитика | Hero + heatmap 14д + по предметам + лидеры/риск | `Analytics.tsx` (порт) | ПОКРЫТО (паритет сверить) |
| Экспорт grades | Сервер ×3 (GET/to-downloads/share) + тост про путь | Клиентский `downloadXlsx`, но `lib/xlsx.ts` **нет в ветке** (импорт висит) | GAP (на серверные POST) |
| Экспорт report/general | ×3 + `shareGeneral` на главной | Нет | GAP |
| ICS | `lessons.ics` / `schedule.ics` | Нет | GAP |
| Шаринг-шторка | `_save_and_share` → `{path, shared}` | Нет (`<a download>` в WebView не работает) | GAP |
| Бэкап | SQLite `.db` + WAL-checkpoint + share | JSON `lessons-backup.json` | GAP (JSON депрекейтить) |
| Restore | upload/latest/named/pick/diag/access | JSON `importBackup` | GAP (эндпоинта нет) |
| TG-бот | Токен save/check/drop, привязки/отвязки 📱 | Поле токена, read-only флаги | ЧАСТИЧНО (check/drop/unbind — GAP) |
| MAX-бот и коды | Токен, teacher-unbind, curator-code per-group + copy/unbind | Поля, teacherCode + copy + локальный regen, curator-code + copy | ЧАСТИЧНО (unbind — GAP; teacherName негде хранить) |
| Update-flow | `version` + check/download/install + banner + dismiss | Нет (About убран) | GAP |
| About/демо в настройках | Версия, баннер обновлений | Убраны; остался донат «Поддержать автора» (Boosty) | УБРАНО осознанно |
| Кнопки/перестановки | Ведомость/Ред/Удалить (предмет), Назад/Изменить/Удалить (группа) | Своя компоновка (шит-меню, табы) | По варианту (действия — см. GAP выше) |
| `legacy.js` в выдаче | Нет (один bundle `app.js`) | Нет (один bundle dist; `xlsx.ts` в ветку не взят) | НЕТ (чистить нечего) |

## 3. В redesign УЖЕ покрыто

Фронт-dist, Today/Groups/GroupDetail/Schedule/Statement/LessonRun/Settings/Analytics,
двусторонний тап + живые статы + prev/next, отмена/счётчик/удаление/возврат, № пары,
ведомость с кликабельными датами, среднее 2–5, read-адаптер (groups/subjects/students/
schedule/today/links/curator/gradebook/attendance/adjacent/maxbot), write-path
(optimistic + debounce + bulk attendance), шит «Начать занятие» через портал.

## 4. GAP (что умеет main, но не умеет redesign)

Замены (substitute UI); edit записей расписания / rename групп / bulk и edit студентов /
hours-edit-delete предметов; отчёты `reports/*` и история оценок студента; экспорты
report/general/ICS и серверные POST grades (client-xlsx висит на отсутствующем `xlsx.ts`);
шаринг-шторка; SQLite-бэкап/restore (JSON — депрекейтить, эндпоинта нет); check/drop/unbind
ботов и привязок; update-flow целиком; `dark→concept` remap; teacherCode-regen только
локален (серверного поля нет); код группы в React локальный, не серверный
(`ensure_curator_code`); time/room скрыты (схемы нет).

## 5. УБРАНО осознанно

About/демо-разделы настроек (живая версия, баннер обновлений, сброс демо) — в ветке хвост
настроек = «Поддержать автора»; ✕ записей расписания (в main и так снят; в React удаление
только через шит-подтверждение); `legacy.js` из выдачи (bundle всегда один).
