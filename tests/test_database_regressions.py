import socket
import sqlite3
from types import SimpleNamespace

import pytest

from database import Database


@pytest.fixture(autouse=True)
def isolate_storage_and_network(monkeypatch):
    """Override the suite's disk-backed fixture with memory-only isolation."""
    connect = sqlite3.connect

    def memory_only_connect(path, *args, **kwargs):
        assert path == ':memory:', 'Regression tests must not open database files'
        return connect(path, *args, **kwargs)

    def no_network(*args, **kwargs):
        raise AssertionError('Network access is forbidden in database regressions')

    monkeypatch.setattr(sqlite3, 'connect', memory_only_connect)
    monkeypatch.setattr('database.DB_PATH', ':memory:')
    monkeypatch.setattr(socket.socket, 'connect', no_network)


@pytest.fixture
def db():
    with Database(':memory:') as database:
        yield database


@pytest.fixture
def journal(db):
    group = db.add_group('Group A')
    other_group = db.add_group('Group B')
    subject = db.add_subject('Math', 30, group)
    replacement = db.add_subject('Physics', 20, group)
    foreign_subject = db.add_subject('Math', 30, other_group)
    first = db.add_student(group, 'First', 'Student')
    second = db.add_student(group, 'Second', 'Student')
    third = db.add_student(group, 'Third', 'Student')
    outsider = db.add_student(other_group, 'Other', 'Student')
    lesson = db.add_lesson(subject, '2026-09-01', lesson_number=3)
    db.mark_attendance(lesson, first, '4')
    db.mark_attendance(lesson, second, '3')
    return SimpleNamespace(
        group=group, subject=subject, replacement=replacement,
        foreign_subject=foreign_subject, first=first, second=second,
        third=third, outsider=outsider, lesson=lesson,
    )


def snapshot(db):
    return (
        [tuple(row) for row in db.conn.execute('SELECT * FROM lessons ORDER BY id')],
        [tuple(row) for row in db.conn.execute('SELECT * FROM grades ORDER BY id')],
    )


@pytest.mark.parametrize('status', ['held', 'scheduled'])
@pytest.mark.parametrize('explicit_none', [False, True])
def test_add_lesson_defaults_actual_subject(db, journal, status, explicit_none):
    kwargs = {'actual_subject_id': None} if explicit_none else {}
    lesson = db.add_lesson(journal.subject, '2026-09-02', status=status, **kwargs)
    row = db.get_lesson(lesson)
    assert row['actual_subject_id'] == journal.subject
    assert row['status'] == status
    assert lesson in [row['id'] for row in db.subject_gradebook(journal.subject)[1]]


def test_add_lesson_preserves_explicit_actual_subject(db, journal):
    lesson = db.add_lesson(journal.subject, '2026-09-02', journal.replacement)
    assert db.get_lesson(lesson)['actual_subject_id'] == journal.replacement


def test_add_lesson_accepts_cancelled_status(db, journal):
    lesson = db.add_lesson(journal.subject, '2026-09-02', status='cancelled')
    assert db.get_lesson(lesson)['status'] == 'cancelled'


@pytest.mark.parametrize('status', ['', 'free', 'replaced', 'canceled', 'unknown', None, [], 1])
@pytest.mark.parametrize('operation', ['add', 'set'])
def test_invalid_status_does_not_change_lessons_or_grades(db, journal, status, operation):
    before = snapshot(db)
    with pytest.raises(ValueError):
        if operation == 'add':
            db.add_lesson(journal.subject, '2026-09-02', status=status)
        else:
            db.set_lesson_status(journal.lesson, status)
    assert snapshot(db) == before
    assert not db.conn.in_transaction


@pytest.mark.parametrize('status', ['scheduled', 'held'])
def test_non_cancelled_status_preserves_grades(db, journal, status):
    before = snapshot(db)[1]
    db.set_lesson_status(journal.lesson, status)
    assert db.get_lesson(journal.lesson)['status'] == status
    assert snapshot(db)[1] == before


