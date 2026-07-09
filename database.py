"""
database.py — ЕДИНСТВЕННОЕ место в проекте, где есть SQL/доступ к SQLite.

Принципы (см. AGENT.md):
  * Единица учёта — ЗАНЯТИЕ (не час). У предмета есть план в занятиях.
  * Неповторяемость данных: группы и студенты уникальны, повторно выбираются, а не дублируются.
  * Миграция на другую СУБД = переписать ТОЛЬКО этот файл, сохранив сигнатуры функций.

Использование:
    db = Database("lessons.db")   # или ":memory:" в тестах
    db.init_schema()
    sid = db.add_subject("Математика", planned_lessons=32, group_name="ИС-11")
    db.add_students_bulk("ИС-11", ["Иванов И.", "Петров П."])
"""
from __future__ import annotations

import sqlite3
from typing import Optional


class Database:
    def __init__(self, path: str = "lessons.db") -> None:
        # check_same_thread=False — Kivy может дёргать БД из разных потоков (напоминания).
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # Внешние ключи в SQLite по умолчанию выключены — включаем.
        self._conn.execute("PRAGMA foreign_keys = ON")

    # ------------------------------------------------------------------ schema
    def init_schema(self) -> None:
        """Создаёт все таблицы, если их ещё нет. Идемпотентно."""
        cur = self._conn.cursor()
        cur.executescript(
            """
            -- Группы. Имя уникально => неповторяемость.
            CREATE TABLE IF NOT EXISTS groups (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            -- Студенты. Уникальны в пределах своей группы.
            CREATE TABLE IF NOT EXISTS students (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
                name     TEXT NOT NULL,
                UNIQUE(group_id, name)
            );

            -- Предметы. planned_lessons — план В ЗАНЯТИЯХ.
            CREATE TABLE IF NOT EXISTS subjects (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT NOT NULL,
                planned_lessons INTEGER NOT NULL DEFAULT 0,
                group_id        INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
                UNIQUE(name, group_id)
            );

            -- Проведённые занятия (факт).
            CREATE TABLE IF NOT EXISTS lessons (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
                held_at    TEXT NOT NULL        -- ISO-дата/время проведения
            );

            -- Отметки: присутствие + опциональная оценка.
            CREATE TABLE IF NOT EXISTS attendance (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                lesson_id  INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
                student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                present    INTEGER NOT NULL DEFAULT 0,   -- 0/1
                grade      INTEGER,                      -- NULL, если только «галочка»
                UNIQUE(lesson_id, student_id)
            );
            """
        )
        self._conn.commit()

    # ------------------------------------------------------------------ groups
    def add_group(self, name: str) -> int:
        """Создаёт группу или возвращает id уже существующей (неповторяемость)."""
        name = name.strip()
        cur = self._conn.cursor()
        cur.execute("INSERT OR IGNORE INTO groups(name) VALUES (?)", (name,))
        self._conn.commit()
        row = cur.execute("SELECT id FROM groups WHERE name = ?", (name,)).fetchone()
        return int(row["id"])

    def list_groups(self) -> list[dict]:
        rows = self._conn.execute("SELECT id, name FROM groups ORDER BY name").fetchall()
        return [dict(r) for r in rows]

    # ---------------------------------------------------------------- students
    def add_student(self, group_name: str, student_name: str) -> int:
        """Добавляет студента в группу; дубликат (та же группа + ФИО) игнорируется."""
        gid = self.add_group(group_name)
        student_name = student_name.strip()
        cur = self._conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO students(group_id, name) VALUES (?, ?)",
            (gid, student_name),
        )
        self._conn.commit()
        row = cur.execute(
            "SELECT id FROM students WHERE group_id = ? AND name = ?",
            (gid, student_name),
        ).fetchone()
        return int(row["id"])

    def add_students_bulk(self, group_name: str, names: list[str]) -> int:
        """
        Массовый ввод: список ФИО (каждый с новой строки уже разбит вызывающим кодом).
        Пустые строки пропускаются. Возвращает число реально добавленных (без дублей).
        """
        added = 0
        existing_before = {s["name"] for s in self.list_students(group_name)}
        for raw in names:
            name = raw.strip()
            if not name:
                continue
            self.add_student(group_name, name)
            if name not in existing_before:
                added += 1
                existing_before.add(name)
        return added

    def list_students(self, group_name: str) -> list[dict]:
        rows = self._conn.execute(
            """
            SELECT s.id, s.name
            FROM students s JOIN groups g ON g.id = s.group_id
            WHERE g.name = ?
            ORDER BY s.name
            """,
            (group_name.strip(),),
        ).fetchall()
        return [dict(r) for r in rows]

    # ---------------------------------------------------------------- subjects
    def add_subject(self, name: str, planned_lessons: int, group_name: str) -> int:
        """Создаёт предмет для группы; дубликат (имя + группа) не создаётся повторно."""
        gid = self.add_group(group_name)
        name = name.strip()
        cur = self._conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO subjects(name, planned_lessons, group_id) VALUES (?, ?, ?)",
            (name, int(planned_lessons), gid),
        )
        self._conn.commit()
        row = cur.execute(
            "SELECT id FROM subjects WHERE name = ? AND group_id = ?", (name, gid)
        ).fetchone()
        return int(row["id"])

    def list_subjects(self) -> list[dict]:
        """
        Список предметов с прогрессом в ЗАНЯТИЯХ (для главного экрана):
        planned / held / remaining.
        """
        rows = self._conn.execute(
            """
            SELECT
                sub.id,
                sub.name,
                g.name AS group_name,
                sub.planned_lessons AS planned,
                (SELECT COUNT(1) FROM lessons l WHERE l.subject_id = sub.id) AS held
            FROM subjects sub
            JOIN groups g ON g.id = sub.group_id
            ORDER BY sub.name
            """
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["remaining"] = max(0, int(d["planned"]) - int(d["held"]))
            result.append(d)
        return result

    # ----------------------------------------------------------------- lessons
    def add_lesson(self, subject_id: int, held_at: str) -> int:
        """Фиксирует факт проведённого занятия (безусловное создание новой записи)."""
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO lessons(subject_id, held_at) VALUES (?, ?)",
            (int(subject_id), held_at),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def get_or_create_lesson(self, subject_id: int, date_str: str, held_at: str) -> int:
        """
        Возвращает id занятия для предмета за указанную ДАТУ (date_str = 'YYYY-MM-DD'),
        создавая его при отсутствии. Именно это защищает от:
          * дублирования занятий (повторный вход в отметку не плодит новые записи и
            не завышает счётчик проведённых занятий);
          * потери введённых отметок (по этому id далее подтягиваются сохранённые оценки).
        Сопоставление по дате: date(held_at) сравнивается с date_str.
        """
        cur = self._conn.cursor()
        row = cur.execute(
            "SELECT id FROM lessons WHERE subject_id = ? AND date(held_at) = ?",
            (int(subject_id), date_str),
        ).fetchone()
        if row:
            return int(row["id"])
        cur.execute(
            "INSERT INTO lessons(subject_id, held_at) VALUES (?, ?)",
            (int(subject_id), held_at),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def get_attendance(self, lesson_id: int) -> dict:
        """
        Возвращает сохранённые отметки занятия в виде
        {student_id: {"present": bool, "grade": Optional[int]}}.
        Нужна, чтобы при повторном открытии занятия подтянуть введённые ранее оценки.
        """
        rows = self._conn.execute(
            "SELECT student_id, present, grade FROM attendance WHERE lesson_id = ?",
            (int(lesson_id),),
        ).fetchall()
        return {
            int(r["student_id"]): {"present": bool(r["present"]), "grade": r["grade"]}
            for r in rows
        }

    def mark_attendance(
        self,
        lesson_id: int,
        student_id: int,
        present: bool,
        grade: Optional[int] = None,
    ) -> None:
        """Отмечает присутствие/оценку. Повторный вызов обновляет отметку (UPSERT)."""
        self._conn.execute(
            """
            INSERT INTO attendance(lesson_id, student_id, present, grade)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(lesson_id, student_id)
            DO UPDATE SET present = excluded.present, grade = excluded.grade
            """,
            (int(lesson_id), int(student_id), 1 if present else 0, grade),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()