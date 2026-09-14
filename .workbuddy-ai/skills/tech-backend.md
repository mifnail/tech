# Skill: tech-backend — Flask API & SQLite Development

**Trigger:** Working on backend code (api.py, database.py, main.py, export, backup).

**Project root:** `c:/Users/user/WorkBuddy AI/2026-09-13-22-13-51/tech`

## Architecture Rules

1. **ALL SQL lives in `database.py`** — never write SQL in `api.py` or elsewhere
2. `api.py` calls `Database` methods, returns JSON via Flask `jsonify`
3. `Database` class: `__init__` opens connection, `init_schema()` + `_migrate()` run automatically
4. Thread-safe: `check_same_thread=False`, each request gets a new `Database()` via `get_db()`
5. `PRAGMA foreign_keys = ON` and `PRAGMA journal_mode=WAL` always set

## Adding a New API Endpoint

Pattern:
```python
# 1. Add the SQL method to database.py
def get_something(self, param: int) -> Sequence[sqlite3.Row]:
    return self.conn.execute(
        "SELECT * FROM table WHERE id = ?", (param,)
    ).fetchall()

# 2. Add the route to api.py
@some_bp.route('/<int:item_id>/something', methods=['GET'])
def get_something(item_id: int):
    return jsonify([dict(r) for r in get_db().get_something(item_id)])
```

## Blueprint Structure (api.py)

| Blueprint | Prefix | Purpose |
|-----------|--------|---------|
| `groups_bp` | `/api/groups` | Groups CRUD + curator codes |
| `students_bp` | `/api/students` | Students CRUD + bulk add + grades |
| `subjects_bp` | `/api/subjects` | Subjects CRUD + gradebook + substitution-list |
| `schedule_bp` | `/api/schedule` | Schedule CRUD + today |
| `lessons_bp` | `/api/lessons` | Lessons CRUD + cancel/substitute + attendance |
| `reports_bp` | `/api/reports` | Daily report, averages, substitutions |
| `export_bp` | `/api/export` | xlsx download, to-downloads, share, general |
| `settings_bp` | `/api/settings/bot` | Telegram bot settings |
| `maxbot_bp` | `/api/settings/maxbot` | MAX bot settings + teacher unbind |
| `bot_bp` | `/api/bot` | Telegram chat links |
| `maxbot_links_bp` | `/api/maxbot` | MAX chat links |
| `backup_bp` | `/api` | /backup, /restore, /restore/latest, /backup/list |

## Helper Functions (api.py)

- `get_db()` — returns new `Database()` instance
- `require_fields(*fields)` — decorator, returns 400 if JSON missing required fields
- `optional_int(value, default)` — safe int conversion from query params
- `dict_row(row)` — converts `sqlite3.Row` to dict
- `row_get(row, key, default)` — defensive `.keys()` check for Row access
- `_lesson_notify_context(db, lesson_id)` — returns (ddmm, subject_name, group_id)
- `_is_bot_active(db, token_key, enabled_key)` — checks token + enabled flag

## Database Methods (database.py) — Quick Reference

### Groups
- `add_group(name)`, `list_groups()`, `delete_group(id)`, `update_group(id, name)`
- `ensure_curator_code(group_id)`, `bind_curator(group_id, chat_id)`, `unbind_curator(group_id)`
- `find_curator_by_code(code)`, `get_curator_chat(group_id)`, `curator_group_for_chat(chat_id)`

### Students
- `add_student(group_id, last, first, middle)`, `add_students_bulk(group_id, students)`
- `list_students(group_id)`, `get_student(id)`, `delete_student(id)`, `update_student(id, ...)`
- `find_students_by_surname(query)` — casefold-based, Cyrillic-safe

### Subjects
- `add_subject(name, hours, group_id)`, `list_subjects(group_id, include_free)`
- `delete_subject(id)`, `update_subject(id, name, hours)`
- `subject_gradebook(subject_id)` → (students, lessons, grades_dict)
- `subject_summary(subject_id)` → row with held_lessons, remaining, average, total_students
- `get_free_subject_id(group_id)` — auto-creates СВОБОДНО
- `is_free_subject(subject_id)`

### Schedule
- `add_schedule_entry(day, num, subject_id, week_type)`, `get_schedule_for_day(day, week_type)`
- `list_schedule()`, `delete_schedule_entry(id)`, `update_schedule_entry(id, ...)`

### Lessons
- `add_lesson(subject_id, date, actual_subject_id, status, lesson_number)`
- `get_lesson(id)`, `delete_lesson(id)`, `cancel_lesson(id)`, `set_lesson_status(id, status)`
- `substitute_lesson(lesson_id, new_subject_id)` — cancels old + creates new
- `list_lessons_by_date(date)`, `list_lessons_for_subject(subject_id)`
- `find_held_lesson(subject_id, date, lesson_number)` — dedup check
- `get_adjacent_lessons(lesson_id)` — (prev_id, next_id)

### Grades
- `mark_attendance(lesson_id, student_id, grade)`, `mark_attendance_bulk(lesson_id, records)`
- `get_attendance(lesson_id)`, `attendance_count(lesson_id)`
- `student_grades(student_id, subject_id)`, `average_grades(subject_id)`

### Settings & Bot Links
- `get_setting(key)`, `set_setting(key, value)`
- `bind_chat(chat_id, student_id)`, `unbind_chat(chat_id)`, `get_chat_link(chat_id)`
- `bind_max(chat_id, student_id)`, `unbind_max(chat_id)`, `get_max_link(chat_id)`
- `list_bot_links()`, `list_max_links()`

## Migrations

`_migrate()` runs on every `Database.__init__`:
- `ALTER TABLE lessons ADD COLUMN status` (idempotent via try/except)
- `UPDATE lessons SET status = 'cancelled' WHERE status = 'free'`
- `ALTER TABLE lessons ADD COLUMN lesson_number` (idempotent)

To add a new column: add `ALTER TABLE` in `_migrate()` with try/except for idempotency.

## Grade Push (Debounced Notifications)

When attendance is marked via POST `/api/lessons/<id>/attendance`:
1. Server starts a 10s debounce timer per (lesson_id, student_id)
2. Only the settled grade (re-read from DB) is sent to the student via MAX bot
3. Curator gets a 60s debounced push with student FIO + grade

Key functions:
- `_fire_grade_push(token, lesson_id, student_id)` — timer callback for student push
- `_fire_curator_push(token, lesson_id, student_id, group_id)` — timer callback for curator
- `_pending` / `_pending_curator` — module-level timer registries

## Backup/Restore

- `_validate_sqlite_bytes(data, require_schedule)` — checks SQLite header + required tables
- `_atomic_replace_db(data)` — checkpoint WAL, write temp, os.replace, clean sidecars
- `_restore_from_bytes(data)` — validate + auto-backup + atomic replace
- `_list_backup_files()` — enumerates `*.db` in Downloads (desktop glob or Android MediaStore)
- `_find_latest_backup_bytes()` — most recent non-auto backup
- Android file picker via `ACTION_OPEN_DOCUMENT` with `activity_bind(on_activity_result=...)`

## Running the Server

```bash
cd tech/
python main.py           # dev mode, opens browser
python main.py --prod    # production, 0.0.0.0
TEACHHELPER_NO_BOT=1 python main.py  # skip bot startup
```

Dependencies: `pip install flask pytest openpyxl certifi`
