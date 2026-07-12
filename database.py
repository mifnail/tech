from __future__ import annotations
import sqlite3
import os
from typing import Optional, Sequence, Any

DB_PATH = os.path.join(os.path.dirname(__file__), 'lessons.db')

class Database:
    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or DB_PATH
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
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
                actual_subject_id INTEGER REFERENCES subjects(id),
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

    def list_subjects(self, group_id: Optional[int] = None, include_free: bool = False) -> Sequence[sqlite3.Row]:
        base = """SELECT s.*, g.name AS group_name,
            COALESCE(h.held, 0) AS held_lessons,
            s.total_hours - COALESCE(h.held, 0) AS remaining
            FROM subjects s
            JOIN groups g ON s.group_id = g.id
            LEFT JOIN (
                SELECT actual_subject_id, COUNT(*) AS held
                FROM lessons WHERE status != 'free' AND actual_subject_id IS NOT NULL
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

    def subject_gradebook(self, subject_id: int) -> Sequence[sqlite3.Row]:
        return self.conn.execute("""
            SELECT s.id AS student_id, s.last_name, s.first_name, s.middle_name,
                g.grade, g.lesson_id, l.date
            FROM students s
            LEFT JOIN grades g ON g.student_id = s.id
            LEFT JOIN lessons l ON g.lesson_id = l.id AND l.actual_subject_id = ? AND l.status != 'free'
            WHERE s.group_id = (SELECT group_id FROM subjects WHERE id = ?)
            ORDER BY s.last_name, s.first_name, l.date
        """, (subject_id, subject_id)).fetchall()

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
                FROM lessons WHERE actual_subject_id = ? AND status != 'free'
                GROUP BY actual_subject_id
            ) h ON 1=1
            LEFT JOIN (
                SELECT l.actual_subject_id, ROUND(AVG(CAST(gr.grade AS REAL)), 2) AS average
                FROM grades gr
                JOIN lessons l ON gr.lesson_id = l.id
                WHERE l.actual_subject_id = ? AND l.status != 'free' AND gr.grade NOT IN ('absent', 'pass', 'fail')
                GROUP BY l.actual_subject_id
            ) avg ON 1=1
            LEFT JOIN (
                SELECT l.actual_subject_id, COUNT(DISTINCT gr.student_id) AS total_students
                FROM grades gr
                JOIN lessons l ON gr.lesson_id = l.id
                WHERE l.actual_subject_id = ? AND l.status != 'free'
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

    def get_schedule_for_day(self, day_of_week: int) -> Sequence[sqlite3.Row]:
        return self.conn.execute("""
            SELECT sch.*, sub.name AS subject_name, g.name AS group_name
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

    def add_lesson(self, subject_id: int, date: str, actual_subject_id: Optional[int] = None, status: str = 'held') -> int:
        cur = self.conn.execute(
            "INSERT INTO lessons (subject_id, actual_subject_id, date, status) VALUES (?, ?, ?, ?)",
            (subject_id, actual_subject_id, date, status))
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

    def set_lesson_status(self, lesson_id: int, status: str) -> None:
        self.conn.execute("UPDATE lessons SET status = ? WHERE id = ?", (status, lesson_id))
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
            ORDER BY ps.name
        """, (date,)).fetchall()

    def list_lessons_for_subject(self, subject_id: int) -> Sequence[sqlite3.Row]:
        return self.conn.execute("""
            SELECT l.*, ps.name AS planned_subject,
                COALESCE(fs.name, ps.name) AS actual_subject_name
            FROM lessons l
            JOIN subjects ps ON l.subject_id = ps.id
            LEFT JOIN subjects fs ON l.actual_subject_id = fs.id
            WHERE l.subject_id = ? OR l.actual_subject_id = ?
            ORDER BY l.date DESC
        """, (subject_id, subject_id)).fetchall()

    def get_adjacent_lessons(self, lesson_id: int) -> tuple[Optional[int], Optional[int]]:
        lesson = self.conn.execute("SELECT subject_id, date FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
        if not lesson:
            return None, None
        prev_row = self.conn.execute("""
            SELECT id FROM lessons WHERE subject_id = ? AND date < ? ORDER BY date DESC LIMIT 1
        """, (lesson['subject_id'], lesson['date'])).fetchone()
        next_row = self.conn.execute("""
            SELECT id FROM lessons WHERE subject_id = ? AND date > ? ORDER BY date ASC LIMIT 1
        """, (lesson['subject_id'], lesson['date'])).fetchone()
        return (prev_row['id'] if prev_row else None, next_row['id'] if next_row else None)

    def substitute_lesson(self, lesson_id: int, new_subject_id: int) -> None:
        is_free = self.is_free_subject(new_subject_id)
        status = 'free' if is_free else 'held'
        self.conn.execute("UPDATE lessons SET actual_subject_id = ?, status = ? WHERE id = ?",
                          (new_subject_id if not is_free else new_subject_id, status, lesson_id))
        self.conn.commit()

    def get_substitutions(self) -> Sequence[sqlite3.Row]:
        return self.conn.execute("""
            SELECT l.*, ps.name AS planned_subject, COALESCE(fs.name, ps.name) AS actual_subject_name,
                g.name AS group_name
            FROM lessons l
            JOIN subjects ps ON l.subject_id = ps.id
            LEFT JOIN subjects fs ON l.actual_subject_id = fs.id
            JOIN groups g ON ps.group_id = g.id
            WHERE l.actual_subject_id IS NOT NULL AND l.actual_subject_id != l.subject_id
            ORDER BY l.date DESC
        """).fetchall()

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
            WHERE l.actual_subject_id = ? AND l.status != 'free' AND g.grade NOT IN ('absent', 'pass', 'fail')
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
            LEFT JOIN lessons l ON g.lesson_id = l.id AND l.date >= date('now', ? || ' days') AND l.status != 'free'
            WHERE s.group_id = ?
            GROUP BY s.id
            HAVING COUNT(g.id) < ?
        """, (f'-{days}', group_id, min_grades)).fetchall()

    def close(self) -> None:
        self.conn.close()
