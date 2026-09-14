import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import api as _api_module


def _make_db_bytes(*tables, schedule=False):
    """Build valid SQLite bytes with the given table names.

    *tables* are base table names; if schedule=True adds 'schedule'.
    Tables carry the application columns required by validate_database_file.
    Returns raw bytes written to a temp file. No internal seq table.
    """
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    tmp.close()
    try:
        conn = sqlite3.connect(tmp.name)
        for t in tables:
            if t == 'groups':
                conn.execute("CREATE TABLE groups (id INTEGER PRIMARY KEY, name TEXT)")
            elif t == 'students':
                conn.execute("CREATE TABLE students (id INTEGER PRIMARY KEY, group_id INTEGER, last_name TEXT, first_name TEXT, middle_name TEXT)")
            elif t == 'subjects':
                conn.execute("CREATE TABLE subjects (id INTEGER PRIMARY KEY, name TEXT, group_id INTEGER, total_hours INTEGER)")
            elif t == 'lessons':
                conn.execute("CREATE TABLE lessons (id INTEGER PRIMARY KEY, subject_id INTEGER, actual_subject_id INTEGER, date TEXT)")
            elif t == 'grades':
                conn.execute("CREATE TABLE grades (id INTEGER PRIMARY KEY, lesson_id INTEGER, student_id INTEGER, grade TEXT)")
            else:
                conn.execute(f"CREATE TABLE {t} (id INTEGER PRIMARY KEY)")
        if schedule:
            conn.execute("CREATE TABLE schedule (id INTEGER PRIMARY KEY, day_of_week INTEGER, lesson_number INTEGER, subject_id INTEGER, week_type INTEGER)")
        conn.close()
        with open(tmp.name, 'rb') as f:
            return f.read()
    finally:
        os.unlink(tmp.name)


def _make_core_only_bytes():
    return _make_db_bytes('groups', 'students', 'subjects', 'lessons', 'grades')


def _make_full_bytes():
    return _make_db_bytes('groups', 'students', 'subjects', 'lessons', 'grades', schedule=True)


def _make_bad_header_bytes():
    return b'NOT_SQLITE_FORMAT' + b'\x00' * (16 - len(b'NOT_SQLITE_FORMAT'))


# ── exactly 4 test functions ────────────────────────────────────────

def test_full_db_no_flag_passes():
    """Full DB (5 core + schedule) with require_schedule=False → no exception."""
    data = _make_full_bytes()
    _api_module._validate_sqlite_bytes(data, require_schedule=False)


def test_full_db_flag_passes():
    """Full DB (5 core + schedule) with require_schedule=True → no exception
    (kwarg-compat guard for the real CI incident)."""
    data = _make_full_bytes()
    _api_module._validate_sqlite_bytes(data, require_schedule=True)


def test_no_schedule_no_flag_passes():
    """5 core tables only, require_schedule=False → no exception."""
    data = _make_core_only_bytes()
    _api_module._validate_sqlite_bytes(data, require_schedule=False)


def test_no_schedule_flag_raises():
    """5 core tables only, require_schedule=True → ValueError."""
    data = _make_core_only_bytes()
    try:
        _api_module._validate_sqlite_bytes(data, require_schedule=True)
        assert False, 'Expected ValueError'
    except ValueError:
        pass  # expected


# ── new tests verifying min-size bump + integrity + sqlite3.Error normalisation ──

def test_truncated_valid_magic_raises():
    """< 100 bytes with valid SQLite magic → ValueError (not sqlite3.DatabaseError)."""
    short = b'SQLite format 3\x00' + b'\xff' * 50   # 66 bytes total
    try:
        _api_module._validate_sqlite_bytes(short, require_schedule=False)
        assert False, 'Expected ValueError'
    except ValueError:
        pass  # expected
    except sqlite3.DatabaseError:
        raise AssertionError('sqlite3.DatabaseError leaked — should be ValueError')


def test_corrupted_page_raises():
    """Valid header + required tables in schema, but zeroed page body → ValueError."""
    # Build a real DB then corrupt: replace bytes after 100-byte header with zeros.
    data = _make_full_bytes()
    assert len(data) > 100
    corrupted = data[:100] + b'\x00' * (len(data) - 100)
    try:
        _api_module._validate_sqlite_bytes(corrupted, require_schedule=False)
        assert False, 'Expected ValueError'
    except ValueError:
        pass  # expected
    except sqlite3.DatabaseError:
        raise AssertionError('sqlite3.DatabaseError leaked — should be ValueError')