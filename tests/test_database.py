"""
Тесты «чистой» логики слоя БД (без Kivy/UI). Гоняются в CI.
Запуск: pytest -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import Database  # noqa: E402


def make_db() -> Database:
    db = Database(":memory:")
    db.init_schema()
    return db


def test_group_uniqueness():
    db = make_db()
    a = db.add_group("ИС-11")
    b = db.add_group("ИС-11")  # тот же => тот же id, не дубликат
    assert a == b
    assert len(db.list_groups()) == 1


def test_student_no_duplicates():
    db = make_db()
    db.add_student("ИС-11", "Иванов И.")
    db.add_student("ИС-11", "Иванов И.")  # дубликат игнорируется
    assert len(db.list_students("ИС-11")) == 1


def test_bulk_students_counts_new_only():
    db = make_db()
    added = db.add_students_bulk("ИС-11", ["Иванов И.", "", "Петров П.", "Иванов И."])
    assert added == 2
    assert len(db.list_students("ИС-11")) == 2


def test_subject_progress_in_lessons():
    db = make_db()
    sid = db.add_subject("Математика", planned_lessons=3, group_name="ИС-11")
    db.add_lesson(sid, "2026-09-01T10:00:00")
    subjects = {s["name"]: s for s in db.list_subjects()}
    m = subjects["Математика"]
    assert m["planned"] == 3
    assert m["held"] == 1
    assert m["remaining"] == 2


def test_attendance_upsert():
    db = make_db()
    sid = db.add_subject("Математика", 3, "ИС-11")
    stud = db.add_student("ИС-11", "Иванов И.")
    lid = db.add_lesson(sid, "2026-09-01T10:00:00")
    db.mark_attendance(lid, stud, present=True, grade=None)
    db.mark_attendance(lid, stud, present=True, grade=5)  # обновление, не дубликат
    rows = db._conn.execute(
        "SELECT present, grade FROM attendance WHERE lesson_id=? AND student_id=?",
        (lid, stud),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["grade"] == 5