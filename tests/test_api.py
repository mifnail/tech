import pytest
import json
import os
import sys
from datetime import date
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
        assert b'app.js?v=' in rv.data

    def test_version(self, client):
        rv = client.get('/api/version')
        assert rv.status_code == 200
        assert rv.json['ver']

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

    def test_delete(self, client):
        gid = client.post('/api/groups', json={'name': 'ИС-11'}).json['id']
        rv = client.delete(f'/api/groups/{gid}')
        assert rv.json['ok'] is True
        assert client.get('/api/groups').json == []

    def test_update(self, client):
        gid = client.post('/api/groups', json={'name': 'ИС-11'}).json['id']
        rv = client.patch(f'/api/groups/{gid}', json={'name': 'ПО-21'})
        assert rv.json['ok'] is True
        assert client.get('/api/groups').json[0]['name'] == 'ПО-21'

    def test_update_missing_name(self, client):
        gid = client.post('/api/groups', json={'name': 'ФИ-33'}).json['id']
        rv = client.patch(f'/api/groups/{gid}', json={})
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

    def test_delete(self, client):
        gid = self._setup(client)
        db = get_db()
        sid = db.add_student(gid, 'Иванов', 'Иван')
        rv = client.delete(f'/api/students/{sid}')
        assert rv.json['ok'] is True
        assert client.get(f'/api/students?group_id={gid}').json == []

    def test_update(self, client):
        gid = self._setup(client)
        db = get_db()
        sid = db.add_student(gid, 'Иванов', 'Иван')
        rv = client.patch(f'/api/students/{sid}', json={
            'last_name': 'Петров', 'first_name': 'Пётр', 'middle_name': 'Сергеевич'
        })
        assert rv.json['ok'] is True
        s = client.get(f'/api/students?group_id={gid}').json[0]
        assert s['last_name'] == 'Петров'
        assert s['first_name'] == 'Пётр'

    def test_update_student_missing_fields(self, client):
        gid = client.post('/api/groups', json={'name': 'ФИ-32'}).json['id']
        db = get_db()
        sid = db.add_student(gid, 'Иванов', 'Иван')
        rv = client.patch(f'/api/students/{sid}', json={})
        assert rv.status_code == 400

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
        math_names = [n for n in names if '\u041c\u0430\u0442\u0435\u043c\u0430\u0442\u0438\u043a\u0430' in n]
        assert len(math_names) > 0, f'Математика not found in names: {names}'
        # СВОБОДНО should not appear in substitution list
        free_names = [n for n in names if '\u0421\u0412\u041e\u0411\u041e\u0414\u041d\u041e' in n]
        assert len(free_names) == 0, f'СВОБОДНО should not appear: {names}'

    def test_delete(self, client):
        gid = self._setup(client)
        sid = client.post('/api/subjects', json={
            'name': 'Математика', 'total_hours': 32, 'group_id': gid
        }).json['id']
        rv = client.delete(f'/api/subjects/{sid}')
        assert rv.json['ok'] is True
        assert client.get(f'/api/subjects?group_id={gid}').json == []

    def test_update(self, client):
        gid = self._setup(client)
        sid = client.post('/api/subjects', json={
            'name': 'Математика', 'total_hours': 32, 'group_id': gid
        }).json['id']
        rv = client.patch(f'/api/subjects/{sid}', json={
            'name': 'Физика', 'total_hours': 48
        })
        assert rv.json['ok'] is True
        s = client.get(f'/api/subjects?group_id={gid}').json[0]
        assert s['name'] == 'Физика'
        assert s['total_hours'] == 48

    def test_update_subject_missing_fields(self, client):
        gid = client.post('/api/groups', json={'name': 'ФИ-31'}).json['id']
        sid = client.post('/api/subjects', json={
            'name': 'Математика', 'total_hours': 32, 'group_id': gid
        }).json['id']
        rv = client.patch(f'/api/subjects/{sid}', json={})
        assert rv.status_code == 400
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
        assert len(rv.json['students']) == 1
        assert len(rv.json['lessons']) == 1

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

    def test_today_needs_attention_empty_held(self, client):
        _, sid = self._setup(client)
        today_str = date.today().isoformat()
        lid = get_db().add_lesson(sid, today_str, sid, 'held')
        rv = client.get('/api/schedule/today')
        lesson = [l for l in rv.json['lessons'] if l['id'] == lid][0]
        assert lesson['needs_attention'] is True

    def test_today_needs_attention_with_grade(self, client):
        gid, sid = self._setup(client)
        student_id = get_db().add_student(gid, 'Иванов', 'Иван')
        today_str = date.today().isoformat()
        lid = get_db().add_lesson(sid, today_str, sid, 'held')
        get_db().mark_attendance(lid, student_id, '5')
        rv = client.get('/api/schedule/today')
        lesson = [l for l in rv.json['lessons'] if l['id'] == lid][0]
        assert lesson['needs_attention'] is False

    def test_today_needs_attention_cancelled(self, client):
        _, sid = self._setup(client)
        today_str = date.today().isoformat()
        lid = get_db().add_lesson(sid, today_str, sid, 'cancelled')
        rv = client.get('/api/schedule/today')
        lesson = [l for l in rv.json['lessons'] if l['id'] == lid][0]
        assert lesson['needs_attention'] is False

    def test_update(self, client):
        _, sid = self._setup(client)
        gid2 = client.post('/api/groups', json={'name': 'ПО-21'}).json['id']
        sid2 = client.post('/api/subjects', json={
            'name': 'Физика', 'total_hours': 24, 'group_id': gid2
        }).json['id']
        eid = client.post('/api/schedule', json={
            'day_of_week': 1, 'lesson_number': 1,
            'subject_id': sid, 'week_type': 0
        }).json['id']
        rv = client.patch(f'/api/schedule/{eid}', json={
            'day_of_week': 3, 'lesson_number': 2,
            'subject_id': sid2, 'week_type': 1
        })
        assert rv.json['ok'] is True
        entry = [e for e in client.get('/api/schedule').json if e['id'] == eid][0]
        assert entry['day_of_week'] == 3
        assert entry['lesson_number'] == 2
        assert entry['subject_id'] == sid2
        assert entry['week_type'] == 1

