import pytest
import json
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import api as _api_module
from database import Database

# ============================================================
# API Tests — 100% coverage of all endpoints
# ============================================================

# Helper: calls the (possibly monkey-patched) get_db from api module
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
    _api_module.get_db = original_db_fn  # restore

# ======================== SPA ========================

class TestSPA:
    def test_index(self, client):
        rv = client.get('/')
        assert rv.status_code == 200
        assert b'<!DOCTYPE html>' in rv.data

# ======================== GROUPS ========================

class TestGroupsAPI:
    def test_list_empty(self, client):
        rv = client.get('/api/groups')
        assert rv.status_code == 200
        assert rv.json == []

    def test_create(self, client):
        rv = client.post('/api/groups', json={'name': 'ИС-11'})
        assert rv.status_code == 201
        assert 'id' in rv.json

    def test_create_and_list(self, client):
        client.post('/api/groups', json={'name': 'ИС-11'})
        client.post('/api/groups', json={'name': 'ПО-21'})
        rv = client.get('/api/groups')
        assert len(rv.json) == 2

    def test_create_missing_name(self, client):
        rv = client.post('/api/groups', json={})
        assert rv.status_code == 400

# ======================== STUDENTS ========================

class TestStudentsAPI:
    def _setup(self, client):
        gid = client.post('/api/groups', json={'name': 'ИС-11'}).json['id']
        return gid

    def test_list_empty(self, client):
        gid = self._setup(client)
        rv = client.get(f'/api/students?group_id={gid}')
        assert rv.json == []

    def test_add_bulk(self, client):
        gid = self._setup(client)
        rv = client.post('/api/students/bulk', json={
            'group_id': gid,
            'students': [
                {'last_name': 'Иванов', 'first_name': 'Иван'},
                {'last_name': 'Петров', 'first_name': 'Петр'},
            ]
        })
        assert rv.status_code == 201
        assert rv.json['added'] == 2

    def test_list_after_add(self, client):
        gid = self._setup(client)
        client.post('/api/students/bulk', json={
            'group_id': gid,
            'students': [{'last_name': 'Иванов', 'first_name': 'Иван'}]
        })
        rv = client.get(f'/api/students?group_id={gid}')
        assert len(rv.json) == 1
        assert rv.json[0]['last_name'] == 'Иванов'

# ======================== SUBJECTS ========================

class TestSubjectsAPI:
    def _setup(self, client):
        gid = client.post('/api/groups', json={'name': 'ИС-11'}).json['id']
        return gid

    def test_list_empty(self, client):
        rv = client.get('/api/subjects')
        assert rv.json == []

    def test_create(self, client):
        gid = self._setup(client)
        rv = client.post('/api/subjects', json={
            'name': 'Математика', 'total_hours': 32, 'group_id': gid
        })
        assert rv.status_code == 201
        assert 'id' in rv.json

    def test_list_with_progress(self, client):
        gid = self._setup(client)
        sid = client.post('/api/subjects', json={
            'name': 'Математика', 'total_hours': 32, 'group_id': gid
        }).json['id']
        db = get_db()
        db.add_lesson(sid, '2026-09-01', sid, 'held')
        rv = client.get(f'/api/subjects?group_id={gid}')
        assert rv.json[0]['held_lessons'] == 1
        assert rv.json[0]['remaining'] == 31

    def test_substitution_list(self, client):
        gid = self._setup(client)
        sid = client.post('/api/subjects', json={
            'name': 'Математика', 'total_hours': 32, 'group_id': gid
        }).json['id']
        rv = client.get(f'/api/subjects/{sid}/substitution-list')
        assert rv.status_code == 200
        names = [s['name'] for s in rv.json]
        free_names = [n for n in names if '\u0421\u0412\u041e\u0411\u041e\u0414\u041d\u041e' in n]
        assert len(free_names) > 0, f'СВОБОДНО not found in names: {names}'
        math_names = [n for n in names if '\u041c\u0430\u0442\u0435\u043c\u0430\u0442\u0438\u043a\u0430' in n]
        assert len(math_names) > 0, f'Математика not found in names: {names}'

    def test_subject_lessons(self, client):
        gid = self._setup(client)
        sid = client.post('/api/subjects', json={
            'name': 'Математика', 'total_hours': 32, 'group_id': gid
        }).json['id']
        db = get_db()
        db.add_lesson(sid, '2026-09-01', sid, 'held')
        rv = client.get(f'/api/subjects/{sid}/lessons')
        assert len(rv.json) == 1

    def test_gradebook(self, client):
        gid = self._setup(client)
        sid = client.post('/api/subjects', json={
            'name': 'Математика', 'total_hours': 32, 'group_id': gid
        }).json['id']
        db = get_db()
        student_id = db.add_student(gid, 'Иванов', 'Иван')
        lid = db.add_lesson(sid, '2026-09-01', sid, 'held')
        db.mark_attendance(lid, student_id, '5')
        rv = client.get(f'/api/subjects/{sid}/gradebook')
        assert rv.json['summary'] is not None
        assert len(rv.json['grades']) > 0

