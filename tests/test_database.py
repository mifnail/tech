import pytest
import os
from database import Database
from datetime import date, timedelta

# ============================================================
# Database Unit Tests — 100% coverage of all public methods
# ============================================================

@pytest.fixture
def db():
    d = Database(':memory:')
    yield d
    d.close()

# ======================== GROUPS ========================

class TestGroups:
    def test_add_group(self, db):
        gid = db.add_group('ИС-11')
        assert isinstance(gid, int) and gid > 0

    def test_add_group_duplicate(self, db):
        db.add_group('ИС-11')
        with pytest.raises(Exception):
            db.add_group('ИС-11')

    def test_list_groups_empty(self, db):
        assert db.list_groups() == []

    def test_list_groups(self, db):
        db.add_group('ИС-11')
        db.add_group('ПО-21')
        groups = db.list_groups()
        assert len(groups) == 2
        assert [g['name'] for g in groups] == ['ИС-11', 'ПО-21']

    def test_list_groups_ordered(self, db):
        db.add_group('ПО-21')
        db.add_group('ИС-11')
        groups = db.list_groups()
        assert groups[0]['name'] == 'ИС-11'

    def test_delete_group(self, db):
        gid = db.add_group('ИС-11')
        db.delete_group(gid)
        assert db.list_groups() == []

# ======================== STUDENTS ========================