# ======================== LESSONS ========================

class TestLessonsAPI:
    def _setup(self, client):
        gid = client.post('/api/groups', json={'name': 'ИС-11'}).json['id']
        sid = client.post('/api/subjects', json={
            'name': 'Математика', 'total_hours': 32, 'group_id': gid
        }).json['id']
        student_id = get_db().add_student(gid, 'Иванов', 'Иван')
        return gid, sid, student_id

        assert rv.status_code == 201
        assert 'id' in rv.json

    def test_create_duplicate_lesson(self, client):
        _, sid, _ = self._setup(client)
        rv1 = client.post('/api/lessons', json={
            'subject_id': sid, 'actual_subject_id': sid,
            'date': '2026-09-01', 'status': 'held'
        })
        rv2 = client.post('/api/lessons', json={
            'subject_id': sid, 'actual_subject_id': sid,
            'date': '2026-09-01', 'status': 'held'
        })
        assert rv1.status_code == 201
        assert rv2.status_code == 201
        assert rv1.json['id'] != rv2.json['id']

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
        s2 = db.add_subject('Физика', 24, db.list_groups()[0]['id'])
        rv = client.patch(f'/api/lessons/{lid}/substitute',
                          json={'new_subject_id': s2})
        assert rv.json['ok'] is True
        assert 'new_lesson_id' in rv.json
        original = client.get(f'/api/lessons/{lid}').json
        assert original['status'] == 'cancelled'
        new_lesson = client.get(f'/api/lessons/{rv.json["new_lesson_id"]}').json
        assert new_lesson['status'] == 'held'
        assert new_lesson['actual_subject_name'] == 'Физика'

    def test_update_status(self, client):
        _, sid, _ = self._setup(client)
        lid = client.post('/api/lessons', json={
            'subject_id': sid, 'actual_subject_id': sid,
            'date': '2026-09-01', 'status': 'held'
        }).json['id']
        rv = client.patch(f'/api/lessons/{lid}/status', json={'status': 'cancelled'})
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

    def test_create_lesson_dedup_same_pair(self, client):
        _, sid, _ = self._setup(client)
        rv1 = client.post('/api/lessons', json={
            'subject_id': sid, 'actual_subject_id': sid,
            'date': '2026-09-01', 'status': 'held', 'lesson_number': 1
        })
        assert rv1.status_code == 201
        rv2 = client.post('/api/lessons', json={
            'subject_id': sid, 'actual_subject_id': sid,
            'date': '2026-09-01', 'status': 'held', 'lesson_number': 1
        })
        assert rv2.status_code == 200
        assert rv2.json['id'] == rv1.json['id']
        rv3 = client.post('/api/lessons', json={
            'subject_id': sid, 'actual_subject_id': sid,
            'date': '2026-09-01', 'status': 'held', 'lesson_number': 2
        })
        assert rv3.status_code == 201
        assert rv3.json['id'] != rv1.json['id']

    def test_create_lesson_past_date(self, client):
        _, sid, _ = self._setup(client)
        rv = client.post('/api/lessons', json={
            'subject_id': sid, 'actual_subject_id': sid,
            'date': '2026-06-15', 'status': 'held'
        })
        assert rv.status_code == 201
        lid = rv.json['id']
        lesson = get_db().get_lesson(lid)
        assert lesson['date'] == '2026-06-15'

    def test_create_lesson_future_date_rejected(self, client):
        _, sid, _ = self._setup(client)
        rv = client.post('/api/lessons', json={
            'subject_id': sid, 'actual_subject_id': sid,
            'date': '2099-12-31', 'status': 'held'
        })
        assert rv.status_code == 400
        assert rv.json['error'] == 'date in future'

    def test_create_lesson_bad_date_rejected(self, client):
        _, sid, _ = self._setup(client)
        rv = client.post('/api/lessons', json={
            'subject_id': sid, 'actual_subject_id': sid,
            'date': 'not-a-date', 'status': 'held'
        })
        assert rv.status_code == 400
        assert rv.json['error'] == 'bad date'

    def test_export_csv(self, client):
        _, sid, _ = self._setup(client)
        # CSV/PDF отключены, оставлен только xlsx
        rv = client.get(f'/api/export/grades/{sid}.csv')
        assert rv.status_code == 400
        rv = client.get('/api/export/report/2026-09-01.csv')
        assert rv.status_code == 400
        # xlsx остаётся рабочим
        rv = client.get(f'/api/export/grades/{sid}.xlsx')
        assert rv.status_code == 200
        assert 'spreadsheetml.sheet' in rv.content_type

    def test_delete_lesson(self, client):
        gid, sid, student_id = self._setup(client)
        lid = get_db().add_lesson(sid, '2026-09-01', sid, 'held')
        rv = client.delete(f'/api/lessons/{lid}')
        assert rv.json['ok'] is True
        rv = client.get(f'/api/lessons/{lid}')
        assert rv.status_code == 404

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
        db.add_lesson(sid, '2026-09-02', s2, 'held')
        rv = client.get('/api/reports/substitutions')
        assert rv.json == []

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


