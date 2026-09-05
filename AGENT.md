# AGENT.md — правила проекта «TeachHelper4» (LessonTracker)

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
- Фронтенд: **Vanilla JS SPA** (без фреймворков), CSS, HTML
- БД: **SQLite** (модуль `sqlite3` из стандартной библиотеки)
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
  ├── subjects (id, name, total_hours, group_id)
  │     └── schedule (id, day_of_week, lesson_number, subject_id, week_type)
  │     └── lessons (id, subject_id, actual_subject_id, date)
  │           └── grades (id, lesson_id, student_id, grade)
  └── students (id, group_id, last_name, first_name, middle_name)
```

### Модули
- `database.py` — ВЕСЬ доступ к SQLite.
- `api.py` — Flask REST API.
- `main.py` — точка входа Flask.
- `static/app.js` — SPA фронтенд.
- `static/style.css` — мобильный UI.
- `templates/index.html` — HTML-оболочка.
- `schedule_file.py` — парсер schedule.txt.
- `calendar_export.py` — выгрузка в .ics.
- `report_export.py` — Excel/PDF отчёты.
- `crash_reporter.py` — обработка исключений.
- `seed_db.py` — тестовая БД.
- `tests/` — автотесты (pytest).

## 4. Definition of Done
1. Код запускается на ПК без ошибок.
2. Автотесты зелёные (`pytest`).
3. Изменение закоммичено с осмысленным сообщением.
4. Проверено в браузере на мобильном viewport.

## 5. Правила процесса
- **Вертикальные срезы:** доводим один пункт до рабочего состояния и коммитим.
- **Ручная проверка:** каждый срез перед коммитом проверяется человеком.
- **Фиксируем маленькие победы:** каждый рабочий срез — отдельный коммит.

## 6. Сборка APK (CI)
- Триггер: push в репозиторий.
- Тип: debug-APK (без подписи).
- Workflow: `.github/workflows/build-apk.yml`.

## 7. Основные запросы к БД
- Создать занятие: `INSERT INTO lessons (subject_id, actual_subject_id, date) VALUES (?, ?, date('now'))`
- Оценки за занятие: `INSERT INTO grades (lesson_id, student_id, grade) VALUES (?, ?, ?)`
- Остаток часов: `SELECT total_hours - COUNT(*) FROM subjects LEFT JOIN lessons ON ...`
- Расписание на сегодня: `SELECT ... FROM schedule JOIN subjects WHERE day_of_week = ?`
- Средний балл: `SELECT AVG(CAST(grade AS REAL)) FROM grades JOIN lessons WHERE grade NOT IN ('absent', 'pass')`
- Замены: `SELECT ... FROM lessons WHERE actual_subject_id != subject_id`