@pytest.mark.parametrize('operation', ['cancel', 'set'])
def test_cancellation_removes_grades(db, journal, operation):
    if operation == 'cancel':
        db.cancel_lesson(journal.lesson)
    else:
        db.set_lesson_status(journal.lesson, 'cancelled')
    assert db.get_lesson(journal.lesson)['status'] == 'cancelled'
    assert db.get_attendance(journal.lesson) == []
    assert not db.conn.in_transaction


@pytest.mark.parametrize('operation', ['cancel', 'set'])
def test_cancellation_rolls_back_when_grade_deletion_fails(db, journal, operation):
    db.conn.execute(f"""
        CREATE TRIGGER fail_grade_deletion BEFORE DELETE ON grades
        WHEN OLD.student_id = {journal.second}
        BEGIN SELECT RAISE(ABORT, 'forced deletion failure'); END
    """)
    before = snapshot(db)
    with pytest.raises(sqlite3.IntegrityError, match='forced deletion failure'):
        if operation == 'cancel':
            db.cancel_lesson(journal.lesson)
        else:
            db.set_lesson_status(journal.lesson, 'cancelled')
    assert not db.conn.in_transaction
    db.conn.commit()
    assert snapshot(db) == before


def test_substitution_uses_one_transaction_and_preserves_slot(db, journal, monkeypatch):
    def no_committing_helper(*args, **kwargs):
        raise AssertionError('Substitution must not call committing helpers')

    monkeypatch.setattr(db, 'cancel_lesson', no_committing_helper)
    monkeypatch.setattr(db, 'add_lesson', no_committing_helper)
    statements = []
    db.conn.set_trace_callback(statements.append)
    replacement = db.substitute_lesson(journal.lesson, journal.replacement)
    db.conn.set_trace_callback(None)
    assert [sql.split()[0] for sql in statements if sql.split()[0] in (
        'BEGIN', 'COMMIT', 'ROLLBACK')] == ['BEGIN', 'COMMIT']
    assert replacement != journal.lesson
    assert db.get_lesson(journal.lesson)['status'] == 'cancelled'
    assert db.get_attendance(journal.lesson) == []
    row = db.get_lesson(replacement)
    assert (row['subject_id'], row['actual_subject_id']) == (
        journal.replacement, journal.replacement)
    assert (row['date'], row['lesson_number'], row['status']) == ('2026-09-01', 3, 'held')
    assert db.get_attendance(replacement) == []


@pytest.mark.parametrize('replacement', ['foreign', 999999, 0, -1, None, True, '2', [], 1.5])
def test_invalid_substitution_preserves_original_and_grades(db, journal, replacement):
    if replacement == 'foreign':
        replacement = journal.foreign_subject
    before = snapshot(db)
    with pytest.raises(ValueError):
        db.substitute_lesson(journal.lesson, replacement)
    assert snapshot(db) == before
    assert not db.conn.in_transaction


def test_substitution_requires_existing_lesson(db, journal):
    before = snapshot(db)
    with pytest.raises(ValueError, match='Lesson not found'):
        db.substitute_lesson(999999, journal.replacement)
    assert snapshot(db) == before


def test_substitution_rolls_back_cancellation_and_grades_on_insert_failure(db, journal):
    db.conn.execute("""
        CREATE TRIGGER fail_replacement BEFORE INSERT ON lessons
        BEGIN SELECT RAISE(ABORT, 'forced replacement failure'); END
    """)
    before = snapshot(db)
    with pytest.raises(sqlite3.IntegrityError, match='forced replacement failure'):
        db.substitute_lesson(journal.lesson, journal.replacement)
    assert not db.conn.in_transaction
    db.conn.commit()
    assert snapshot(db) == before


