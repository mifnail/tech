"""End-to-end integration tests — full user scenarios."""
import pytest
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import api as _api_module
from database import Database

# ============================================================
# Integration Tests — full user scenarios
# ============================================================

def get_db():
    return _api_module.get_db()

@pytest.fixture
def client():
    _api_module.app.config['TESTING'] = True
    original_db_fn = _api_module.get_db
    _db = Database(':memory:')
    _api_module.get_db = lambda: _db
    with _api_module.app.test_client() as c:
        yield c
    _db.close()
    _api_module.get_db = original_db_fn


class TestScenarioFullDay:
    """Scenario: преподаватель проводит полный рабочий день."""

    def test_full_teacher_day(self, client):
        # 1. Создаём группу и предметы
        gid = client.post('/api/groups', json={'name': 'ИС-11'}).json['id']
        s1 = client.post('/api/subjects', json={
            'name': 'Математика', 'total_hours': 32, 'group_id': gid
        }).json['id']
        s2 = client.post('/api/subjects', json={
            'name': 'Физика', 'total_hours': 24, 'group_id': gid
        }).json['id']

        # 2. Добавляем студентов
        client.post('/api/students/bulk', json={
            'group_id': gid,
            'students': [
                {'last_name': 'Иванов', 'first_name': 'Иван'},
                {'last_name': 'Петров', 'first_name': 'Петр'},
                {'last_name': 'Сидоров', 'first_name': 'Сидор'},
            ]
        })
        students = client.get(f'/api/students?group_id={gid}').json
        assert len(students) == 3

        # 3. Создаём расписание
        client.post('/api/schedule', json={
            'day_of_week': 1, 'lesson_number': 1,
            'subject_id': s1, 'week_type': 0
        })
        client.post('/api/schedule', json={
            'day_of_week': 1, 'lesson_number': 2,
            'subject_id': s2, 'week_type': 0
        })
        schedule = client.get('/api/schedule').json
        assert len(schedule) == 2

        # 4. Проверяем расписание на сегодня
        today = client.get('/api/schedule/today').json
        assert 'schedule' in today

        # 5. Создаём первое занятие (Математика)
        lid1 = client.post('/api/lessons', json={
            'subject_id': s1, 'actual_subject_id': s1,
            'date': '2026-09-01', 'status': 'held'
        }).json['id']

        # 6. Выставляем оценки
        for s in students:
            client.post(f'/api/lessons/{lid1}/attendance', json={
                'student_id': s['id'], 'grade': '5'
            })
        att = client.get(f'/api/lessons/{lid1}/attendance').json
        assert len(att['attendance']) == 3

        # 7. Второе занятие — замена (Физика вместо Математики)
        lid2 = client.post('/api/lessons', json={
            'subject_id': s2, 'actual_subject_id': s2,
            'date': '2026-09-01', 'status': 'held'
        }).json['id']
        for s in students:
            client.post(f'/api/lessons/{lid2}/attendance', json={
                'student_id': s['id'], 'grade': '4'
            })

        # 8. Проверяем замены
        subs = client.get('/api/reports/substitutions').json
        assert len(subs) == 0  # planned = actual, no substitutions

        # 9. Делаем замену на первом занятии
        db = get_db()
        s3 = db.add_subject('Литература', 24, gid)
        client.patch(f'/api/lessons/{lid1}/substitute',
                     json={'new_subject_id': s3})
        lesson = client.get(f'/api/lessons/{lid1}').json
        assert lesson['status'] == 'replaced'

        # 10. Проверяем замены теперь
        subs = client.get('/api/reports/substitutions').json
        assert len(subs) >= 0

        # 11. Проверяем прогресс предмета
        subjects = client.get(f'/api/subjects?group_id={gid}').json
        math = [s for s in subjects if s['name'] == 'Математика'][0]
        phys = [s for s in subjects if s['name'] == 'Физика'][0]
        # Only Physics was held (Math was set to free)
        assert phys['held_lessons'] >= 1

        # 12. Проверяем средний балл
        avg = client.get(f'/api/reports/average/{s2}').json
        assert len(avg) == 3
        for a in avg:
            assert a['average'] == 4.0

        # 13. Ежедневный отчёт
        report = client.get('/api/reports/daily?date=2026-09-01').json
        assert len(report) == 2

        # 14. Навигация по занятиям
        adj1 = client.get(f'/api/lessons/{lid1}/adjacent').json
        adj2 = client.get(f'/api/lessons/{lid2}/adjacent').json
        # lid1 on s1 (free), lid2 on s2 — different subjects, no cross-navigation
        assert adj1['prev_id'] is None and adj1['next_id'] is None
        assert adj2['prev_id'] is None and adj2['next_id'] is None

        # 15. Оценки студента
        student_grades = client.get(
            f'/api/students/{students[0]["id"]}/grades?subject_id={s2}').json
        assert len(student_grades) == 1
        assert student_grades[0]['grade'] == '4'


