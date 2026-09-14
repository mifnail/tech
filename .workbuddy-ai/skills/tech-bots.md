# Skill: tech-bots — Telegram & MAX Bot Development

**Trigger:** Working on bot code (tgbot.py, maxbot.py, botcore.py).

**Project root:** `c:/Users/user/WorkBuddy AI/2026-09-13-22-13-51/tech`

## Core Principle

Bots use **stdlib only** (urllib, json, ssl, threading, time) + certifi for CA.
No `requests`, no `telebot`, no `aiogram`. Long-polling runs in daemon threads alongside Flask.

## botcore.py — Shared Transport

| Function | Purpose |
|----------|---------|
| `_ctx()` | SSL context (certifi if available, fallback to system) |
| `open_url_with_fallback(req, urlopen, timeout)` | urlopen with CERTIFICATE_VERIFY_FAILED fallback |
| `open_raw_with_fallback(req, urlopen, timeout)` | Same but returns raw response (for binary) |
| `retry_on_connection(fn, retries, sleep)` | Retries only on "no connection" errors |
| `supervise(name, target_factory, interval)` | Worker thread + supervisor that restarts on death |
| `_fio(row)` | Format "LastName FirstName" |
| `_fmt_date(iso)` | Format ISO date to "DD.MM" |
| `BotError` | Base exception for API/network errors |
| `BotRateLimited(wait)` | 429 rate limit exception with retry_after |

**Testing pattern:** All bot functions accept `urlopen=None` parameter for injecting fakes.

## tgbot.py — Telegram Bot

**API:** `https://api.telegram.org/bot<token>/<method>`

### Key Functions
- `_call(token, method, params, urlopen)` — single API call, raises BotError
- `get_me(token)` — getMe with retries
- `send_message(token, chat_id, text, urlopen)` — sendMessage with permanent keyboard
- `get_updates(token, offset, timeout, urlopen)` — getUpdates (long-polling)
- `process_text(text, chat_id, db)` — **pure function**, all dialog logic, testable without network
- `run_polling(token, db_factory, stop_event, urlopen)` — polling loop
- `start_polling(token)` — starts daemon thread via `supervise()`

### Dialog Flow (process_text)
1. `/start` — if bound: show name + help; if not: show WELCOME
2. `/help` — show help text (bound vs unbound variants)
3. If not bound and text is not a command: try surname match → bind or ask for disambiguation
4. `/grades` (or "Оценки") — show student's grades grouped by subject
5. `/today` (or "Сегодня") — today's lessons + marks
6. `/unbind` — remove binding

### Permanent Keyboard
```
[Оценки] [Сегодня]
[Помощь] [Отвязать]
```

### Settings Persistence
- `bot_token` — in `app_settings`
- `bot_enabled` — '1' or '0'
- `bot_last_update` — offset for polling continuity

## maxbot.py — MAX Bot

**API:** `https://platform-api2.max.ru`

### Key Functions
- `_get(path, token, urlopen)` / `_post(path, token, data, urlopen)` — API calls
- `check(token)` — verify token via GET /updates?timeout=0&limit=1
- `send_message(token, chat_id, text, urlopen)` — POST /messages
- `upload_file(token, data, filename, urlopen)` — 2-step: POST /uploads → POST multipart to URL
- `send_file(token, chat_id, file_token, caption, urlopen)` — send file attachment
- `send_with_buttons(token, chat_id, text, urlopen)` — inline keyboard (callback + message buttons)
- `answer_callback(token, callback_id, notification, urlopen)` — answer callback
- `get_updates(token, marker, timeout, urlopen)` — long-polling, returns (updates, new_marker)
- `process_text(text, chat_id, db)` — pure dialog logic
- `run_polling(token, db_factory, stop_event, urlopen)` — polling loop
- `start_polling(token)` — daemon thread via supervise
- `notify_grade(token, student_id, grade, date_str, subject_name)` — push new grade to student
- `start_reminders(token)` — daemon thread for evening reminders + morning digest

### Roles (process_text handles all)

1. **Student** — bound via surname, sees own grades/schedule/avg/debts/vedomost
2. **Curator** — bound via `/curator КОД`, gets group vedomost
3. **Teacher** — bound via `/teacher КОД`, gets all-group vedomost + morning digest

### Dialog Flow Priority
1. `/curator КОД` or bare curator code → bind curator
2. `/teacher КОД` or bare teacher code → bind teacher
3. Teacher-bound chat → teacher commands (vedomost, help, unbind)
4. Curator-bound chat → curator commands
5. Student flow: `/start`, `/help`, surname binding, `/grades`, `/today`, `/schedule`, `/avg`, `/debts`, `/vedomost`, `/unbind`

### Vedomost Flow
- `process_text` returns `'VEDOMOST:'`, `'VEDOMOST_CURATOR:'`, or `'VEDOMOST_TEACHER:'`
- Polling loop detects prefix and calls `_handle_vedomost`, `_handle_curator_vedomost`, or `_handle_teacher_vedomost`
- Each sends xlsx files per subject with 0.6s gaps

### File Restore via Bot
- Teacher/curator sends a `.db` file in chat
- `_handle_file_restore` downloads, validates (requires `schedule` table), restores
- Bindings (teacher, curators, max_links, bot_links) snapshotted before restore and re-applied after

### Reminder System
- `run_reminders(token, db_factory, stop_event)` — 600s loop
- `due_reminder(hour, last_sent, today)` — True at 17:00-18:00 if not sent today
- `reminder_targets(db, tomorrow_iso)` — (chat_id, text) pairs for students with tomorrow lessons
- `due_teacher_digest(hour, last_sent, today)` — True at 7:00 if not sent today
- `teacher_targets(db, today_iso)` — digest text with lesson counts

### Settings Persistence
- `max_bot_token`, `max_bot_enabled` — bot config
- `max_teacher_code`, `max_teacher_chat` — teacher binding
- `max_last_marker` — polling continuity
- `max_last_reminder`, `max_teacher_digest_date` — reminder scheduling

## Bot Startup (main.py)

- `_maybe_start_bot(debug)` — Telegram, skips in debug reloader (WERKZEUG_RUN_MAIN)
- `_maybe_start_maxbot(debug)` — MAX, same pattern
- `TEACHHELPER_NO_BOT=1` env var disables both
- Both start via `supervise()` which auto-restarts dead threads

## Grade Push Pipeline (api.py → maxbot.py)

1. POST `/api/lessons/<id>/attendance` marks grade
2. If MAX bot active: 10s debounce timer per (lesson_id, student_id)
3. Timer fires `_fire_grade_push` → re-reads settled grade → calls `maxbot.notify_grade`
4. If curator exists: 60s debounce timer → `_fire_curator_push` → sends FIO + grade to curator
5. Cancel/substitute events trigger immediate `_notify_group_chats` to all bound students