# ======================== SCHEDULE ========================

class TestScheduleAPI:
    def _setup(self, client):
        gid = client.post('/api/groups', json={'name': 'ИС-11'}).json['id']
        sid = client.post('/api/subjects', json={
            'name': 'Математика', 'total_hours': 32, 'group_id': gid
        }).json['id']
        return gid, sid

    def test_list_empty(self, client):
        rv = client.get('/api/schedule')
        assert rv.json == []

    def test_add_entry(self, client):
        _, sid = self._setup(client)
        rv = client.post('/api/schedule', json={
            'day_of_week': 1, 'lesson_number': 1,
            'subject_id': sid, 'week_type': 0
        })
        assert rv.status_code == 201
        assert 'id' in rv.json

    def test_list(self, client):
        _, sid = self._setup(client)
        client.post('/api/schedule', json={
            'day_of_week': 1, 'lesson_number': 1,
            'subject_id': sid, 'week_type': 0
        })
        rv = client.get('/api/schedule')
        assert len(rv.json) == 1

    def test_delete(self, client):
        _, sid = self._setup(client)
        eid = client.post('/api/schedule', json={
            'day_of_week': 1, 'lesson_number': 1,
            'subject_id': sid, 'week_type': 0
        }).json['id']
        rv = client.delete(f'/api/schedule/{eid}')
        assert rv.json['ok'] is True
        assert client.get('/api/schedule').json == []

    def test_today(self, client):
        _, sid = self._setup(client)
        rv = client.get('/api/schedule/today')
        assert rv.status_code == 200
        assert 'date' in rv.json
        assert 'schedule' in rv.json
        assert 'lessons' in rv.json

# ======================== LESSONS ========================

class TestLessonsAPI:
    def _setup(self, client):
        gid = client.post('/api/groups', json={'name': 'ИС-11'}).json['id']
        sid = client.post('/api/subjects', json={
            'name': 'Математика', 'total_hours': 32, 'group_id': gid
        }).json['id']
        student_id = get_db().add_student(gid, 'Иванов', 'Иван')
        return gid, sid, student_id

    def test_create_lesson(self, client):
        _, sid, _ = self._setup(client)
        rv = client.post('/api/lessons', json={
            'subject_id': sid, 'actual_subject_id': sid,
            'date': '2026-09-01', 'status': 'held'
        })
        assert rv.status_code == 201
        assert 'id' in rv.json

    def test_get_lesson(self, client):
        _, sid, _ = self._setup(client)
        lid = client.post('/api/lessons', json={
            'subject_id': sid, 'actual_subject_id': sid,
            'date': '2026-09-01', 'status': 'held'
        }).json['id']
        rv = client.get(f'/api/lessons/{lid}')
        assert rv.json['planned_subject'] == 'Математика'
        assert rv.json['status'] == 'held'

    def test_get_lesson_not_found(self, client):
        rv = client.get('/api/lessons/999')
        assert rv.status_code == 404

    def test_substitute(self, client):
        _, sid, _ = self._setup(client)
        lid = client.post('/api/lessons', json={
            'subject_id': sid, 'actual_subject_id': sid,
            'date': '2026-09-01', 'status': 'held'
        }).json['id']
        db = get_db()
        free_id = db.get_free_subject_id(get_db().list_groups()[0]['id'])
        rv = client.patch(f'/api/lessons/{lid}/substitute',
                          json={'new_subject_id': free_id})
        assert rv.json['ok'] is True

    def test_update_status(self, client):
        _, sid, _ = self._setup(client)
        lid = client.post('/api/lessons', json={
            'subject_id': sid, 'actual_subject_id': sid,
            'date': '2026-09-01', 'status': 'held'
        }).json['id']
        rv = client.patch(f'/api/lessons/{lid}/status', json={'status': 'free'})
        assert rv.json['ok'] is True

    def test_adjacent(self, client):
        _, sid, _ = self._setup(client)
        l1 = client.post('/api/lessons', json={
            'subject_id': sid, 'actual_subject_id': sid,
            'date': '2026-09-01', 'status': 'held'
        }).json['id']
        l2 = client.post('/api/lessons', json={
            'subject_id': sid, 'actual_subject_id': sid,
            'date': '2026-09-02', 'status': 'held'
        }).json['id']
        rv = client.get(f'/api/lessons/{l1}/adjacent')
        assert rv.json['prev_id'] is None
        assert rv.json['next_id'] == l2

    def test_attendance_get(self, client):
        _, sid, student_id = self._setup(client)
        lid = client.post('/api/lessons', json={
            'subject_id': sid, 'actual_subject_id': sid,
            'date': '2026-09-01', 'status': 'held'
        }).json['id']
        rv = client.get(f'/api/lessons/{lid}/attendance')
        assert rv.status_code == 200
        assert 'lesson' in rv.json
        assert 'students' in rv.json
        assert 'attendance' in rv.json

    def test_attendance_post(self, client):
        _, sid, student_id = self._setup(client)
        lid = client.post('/api/lessons', json={
            'subject_id': sid, 'actual_subject_id': sid,
            'date': '2026-09-01', 'status': 'held'
        }).json['id']
        rv = client.post(f'/api/lessons/{lid}/attendance', json={
            'student_id': student_id, 'grade': '5'
        })
        assert rv.json['ok'] is True
        att = client.get(f'/api/lessons/{lid}/attendance').json['attendance']
        assert len(att) == 1

    def test_lessons_by_date(self, client):
        _, sid, _ = self._setup(client)
        client.post('/api/lessons', json={
            'subject_id': sid, 'actual_subject_id': sid,
            'date': '2026-09-01', 'status': 'held'
        })
        rv = client.get('/api/lessons/date/2026-09-01')
        assert len(rv.json) == 1
        rv = client.get('/api/lessons/date/2099-01-01')
        assert rv.json == []