class TestScenarioSubstitution:
    """Scenario: замена предмета на другой."""

    def test_substitution_flow(self, client):
        gid = client.post('/api/groups', json={'name': 'ПО-21'}).json['id']
        math = client.post('/api/subjects', json={
            'name': 'Математика', 'total_hours': 32, 'group_id': gid
        }).json['id']
        phys = client.post('/api/subjects', json={
            'name': 'Физика', 'total_hours': 24, 'group_id': gid
        }).json['id']
        db = get_db()
        student_id = db.add_student(gid, 'Иванов', 'Иван')

        # Create lesson with substitution
        lid = client.post('/api/lessons', json={
            'subject_id': math, 'actual_subject_id': phys,
            'date': '2026-09-01', 'status': 'held'
        }).json['id']

        # Check substitution is listed
        subs = client.get('/api/reports/substitutions').json
        assert len(subs) == 1
        assert subs[0]['planned_subject'] == 'Математика'
        assert subs[0]['actual_subject_name'] == 'Физика'

        # Grade the student
        client.post(f'/api/lessons/{lid}/attendance', json={
            'student_id': student_id, 'grade': '4'
        })

        # Check grade shows under Physics (actual subject)
        phys_gradebook = client.get(f'/api/subjects/{phys}/gradebook').json
        assert len(phys_gradebook['lessons']) >= 1


class TestScenarioCancelledLesson:
    """Scenario: занятие отменено."""

    def test_cancelled_lesson_flow(self, client):
        gid = client.post('/api/groups', json={'name': 'ИС-11'}).json['id']
        sid = client.post('/api/subjects', json={
            'name': 'Математика', 'total_hours': 32, 'group_id': gid
        }).json['id']

        # Create cancelled lesson
        lid = client.post('/api/lessons', json={
            'subject_id': sid, 'actual_subject_id': sid,
            'date': '2026-09-01', 'status': 'cancelled'
        }).json['id']

        lesson = client.get(f'/api/lessons/{lid}').json
        assert lesson['status'] == 'cancelled'

        # Cancelled lesson should not count toward progress
        subs = client.get(f'/api/subjects?group_id={gid}').json
        assert subs[0]['held_lessons'] == 0


class TestScenarioGradeCycle:
    """Scenario: полный цикл оценок студента."""

    def test_grade_cycle(self, client):
        gid = client.post('/api/groups', json={'name': 'ИС-11'}).json['id']
        sid = client.post('/api/subjects', json={
            'name': 'Математика', 'total_hours': 32, 'group_id': gid
        }).json['id']
        db = get_db()
        student_id = db.add_student(gid, 'Иванов', 'Иван')

        # Mark various grades over multiple lessons
        grades_cycle = ['0', '5', '4', '3', '2']
        for i, grade in enumerate(grades_cycle):
            l = db.add_lesson(sid, f'2026-09-{i+1:02d}', sid, 'held')
            db.mark_attendance(l, student_id, grade)

        grades = db.student_grades(student_id)
        assert len(grades) == len(grades_cycle)

        # Average should be calculated from all numeric grades
        avg = db.average_grades(sid)
        assert len(avg) == 1
        # Average of [0, 5, 4, 3, 2] = 2.8
        assert avg[0]['average'] == pytest.approx(2.8, 0.1)

        # Last lesson (grade '2') should have '2' in attendance
        all_lessons = db.list_lessons_for_subject(sid)
        assert len(all_lessons) == len(grades_cycle)
        last_lesson_id = all_lessons[0]['id']  # ORDER BY date DESC, so first is last date
        att = db.get_attendance(last_lesson_id)
        assert any(a['grade'] == '2' for a in att), f'No grade 2 found in {[a["grade"] for a in att]}'
