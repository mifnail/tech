import io
import json
import os
import sys
import threading
import urllib.error

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import api as _api_module
from database import Database
import maxbot
from maxbot import process_text, due_reminder, reminder_targets


@pytest.fixture
def db():
    d = Database(':memory:')
    yield d
    d.close()


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


def get_db():
    return _api_module.get_db()


def _seed(db, last='Иванов', first='Иван'):
    gid = db.add_group('ИС-11')
    sid = db.add_subject('Математика', 32, gid)
    st = db.add_student(gid, last, first, 'Иванович')
    return gid, sid, st


# ======================== FAKE HTTP ========================

class FakeResp:
    def __init__(self, payload: bytes):
        self._p = payload

    def read(self):
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _fake_urlopen_factory(script, record):
    def fake(req, timeout=None, **kw):
        record.append((req.get_method(), req.full_url))
        kind, payload = script.pop(0)
        if kind == 'json':
            return FakeResp(json.dumps(payload).encode())
        if kind == 'http401':
            raise urllib.error.HTTPError(req.full_url, 401, 'Unauthorized', {}, None)
        if kind == 'urlerror':
            raise urllib.error.URLError('dns fail')
        raise AssertionError('bad script kind')
    return fake


# ======================== MAX LINKS (DB) ========================

class TestMaxLinks:
    def test_bind_roundtrip(self, db):
        _, _, st = _seed(db)
        assert db.get_max_link(111) is None
        db.bind_max(111, st)
        assert db.get_max_link(111) == st
        assert db.get_max_student_chat(st) == 111
        db.unbind_max(111)
        assert db.get_max_link(111) is None

    def test_unbind_student(self, db):
        _, _, st = _seed(db)
        db.bind_max(111, st)
        db.unbind_max_student(st)
        assert db.get_max_link(111) is None
        assert db.get_max_student_chat(st) is None

    def test_one_to_one(self, db):
        gid = db.add_group('ИС-11')
        db.add_subject('Математика', 32, gid)
        s1 = db.add_student(gid, 'Иванов', 'Иван')
        s2 = db.add_student(gid, 'Петров', 'Пётр')
        db.bind_max(111, s1)
        with pytest.raises(Exception):
            db.bind_max(111, s2)  # chat busy
        with pytest.raises(Exception):
            db.bind_max(222, s1)  # student busy

    def test_list(self, db):
        _, _, st = _seed(db)
        db.bind_max(111, st)
        rows = [dict(r) for r in db.list_max_links()]
        assert len(rows) == 1
        assert rows[0]['chat_id'] == 111
        assert rows[0]['last_name'] == 'Иванов'


# ======================== DIALOG LOGIC ========================

class TestDialog:
    def test_start_new(self, db):
        _seed(db)
        r = process_text('/start', 111, db)
        assert 'фамилию' in r

    def test_bind_and_grades(self, db):
        gid, sid, st = _seed(db)
        lid = db.add_lesson(sid, '2026-09-01', sid, 'held', 1)
        db.mark_attendance(lid, st, '5')
        r = process_text('Иванов', 111, db)
        assert 'Готово' in r and '5' in r
        assert db.get_max_link(111) == st
        r2 = process_text('/grades', 111, db)
        assert 'Математика' in r2 and '5' in r2

    def test_squat_refused(self, db):
        _, _, st = _seed(db)
        db.bind_max(111, st)
        r = process_text('Иванов', 222, db)
        assert 'другому чату' in r
        assert db.get_max_link(222) is None

    def test_unknown_surname(self, db):
        _seed(db)
        assert 'Не нашёл' in process_text('Сидоров', 111, db)

    def test_multi_clarify(self, db):
        gid = db.add_group('ИС-11')
        db.add_subject('Математика', 32, gid)
        db.add_student(gid, 'Иванов', 'Иван')
        db.add_student(gid, 'Иванов', 'Пётр')
        r = process_text('Иванов', 111, db)
        assert 'Имя' in r
        r2 = process_text('Иванов Иван', 111, db)
        assert 'Готово' in r2

    def test_grades_unbound(self, db):
        _seed(db)
        assert 'привяжись' in process_text('/grades', 111, db).lower() \
            or 'фамилию' in process_text('/grades', 111, db)

    def test_today(self, db):
        from datetime import date as _d
        gid, sid, st = _seed(db)
        today = _d.today().isoformat()
        lid = db.add_lesson(sid, today, sid, 'held', 1)
        db.mark_attendance(lid, st, '4')
        db.bind_max(111, st)
        r = process_text('/today', 111, db)
        assert 'Математика' in r and '4' in r

    def test_today_empty(self, db):
        _, _, st = _seed(db)
        db.bind_max(111, st)
        assert 'нет' in process_text('/today', 111, db)

    def test_help_unbind(self, db):
        _, _, st = _seed(db)
        assert '/start' in process_text('/help', 111, db)
        db.bind_max(111, st)
        assert '/grades' in process_text('/help', 111, db)
        assert 'не знаю' in process_text('/nope', 111, db).lower()
        assert 'снята' in process_text('/unbind', 111, db).lower()
        assert db.get_max_link(111) is None

    def test_no_grades(self, db):
        from tgbot import my_grades_text
        _, _, st = _seed(db)
        assert 'пока нет' in my_grades_text(db, st)


# ======================== MAX CLIENT (fake net) ========================