# ======================== REPORTS ========================

class TestReportsAPI:
    def _setup(self, client):
        gid = client.post('/api/groups', json={'name': 'ИС-11'}).json['id']
        db = get_db()
        sid = db.add_subject('Математика', 32, gid)
        student_id = db.add_student(gid, 'Иванов', 'Иван')
        lid = db.add_lesson(sid, '2026-09-01', sid, 'held')
        db.mark_attendance(lid, student_id, '5')
        return gid, sid, student_id

    def test_substitutions(self, client):
        gid, sid, _ = self._setup(client)
        db = get_db()
        s2 = db.add_subject('Физика', 24, gid)
        lid = db.add_lesson(sid, '2026-09-02', s2, 'held')
        rv = client.get('/api/reports/substitutions')
        assert len(rv.json) == 1

    def test_average(self, client):
        _, sid, _ = self._setup(client)
        rv = client.get(f'/api/reports/average/{sid}')
        assert len(rv.json) == 1
        assert rv.json[0]['average'] == 5.0

    def test_daily(self, client):
        # First create data for the report
        gid = client.post('/api/groups', json={'name': 'ИС-11'}).json['id']
        sid = client.post('/api/subjects', json={
            'name': 'Математика', 'total_hours': 32, 'group_id': gid
        }).json['id']
        db = get_db()
        student_id = db.add_student(gid, 'Иванов', 'Иван')
        lid = db.add_lesson(sid, '2026-09-01', sid, 'held')
        db.mark_attendance(lid, student_id, '5')
        rv = client.get('/api/reports/daily?date=2026-09-01')
        assert len(rv.json) >= 1

    def test_neglected(self, client):
        gid, _, _ = self._setup(client)
        rv = client.get(f'/api/reports/neglected/{gid}?min_grades=10&days=1')
        assert len(rv.json) == 1

# ======================== STUDENT GRADES ========================

class TestStudentGradesAPI:
    def test_student_grades(self, client):
        gid = client.post('/api/groups', json={'name': 'ИС-11'}).json['id']
        db = get_db()
        sid = db.add_subject('Математика', 32, gid)
        student_id = db.add_student(gid, 'Иванов', 'Иван')
        lid = db.add_lesson(sid, '2026-09-01', sid, 'held')
        db.mark_attendance(lid, student_id, '5')
        rv = client.get(f'/api/students/{student_id}/grades')
        assert len(rv.json) == 1
        rv = client.get(f'/api/students/{student_id}/grades?subject_id={sid}')
        assert len(rv.json) == 1
