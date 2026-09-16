import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import api as _api_module
from database import Database


import pytest


@pytest.fixture
def client():
    _api_module.app.config['TESTING'] = True
    original = _api_module.get_db
    _db = Database(':memory:')
    _api_module.get_db = lambda: _db
    with _api_module.app.test_client() as c:
        yield c
    _db.close()
    _api_module.get_db = original


def get_db():
    return _api_module.get_db()


def _setup(client):
    gid = client.post('/api/groups', json={'name': 'ИС-11'}).json['id']
    sid = client.post('/api/subjects', json={'name': 'Мат', 'total_hours': 32, 'group_id': gid}).json['id']
    db = get_db()
    s1 = db.add_student(gid, 'Иванов', 'Иван')
    s2 = db.add_student(gid, 'Петров', 'Петр')
    lid = db.add_lesson(sid, '2026-09-01', sid, 'held')
    # also create lesson scheduled for cancelled test? use same
    return gid, sid, s1, s2, lid


class TestConduct:
    def test_conduct_empty_list(self, client):
        _, _, _, _, lid = _setup(client)
        rv = client.post(f'/api/lessons/{lid}/conduct', json=[])
        assert rv.status_code == 200
        assert rv.json == {'ok': True, 'notified': 0}

    def test_conduct_empty_records_wrapper(self, client):
        _, _, _, _, lid = _setup(client)
        rv = client.post(f'/api/lessons/{lid}/conduct', json={'records': []})
        assert rv.status_code == 200
        assert rv.json['notified'] == 0

    def test_conduct_bad_payload(self, client):
        _, _, _, _, lid = _setup(client)
        rv = client.post(f'/api/lessons/{lid}/conduct', json={'bad': 123})
        assert rv.status_code == 400
        rv2 = client.post(f'/api/lessons/{lid}/conduct', json=[{'student_id': 1}])
        assert rv2.status_code == 400
        rv3 = client.post(f'/api/lessons/{lid}/conduct', json="notalist")
        assert rv3.status_code == 400

    def test_conduct_cancelled_400(self, client):
        gid, sid, s1, s2, lid = _setup(client)
        db = get_db()
        db.cancel_lesson(lid)
        rv = client.post(f'/api/lessons/{lid}/conduct', json=[{'student_id': s1, 'grade': '5'}])
        assert rv.status_code == 400
        assert 'cancelled' in rv.json['error'].lower()

    def test_conduct_notified_counts_only_changed(self, client, monkeypatch):
        gid, sid, s1, s2, lid = _setup(client)
        db = get_db()
        db.set_setting('max_bot_token', 'fake-token')
        db.set_setting('max_bot_enabled', '1')
        # mock pushes
        sent = []

        def fake_notify(token, student_id, grade, date_str, subject, urlopen=None):
            sent.append(('student', student_id, grade))

        def fake_send(token, chat_id, text, urlopen=None):
            sent.append(('curator', chat_id, text))

        monkeypatch.setattr('maxbot.notify_grade', fake_notify)
        monkeypatch.setattr('maxbot.send_message', fake_send)

        # first conduct with 2 grades changed from "" to "5" and "4"
        rv = client.post(f'/api/lessons/{lid}/conduct', json=[
            {'student_id': s1, 'grade': '5'},
            {'student_id': s2, 'grade': '4'},
        ])
        assert rv.status_code == 200
        assert rv.json['ok'] is True
        assert rv.json['notified'] == 2
        # wait for daemon thread to fire (it sleeps 0.6 each)
        import time
        time.sleep(1.5)
        # should have at least 2 student pushes (curator none because no curator bound)
        student_pushes = [x for x in sent if x[0] == 'student']
        assert len(student_pushes) == 2

        # second conduct without changes -> notified 0
        sent.clear()
        rv2 = client.post(f'/api/lessons/{lid}/conduct', json=[
            {'student_id': s1, 'grade': '5'},
            {'student_id': s2, 'grade': '4'},
        ])
        assert rv2.status_code == 200
        assert rv2.json['notified'] == 0
        time.sleep(0.8)
        assert len([x for x in sent if x[0] == 'student']) == 0

    def test_conduct_partial_change(self, client, monkeypatch):
        gid, sid, s1, s2, lid = _setup(client)
        db = get_db()
        db.set_setting('max_bot_token', 'fake-token')
        db.set_setting('max_bot_enabled', '1')
        sent = []

        def fake_notify(token, student_id, grade, date_str, subject, urlopen=None):
            sent.append(student_id)

        monkeypatch.setattr('maxbot.notify_grade', fake_notify)
        monkeypatch.setattr('maxbot.send_message', lambda *a, **kw: None)

        # initial 2 grades
        client.post(f'/api/lessons/{lid}/conduct', json=[
            {'student_id': s1, 'grade': '5'},
            {'student_id': s2, 'grade': '4'},
        ])
        import time
        time.sleep(0.8)
        sent.clear()
        # change only s1
        rv = client.post(f'/api/lessons/{lid}/conduct', json=[
            {'student_id': s1, 'grade': '3'},
            {'student_id': s2, 'grade': '4'},
        ])
        assert rv.json['notified'] == 1
        time.sleep(0.8)
        assert sent == [s1]

    def test_conduct_with_curator(self, client, monkeypatch):
        gid, sid, s1, s2, lid = _setup(client)
        db = get_db()
        db.set_setting('max_bot_token', 'fake-token')
        db.set_setting('max_bot_enabled', '1')
        db.bind_curator(gid, 99999)
        sent_student = []
        sent_curator = []

        def fake_notify(token, student_id, grade, date_str, subject, urlopen=None):
            sent_student.append(student_id)

        def fake_send(token, chat_id, text, urlopen=None):
            sent_curator.append((chat_id, text))

        monkeypatch.setattr('maxbot.notify_grade', fake_notify)
        monkeypatch.setattr('maxbot.send_message', fake_send)

        rv = client.post(f'/api/lessons/{lid}/conduct', json=[
            {'student_id': s1, 'grade': '5'},
        ])
        assert rv.json['notified'] == 1
        import time
        time.sleep(0.8)
        assert sent_student == [s1]
        assert len(sent_curator) == 1
        assert sent_curator[0][0] == 99999
        assert 'Иванов' in sent_curator[0][1]
        assert '5' in sent_curator[0][1]

    def test_conduct_records_wrapper(self, client, monkeypatch):
        gid, sid, s1, _, lid = _setup(client)
        db = get_db()
        db.set_setting('max_bot_token', 'fake-token')
        db.set_setting('max_bot_enabled', '1')
        monkeypatch.setattr('maxbot.notify_grade', lambda *a, **kw: None)
        monkeypatch.setattr('maxbot.send_message', lambda *a, **kw: None)
        rv = client.post(f'/api/lessons/{lid}/conduct', json={'records': [{'student_id': s1, 'grade': '5'}]})
        assert rv.status_code == 200
        assert rv.json['notified'] == 1

    def test_conduct_single_object(self, client, monkeypatch):
        gid, sid, s1, _, lid = _setup(client)
        db = get_db()
        db.set_setting('max_bot_token', 'fake-token')
        db.set_setting('max_bot_enabled', '1')
        monkeypatch.setattr('maxbot.notify_grade', lambda *a, **kw: None)
        monkeypatch.setattr('maxbot.send_message', lambda *a, **kw: None)
        rv = client.post(f'/api/lessons/{lid}/conduct', json={'student_id': s1, 'grade': '5'})
        assert rv.status_code == 200
        assert rv.json['notified'] == 1

    def test_conduct_no_token_no_notify(self, client):
        gid, sid, s1, _, lid = _setup(client)
        # no token set
        rv = client.post(f'/api/lessons/{lid}/conduct', json=[{'student_id': s1, 'grade': '5'}])
        assert rv.status_code == 200
        assert rv.json['notified'] == 0

    def test_conduct_equal_skip(self, client, monkeypatch):
        gid, sid, s1, _, lid = _setup(client)
        db = get_db()
        db.set_setting('max_bot_token', 'fake-token')
        db.set_setting('max_bot_enabled', '1')
        monkeypatch.setattr('maxbot.notify_grade', lambda *a, **kw: None)
        monkeypatch.setattr('maxbot.send_message', lambda *a, **kw: None)
        db.mark_attendance(lid, s1, '5')
        rv = client.post(f'/api/lessons/{lid}/conduct', json=[{'student_id': s1, 'grade': '5'}])
        assert rv.json['notified'] == 0
        rv2 = client.post(f'/api/lessons/{lid}/conduct', json=[{'student_id': s1, 'grade': '4'}])
        assert rv2.json['notified'] == 1
