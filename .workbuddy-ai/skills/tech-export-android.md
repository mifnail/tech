# Skill: tech-export-android — Export, Backup & Android Integration

**Trigger:** Working on export (report_export.py), backup/restore, Android-specific code (jnius, MediaStore, share).

**Project root:** `c:/Users/user/WorkBuddy AI/2026-09-13-22-13-51/tech`

## Export (report_export.py)

### Available Formats
- **Excel (.xlsx)** — openpyxl, primary format
- PDF — reportlab (code exists but disabled in API routes, returns 400 for non-xlsx)
- CSV — legacy, file-based (not served by API)

### Guarded Imports
```python
try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False
```
If openpyxl is missing, `export_*` raises `RuntimeError("openpyxl not installed")`.

### Export Functions
- `export_grades_xlsx(subject_id, db)` — group gradebook (students × lessons)
- `export_student_grades_xlsx(subject_id, student_id, db)` — single student row
- `export_report_xlsx(date, db)` — daily report (subject, group, status, counts)
- `export_general_xlsx(db)` — all subjects, one sheet each
- `_gradebook_table(subject_id, db)` — shared builder for gradebook tables

### Excel Style
- Header: blue fill (#4472C4), white bold text, centered
- Cells: thin borders, size 10
- Auto-width columns (max 30 chars)
- Sheet name: sanitized (colons → dashes, max 31 chars)
- Duplicate sheet names: suffixed with " (N)"

### Grade Display in Excel
| Grade value | Excel cell |
|-------------|-----------|
| `None` / missing | "Н" |
| `"0"` (present) | "." |
| `"5"/"4"/"3"/"2"` | The number |
| `"absent"` | "absent" |

### Average Calculation
`_avg_str(grades, student_id)` — average of numeric grades 2-5, 2 decimal places, "—" if none.

## API Export Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/export/grades/<id>.xlsx` | GET | Download gradebook xlsx |
| `/api/export/report/<date>.xlsx` | GET | Download daily report xlsx |
| `/api/export/grades/<id>/to-downloads` | POST | Save to Android Downloads |
| `/api/export/report/<date>/to-downloads` | POST | Save to Downloads |
| `/api/export/grades/<id>/share` | POST | Save + open share sheet |
| `/api/export/report/<date>/share` | POST | Save + open share sheet |
| `/api/export/general.xlsx` | GET | Download all-subjects xlsx |
| `/api/export/general/to-downloads` | POST | Save general to Downloads |
| `/api/export/general/share` | POST | Save + share general |
| `/api/export/lessons.ics` | GET | Disabled (400) |
| `/api/export/schedule.ics` | GET | Disabled (400) |

## Android Integration (api.py)

### Saving to Downloads
`_save_to_downloads_full(data, filename, mimetype)` → (path, content_uri)

- **Android 10+ (API 29+):** MediaStore.Downloads API via ContentResolver
  - Delete old file with same display_name first (avoid "Failed to build unique file")
  - If name collision persists, append timestamp
  - Write bytes via `resolver.openOutputStream(uri)`
- **Android <10:** Direct file write to `/sdcard/Download/`
- **Desktop:** Write to `~/Downloads/`

### Share Sheet
`_share_file(uri_string, mimetype, label)` — opens Android share via `Intent.ACTION_SEND`
- Requires content URI from MediaStore
- Sets `FLAG_GRANT_READ_URI_PERMISSION`
- Only works on Android (returns error on desktop)

### Android Context
`_android_context()` — gets Activity/Context:
1. Try `org.kivy.android.PythonActivity.mActivity`
2. Fallback: `android.app.ActivityThread.currentActivityThread().getApplication()`

### Native File Picker
`_start_picker()` — launches `ACTION_OPEN_DOCUMENT` for `.db` files:
- `activity_bind(on_activity_result=_on_pick_result)` on UI thread
- Picks content URI → reads bytes on Flask thread (not UI thread)
- 120s timeout for user to pick file
- `_drain_pfd(pfd)` — read bytes from ParcelFileDescriptor
- `_drain_istream(stream)` — read bytes from InputStream (chunked Java byte[])

### Key Android Gotchas
- Nested Java classes use `$` not `.`: `MediaStore$Downloads`, `Build$VERSION`
- `PythonActivity` may not exist in WebView bootstrap — always have fallback
- `pyjnius` import only works on Android — guard with try/except ImportError
- ContentResolver queries need explicit column indices
- Cursor must be closed in finally block

## Backup/Restore

### Validation (`_validate_sqlite_bytes`)
1. Min 100 bytes
2. Header: `SQLite format 3\x00`
3. Required tables: groups, students, subjects, lessons, grades (+ schedule if required)
4. `PRAGMA quick_check` must return 'ok'

### Restore Flow (`_restore_from_bytes`)
1. Validate bytes
2. Auto-backup current DB to Downloads (`teachhelper_backup_<timestamp>.db`)
3. Checkpoint WAL on current DB
4. Write to temp file (`_DB_PATH.tmp_restore`)
5. `os.replace()` — atomic
6. Delete `-wal` and `-shm` sidecar files

### Backup Routes
| Route | Method | Purpose |
|-------|--------|---------|
| `/api/backup` | POST | Save current DB to Downloads |
| `/api/backup/share` | POST | Save + share |
| `/api/backup/list` | GET | List `*.db` in Downloads |
| `/api/restore` | POST | Restore from uploaded file |
| `/api/restore/latest` | POST | Restore most recent backup |
| `/api/restore/named` | POST | Restore by name from list |

### Backup Naming Convention
- Manual: `teachhelper_<YYYY-MM-DD>.db`
- Auto (pre-restore): `teachhelper_backup_<YYYYMMDD_HHMMSS>.db`
- Auto-backups are excluded from "restore latest" to prevent ping-pong

### Backup List Sorting
1. `teachhelper_*` first (manual backups)
2. Other `*.db` files
3. Each group sorted by mtime descending

## Buildozer (APK Build)

- **Spec file:** `buildozer.spec`
- **CI:** `.github/workflows/build-apk.yml`
- Build triggered on push
- Output: debug APK (unsigned)
- **Never build APK locally** — only via GitHub Actions
- `release.keystore` exists in repo for signing (CI only)

### buildozer.spec Highlights
- Bootstrap: webview (not sdl2)
- Android API: 34
- NDK: 25c
- fullscreen=0
- Python 3
