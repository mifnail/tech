import pytest
import os
from database import Database

@pytest.fixture
def db():
    d = Database(':memory:')
    yield d
    d.close()

def test_groups(db):
    gid = db.add_group('ИС-11')
    groups = db.list_groups()
    assert len(groups) == 1
    assert groups[0]['name'] == 'ИС-11'

def test_students(db):
    gid = db.add_group('ИС-11')
    db.add_student(gid, 'Иванов', 'Иван')
    students = db.list_students(gid)
    assert len(students) == 1
    assert students[0]['last_name'] == 'Иванов'

def test_subject(db):
    gid = db.add_group('ИС-11')
    sid = db.add_subject('Математика', 32, gid)
    subjects = db.list_subjects()
    assert len(subjects) == 1
    assert subjects[0]['total_hours'] == 32

def test_lesson(db):
    gid = db.add_group('ИС-11')
    sid = db.add_subject('Математика', 32, gid)
    lid = db.add_lesson(sid, '2026-09-01', sid)
    lesson = db.get_lesson(lid)
    assert lesson is not None
    assert lesson['date'] == '2026-09-01'

def test_grade(db):
    gid = db.add_group('ИС-11')
    sid = db.add_subject('Математика', 32, gid)
    student_id = db.add_student(gid, 'Иванов', 'Иван')
    lid = db.add_lesson(sid, '2026-09-01', sid)
    db.mark_attendance(lid, student_id, '5')
    att = db.get_attendance(lid)
    assert len(att) == 1
    assert att[0]['grade'] == '5'

def test_schedule(db):
    gid = db.add_group('ИС-11')
    sid = db.add_subject('Математика', 32, gid)
    eid = db.add_schedule_entry(1, 1, sid, 0)
    entries = db.get_schedule_for_day(1)
    assert len(entries) == 1
    assert entries[0]['lesson_number'] == 1

def test_substitution(db):
    gid = db.add_group('ИС-11')
    s1 = db.add_subject('Математика', 32, gid)
    s2 = db.add_subject('Физика', 24, gid)
    lid = db.add_lesson(s1, '2026-09-01', s2)
    subs = db.get_substitutions()
    assert len(subs) == 1