@pytest.mark.parametrize('grade', ['0', '2', '3', '4', '5', 'absent', 'pass', 'present'])
@pytest.mark.parametrize('bulk', [False, True])
def test_attendance_accepts_current_and_legacy_values(db, journal, grade, bulk):
    if bulk:
        db.mark_attendance_bulk(journal.lesson, [{'student_id': journal.first, 'grade': grade}])
    else:
        db.mark_attendance(journal.lesson, journal.first, grade)
    grades = {row['student_id']: row['grade'] for row in db.get_attendance(journal.lesson)}
    assert grades == {journal.first: grade, journal.second: '3'}


@pytest.mark.parametrize('grade', ['', None])
@pytest.mark.parametrize('bulk', [False, True])
def test_empty_attendance_value_deletes_grade(db, journal, grade, bulk):
    if bulk:
        db.mark_attendance_bulk(journal.lesson, [{'student_id': journal.first, 'grade': grade}])
    else:
        db.mark_attendance(journal.lesson, journal.first, grade)
    assert [row['student_id'] for row in db.get_attendance(journal.lesson)] == [journal.second]


@pytest.mark.parametrize('records', [None, {}, 'records', (), 1])
def test_bulk_requires_list(db, journal, records):
    before = snapshot(db)
    with pytest.raises(ValueError):
        db.mark_attendance_bulk(journal.lesson, records)
    assert snapshot(db) == before


@pytest.mark.parametrize('record', [None, [], 'record', {}, {'student_id': 1}, {'grade': '5'}])
def test_bulk_rejects_malformed_record_without_partial_update(db, journal, record):
    before = snapshot(db)
    with pytest.raises(ValueError):
        db.mark_attendance_bulk(journal.lesson, [
            {'student_id': journal.first, 'grade': '5'}, record,
        ])
    assert snapshot(db) == before
    assert not db.conn.in_transaction


@pytest.mark.parametrize('grade', ['1', '6', 'invalid', ' ', 0, 5, False, [], {}])
@pytest.mark.parametrize('bulk', [False, True])
def test_invalid_grade_does_not_change_attendance(db, journal, grade, bulk):
    before = snapshot(db)
    with pytest.raises(ValueError):
        if bulk:
            db.mark_attendance_bulk(journal.lesson, [
                {'student_id': journal.first, 'grade': ''},
                {'student_id': journal.second, 'grade': grade},
            ])
        else:
            db.mark_attendance(journal.lesson, journal.first, grade)
    assert snapshot(db) == before
    assert not db.conn.in_transaction


@pytest.mark.parametrize('student', ['outsider', 999999, 0, -1, None, True, '1', 1.0, [], {}])
@pytest.mark.parametrize('bulk', [False, True])
def test_invalid_student_does_not_change_attendance(db, journal, student, bulk):
    if student == 'outsider':
        student = journal.outsider
    before = snapshot(db)
    with pytest.raises(ValueError):
        if bulk:
            db.mark_attendance_bulk(journal.lesson, [
                {'student_id': journal.first, 'grade': '5'},
                {'student_id': student, 'grade': None},
            ])
        else:
            db.mark_attendance(journal.lesson, student, None)
    assert snapshot(db) == before
    assert not db.conn.in_transaction


@pytest.mark.parametrize('bulk', [False, True])
@pytest.mark.parametrize('grade', ['5', '', None])
@pytest.mark.parametrize('lesson_state', ['cancelled', 'missing'])
def test_attendance_rejects_cancelled_or_missing_lesson(db, journal, bulk, grade, lesson_state):
    lesson = journal.lesson
    if lesson_state == 'cancelled':
        db.cancel_lesson(lesson)
    else:
        lesson = 999999
    before = snapshot(db)
    with pytest.raises(ValueError):
        if bulk:
            db.mark_attendance_bulk(lesson, [{'student_id': journal.first, 'grade': grade}])
        else:
            db.mark_attendance(lesson, journal.first, grade)
    assert snapshot(db) == before


