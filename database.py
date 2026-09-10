from __future__ import annotations
import sqlite3
import os
import shutil
from typing import Optional, Sequence, Any

# ─────────────────────── DB path resolution ───────────────────────
# Desktop: lessons.db рядом со скриптом (как раньше).
# Android: ANDROID_PRIVATE/files/lessons.db (переживает обновления APK).
# При первом запуске на Android копируем lessons.db из APK (bundle)
# в persistent storage, чтобы данные не терялись.

def _is_android() -> bool:
    return bool(os.environ.get('ANDROID_PRIVATE') or os.environ.get('ANDROID_ARGUMENT'))

def _bundled_db_path() -> str:
    """Путь к lessons.db внутри APK (read-only, рядом со скриптом)."""
    return os.path.join(os.path.dirname(__file__), 'lessons.db')

def _persistent_db_path() -> str:
    """Путь к persistent lessons.db (Android external storage)."""
    private = os.environ.get('ANDROID_PRIVATE', '')
    files_dir = os.path.join(private, 'files')
    os.makedirs(files_dir, exist_ok=True)
    return os.path.join(files_dir, 'lessons.db')

def _resolve_db_path() -> str:
    if _is_android():
        persistent = _persistent_db_path()
        bundled = _bundled_db_path()
        if not os.path.exists(persistent):
            # Первый запуск — копируем bundled DB (если есть) в persistent
            if os.path.exists(bundled):
                shutil.copy2(bundled, persistent)
        return persistent
    # Desktop — рядом со скриптом
    return os.path.join(os.path.dirname(__file__), 'lessons.db')

DB_PATH = _resolve_db_path()

