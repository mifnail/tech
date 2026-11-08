"""Отменённое занятие не должно выглядеть как запланированное.

Регресс: `subject_gradebook` отфильтровывал status='cancelled'. После
перезагрузки приложения отменённое занятие пропадало из локальной БД,
слот в расписании освобождался, и плановая строка снова отображалась
как «запланированное занятие» — хотя уведомление об отмене студентам
и куратору уже ушло.
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def journal(tmp_path):
    import database
    db = database.Database(str(tmp_path / 'journal.db'))
    group_id = db.add_group('АДТ-31')
    subject_id = db.add_subject('МДК.01', 30, group_id)
    student_id = db.add_student(group_id, 'Иванов', 'Иван', 'И')
    lesson_id = db.add_lesson(subject_id, '2026-11-06', status='scheduled')
    db.mark_attendance_bulk(lesson_id, [{'student_id': student_id, 'grade': '4'}])
    yield db, group_id, subject_id, student_id, lesson_id
    db.close()


def test_cancelled_lesson_stays_in_gradebook(journal):
    """Отмена меняет статус, но занятие остаётся в выдаче предмета."""
    db, _, subject_id, _, lesson_id = journal
    db.cancel_lesson(lesson_id)

    _, lessons, grades = db.subject_gradebook(subject_id)
    rows = {row['id']: row for row in lessons}

    assert lesson_id in rows, 'отменённое занятие пропало из gradebook'
    assert rows[lesson_id]['status'] == 'cancelled'
    # Оценок у отменённого нет — они удалены при отмене.
    assert grades == {}


def test_cancelled_lesson_does_not_count_as_held(journal):
    db, _, subject_id, _, lesson_id = journal
    db.cancel_lesson(lesson_id)

    summary = db.subject_summary(subject_id)
    assert summary['held_lessons'] == 0
    assert summary['remaining'] == 30


def test_replaced_lesson_is_still_hidden(journal):
    """Заменённое занятие — другое дело: его в выдаче быть не должно."""
    db, _, subject_id, _, lesson_id = journal
    db.conn.execute("UPDATE lessons SET status = 'replaced' WHERE id = ?", (lesson_id,))
    db.conn.commit()

    _, lessons, _ = db.subject_gradebook(subject_id)
    assert lesson_id not in {row['id'] for row in lessons}


@pytest.fixture()
def client():
    """Клиент API поверх общей тестовой БД (как в test_api.py)."""
    import api as api_module
    from database import Database
    api_module.app.config['TESTING'] = True
    original_db_fn = api_module.get_db
    _db = Database(':memory:')
    api_module.get_db = lambda: _db
    with api_module.app.test_client() as c:
        yield c
    _db.close()
    api_module.get_db = original_db_fn


def test_api_gradebook_returns_cancelled_lesson(client):
    """Фронт получает отменённое занятие и не рисует план заново."""
    import api as api_module
    db = api_module.get_db()
    group_id = db.add_group('АДТ-31')
    subject_id = db.add_subject('МДК.01', 30, group_id)
    lesson_id = db.add_lesson(subject_id, '2026-11-06', status='scheduled')
    db.cancel_lesson(lesson_id)

    rv = client.get(f'/api/subjects/{subject_id}/gradebook')
    assert rv.status_code == 200
    lessons = {row['id']: row for row in rv.get_json()['lessons']}
    assert lesson_id in lessons
    assert lessons[lesson_id]['status'] == 'cancelled'