def test_empty_bulk_is_noop(db, journal):
    before = snapshot(db)
    db.mark_attendance_bulk(journal.lesson, [])
    db.mark_attendance_bulk(999999, [])
    assert snapshot(db) == before
    assert not db.conn.in_transaction


def test_bulk_commits_once_without_calling_single_record_method(db, journal, monkeypatch):
    def no_single_record_call(*args, **kwargs):
        raise AssertionError('Bulk attendance must not call mark_attendance')

    monkeypatch.setattr(db, 'mark_attendance', no_single_record_call)
    statements = []
    db.conn.set_trace_callback(statements.append)
    db.mark_attendance_bulk(journal.lesson, [
        {'student_id': journal.first, 'grade': None},
        {'student_id': journal.second, 'grade': '5'},
        {'student_id': journal.third, 'grade': 'present'},
    ])
    db.conn.set_trace_callback(None)
    assert [sql.split()[0] for sql in statements if sql.split()[0] in (
        'BEGIN', 'COMMIT', 'ROLLBACK')] == ['BEGIN', 'COMMIT']
    assert {row['student_id']: row['grade'] for row in db.get_attendance(journal.lesson)} == {
        journal.second: '5', journal.third: 'present',
    }


def test_bulk_rolls_back_deletion_and_update_when_later_insert_fails(db, journal):
    db.conn.execute(f"""
        CREATE TRIGGER fail_attendance BEFORE INSERT ON grades
        WHEN NEW.student_id = {journal.third}
        BEGIN SELECT RAISE(ABORT, 'forced attendance failure'); END
    """)
    before = snapshot(db)
    with pytest.raises(sqlite3.IntegrityError, match='forced attendance failure'):
        db.mark_attendance_bulk(journal.lesson, [
            {'student_id': journal.first, 'grade': None},
            {'student_id': journal.second, 'grade': '5'},
            {'student_id': journal.third, 'grade': 'present'},
        ])
    assert not db.conn.in_transaction
    db.conn.commit()
    assert snapshot(db) == before


@pytest.mark.parametrize('offset,status', [(-15, 'held'), (1, 'held'), (0, 'cancelled'), (0, 'replaced')])
def test_recent_grades_excludes_old_future_and_inactive_lessons(db, offset, status):
    group = db.add_group('Group A')
    subject = db.add_subject('Math', 30, group)
    student = db.add_student(group, 'First', 'Student')
    lesson_date = db.conn.execute("SELECT date('now', ?)", (f'{offset:+d} days',)).fetchone()[0]
    lesson = db.add_lesson(subject, lesson_date)
    db.mark_attendance(lesson, student, '5')
    # Simulate historical inactive lessons whose grades were not cleaned up.
    with db.conn:
        db.conn.execute('UPDATE lessons SET status = ? WHERE id = ?', (status, lesson))
    rows = db.students_without_recent_grades(group, min_grades=1, days=14)
    assert [(row['id'], row['recent_grades']) for row in rows] == [(student, 0)]


def test_recent_grades_includes_boundaries_and_filters_by_count_and_group(db):
    group = db.add_group('Group A')
    subject = db.add_subject('Math', 30, group)
    graded = db.add_student(group, 'Graded', 'Student')
    ungraded = db.add_student(group, 'Ungraded', 'Student')
    other_group = db.add_group('Group B')
    db.add_student(other_group, 'Other', 'Student')
    for offset in (-14, 0):
        lesson_date = db.conn.execute("SELECT date('now', ?)", (f'{offset:+d} days',)).fetchone()[0]
        lesson = db.add_lesson(subject, lesson_date)
        db.mark_attendance(lesson, graded, '5')
    counts = {row['id']: row['recent_grades'] for row in
              db.students_without_recent_grades(group, min_grades=3, days=14)}
    assert counts == {graded: 2, ungraded: 0}
    rows = db.students_without_recent_grades(group, min_grades=2, days=14)
    assert [(row['id'], row['recent_grades']) for row in rows] == [(ungraded, 0)]