class Database:
    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or DB_PATH
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        try:
            self.conn.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass
        try:
            self.conn.execute("PRAGMA busy_timeout = 5000")
        except Exception:
            pass
        self.init_schema()
        self._migrate()

    def __enter__(self) -> 'Database':
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def init_schema(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
                last_name TEXT NOT NULL,
                first_name TEXT NOT NULL,
                middle_name TEXT NOT NULL DEFAULT '',
                UNIQUE(group_id, last_name, first_name, middle_name)
            );

            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                total_hours INTEGER NOT NULL DEFAULT 0,
                group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
                UNIQUE(name, group_id)
            );

            CREATE TABLE IF NOT EXISTS schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day_of_week INTEGER NOT NULL,
                lesson_number INTEGER NOT NULL,
                subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
                week_type INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
                actual_subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE,
                date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'held'
            );

            CREATE TABLE IF NOT EXISTS grades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
                student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                grade TEXT NOT NULL,
                UNIQUE(lesson_id, student_id)
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bot_links (
                chat_id INTEGER PRIMARY KEY,
                student_id INTEGER NOT NULL UNIQUE REFERENCES students(id) ON DELETE CASCADE,
                created TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS max_links (
                chat_id INTEGER PRIMARY KEY,
                student_id INTEGER NOT NULL UNIQUE REFERENCES students(id) ON DELETE CASCADE,
                created TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS curators (
                group_id INTEGER PRIMARY KEY REFERENCES groups(id) ON DELETE CASCADE,
                chat_id INTEGER,
                code TEXT NOT NULL UNIQUE,
                created TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_students_group ON students(group_id);
            CREATE INDEX IF NOT EXISTS idx_subjects_group ON subjects(group_id);
            CREATE INDEX IF NOT EXISTS idx_schedule_subject ON schedule(subject_id);
            CREATE INDEX IF NOT EXISTS idx_lessons_subject ON lessons(subject_id);
            CREATE INDEX IF NOT EXISTS idx_lessons_actual ON lessons(actual_subject_id);
            CREATE INDEX IF NOT EXISTS idx_lessons_date ON lessons(date);
            CREATE INDEX IF NOT EXISTS idx_grades_lesson ON grades(lesson_id);
            CREATE INDEX IF NOT EXISTS idx_grades_student ON grades(student_id);
        """)
        self.conn.commit()

    def _migrate(self) -> None:
        try:
            self.conn.execute("ALTER TABLE lessons ADD COLUMN status TEXT NOT NULL DEFAULT 'held'")
            self.conn.commit()
        except sqlite3.OperationalError:
            pass
        self.conn.execute("UPDATE lessons SET status = 'cancelled' WHERE status = 'free'")
        self.conn.commit()
        # Add lesson_number column for duplicate lessons support
        try:
            self.conn.execute("ALTER TABLE lessons ADD COLUMN lesson_number INTEGER")
            self.conn.commit()
        except sqlite3.OperationalError:
            pass

    def get_setting(self, key: str) -> Optional[str]:
        """Прочитать настройку (токен Яндекса, ссылки публикаций). Нет — None."""
        row = self.conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
        return row['value'] if row else None

    def set_setting(self, key: str, value: Optional[str]) -> None:
        """Сохранить настройку; value=None — удалить."""
        if value is None:
            self.conn.execute("DELETE FROM app_settings WHERE key = ?", (key,))
        else:
            self.conn.execute(
                "INSERT INTO app_settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value))
        self.conn.commit()

    # ---- Telegram bot: привязка чат <-> студент (строго 1:1) ----
    def find_students_by_surname(self, query: str) -> Sequence[sqlite3.Row]:
        """Поиск по 'Фамилия' или 'Фамилия Имя' (префикс, без учёта регистра).

        Регистр снимаем в Python (casefold): встроенный LOWER() в SQLite
        работает только с ASCII и кириллицу не сравнивает.
        """
        parts = (query or '').split()
        if not parts:
            return []
        last = parts[0].casefold()
        first = parts[1].casefold() if len(parts) > 1 else None
        out = []
        for r in self.conn.execute(
                "SELECT * FROM students ORDER BY last_name, first_name").fetchall():
            if not r['last_name'].casefold().startswith(last):
                continue
            if first is not None and not r['first_name'].casefold().startswith(first):
                continue
            out.append(r)
            if len(out) >= 10:
                break
        return out

    def bind_chat(self, chat_id: int, student_id: int) -> None:
        self.conn.execute(
            "INSERT INTO bot_links (chat_id, student_id) VALUES (?, ?)",
            (chat_id, student_id))
        self.conn.commit()

    def unbind_chat(self, chat_id: int) -> None:
        self.conn.execute("DELETE FROM bot_links WHERE chat_id = ?", (chat_id,))
        self.conn.commit()

    def unbind_student(self, student_id: int) -> None:
        self.conn.execute("DELETE FROM bot_links WHERE student_id = ?", (student_id,))
        self.conn.commit()

    def get_chat_link(self, chat_id: int) -> Optional[int]:
        row = self.conn.execute(
            "SELECT student_id FROM bot_links WHERE chat_id = ?", (chat_id,)).fetchone()
        return row['student_id'] if row else None

    def get_student_chat(self, student_id: int) -> Optional[int]:
        row = self.conn.execute(
            "SELECT chat_id FROM bot_links WHERE student_id = ?", (student_id,)).fetchone()
        return row['chat_id'] if row else None

    def list_bot_links(self) -> Sequence[sqlite3.Row]:
        return self.conn.execute("""
            SELECT bl.chat_id, bl.student_id, bl.created,
                   s.last_name, s.first_name, s.middle_name
            FROM bot_links bl JOIN students s ON s.id = bl.student_id
            ORDER BY s.last_name, s.first_name
        """).fetchall()

    # ---- MAX bot: привязка чат <-> студент (строго 1:1) ----
    def bind_max(self, chat_id: int, student_id: int) -> None:
        self.conn.execute(
            "INSERT INTO max_links (chat_id, student_id) VALUES (?, ?)",
            (chat_id, student_id))
        self.conn.commit()

    def unbind_max(self, chat_id: int) -> None:
        self.conn.execute("DELETE FROM max_links WHERE chat_id = ?", (chat_id,))
        self.conn.commit()

    def unbind_max_student(self, student_id: int) -> None:
        self.conn.execute("DELETE FROM max_links WHERE student_id = ?", (student_id,))
        self.conn.commit()

    def get_max_link(self, chat_id: int) -> Optional[int]:
        row = self.conn.execute(
            "SELECT student_id FROM max_links WHERE chat_id = ?", (chat_id,)).fetchone()
        return row['student_id'] if row else None

    def get_max_student_chat(self, student_id: int) -> Optional[int]:
        row = self.conn.execute(
            "SELECT chat_id FROM max_links WHERE student_id = ?", (student_id,)).fetchone()
        return row['chat_id'] if row else None

    def list_max_links(self) -> Sequence[sqlite3.Row]:
        return self.conn.execute("""
            SELECT ml.chat_id, ml.student_id, ml.created,
                   s.last_name, s.first_name, s.middle_name
            FROM max_links ml JOIN students s ON s.id = ml.student_id
            ORDER BY s.last_name, s.first_name
        """).fetchall()

    # ---- Curators per group ----
    def ensure_curator_code(self, group_id: int) -> str:
        row = self.conn.execute("SELECT code FROM curators WHERE group_id=?", (group_id,)).fetchone()
        if row:
            return row['code']
        import uuid
        code = uuid.uuid4().hex[:8]
        # ensure uniqueness
        while self.conn.execute("SELECT 1 FROM curators WHERE code=?", (code,)).fetchone():
            code = uuid.uuid4().hex[:8]
        self.conn.execute("INSERT INTO curators (group_id, code) VALUES (?, ?)", (group_id, code))
        self.conn.commit()
        return code

    def bind_curator(self, group_id: int, chat_id: int) -> None:
        self.ensure_curator_code(group_id)
        self.conn.execute("UPDATE curators SET chat_id=? WHERE group_id=?", (chat_id, group_id))
        self.conn.commit()

    def unbind_curator(self, group_id: int) -> None:
        self.conn.execute("UPDATE curators SET chat_id=NULL WHERE group_id=?", (group_id,))
        self.conn.commit()

    def find_curator_by_code(self, code: str) -> Optional[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM curators WHERE code=?", (code,)).fetchone()

    def get_curator_chat(self, group_id: int) -> Optional[int]:
        row = self.conn.execute("SELECT chat_id FROM curators WHERE group_id=?", (group_id,)).fetchone()
        return row['chat_id'] if row and row['chat_id'] is not None else None

    def curator_group_for_chat(self, chat_id: int) -> Optional[int]:
        row = self.conn.execute("SELECT group_id FROM curators WHERE chat_id=?", (chat_id,)).fetchone()
        return row['group_id'] if row else None

    def get_curator(self, group_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM curators WHERE group_id=?", (group_id,)).fetchone()

    def get_free_subject_id(self, group_id: int) -> int:
        row = self.conn.execute("SELECT id FROM subjects WHERE name = 'СВОБОДНО' AND group_id = ?", (group_id,)).fetchone()
        if row:
            return row['id']
        cur = self.conn.execute("INSERT INTO subjects (name, total_hours, group_id) VALUES ('СВОБОДНО', 0, ?)", (group_id,))
        self.conn.commit()
        return cur.lastrowid

    def is_free_subject(self, subject_id: int) -> bool:
        row = self.conn.execute("SELECT name FROM subjects WHERE id = ?", (subject_id,)).fetchone()
        return row is not None and row['name'] == 'СВОБОДНО'

    def add_group(self, name: str) -> int:
        cur = self.conn.execute("INSERT INTO groups (name) VALUES (?)", (name,))
        self.conn.commit()
        return cur.lastrowid

    def list_groups(self) -> Sequence[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM groups ORDER BY name").fetchall()

    def delete_group(self, group_id: int) -> None:
        self.conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))
        self.conn.commit()

    def update_group(self, group_id: int, name: str) -> None:
        self.conn.execute("UPDATE groups SET name = ? WHERE id = ?", (name, group_id))
        self.conn.commit()

    def add_student(self, group_id: int, last_name: str, first_name: str, middle_name: str = '') -> int:
        cur = self.conn.execute(
            "INSERT INTO students (group_id, last_name, first_name, middle_name) VALUES (?, ?, ?, ?)",
            (group_id, last_name, first_name, middle_name or ''))
        self.conn.commit()
        return cur.lastrowid

    def add_students_bulk(self, group_id: int, students: list[dict]) -> int:
        cur = self.conn.executemany(
            "INSERT OR IGNORE INTO students (group_id, last_name, first_name, middle_name) VALUES (?, ?, ?, ?)",
            [(group_id, s.get('last_name'), s.get('first_name'), s.get('middle_name') or '') for s in students])
        self.conn.commit()
        return cur.rowcount

    def delete_student(self, student_id: int) -> None:
        self.conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
        self.conn.commit()

    def update_student(self, student_id: int, last_name: str, first_name: str, middle_name: str = '') -> None:
        self.conn.execute(
            "UPDATE students SET last_name = ?, first_name = ?, middle_name = ? WHERE id = ?",
            (last_name, first_name, middle_name, student_id)
        )
        self.conn.commit()

    def list_students(self, group_id: Optional[int] = None) -> Sequence[sqlite3.Row]:
        if group_id is not None:
            return self.conn.execute(
                "SELECT * FROM students WHERE group_id = ? ORDER BY last_name, first_name", (group_id,)).fetchall()
        return self.conn.execute("SELECT s.*, g.name AS group_name FROM students s JOIN groups g ON s.group_id = g.id ORDER BY g.name, s.last_name").fetchall()

    def add_subject(self, name: str, total_hours: int, group_id: int) -> int:
        cur = self.conn.execute(
            "INSERT INTO subjects (name, total_hours, group_id) VALUES (?, ?, ?)",
            (name, total_hours, group_id))
        self.conn.commit()
        return cur.lastrowid

    def delete_subject(self, subject_id: int) -> None:
        # Совместимость со старыми БД где actual_subject_id без ON DELETE CASCADE
        # Удаляем занятия, где этот предмет — фактический (замены)
        self.conn.execute("DELETE FROM grades WHERE lesson_id IN (SELECT id FROM lessons WHERE actual_subject_id = ?)", (subject_id,))
        self.conn.execute("DELETE FROM lessons WHERE actual_subject_id = ?", (subject_id,))
        # subject_id каскадно удалится сам, но на всякий случай чистим и по нему
        self.conn.execute("DELETE FROM grades WHERE lesson_id IN (SELECT id FROM lessons WHERE subject_id = ?)", (subject_id,))
        self.conn.execute("DELETE FROM lessons WHERE subject_id = ?", (subject_id,))
        self.conn.execute("DELETE FROM schedule WHERE subject_id = ?", (subject_id,))
        self.conn.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
        self.conn.commit()

    def update_subject(self, subject_id: int, name: str, total_hours: int) -> None:
        self.conn.execute(
            "UPDATE subjects SET name = ?, total_hours = ? WHERE id = ?",
            (name, total_hours, subject_id)
        )
        self.conn.commit()

    def list_subjects(self, group_id: Optional[int] = None, include_free: bool = False) -> Sequence[sqlite3.Row]:
        base = """SELECT s.*, g.name AS group_name,
            COALESCE(h.held, 0) AS held_lessons,
            s.total_hours - COALESCE(h.held, 0) AS remaining
            FROM subjects s
            JOIN groups g ON s.group_id = g.id
            LEFT JOIN (
                SELECT actual_subject_id, COUNT(*) AS held
                FROM lessons WHERE status NOT IN ('cancelled', 'replaced') AND actual_subject_id IS NOT NULL
                GROUP BY actual_subject_id
            ) h ON h.actual_subject_id = s.id"""
        where = ""
        if group_id is not None:
            where = " WHERE s.group_id = ?"
        if not include_free:
            where += " AND s.name != 'СВОБОДНО'" if where else " WHERE s.name != 'СВОБОДНО'"
        order = " ORDER BY g.name, s.name"
        if group_id is not None:
            return self.conn.execute(base + where + order, (group_id,)).fetchall()
        return self.conn.execute(base + where + order).fetchall()

    def subject_gradebook(self, subject_id: int) -> tuple[list, list, dict]:
        group_id = self.conn.execute("SELECT group_id FROM subjects WHERE id = ?", (subject_id,)).fetchone()['group_id']
        students = [dict(r) for r in self.conn.execute("""
            SELECT id, last_name, first_name, middle_name FROM students WHERE group_id = ? ORDER BY last_name, first_name
        """, (group_id,)).fetchall()]
        lessons = [dict(r) for r in self.conn.execute("""
            SELECT l.id, l.date, l.lesson_number FROM lessons l
            WHERE l.actual_subject_id = ? AND l.status NOT IN ('cancelled', 'replaced')
            ORDER BY l.date, COALESCE(l.lesson_number, 999), l.id
        """, (subject_id,)).fetchall()]
        grades = {}
        for row in self.conn.execute("""
            SELECT g.student_id, g.lesson_id, g.grade FROM grades g
            JOIN lessons l ON g.lesson_id = l.id
            WHERE l.actual_subject_id = ? AND l.status NOT IN ('cancelled', 'replaced')
        """, (subject_id,)).fetchall():
            grades.setdefault(str(row['student_id']), {})[str(row['lesson_id'])] = row['grade']
        return students, lessons, grades

    def subject_summary(self, subject_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute("""
            SELECT s.*, g.name AS group_name,
                COALESCE(h.held, 0) AS held_lessons,
                s.total_hours - COALESCE(h.held, 0) AS remaining,
                COALESCE(avg.average, 0) AS average_grade,
                COALESCE(att.total_students, 0) AS total_students
            FROM subjects s
            JOIN groups g ON s.group_id = g.id
            LEFT JOIN (
                SELECT actual_subject_id, COUNT(*) AS held
                FROM lessons WHERE actual_subject_id = ? AND status NOT IN ('cancelled', 'replaced')
                GROUP BY actual_subject_id
            ) h ON 1=1
            LEFT JOIN (
                SELECT l.actual_subject_id, ROUND(AVG(CAST(gr.grade AS REAL)), 2) AS average
                FROM grades gr
                JOIN lessons l ON gr.lesson_id = l.id
                WHERE l.actual_subject_id = ? AND l.status NOT IN ('cancelled', 'replaced') AND gr.grade IN ('2', '3', '4', '5')
                GROUP BY l.actual_subject_id
            ) avg ON 1=1
            LEFT JOIN (
                SELECT l.actual_subject_id, COUNT(DISTINCT gr.student_id) AS total_students
                FROM grades gr
                JOIN lessons l ON gr.lesson_id = l.id
                WHERE l.actual_subject_id = ? AND l.status NOT IN ('cancelled', 'replaced')
                GROUP BY l.actual_subject_id
            ) att ON 1=1
            WHERE s.id = ?
        """, (subject_id, subject_id, subject_id, subject_id)).fetchone()

    def add_schedule_entry(self, day_of_week: int, lesson_number: int, subject_id: int, week_type: int = 0) -> int:
        cur = self.conn.execute(
            "INSERT INTO schedule (day_of_week, lesson_number, subject_id, week_type) VALUES (?, ?, ?, ?)",
            (day_of_week, lesson_number, subject_id, week_type))
        self.conn.commit()
        return cur.lastrowid

    def get_schedule_for_day(self, day_of_week: int, current_week_type: Optional[int] = None) -> Sequence[sqlite3.Row]:
        if current_week_type is not None:
            return self.conn.execute("""
                SELECT sch.*, sub.name AS subject_name, g.name AS group_name, sub.group_id AS group_id
                FROM schedule sch
                JOIN subjects sub ON sch.subject_id = sub.id
                JOIN groups g ON sub.group_id = g.id
                WHERE sch.day_of_week = ? AND (sch.week_type = 0 OR sch.week_type = ?)
                ORDER BY sch.lesson_number
            """, (day_of_week, current_week_type)).fetchall()
        return self.conn.execute("""
            SELECT sch.*, sub.name AS subject_name, g.name AS group_name, sub.group_id AS group_id
            FROM schedule sch
            JOIN subjects sub ON sch.subject_id = sub.id
            JOIN groups g ON sub.group_id = g.id
            WHERE sch.day_of_week = ?
            ORDER BY sch.lesson_number
        """, (day_of_week,)).fetchall()

    def list_schedule(self) -> Sequence[sqlite3.Row]:
        return self.conn.execute("""
            SELECT sch.*, sub.name AS subject_name, g.name AS group_name
            FROM schedule sch
            JOIN subjects sub ON sch.subject_id = sub.id
            JOIN groups g ON sub.group_id = g.id
            ORDER BY sch.day_of_week, sch.lesson_number
        """).fetchall()

    def delete_schedule_entry(self, entry_id: int) -> None:
        self.conn.execute("DELETE FROM schedule WHERE id = ?", (entry_id,))
        self.conn.commit()

    def update_schedule_entry(self, entry_id: int, day_of_week: int, lesson_number: int, subject_id: int, week_type: int) -> None:
        self.conn.execute(
            "UPDATE schedule SET day_of_week = ?, lesson_number = ?, subject_id = ?, week_type = ? WHERE id = ?",
            (day_of_week, lesson_number, subject_id, week_type, entry_id))
        self.conn.commit()

    def add_lesson(self, subject_id: int, date: str, actual_subject_id: Optional[int] = None, status: str = 'held', lesson_number: Optional[int] = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO lessons (subject_id, actual_subject_id, date, status, lesson_number) VALUES (?, ?, ?, ?, ?)",
            (subject_id, actual_subject_id, date, status, lesson_number))
        self.conn.commit()
        return cur.lastrowid

    def get_lesson(self, lesson_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute("""
            SELECT l.*, ps.name AS planned_subject,
                COALESCE(fs.name, ps.name) AS actual_subject_name,
                g.name AS group_name
            FROM lessons l
            JOIN subjects ps ON l.subject_id = ps.id
            LEFT JOIN subjects fs ON l.actual_subject_id = fs.id
            JOIN groups g ON ps.group_id = g.id
            WHERE l.id = ?
        """, (lesson_id,)).fetchone()

    def get_student(self, student_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()

    def set_lesson_status(self, lesson_id: int, status: str) -> None:
        self.conn.execute("UPDATE lessons SET status = ? WHERE id = ?", (status, lesson_id))
        self.conn.commit()

    def cancel_lesson(self, lesson_id: int) -> None:
        self.conn.execute("UPDATE lessons SET status = 'cancelled' WHERE id = ?", (lesson_id,))
        self.conn.execute("DELETE FROM grades WHERE lesson_id = ?", (lesson_id,))
        self.conn.commit()

    def delete_lesson(self, lesson_id: int) -> None:
        self.conn.execute("DELETE FROM grades WHERE lesson_id = ?", (lesson_id,))
        self.conn.execute("DELETE FROM lessons WHERE id = ?", (lesson_id,))
        self.conn.commit()

    def list_lessons_by_date(self, date: str) -> Sequence[sqlite3.Row]:
        return self.conn.execute("""
            SELECT l.*, ps.name AS planned_subject,
                COALESCE(fs.name, ps.name) AS actual_subject_name,
                g.name AS group_name,
                ps.group_id
            FROM lessons l
            JOIN subjects ps ON l.subject_id = ps.id
            LEFT JOIN subjects fs ON l.actual_subject_id = fs.id
            JOIN groups g ON ps.group_id = g.id
            WHERE l.date = ?
            ORDER BY COALESCE(l.lesson_number, 999), ps.name, l.id
        """, (date,)).fetchall()

    def find_held_lesson(self, subject_id: int, date: str, lesson_number: Optional[int] = None) -> Optional[sqlite3.Row]:
        """Найти уже созданное проведённое занятие, чтобы не плодить дубли по двойному тапу."""
        if lesson_number is None:
            return None
        return self.conn.execute("""
            SELECT * FROM lessons
            WHERE subject_id = ? AND date = ? AND lesson_number = ? AND status = 'held'
            ORDER BY id LIMIT 1
        """, (subject_id, date, lesson_number)).fetchone()

    def list_lessons_for_subject(self, subject_id: int) -> Sequence[sqlite3.Row]:
        return self.conn.execute("""
            SELECT l.*, ps.name AS planned_subject,
                COALESCE(fs.name, ps.name) AS actual_subject_name
            FROM lessons l
            JOIN subjects ps ON l.subject_id = ps.id
            LEFT JOIN subjects fs ON l.actual_subject_id = fs.id
            WHERE l.subject_id = ? OR l.actual_subject_id = ?
            ORDER BY l.date DESC, COALESCE(l.lesson_number, 999), l.id DESC
        """, (subject_id, subject_id)).fetchall()

    def get_adjacent_lessons(self, lesson_id: int) -> tuple[Optional[int], Optional[int]]:
        lesson = self.conn.execute("SELECT subject_id, date FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
        if not lesson:
            return None, None
        rows = self.conn.execute("""
            SELECT id FROM lessons WHERE subject_id = ?
            ORDER BY date, COALESCE(lesson_number, 999), id
        """, (lesson['subject_id'],)).fetchall()
        ids = [r['id'] for r in rows]
        try:
            i = ids.index(lesson_id)
        except ValueError:
            return None, None
        prev_id = ids[i - 1] if i > 0 else None
        next_id = ids[i + 1] if i + 1 < len(ids) else None
        return prev_id, next_id

    def substitute_lesson(self, lesson_id: int, new_subject_id: int) -> int:
        lesson = self.conn.execute("SELECT date, lesson_number FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
        if not lesson:
            raise ValueError("Lesson not found")
        self.cancel_lesson(lesson_id)
        new_id = self.add_lesson(new_subject_id, lesson['date'], new_subject_id, 'held', lesson['lesson_number'])
        return new_id

    def get_substitutions(self) -> Sequence[sqlite3.Row]:
        return []

    def mark_attendance(self, lesson_id: int, student_id: int, grade: str) -> None:
        if not grade:
            self.conn.execute("DELETE FROM grades WHERE lesson_id = ? AND student_id = ?", (lesson_id, student_id))
        else:
            self.conn.execute("""
                INSERT INTO grades (lesson_id, student_id, grade) VALUES (?, ?, ?)
                ON CONFLICT(lesson_id, student_id) DO UPDATE SET grade = excluded.grade
            """, (lesson_id, student_id, grade))
        self.conn.commit()

    def mark_attendance_bulk(self, lesson_id: int, records: list[dict]) -> None:
        mark = self.mark_attendance
        for r in records:
            mark(lesson_id, r['student_id'], r['grade'])

    def get_attendance(self, lesson_id: int) -> Sequence[sqlite3.Row]:
        return self.conn.execute("""
            SELECT g.*, s.last_name, s.first_name, s.middle_name
            FROM grades g
            JOIN students s ON g.student_id = s.id
            WHERE g.lesson_id = ?
            ORDER BY s.last_name, s.first_name
        """, (lesson_id,)).fetchall()

    def attendance_count(self, lesson_id: int) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM grades WHERE lesson_id = ?", (lesson_id,)
        ).fetchone()[0]

    def student_grades(self, student_id: int, subject_id: Optional[int] = None) -> Sequence[sqlite3.Row]:
        if subject_id is not None:
            return self.conn.execute("""
                SELECT g.*, l.date, COALESCE(fs.name, ps.name) AS subject_name
                FROM grades g
                JOIN lessons l ON g.lesson_id = l.id
                JOIN subjects ps ON l.subject_id = ps.id
                LEFT JOIN subjects fs ON l.actual_subject_id = fs.id
                WHERE g.student_id = ? AND (l.subject_id = ? OR l.actual_subject_id = ?)
                ORDER BY l.date DESC
            """, (student_id, subject_id, subject_id)).fetchall()
        return self.conn.execute("""
            SELECT g.*, l.date, COALESCE(fs.name, ps.name) AS subject_name
            FROM grades g
            JOIN lessons l ON g.lesson_id = l.id
            JOIN subjects ps ON l.subject_id = ps.id
            LEFT JOIN subjects fs ON l.actual_subject_id = fs.id
            WHERE g.student_id = ?
            ORDER BY l.date DESC
        """, (student_id,)).fetchall()

    def average_grades(self, subject_id: int) -> Sequence[sqlite3.Row]:
        return self.conn.execute("""
            SELECT s.id, s.last_name, s.first_name, s.middle_name,
                ROUND(AVG(CAST(g.grade AS REAL)), 2) AS average
            FROM students s
            JOIN grades g ON g.student_id = s.id
            JOIN lessons l ON g.lesson_id = l.id
            WHERE l.actual_subject_id = ? AND l.status NOT IN ('cancelled', 'replaced') AND g.grade IN ('2', '3', '4', '5')
            GROUP BY s.id
            ORDER BY average DESC
        """, (subject_id,)).fetchall()

    def get_group_students(self, lesson_id: int) -> Sequence[sqlite3.Row]:
        return self.conn.execute("""
            SELECT s.* FROM students s
            WHERE s.group_id = (SELECT ps.group_id FROM lessons l JOIN subjects ps ON l.subject_id = ps.id WHERE l.id = ?)
            ORDER BY s.last_name, s.first_name
        """, (lesson_id,)).fetchall()

    def daily_report(self, date: Optional[str] = None) -> Sequence[sqlite3.Row]:
        if date is None:
            from datetime import date as dt_date
            date = dt_date.today().isoformat()
        return self.conn.execute("""
            SELECT l.id, l.status, COALESCE(fs.name, ps.name) AS subject_name, g.name AS group_name,
                COUNT(gr.id) AS grades_count,
                SUM(CASE WHEN gr.grade = 'absent' THEN 1 ELSE 0 END) AS absent_count
            FROM lessons l
            JOIN subjects ps ON l.subject_id = ps.id
            LEFT JOIN subjects fs ON l.actual_subject_id = fs.id
            JOIN groups g ON ps.group_id = g.id
            LEFT JOIN grades gr ON gr.lesson_id = l.id
            WHERE l.date = ?
            GROUP BY l.id
            ORDER BY subject_name
        """, (date,)).fetchall()

    def students_without_recent_grades(self, group_id: int, min_grades: int = 3, days: int = 14) -> Sequence[sqlite3.Row]:
        return self.conn.execute("""
            SELECT s.id, s.last_name, s.first_name, s.middle_name,
                COUNT(g.id) AS recent_grades
            FROM students s
            LEFT JOIN grades g ON g.student_id = s.id
            LEFT JOIN lessons l ON g.lesson_id = l.id AND l.date >= date('now', ? || ' days') AND l.status NOT IN ('cancelled', 'replaced')
            WHERE s.group_id = ?
            GROUP BY s.id
            HAVING COUNT(g.id) < ?
        """, (f'-{days}', group_id, min_grades)).fetchall()

    def _is_empty(self) -> bool:
        return self.conn.execute("SELECT COUNT(*) AS c FROM groups").fetchone()['c'] == 0

    def seed_default(self) -> None:
        if not self._is_empty():
            return
        gid = self.add_group('ИС-11')
        for s in [
            ('Иванов', 'Иван', 'Иванович'),
            ('Петров', 'Пётр', 'Петрович'),
            ('Сидорова', 'Мария', 'Сергеевна'),
            ('Кузнецов', 'Алексей', 'Андреевич'),
            ('Смирнова', 'Ольга', 'Викторовна'),
        ]:
            self.add_student(gid, *s)
        math_id = self.add_subject('Математика', 100, gid)
        lit_id = self.add_subject('Литература', 100, gid)
        for day in range(1, 6):
            self.add_schedule_entry(day, 1, math_id, 0)
            self.add_schedule_entry(day, 2, lit_id, 0)
        self.add_schedule_entry(6, 1, lit_id, 1)
        self.add_schedule_entry(6, 2, lit_id, 1)
        self.add_schedule_entry(6, 1, math_id, 2)
        self.add_schedule_entry(6, 2, math_id, 2)

    def close(self) -> None:
        try:
            self.conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        except Exception:
            pass
        self.conn.close()
