# Skill: tech-overview — Project Constitution & Architecture

**Trigger:** Working on the "Учет занятий" (Lesson Tracker) project. Read this first.

**Project root:** `c:/Users/user/WorkBuddy AI/2026-09-13-22-13-51/tech`

## What This Project Is

Mobile teacher's journal (Android APK + desktop browser). Tracks lessons, attendance,
grades, exports to Excel, sends notifications via Telegram and MAX bots.
Works offline as a WebView app.

**Version:** 0.237 (see `VERSION` file)

## Stack — FROZEN (do NOT change without owner approval)

| Layer | Technology |
|-------|-----------|
| Backend | Python 3, Flask (REST API) |
| Database | SQLite (`sqlite3` stdlib), WAL mode |
| Frontend (active) | React + TypeScript + Vite (`mobile-teacher-app-redesign/`) |
| Frontend (legacy) | Vanilla JS SPA (`static/app.js`) — being replaced |
| Export | openpyxl (`.xlsx` only; PDF/CSV/ICS disabled) |
| Bots | stdlib only + certifi (long-polling, no external libs) |
| Mobile | Buildozer / python-for-android WebView bootstrap |
| CI/CD | GitHub Actions (`.github/workflows/build-apk.yml`) |
| Tests | pytest, in-memory SQLite |

### Forbidden dependencies
- matplotlib, numpy, pillow — heavy native wheels
- Kivy — removed entirely, UI is WebView
- Any new dependency requires owner approval

## Architecture

```
main.py              → Entry point (Flask + background bot threads)
api.py               → Flask REST API (~2000 lines, all endpoints)
database.py          → ALL SQLite access (schema, migrations, queries)
botcore.py           → Shared HTTP transport for bots (SSL, retries, texts)
tgbot.py             → Telegram bot "Мои оценки" (read-only for students)
maxbot.py            → MAX bot (grades, files, reminders, curators, teacher)
report_export.py     → Excel export (openpyxl, guarded import)
crash_reporter.py    → Exception handling
schedule_file.py     → schedule.txt parser
seed_db.py           → Test database seeder
mobile-teacher-app-redesign/  → React/TS frontend (Vite, singlefile build)
static/app.js        → Legacy vanilla JS SPA
templates/index.html → Legacy HTML shell
tests/               → pytest tests (123 tests)
```

## DB Schema

```
groups (id, name)
  ├── subjects (id, name, total_hours, group_id, is_free)
  │     ├── schedule (id, day_of_week, lesson_number, subject_id, week_type)
  │     └── lessons (id, subject_id, actual_subject_id, date, status, lesson_number)
  │           └── grades (id, lesson_id, student_id, grade)
  ├── students (id, group_id, last_name, first_name, middle_name)
  ├── bot_links (chat_id, student_id)    — Telegram bindings
  ├── max_links (chat_id, student_id)    — MAX bindings
  ├── curators (group_id, chat_id, code) — group curator bindings
  └── app_settings (key, value)           — tokens, flags, codes
```

**Key concepts:**
- `actual_subject_id` — always filled, equals `subject_id` for normal lessons; differs for substitutions
- Lesson statuses: `held` (conducted), `cancelled` (grades deleted, not counted)
- Grade values: `'0'`/`'present'` (present, no mark), `'5'`/`'4'`/`'3'`/`'2'` (grades), `'absent'` (Н/Я), `null`/empty (not marked)
- `week_type`: 0=every week, 1=odd week, 2=even week
- `lesson_number` — order of lesson in the day (supports duplicates)
- `СВОБОДНО` subject — auto-created per group for substitutions

## REST API Structure

All endpoints under `/api/`:
- Groups: `/api/groups` (GET, POST, PATCH, DELETE) + `/api/groups/<id>/curator`
- Students: `/api/students` (GET), `/api/students/bulk` (POST), `/api/students/<id>` (PATCH, DELETE)
- Subjects: `/api/subjects` (GET, POST), `/api/subjects/<id>` (PATCH, DELETE) + gradebook, substitution-list, lessons
- Schedule: `/api/schedule` (GET, POST, PATCH, DELETE) + `/api/schedule/today`
- Lessons: `/api/lessons` (POST), `/api/lessons/<id>` (GET, DELETE) + cancel, substitute, status, adjacent, attendance
- Reports: `/api/reports/daily`, `/api/reports/average/<id>`, `/api/reports/substitutions`
- Export: `/api/export/grades/<id>.xlsx`, `/api/export/report/<date>.xlsx` + to-downloads, share variants
- Settings: `/api/settings/bot`, `/api/settings/maxbot`
- Bot links: `/api/bot/links`, `/api/maxbot/links`
- Backup: `/api/backup`, `/api/restore`, `/api/restore/latest`, `/api/backup/list`, `/api/restore/named`

## Definition of Done (from AGENT.md)

1. Code runs on PC without errors
2. Tests are green (`python -m pytest tests/ -v`)
3. Change committed with meaningful message
4. Checked in browser on mobile viewport

## Process Rules

- **Vertical slices:** complete one feature fully, then commit
- **Manual check** before each commit
- **One commit per feature** (small wins)
- **APK built only in GitHub Actions** — never locally
- All SQL stays in `database.py` — API layer never runs raw SQL
- `lessons.db` is sacred — tests always use `:memory:` SQLite

## Key Files to Read

- `AGENT.md` — project constitution (read at start of every session)
- `docs/SPECIFICATION.md` — detailed spec with API docs
- `PLAN.md` — implementation roadmap
- `PROMPT.md` — original project prompt
- `docs/DIAGRAMS.md` — ER diagrams
