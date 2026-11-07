# AGENT.md — правила проекта «Учет занятий»

> Этот файл — «конституция» проекта для AI-агента и для людей.
> **Читать в начале КАЖДОЙ сессии.** Стек и архитектура зафиксированы ниже.

## 1. Цель проекта
Мобильное приложение (Android/APK) для преподавателя: учёт проведённых занятий,
посещаемости и успеваемости по предметам и группам.

**Единица учёта — ЗАНЯТИЕ**, не академический час.
У предмета есть план в часах; контролируем проведённые / оставшиеся занятия.

## 2. Стек (НЕ менять без явного согласования с владельцем)
- Язык: **Python 3**
- Бэкенд: **Flask** (REST API)
- Фронтенд: **React + TypeScript + Vite** (`mobile-teacher-app-redesign/`)
- БД: **SQLite** (модуль `sqlite3` из стандартной библиотеки)
- Боты: **stdlib + certifi** (long-polling в фоне, общий транспорт — `botcore.py`)
- Мобильная сборка: **WebView** (python-for-android) / Buildozer
- Сборка APK: **только GitHub Actions**. Локально APK НЕ собираем.

### Запрещённые зависимости
- **matplotlib, numpy, pillow** — тяжёлые нативные колёса.
- **Kivy** — полностью удалён, UI через WebView.
- Любая новая зависимость добавляется только после согласования.

## 3. Архитектура (модульная, весь SQL изолирован)

### Схема БД (английские названия)
```
groups (id, name)
  ├── subjects (id, name, total_hours, group_id, closed_at)
  │     └── schedule (id, day_of_week, lesson_number, subject_id, week_type, valid_from)
  │     └── lessons (id, subject_id, actual_subject_id, date, status, lesson_number)
  │           └── grades (id, lesson_id, student_id, grade)
  ├── students (id, group_id, last_name, first_name, middle_name)
  ├── curators (group_id, chat_id, code, created)
  ├── bot_links (chat_id, student_id, created)    — Telegram
  └── max_links (chat_id, student_id, created)     — MAX
app_settings (key, value)                          — токены, код преподавателя
```

### Модули
- `database.py` — ВЕСЬ доступ к SQLite (схема, миграции, запросы).
- `api.py` — Flask REST API (HTTP-роуты, валидация, экспорт, бэкап).
- `main.py` — точка входа Flask + фоновые боты.
- `botcore.py` — общий HTTP-транспорт ботов (SSL, ретраи, тексты).
- `maxbot.py` — MAX-бот: сводки, файлы, пуши, напоминания, кураторы, дайджест.
- `tgbot.py` — Telegram-бот «Мои оценки» (read-only + постоянная клавиатура).
- `calendar_export.py` — экспорт расписания/занятий в .ics.
- `report_export.py` — ведомости `.xlsx` (групповая и личная).
- `schedule_file.py` — парсер schedule.txt.
- `crash_reporter.py` — обработка исключений.
- `seed_db.py` — тестовая БД.
- `mobile-teacher-app-redesign/` — фронтенд: исходники + `dist/index.html` (то, что раздаёт сервер и едет в APK).
- `tests/` — автотесты (pytest, 586+).
- `mobile-teacher-app-redesign/tests/` — фронтенд-тесты (node --test).
- `mobile-teacher-app-redesign/e2e/` — Playwright-тесты.

## 4. Definition of Done
1. Код запускается на ПК без ошибок.
2. Автотесты зелёные (`python -m pytest tests/ -q`, `node --test tests/*.cjs`).
3. Изменение закоммичено с осмысленным сообщением.
4. Проверено в браузере на мобильном viewport.

## 5. Правила процесса
- **Вертикальные срезы:** доводим один пункт до рабочего состояния и коммитим.
- **Ручная проверка:** каждый срез перед коммитом проверяется человеком.
- **Фиксируем маленькие победы:** каждый рабочий срез — отдельный коммит.
- **Релиз:** при коммите-релизе обновлять `VERSION` и `CHANGELOG.md`.

## 6. Сборка APK (CI)
- Триггер: push в репозиторий.
- Тип: debug-APK (без подписи).
- Workflow: `.github/workflows/build-apk.yml`.

## 7. Основные запросы к БД
- Создать занятие: `INSERT INTO lessons (subject_id, actual_subject_id, date, status) VALUES (?, ?, ?, 'scheduled')`
- Оценки за занятие: `INSERT INTO grades (lesson_id, student_id, grade) VALUES (?, ?, ?)`
- Остаток часов: `SELECT total_hours - COUNT(*) FROM subjects LEFT JOIN lessons ON ...`
- Расписание на сегодня: `SELECT ... FROM schedule JOIN subjects WHERE day_of_week = ?`
- Средний балл: `SELECT AVG(CAST(grade AS REAL)) FROM grades JOIN lessons WHERE grade IN ('5','4','3','2')`
- Замены: `SELECT ... FROM lessons WHERE actual_subject_id != subject_id`
- Закрытые предметы: `SELECT ... FROM subjects WHERE closed_at IS NOT NULL`
