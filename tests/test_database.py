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


def test_only_held_counts_as_progress():
    """В прогресс идут только занятия со статусом 'held' (не scheduled/cancelled)."""
    db = make_db()
    sid = db.add_subject("Математика", planned_lessons=5, group_name="ИС-11")
    db.add_lesson(sid, "2026-09-01T10:00:00", status="held")
    db.add_lesson(sid, "2026-09-01T14:00:00", status="scheduled")  # ещё не проведено
    db.add_lesson(sid, "2026-09-02T10:00:00", status="cancelled")  # отменено
    m = {s["name"]: s for s in db.list_subjects()}["Математика"]
    assert m["held"] == 1           # только одно проведённое
    assert m["remaining"] == 4


def test_set_lesson_status_cancel_excludes_from_progress():
    """Отмена проведённого занятия убирает его из учёта, но запись остаётся."""
    db = make_db()
    sid = db.add_subject("Математика", 5, "ИС-11")
    lid = db.add_lesson(sid, "2026-09-01T10:00:00", status="held")
    assert {s["name"]: s for s in db.list_subjects()}["Математика"]["held"] == 1
    db.set_lesson_status(lid, "cancelled")
    assert {s["name"]: s for s in db.list_subjects()}["Математика"]["held"] == 0
    assert db.get_lesson(lid)["status"] == "cancelled"  # запись не удалена


def test_get_and_update_subject():
    """Редактирование карточки предмета: название, план, группа; занятия сохраняются."""
    db = make_db()
    sid = db.add_subject("Математика", planned_lessons=10, group_name="ИС-11")
    db.add_lesson(sid, "2026-09-01T09:00:00", status="held")

    card = db.get_subject(sid)
    assert card["name"] == "Математика"
    assert card["planned"] == 10
    assert card["group_name"] == "ИС-11"

    db.update_subject(sid, "Высшая математика", 15, "ИС-12")
    card = db.get_subject(sid)
    assert card["name"] == "Высшая математика"
    assert card["planned"] == 15
    assert card["group_name"] == "ИС-12"

    # Проведённое занятие осталось привязанным — учёт не потерян.
    m = {s["id"]: s for s in db.list_subjects()}[sid]
    assert m["held"] == 1
    assert m["remaining"] == 14


def test_update_subject_rejects_duplicate():
    """Нельзя переименовать предмет так, чтобы совпал с другим (имя+группа)."""
    db = make_db()
    db.add_subject("Высшая математика", 5, "ИС-12")
    sid2 = db.add_subject("Физика", 5, "ИС-12")
    import pytest
    with pytest.raises(ValueError):
        db.update_subject(sid2, "Высшая математика", 5, "ИС-12")


def test_get_subject_missing_returns_none():
    db = make_db()
    assert db.get_subject(999) is None


def test_multiple_lessons_same_day_same_subject():
    """По одному предмету в день может быть несколько занятий (в т.ч. параллельных)."""
    db = make_db()
    sid = db.add_subject("Математика", 10, "ИС-11")
    db.add_lesson(sid, "2026-09-01T09:00:00", status="scheduled")
    db.add_lesson(sid, "2026-09-01T14:00:00", status="scheduled")
    same_day = db.list_lessons_by_date(sid, "2026-09-01")
    assert len(same_day) == 2


def test_schedule_for_date_all_subjects():
    """Расписание на дату содержит занятия ВСЕХ предметов независимо от статуса."""
    db = make_db()
    s1 = db.add_subject("Математика", 5, "ИС-11")
    s2 = db.add_subject("Программирование", 5, "ИС-11")
    db.add_lesson(s1, "2026-09-01T09:00:00", status="scheduled")
    db.add_lesson(s2, "2026-09-01T09:00:00", status="scheduled")  # параллельное
    db.add_lesson(s1, "2026-09-02T09:00:00", status="held")       # другой день
    sched = db.list_schedule_for_date("2026-09-01")
    assert len(sched) == 2
    assert {r["subject_name"] for r in sched} == {"Математика", "Программирование"}


def test_change_lesson_subject_clears_attendance():
    """Замена предмета у занятия переносит его и очищает прежние отметки."""
    db = make_db()
    s1 = db.add_subject("Математика", 5, "ИС-11")
    s2 = db.add_subject("Физика", 5, "ИС-11")
    stud = db.add_student("ИС-11", "Иванов И.")
    lid = db.add_lesson(s1, "2026-09-01T09:00:00", status="held")
    db.mark_attendance(lid, stud, present=True, grade=5)
    db.change_lesson_subject(lid, s2)
    assert db.get_lesson(lid)["subject_id"] == s2
    assert db.get_attendance(lid) == {}  # отметки очищены


def test_calendar_excludes_cancelled():
    """Выгрузка в календарь не включает отменённые занятия."""
    db = make_db()
    sid = db.add_subject("Математика", 5, "ИС-11")
    db.add_lesson(sid, "2026-09-01T09:00:00", status="held")
    db.add_lesson(sid, "2026-09-02T09:00:00", status="cancelled")
    cal = db.list_lessons_for_calendar()
    assert len(cal) == 1
    assert cal[0]["status"] != "cancelled"


def test_subject_gradebook_avg_and_attendance():
    """Ведомость: средний балл по held-занятиям + счётчики присут./отсут."""
    db = make_db()
    sid = db.add_subject("Математика", 5, "ИС-11")
    a = db.add_student("ИС-11", "Алексеев А.")
    b = db.add_student("ИС-11", "Борисов Б.")
    l1 = db.add_lesson(sid, "2026-09-01T10:00:00", status="held")
    l2 = db.add_lesson(sid, "2026-09-02T10:00:00", status="held")
    lc = db.add_lesson(sid, "2026-09-03T10:00:00", status="cancelled")
    # Алексеев: 5 и 4 (среднее 4.5), присут. 2 раза.
    db.mark_attendance(l1, a, present=True, grade=5)
    db.mark_attendance(l2, a, present=True, grade=4)
    # Оценка на отменённом занятии НЕ должна учитываться.
    db.mark_attendance(lc, a, present=True, grade=2)
    # Борисов: одна галочка без оценки + один пропуск.
    db.mark_attendance(l1, b, present=True, grade=None)
    db.mark_attendance(l2, b, present=False)
    gb = {r["name"]: r for r in db.subject_gradebook(sid)}
    assert gb["Алексеев А."]["avg_grade"] == 4.5
    assert gb["Алексеев А."]["grades_count"] == 2
    assert gb["Алексеев А."]["present_count"] == 2
    assert gb["Борисов Б."]["avg_grade"] is None
    assert gb["Борисов Б."]["present_count"] == 1
    assert gb["Борисов Б."]["absent_count"] == 1


def test_subject_summary_progress():
    db = make_db()
    sid = db.add_subject("Математика", 4, "ИС-11")
    db.add_lesson(sid, "2026-09-01T10:00:00", status="held")
    s = db.subject_summary(sid)
    assert s["planned"] == 4 and s["held"] == 1 and s["remaining"] == 3


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