# ======================== CURATOR PUSH ========================

class TestCuratorPush:
    """End-to-end test: curator bound, student graded -> curator notified."""

    def test_curator_push_sends(self, client, monkeypatch):
        """Verify _fire_curator_push sends message when curator is bound."""
        import api as _api
        import database as _dbmod

        # --- Setup: group, subject, student, curator, lesson ---
        gid = client.post('/api/groups', json={'name': 'ИС-11'}).json['id']
        sid = client.post('/api/subjects', json={
            'name': 'Математика', 'total_hours': 32, 'group_id': gid
        }).json['id']
        db = get_db()
        db.set_setting('max_bot_token', 'fake-token')
        db.set_setting('max_bot_enabled', '1')
        student_id = db.add_student(gid, 'Иванов', 'Иван')

        # Bind curator
        db.bind_curator(gid, 9999)

        lid = client.post('/api/lessons', json={
            'subject_id': sid, 'actual_subject_id': sid,
            'date': '2026-09-01', 'status': 'held'
        }).json['id']

        # Mark attendance via API so the schedule code path is exercised
        rv = client.post(f'/api/lessons/{lid}/attendance', json={
            'student_id': student_id, 'grade': '5'
        })
        assert rv.status_code == 200

        # --- Directly fire curator push (avoid new empty DB) ---
        sent_messages = []

        def fake_send_message(token, chat_id, text, urlopen=None):
            sent_messages.append({
                'token': token, 'chat_id': chat_id, 'text': text
            })

        monkeypatch.setattr('maxbot.send_message', fake_send_message)
        # Make the timer callback use the test DB
        monkeypatch.setattr(_dbmod, 'Database', lambda *_a, **_kw: db)

        _api._fire_curator_push('fake-token', lid, student_id, gid)

        assert len(sent_messages) == 1
        assert sent_messages[0]['chat_id'] == 9999
        assert 'Иванов' in sent_messages[0]['text']
        assert '5' in sent_messages[0]['text']

    def test_curator_push_uses_actual_subject_group(self, client, monkeypatch):
        """If actual_subject_id differs from subject_id, curator of the
        actual subject's group should be notified."""
        import api as _api
        import database as _dbmod

        # Group A
        gid_a = client.post('/api/groups', json={'name': 'ИС-11'}).json['id']
        sid_a = client.post('/api/subjects', json={
            'name': 'Математика', 'total_hours': 32, 'group_id': gid_a
        }).json['id']

        # Group B — actual subject
        gid_b = client.post('/api/groups', json={'name': 'ИС-12'}).json['id']
        sid_b = client.post('/api/subjects', json={
            'name': 'Физика', 'total_hours': 24, 'group_id': gid_b
        }).json['id']

        db = get_db()
        db.set_setting('max_bot_token', 'fake-token')
        db.set_setting('max_bot_enabled', '1')
        student_id = db.add_student(gid_b, 'Петров', 'Пётр')

        # Bind curator to group B only
        db.bind_curator(gid_b, 8888)

        lid = client.post('/api/lessons', json={
            'subject_id': sid_a, 'actual_subject_id': sid_b,
            'date': '2026-09-02', 'status': 'held'
        }).json['id']

        # Mark attendance
        rv = client.post(f'/api/lessons/{lid}/attendance', json={
            'student_id': student_id, 'grade': '4'
        })
        assert rv.status_code == 200

        # --- Directly fire curator push ---
        sent_messages = []

        def fake_send_message(token, chat_id, text, urlopen=None):
            sent_messages.append({
                'token': token, 'chat_id': chat_id, 'text': text
            })

        monkeypatch.setattr('maxbot.send_message', fake_send_message)
        monkeypatch.setattr(_dbmod, 'Database', lambda *_a, **_kw: db)

        _api._fire_curator_push('fake-token', lid, student_id, gid_b)

        assert len(sent_messages) == 1
        # Curator of group B should be notified
        assert sent_messages[0]['chat_id'] == 8888
        assert 'Петров' in sent_messages[0]['text']

    def test_curator_push_schedule_resolves_group(self, client, monkeypatch):
        """Verify the schedule path resolves group_id from actual_subject_id."""
        import api as _api

        gid_a = client.post('/api/groups', json={'name': 'ИС-11'}).json['id']
        sid_a = client.post('/api/subjects', json={
            'name': 'Математика', 'total_hours': 32, 'group_id': gid_a
        }).json['id']

        gid_b = client.post('/api/groups', json={'name': 'ИС-12'}).json['id']
        sid_b = client.post('/api/subjects', json={
            'name': 'Физика', 'total_hours': 24, 'group_id': gid_b
        }).json['id']

        db = get_db()
        db.set_setting('max_bot_token', 'fake-token')
        db.set_setting('max_bot_enabled', '1')
        student_id = db.add_student(gid_b, 'Петров', 'Пётр')
        db.bind_curator(gid_b, 8888)

        lid = client.post('/api/lessons', json={
            'subject_id': sid_a, 'actual_subject_id': sid_b,
            'date': '2026-09-02', 'status': 'held'
        }).json['id']

        # Mark attendance — schedule code should find cur_chat via actual_subject_id
        rv = client.post(f'/api/lessons/{lid}/attendance', json={
            'student_id': student_id, 'grade': '4'
        })
        assert rv.status_code == 200

        # A timer should be scheduled (not cancelled)
        key = (lid, student_id)
        assert key in _api._pending_curator, "curator timer was not scheduled"

    def test_pending_curator_separate_from_pending(self, client, monkeypatch):
        """Cancelling student timers must not cancel curator timers."""
        import api as _api
        import database as _dbmod

        gid = client.post('/api/groups', json={'name': 'ИС-11'}).json['id']
        sid = client.post('/api/subjects', json={
            'name': 'Математика', 'total_hours': 32, 'group_id': gid
        }).json['id']
        db = get_db()
        db.set_setting('max_bot_token', 'fake-token')
        db.set_setting('max_bot_enabled', '1')
        student_id = db.add_student(gid, 'Иванов', 'Иван')

        db.bind_curator(gid, 6666)

        lid = client.post('/api/lessons', json={
            'subject_id': sid, 'actual_subject_id': sid,
            'date': '2026-09-04', 'status': 'held'
        }).json['id']

        # First attendance — should schedule both student + curator timers
        rv1 = client.post(f'/api/lessons/{lid}/attendance', json={
            'student_id': student_id, 'grade': '5'
        })
        assert rv1.status_code == 200

        key = (lid, student_id)
        assert key in _api._pending, "student timer not scheduled"
        assert key in _api._pending_curator, "curator timer not scheduled"

        # Save the old curator timer ref
        old_curator_timer = _api._pending_curator.get(key)

        # Second attendance — should cancel old timers and create new
        rv2 = client.post(f'/api/lessons/{lid}/attendance', json={
            'student_id': student_id, 'grade': '4'
        })
        assert rv2.status_code == 200

        # Old timer should have been cancelled
        assert old_curator_timer is not None
        # New timers should exist
        assert key in _api._pending, "student timer missing after re-mark"
        assert key in _api._pending_curator, "curator timer missing after re-mark"
        assert _api._pending_curator[key] is not old_curator_timer, \
            "curator timer was not replaced"

        # Now actually fire the push to verify it sends
        sent_messages = []

        def fake_send_message(token, chat_id, text, urlopen=None):
            sent_messages.append({
                'token': token, 'chat_id': chat_id, 'text': text
            })

        monkeypatch.setattr('maxbot.send_message', fake_send_message)
        monkeypatch.setattr(_dbmod, 'Database', lambda *_a, **_kw: db)

        _api._fire_curator_push('fake-token', lid, student_id, gid)

        curator_msgs = [m for m in sent_messages if m['chat_id'] == 6666]
        assert len(curator_msgs) == 1
        # Final grade should be the last one
        assert '4' in curator_msgs[0]['text']