class TestMaxClient:
    def test_check(self):
        rec = []
        fake = _fake_urlopen_factory([
            ('json', {'updates': [], 'marker': 42}),
        ], rec)
        result = maxbot.check('tok', urlopen=fake)
        assert result
        assert rec[0][0] == 'GET'
        assert 'timeout=0' in rec[0][1]

    def test_send_message(self):
        rec = []
        fake = _fake_urlopen_factory([
            ('json', {'ok': True}),
        ], rec)
        maxbot.send_message('tok', 111, 'hello', urlopen=fake)
        assert rec[0][0] == 'POST'
        assert 'chat_id=111' in rec[0][1]

    def test_send_message_truncate(self):
        rec = []
        fake = _fake_urlopen_factory([
            ('json', {'ok': True}),
        ], rec)
        maxbot.send_message('tok', 1, 'x' * 5000, urlopen=fake)
        assert rec[0][0] == 'POST'

    def test_get_updates(self):
        rec = []
        fake = _fake_urlopen_factory([
            ('json', {'updates': [{'type': 'message_created'}], 'marker': 99}),
        ], rec)
        updates, marker = maxbot.get_updates('tok', marker=10, timeout=5, urlopen=fake)
        assert len(updates) == 1
        assert marker == 99
        assert 'marker=10' in rec[0][1]

    def test_get_updates_no_marker(self):
        rec = []
        fake = _fake_urlopen_factory([
            ('json', {'updates': [], 'marker': 5}),
        ], rec)
        updates, marker = maxbot.get_updates('tok', marker=None, timeout=5, urlopen=fake)
        assert updates == []
        assert marker == 5
        assert 'marker=' not in rec[0][1]

    def test_401(self):
        fake = _fake_urlopen_factory([('http401', None)], [])
        with pytest.raises(maxbot.MaxError):
            maxbot.check('bad', urlopen=fake)


# ======================== REMINDERS ========================

class TestReminders:
    def test_due_reminder_hour_17(self):
        assert due_reminder(17, None, '2026-09-01') is True

    def test_due_reminder_hour_18(self):
        assert due_reminder(18, '2026-09-01', '2026-09-02') is True

    def test_due_reminder_already_sent(self):
        assert due_reminder(17, '2026-09-01', '2026-09-01') is False

    def test_due_reminder_wrong_hour(self):
        assert due_reminder(10, None, '2026-09-01') is False

    def test_reminder_targets_grouping(self, db):
        from datetime import date, timedelta
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        s1 = db.add_student(gid, 'Иванов', 'Иван')
        s2 = db.add_student(gid, 'Петров', 'Пётр')
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        lid = db.add_lesson(sid, tomorrow, sid, 'held', 1)
        db.bind_max(1001, s1)
        db.bind_max(1002, s2)
        targets = reminder_targets(db, tomorrow)
        assert len(targets) == 2
        chat_ids = {t[0] for t in targets}
        assert 1001 in chat_ids and 1002 in chat_ids
        assert 'Математика' in targets[0][1]

    def test_reminder_targets_no_lessons(self, db):
        from datetime import date, timedelta
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        assert reminder_targets(db, tomorrow) == []

    def test_reminder_targets_no_chats(self, db):
        from datetime import date, timedelta
        gid = db.add_group('ИС-11')
        sid = db.add_subject('Математика', 32, gid)
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        lid = db.add_lesson(sid, tomorrow, sid, 'held', 1)
        assert reminder_targets(db, tomorrow) == []


# ======================== PROCESS TEXT (extended) ========================

class TestProcessTextExtended:
    def test_already_bound_start(self, db):
        _, _, st = _seed(db)
        db.bind_max(111, st)
        r = process_text('/start', 111, db)
        assert 'привязан' in r.lower()

    def test_command_before_bind(self, db):
        _seed(db)
        r = process_text('/grades', 111, db)
        assert 'привяжись' in r.lower() or 'фамилию' in r

    def test_unknown_command(self, db):
        _, _, st = _seed(db)
        db.bind_max(111, st)
        r = process_text('/blah', 111, db)
        assert 'не знаю' in r.lower()


# ======================== API ========================

class TestMaxBotAPI:
    def test_settings_crud(self, client):
        assert client.get('/api/settings/maxbot').json == {'has_token': False, 'enabled': False}
        rv = client.post('/api/settings/maxbot', json={'token': 'abc', 'enabled': True}).json
        assert rv == {'ok': True, 'has_token': True, 'enabled': True}
        rv = client.get('/api/settings/maxbot').json
        assert rv == {'has_token': True, 'enabled': True}
        assert 'abc' not in json.dumps(rv)
        assert client.delete('/api/settings/maxbot').json == {'ok': True}
        assert client.get('/api/settings/maxbot').json['has_token'] is False

    def test_check_no_token(self, client):
        assert client.get('/api/settings/maxbot/check').status_code == 400

    def test_check_ok(self, client, monkeypatch):
        import urllib.request
        client.post('/api/settings/maxbot', json={'token': 't'})
        body = json.dumps({'updates': [], 'marker': 1}).encode()

        def fake(req, timeout=None, **kw):
            return FakeResp(body)

        monkeypatch.setattr(urllib.request, 'urlopen', fake)
        rv = client.get('/api/settings/maxbot/check')
        assert rv.json == {'ok': True}

    def test_links(self, client):
        gid = client.post('/api/groups', json={'name': 'ИС-11'}).json['id']
        sid = client.post('/api/subjects', json={
            'name': 'Математика', 'total_hours': 32, 'group_id': gid}).json['id']
        st = get_db().add_student(gid, 'Иванов', 'Иван')
        get_db().bind_max(111, st)
        rows = client.get('/api/maxbot/links').json
        assert len(rows) == 1 and rows[0]['chat_id'] == 111
        assert client.delete(f'/api/maxbot/links/by-student/{st}').json == {'ok': True}
        assert client.get('/api/maxbot/links').json == []
