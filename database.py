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

            -- Занятия. У КАЖДОГО занятия есть СТАТУС:
            --   'scheduled' — по расписанию, ещё не проведено;
            --   'held'      — проведено (ТОЛЬКО такие идут в прогресс/учёт);
            --   'cancelled' — отменено (остаётся в БД как «не проведено», в учёт НЕ идёт).
            -- По одному предмету в день может быть НЕСКОЛЬКО занятий (в т.ч. параллельных).
            CREATE TABLE IF NOT EXISTS lessons (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
                held_at    TEXT NOT NULL,       -- ISO-дата/время занятия
                status     TEXT NOT NULL DEFAULT 'held'  -- scheduled | held | cancelled
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
        self._migrate_add_lesson_status()

    def _migrate_add_lesson_status(self) -> None:
        """
        Миграция для уже существующих lessons.db (созданных до появления статуса):
        добавляет колонку lessons.status со значением по умолчанию 'held', чтобы
        ранее проведённые занятия остались учтёнными. Идемпотентно.
        """
        cols = [
            r["name"]
            for r in self._conn.execute("PRAGMA table_info(lessons)").fetchall()
        ]
        if "status" not in cols:
            self._conn.execute(
                "ALTER TABLE lessons ADD COLUMN status TEXT NOT NULL DEFAULT 'held'"
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
                (SELECT COUNT(1) FROM lessons l
                   WHERE l.subject_id = sub.id AND l.status = 'held') AS held
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

    # -------------------------------------------------------------- gradebook
    def subject_summary(self, subject_id: int) -> Optional[dict]:
        """
        Сводка по ОДНОМУ предмету: план / проведено / осталось (в ЗАНЯТИЯХ).
        Проведённые — только занятия со статусом 'held'.
        """
        row = self._conn.execute(
            """
            SELECT sub.id, sub.name, g.name AS group_name,
                   sub.planned_lessons AS planned,
                   (SELECT COUNT(1) FROM lessons l
                      WHERE l.subject_id = sub.id AND l.status = 'held') AS held
            FROM subjects sub
            JOIN groups g ON g.id = sub.group_id
            WHERE sub.id = ?
            """,
            (int(subject_id),),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["remaining"] = max(0, int(d["planned"]) - int(d["held"]))
        return d

    def subject_gradebook(self, subject_id: int) -> list[dict]:
        """
        ВЕДОМОСТЬ УСПЕВАЕМОСТИ по предмету — ПОФАМИЛЬНО. Для каждого студента группы:
          name          — ФИО,
          avg_grade     — среднеарифметический балл по его оценкам (None, если оценок нет),
          grades_count  — сколько оценок выставлено,
          present_count — на скольких проведённых занятиях отмечен как присутствующий,
          absent_count  — на скольких проведённых занятиях отмечен отсутствующим.

        Учитываются ТОЛЬКО занятия со статусом 'held' (отменённые/по расписанию — нет).
        Список отсортирован по ФИО. Средний балл считаем в Python (по «сырым» оценкам),
        чтобы избежать различий округления между СУБД.
        """
        # Группа предмета.
        subj = self._conn.execute(
            "SELECT sub.id, g.name AS group_name FROM subjects sub "
            "JOIN groups g ON g.id = sub.group_id WHERE sub.id = ?",
            (int(subject_id),),
        ).fetchone()
        if not subj:
            return []
        students = self.list_students(subj["group_name"])

        # Все отметки по held-занятиям этого предмета: student_id, present, grade.
        rows = self._conn.execute(
            """
            SELECT a.student_id, a.present, a.grade
            FROM attendance a
            JOIN lessons l ON l.id = a.lesson_id
            WHERE l.subject_id = ? AND l.status = 'held'
            """,
            (int(subject_id),),
        ).fetchall()

        grades_by_student: dict[int, list[int]] = {}
        present_by_student: dict[int, int] = {}
        absent_by_student: dict[int, int] = {}
        for r in rows:
            sid = int(r["student_id"])
            if r["present"]:
                present_by_student[sid] = present_by_student.get(sid, 0) + 1
            else:
                absent_by_student[sid] = absent_by_student.get(sid, 0) + 1
            if r["grade"] is not None:
                grades_by_student.setdefault(sid, []).append(int(r["grade"]))

        result = []
        for st in students:
            sid = st["id"]
            grades = grades_by_student.get(sid, [])
            avg = round(sum(grades) / len(grades), 2) if grades else None
            result.append(
                {
                    "student_id": sid,
                    "name": st["name"],
                    "avg_grade": avg,
                    "grades_count": len(grades),
                    "present_count": present_by_student.get(sid, 0),
                    "absent_count": absent_by_student.get(sid, 0),
                }
            )
        return result

    # ----------------------------------------------------------------- lessons
    #
    # Статусы занятия:
    #   'scheduled' — по расписанию, ещё не проведено;
    #   'held'      — проведено (ТОЛЬКО такие идут в прогресс/учёт);
    #   'cancelled' — отменено (в БД остаётся «не проведено», в учёт НЕ идёт).
    LESSON_STATUSES = ("scheduled", "held", "cancelled")

    def add_lesson(self, subject_id: int, held_at: str, status: str = "held") -> int:
        """
        Создаёт занятие с указанным статусом (по умолчанию 'held' — совместимость с
        прежним кодом/seed). Для занятия по расписанию используйте status='scheduled',
        для внеочередного проведённого — 'held'.
        """
        if status not in self.LESSON_STATUSES:
            raise ValueError(f"Недопустимый статус занятия: {status}")
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO lessons(subject_id, held_at, status) VALUES (?, ?, ?)",
            (int(subject_id), held_at, status),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def set_lesson_status(self, lesson_id: int, status: str) -> None:
        """Меняет статус занятия (scheduled/held/cancelled). Отмена не удаляет запись."""
        if status not in self.LESSON_STATUSES:
            raise ValueError(f"Недопустимый статус занятия: {status}")
        self._conn.execute(
            "UPDATE lessons SET status = ? WHERE id = ?", (status, int(lesson_id))
        )
        self._conn.commit()

    def change_lesson_subject(self, lesson_id: int, subject_id: int) -> None:
        """
        Переносит занятие на другой предмет («заменить на другое»). Отметки
        посещаемости очищаются, т.к. состав группы у нового предмета может отличаться.
        """
        self._conn.execute(
            "DELETE FROM attendance WHERE lesson_id = ?", (int(lesson_id),)
        )
        self._conn.execute(
            "UPDATE lessons SET subject_id = ? WHERE id = ?",
            (int(subject_id), int(lesson_id)),
        )
        self._conn.commit()

    def get_lesson(self, lesson_id: int) -> Optional[dict]:
        """Одно занятие с данными предмета и группы (для экрана отметки/расписания)."""
        row = self._conn.execute(
            """
            SELECT l.id, l.subject_id, l.held_at, l.status,
                   sub.name AS subject_name, g.name AS group_name
            FROM lessons l
            JOIN subjects sub ON sub.id = l.subject_id
            JOIN groups g ON g.id = sub.group_id
            WHERE l.id = ?
            """,
            (int(lesson_id),),
        ).fetchone()
        return dict(row) if row else None

    def list_schedule_for_date(self, date_str: str) -> list[dict]:
        """
        РАСПИСАНИЕ НА ДЕНЬ: все занятия ВСЕХ предметов за дату (date_str='YYYY-MM-DD'),
        независимо от статуса — это отдельный от сводного главного экран.
        По одному предмету в день может быть НЕСКОЛЬКО занятий (в т.ч. параллельных).
        Для каждого — статус и счётчики отметок. Отсортировано по времени.
        """
        rows = self._conn.execute(
            """
            SELECT
                l.id,
                l.subject_id,
                l.held_at,
                l.status,
                sub.name AS subject_name,
                g.name   AS group_name,
                (SELECT COUNT(1) FROM attendance a
                   WHERE a.lesson_id = l.id AND a.present = 1) AS present_count,
                (SELECT COUNT(1) FROM attendance a
                   WHERE a.lesson_id = l.id AND a.grade IS NOT NULL) AS graded_count
            FROM lessons l
            JOIN subjects sub ON sub.id = l.subject_id
            JOIN groups g ON g.id = sub.group_id
            WHERE date(l.held_at) = ?
            ORDER BY l.held_at
            """,
            (date_str,),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_lessons_by_date(self, subject_id: int, date_str: str) -> list[dict]:
        """
        Список занятий ОДНОГО предмета за дату (date_str='YYYY-MM-DD') — со статусом
        и счётчиками отметок. Отсортировано по времени проведения.
        """
        rows = self._conn.execute(
            """
            SELECT
                l.id,
                l.held_at,
                l.status,
                (SELECT COUNT(1) FROM attendance a
                   WHERE a.lesson_id = l.id AND a.present = 1) AS present_count,
                (SELECT COUNT(1) FROM attendance a
                   WHERE a.lesson_id = l.id AND a.grade IS NOT NULL) AS graded_count
            FROM lessons l
            WHERE l.subject_id = ? AND date(l.held_at) = ?
            ORDER BY l.held_at
            """,
            (int(subject_id), date_str),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_lessons_for_calendar(self) -> list[dict]:
        """
        Данные для выгрузки в календарь (Google/Яндекс через .ics): все занятия, КРОМЕ
        отменённых, с временем начала и названием предмета/группой. Экспорт формирует
        calendar_export.py из этих строк.
        """
        rows = self._conn.execute(
            """
            SELECT l.id, l.held_at, l.status,
                   sub.name AS subject_name, g.name AS group_name
            FROM lessons l
            JOIN subjects sub ON sub.id = l.subject_id
            JOIN groups g ON g.id = sub.group_id
            WHERE l.status != 'cancelled'
            ORDER BY l.held_at
            """
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_lesson(self, lesson_id: int) -> None:
        """Удаляет занятие (и каскадно его отметки) — например, случайно созданное."""
        self._conn.execute("DELETE FROM lessons WHERE id = ?", (int(lesson_id),))
        self._conn.commit()

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