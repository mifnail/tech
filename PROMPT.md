# Prompt: Электронный журнал преподавателя (Flask + SPA + Android)

## Концепт

Мобильное веб-приложение для преподавателя: учёт занятий, посещаемости, замен, расписания. Работает как Flask-сервер, открывается в WebView на Android (buildozer). Никаких JS-фреймворков — чистая vanilla JS SPA.

## Стек

- **Backend**: Flask + SQLite (один файл `api.py` + `database.py`)
- **Frontend**: Vanilla JS SPA (один файл `static/app.js`), никаких фреймворков
- **Android**: Buildozer 1.6.0, NDK 25c, fullscreen=0
- **Экспорт**: reportlab (PDF), openpyxl (Excel), icalendar (ICS)
- **Тесты**: pytest, in-memory SQLite

## Архитектура

### База данных (SQLite, `database.py`)

**Таблицы:**
- `groups` — id, name (UNIQUE)
- `subjects` — id, name, total_hours, group_id → groups, is_free (0/1)
- `students` — id, group_id → groups, last_name, first_name, middle_name
- `lessons` — id, subject_id → subjects, actual_subject_id → subjects, date, status ('held'|'cancelled')
- `grades` — id, lesson_id → lessons, student_id → students, grade
- `schedule` — id, day_of_week (1-6), lesson_number, subject_id → subjects, week_type (0=каждую, 1=нечётная, 2=чётная)

**Ключевые решения:**
- `actual_subject_id` — всегда заполняется, равен `subject_id` для обычных занятий. Позволяет JOIN-ить для получения имени предмета.
- Статусы занятий: `'held'` (проведено), `'cancelled'` (отменено). Статус `'replaced'` удалён.
- Замена: исходное занятие → `cancelled` + удаление оценок, создаётся новое `held` занятие для предмета замены.
- СВОБОДНО — отдельный subject с `is_free=1`, создаётся автоматически при инициализации БД.
- Расписание: `week_type` (0=каждую, 1=нечётная, 2=чётная).
- Оценки: цикл `2→3→4→5→н→ос→пусто→2`.
- Экспорт: PDF (reportlab), Excel (openpyxl — импорт с guarded), ICS (icalendar).
- Gradebook: cross-table (студенты × занятия), `subject_gradebook` возвращает `(lessons, students, matrix)`.
- `confirm()` в WebView работает, но `delete` как имя метода — нет (зарезервированное слово).
- Импорт openpyxl констант — guarded (try/except на уровне модуля).
- Тесты: pytest, in-memory SQLite, фикстура `db` с `Database(':memory:')`, фикстура `client` с Flask test client.