class TestStudents:
    def test_add_student(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_student(gid, 'Иванов', 'Иван')
        assert isinstance(sid, int) and sid > 0

    def test_add_student_with_middle(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_student(gid, 'Иванов', 'Иван', 'Иванович')
        students = db.list_students(gid)
        assert students[0]['middle_name'] == 'Иванович'

    def test_add_student_duplicate_in_group(self, db):
        gid = db.add_group('ИС-11')
        db.add_student(gid, 'Иванов', 'Иван')
        with pytest.raises(Exception):
            db.add_student(gid, 'Иванов', 'Иван')

    def test_add_student_same_name_different_middle(self, db):
        gid = db.add_group('ИС-11')
        db.add_student(gid, 'Иванов', 'Иван', 'Иванович')
        sid = db.add_student(gid, 'Иванов', 'Иван', 'Сергеевич')
        assert sid > 0

    def test_add_student_same_name_different_group(self, db):
        g1 = db.add_group('ИС-11')
        g2 = db.add_group('ПО-21')
        db.add_student(g1, 'Иванов', 'Иван')
        sid = db.add_student(g2, 'Иванов', 'Иван')
        assert sid > 0

    def test_list_students_by_group(self, db):
        gid = db.add_group('ИС-11')
        db.add_student(gid, 'Петров', 'Петр')
        db.add_student(gid, 'Иванов', 'Иван')
        students = db.list_students(gid)
        assert len(students) == 2
        assert students[0]['last_name'] == 'Иванов'  # ordered

    def test_list_students_all(self, db):
        g1 = db.add_group('ИС-11')
        g2 = db.add_group('ПО-21')
        db.add_student(g1, 'Иванов', 'Иван')
        db.add_student(g2, 'Петров', 'Петр')
        students = db.list_students()
        assert len(students) == 2

    def test_add_students_bulk(self, db):
        gid = db.add_group('ИС-11')
        students = [
            {'last_name': 'Иванов', 'first_name': 'Иван'},
            {'last_name': 'Петров', 'first_name': 'Петр', 'middle_name': 'Петрович'},
        ]
        count = db.add_students_bulk(gid, students)
        assert count == 2
        assert len(db.list_students(gid)) == 2

    def test_add_students_bulk_ignore_duplicates(self, db):
        gid = db.add_group('ИС-11')
        students = [
            {'last_name': 'Иванов', 'first_name': 'Иван'},
            {'last_name': 'Петров', 'first_name': 'Петр'},
            {'last_name': 'Иванов', 'first_name': 'Иван'},
        ]
        count = db.add_students_bulk(gid, students)
        assert count == 2  # Петров + Иванов (only one Иванов inserted, duplicate ignored)

    def test_delete_student(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_student(gid, 'Иванов', 'Иван')
        db.delete_student(sid)
        assert db.list_students(gid) == []

# ======================== SUBJECTS ========================

class TestSubjects:
    def test_add_subject(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        assert isinstance(sid, int) and sid > 0

    def test_add_subject_duplicate(self, db):
        gid = db.add_group('ИС-11')
        db.add_subject('Математика', 32, gid)
        with pytest.raises(Exception):
            db.add_subject('Математика', 32, gid)

    def test_list_subjects_empty(self, db):
        assert db.list_subjects() == []

    def test_list_subjects_by_group(self, db):
        gid = db.add_group('ИС-11')
        db.add_subject('Математика', 32, gid)
        db.add_subject('Физика', 24, gid)
        subjects = db.list_subjects(gid)
        assert len(subjects) == 2

    def test_list_subjects_with_progress(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        db.add_lesson(sid, '2026-09-01', sid, 'held')
        subjects = db.list_subjects(gid)
        assert subjects[0]['held_lessons'] == 1
        assert subjects[0]['remaining'] == 31

    def test_list_subjects_excludes_free(self, db):
        gid = db.add_group('ИС-11')
        db.add_subject('Математика', 32, gid)
        free_id = db.get_free_subject_id(gid)
        subjects = db.list_subjects(gid)
        names = [s['name'] for s in subjects]
        assert 'СВОБОДНО' not in names

    def test_list_subjects_includes_free_when_requested(self, db):
        gid = db.add_group('ИС-11')
        db.add_subject('Математика', 32, gid)
        free_id = db.get_free_subject_id(gid)
        subjects = db.list_subjects(gid, include_free=True)
        names = [s['name'] for s in subjects]
        assert 'СВОБОДНО' in names

    def test_subject_summary(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        summary = db.subject_summary(sid)
        assert summary['total_hours'] == 32
        assert summary['held_lessons'] == 0

    def test_subject_gradebook(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        student_id = db.add_student(gid, 'Иванов', 'Иван')
        lid = db.add_lesson(sid, '2026-09-01', sid, 'held')
        db.mark_attendance(lid, student_id, '5')
        students, lessons, grades = db.subject_gradebook(sid)
        assert len(students) == 1
        assert len(lessons) == 1
        assert str(student_id) in grades
        assert str(lid) in grades[str(student_id)]

    def test_delete_subject(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        db.delete_subject(sid)
        assert db.list_subjects() == []

# ======================== FREE SUBJECT ========================

class TestFreeSubject:
    def test_get_free_subject_id_creates(self, db):
        gid = db.add_group('ИС-11')
        free_id = db.get_free_subject_id(gid)
        assert isinstance(free_id, int) and free_id > 0

    def test_get_free_subject_id_reuses(self, db):
        gid = db.add_group('ИС-11')
        free_id1 = db.get_free_subject_id(gid)
        free_id2 = db.get_free_subject_id(gid)
        assert free_id1 == free_id2

    def test_is_free_subject(self, db):
        gid = db.add_group('ИС-11')
        free_id = db.get_free_subject_id(gid)
        assert db.is_free_subject(free_id) is True

    def test_is_free_subject_regular(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        assert db.is_free_subject(sid) is False

# ======================== SCHEDULE ========================

class TestSchedule:
    def test_add_schedule_entry(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        eid = db.add_schedule_entry(1, 1, sid, 0)
        assert isinstance(eid, int) and eid > 0

    def test_get_schedule_for_day(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        db.add_schedule_entry(1, 1, sid, 0)
        db.add_schedule_entry(2, 1, sid, 0)
        entries = db.get_schedule_for_day(1)
        assert len(entries) == 1
        assert entries[0]['day_of_week'] == 1

    def test_get_schedule_for_day_empty(self, db):
        assert db.get_schedule_for_day(1) == []

    def test_list_schedule(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        db.add_schedule_entry(1, 1, sid, 0)
        db.add_schedule_entry(1, 2, sid, 1)
        entries = db.list_schedule()
        assert len(entries) == 2

    def test_delete_schedule_entry(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        eid = db.add_schedule_entry(1, 1, sid, 0)
        db.delete_schedule_entry(eid)
        assert db.list_schedule() == []

    def test_schedule_entry_joins_subject_and_group(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        db.add_schedule_entry(1, 1, sid, 0)
        entries = db.list_schedule()
        assert entries[0]['subject_name'] == 'Математика'
        assert entries[0]['group_name'] == 'ИС-11'

    def test_get_schedule_for_day_filters_week_type(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        db.add_schedule_entry(1, 1, sid, 0)  # каждую
        db.add_schedule_entry(1, 2, sid, 1)  # нечётная
        db.add_schedule_entry(1, 3, sid, 2)  # чётная
        all_entries = db.get_schedule_for_day(1)
        assert len(all_entries) == 3
        odd_entries = db.get_schedule_for_day(1, current_week_type=1)
        assert len(odd_entries) == 2  # каждую + нечётная
        even_entries = db.get_schedule_for_day(1, current_week_type=2)
        assert len(even_entries) == 2  # каждую + чётная

    def test_update_schedule_entry(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        sid2 = db.add_subject('Физика', 24, gid)
        eid = db.add_schedule_entry(1, 1, sid, 0)
        db.update_schedule_entry(eid, 3, 2, sid2, 1)
        entries = db.list_schedule()
        assert len(entries) == 1
        assert entries[0]['day_of_week'] == 3
        assert entries[0]['lesson_number'] == 2
        assert entries[0]['subject_id'] == sid2
        assert entries[0]['week_type'] == 1

# ======================== LESSONS ========================

class TestLessons:
    def test_add_lesson(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        lid = db.add_lesson(sid, '2026-09-01', sid, 'held')
        assert isinstance(lid, int) and lid > 0

    def test_add_lesson_without_actual(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        lid = db.add_lesson(sid, '2026-09-01', None, 'held')
        lesson = db.get_lesson(lid)
        assert lesson['status'] == 'held'

    def test_add_lesson_default_status(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        lid = db.add_lesson(sid, '2026-09-01', sid)
        lesson = db.get_lesson(lid)
        assert lesson['status'] == 'held'

    def test_add_free_lesson(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        lid = db.add_lesson(sid, '2026-09-01', sid, 'cancelled')
        lesson = db.get_lesson(lid)
        assert lesson['status'] == 'cancelled'

    def test_get_lesson_not_found(self, db):
        assert db.get_lesson(999) is None

    def test_get_lesson_details(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        lid = db.add_lesson(sid, '2026-09-01', sid, 'held')
        lesson = db.get_lesson(lid)
        assert lesson['planned_subject'] == 'Математика'
        assert lesson['actual_subject_name'] == 'Математика'
        assert lesson['group_name'] == 'ИС-11'

    def test_get_lesson_with_substitution(self, db):
        gid = db.add_group('ИС-11')
        s1 = db.add_subject('Математика', 32, gid)
        s2 = db.add_subject('Физика', 24, gid)
        lid = db.add_lesson(s1, '2026-09-01', s2, 'held')
        lesson = db.get_lesson(lid)
        assert lesson['actual_subject_name'] == 'Физика'

    def test_set_lesson_status(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        lid = db.add_lesson(sid, '2026-09-01', sid, 'held')
        db.set_lesson_status(lid, 'cancelled')
        assert db.get_lesson(lid)['status'] == 'cancelled'

    def test_list_lessons_by_date(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        db.add_lesson(sid, '2026-09-01', sid, 'held')
        db.add_lesson(sid, '2026-09-02', sid, 'held')
        lessons = db.list_lessons_by_date('2026-09-01')
        assert len(lessons) == 1

    def test_list_lessons_by_date_empty(self, db):
        assert db.list_lessons_by_date('2099-01-01') == []

    def test_list_lessons_for_subject(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        db.add_lesson(sid, '2026-09-01', sid, 'held')
        db.add_lesson(sid, '2026-09-02', sid, 'held')
        lessons = db.list_lessons_for_subject(sid)
        assert len(lessons) == 2

    def test_list_lessons_for_subject_includes_substitutions(self, db):
        gid = db.add_group('ИС-11')
        s1 = db.add_subject('Математика', 32, gid)
        s2 = db.add_subject('Физика', 24, gid)
        db.add_lesson(s1, '2026-09-01', s2, 'held')
        lessons = db.list_lessons_for_subject(s1)
        assert len(lessons) == 1

    def test_substitute_lesson(self, db):
        gid = db.add_group('ИС-11')
        s1 = db.add_subject('Математика', 32, gid)
        s2 = db.add_subject('Физика', 24, gid)
        lid = db.add_lesson(s1, '2026-09-01', s1, 'held')
        new_id = db.substitute_lesson(lid, s2)
        original = db.get_lesson(lid)
        assert original['status'] == 'cancelled'
        new_lesson = db.get_lesson(new_id)
        assert new_lesson['actual_subject_name'] == 'Физика'
        assert new_lesson['status'] == 'held'

    def test_substitute_lesson_cancels_original_and_creates_new(self, db):
        gid = db.add_group('ИС-11')
        s1 = db.add_subject('Математика', 32, gid)
        s2 = db.add_subject('Физика', 24, gid)
        student_id = db.add_student(gid, 'Иванов', 'Иван')
        lid = db.add_lesson(s1, '2026-09-01', s1, 'held')
        db.mark_attendance(lid, student_id, '5')
        new_id = db.substitute_lesson(lid, s2)
        original = db.get_lesson(lid)
        assert original['status'] == 'cancelled'
        assert db.get_attendance(lid) == []
        new_lesson = db.get_lesson(new_id)
        assert new_lesson['status'] == 'held'
        assert new_lesson['actual_subject_name'] == 'Физика'
        assert new_lesson['date'] == '2026-09-01'

    def test_get_substitutions(self, db):
        gid = db.add_group('ИС-11')
        s1 = db.add_subject('Математика', 32, gid)
        s2 = db.add_subject('Физика', 24, gid)
        db.add_lesson(s1, '2026-09-01', s2, 'held')
        subs = db.get_substitutions()
        assert subs == []

    def test_get_substitutions_excludes_planned(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        db.add_lesson(sid, '2026-09-01', sid, 'held')
        subs = db.get_substitutions()
        assert subs == []

    def test_get_adjacent_lessons(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        l1 = db.add_lesson(sid, '2026-09-01', sid, 'held')
        l2 = db.add_lesson(sid, '2026-09-02', sid, 'held')
        l3 = db.add_lesson(sid, '2026-09-03', sid, 'held')
        prev, next = db.get_adjacent_lessons(l2)
        assert prev == l1
        assert next == l3

    def test_get_adjacent_lessons_first(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        l1 = db.add_lesson(sid, '2026-09-01', sid, 'held')
        l2 = db.add_lesson(sid, '2026-09-02', sid, 'held')
        prev, next = db.get_adjacent_lessons(l1)
        assert prev is None
        assert next == l2

    def test_get_adjacent_lessons_last(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        l1 = db.add_lesson(sid, '2026-09-01', sid, 'held')
        l2 = db.add_lesson(sid, '2026-09-02', sid, 'held')
        prev, next = db.get_adjacent_lessons(l2)
        assert prev == l1
        assert next is None

    def test_get_adjacent_lessons_not_found(self, db):
        prev, next = db.get_adjacent_lessons(999)
        assert prev is None and next is None

# ======================== GRADES ========================

class TestGrades:
    def test_mark_attendance(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        student_id = db.add_student(gid, 'Иванов', 'Иван')
        lid = db.add_lesson(sid, '2026-09-01', sid, 'held')
        db.mark_attendance(lid, student_id, '5')
        att = db.get_attendance(lid)
        assert len(att) == 1
        assert att[0]['grade'] == '5'

    def test_mark_attendance_update(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        student_id = db.add_student(gid, 'Иванов', 'Иван')
        lid = db.add_lesson(sid, '2026-09-01', sid, 'held')
        db.mark_attendance(lid, student_id, '3')
        db.mark_attendance(lid, student_id, '5')
        att = db.get_attendance(lid)
        assert att[0]['grade'] == '5'

    def test_mark_attendance_bulk(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        s1 = db.add_student(gid, 'Иванов', 'Иван')
        s2 = db.add_student(gid, 'Петров', 'Петр')
        lid = db.add_lesson(sid, '2026-09-01', sid, 'held')
        db.mark_attendance_bulk(lid, [
            {'student_id': s1, 'grade': '5'},
            {'student_id': s2, 'grade': '4'},
        ])
        att = db.get_attendance(lid)
        assert len(att) == 2

    def test_get_attendance_empty(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        lid = db.add_lesson(sid, '2026-09-01', sid, 'held')
        assert db.get_attendance(lid) == []

    def test_student_grades(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        student_id = db.add_student(gid, 'Иванов', 'Иван')
        lid = db.add_lesson(sid, '2026-09-01', sid, 'held')
        db.mark_attendance(lid, student_id, '5')
        grades = db.student_grades(student_id)
        assert len(grades) == 1

    def test_student_grades_by_subject(self, db):
        gid = db.add_group('ИС-11')
        s1 = db.add_subject('Математика', 32, gid)
        s2 = db.add_subject('Физика', 24, gid)
        student_id = db.add_student(gid, 'Иванов', 'Иван')
        l1 = db.add_lesson(s1, '2026-09-01', s1, 'held')
        l2 = db.add_lesson(s2, '2026-09-02', s2, 'held')
        db.mark_attendance(l1, student_id, '5')
        db.mark_attendance(l2, student_id, '4')
        grades = db.student_grades(student_id, s1)
        assert len(grades) == 1
        assert grades[0]['grade'] == '5'

    def test_average_grades(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        s1 = db.add_student(gid, 'Иванов', 'Иван')
        s2 = db.add_student(gid, 'Петров', 'Петр')
        lid = db.add_lesson(sid, '2026-09-01', sid, 'held')
        db.mark_attendance(lid, s1, '5')
        db.mark_attendance(lid, s2, '3')
        avgs = db.average_grades(sid)
        assert len(avgs) == 2
        assert avgs[0]['average'] == 5.0  # sorted desc

    def test_average_grades_excludes_non_numeric(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        student_id = db.add_student(gid, 'Иванов', 'Иван')
        lid = db.add_lesson(sid, '2026-09-01', sid, 'held')
        db.mark_attendance(lid, student_id, 'absent')
        avgs = db.average_grades(sid)
        assert avgs == []

    def test_average_grades_excludes_cancelled_lessons(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        student_id = db.add_student(gid, 'Иванов', 'Иван')
        lid = db.add_lesson(sid, '2026-09-01', sid, 'cancelled')
        db.mark_attendance(lid, student_id, '5')
        avgs = db.average_grades(sid)
        assert avgs == []

# ======================== REPORTS ========================

class TestReports:
    def test_daily_report(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        student_id = db.add_student(gid, 'Иванов', 'Иван')
        lid = db.add_lesson(sid, '2026-09-01', sid, 'held')
        db.mark_attendance(lid, student_id, '5')
        report = db.daily_report('2026-09-01')
        assert len(report) == 1
        assert report[0]['grades_count'] == 1

    def test_daily_report_empty_date(self, db):
        assert db.daily_report('2099-01-01') == []

    def test_students_without_recent_grades(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        s1 = db.add_student(gid, 'Иванов', 'Иван')
        s2 = db.add_student(gid, 'Петров', 'Петр')
        today_str = date.today().isoformat()
        lid = db.add_lesson(sid, today_str, sid, 'held')
        db.mark_attendance(lid, s1, '5')
        neglected = db.students_without_recent_grades(gid, min_grades=1, days=30)
        ids = [s['id'] for s in neglected]
        assert s1 not in ids
        assert s2 in ids

    def test_get_group_students(self, db):
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        db.add_student(gid, 'Иванов', 'Иван')
        lid = db.add_lesson(sid, '2026-09-01', sid, 'held')
        students = db.get_group_students(lid)
        assert len(students) == 1
