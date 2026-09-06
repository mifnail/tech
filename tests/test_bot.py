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
import tgbot
from tgbot import process_text, my_grades_text, today_text


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


# ======================== LINKS (DB) ========================

class TestBotLinks:
    def test_bind_roundtrip(self, db):
        _, _, st = _seed(db)
        assert db.get_chat_link(111) is None
        db.bind_chat(111, st)
        assert db.get_chat_link(111) == st
        assert db.get_student_chat(st) == 111
        db.unbind_chat(111)
        assert db.get_chat_link(111) is None

    def test_unbind_student(self, db):
        _, _, st = _seed(db)
        db.bind_chat(111, st)
        db.unbind_student(st)
        assert db.get_chat_link(111) is None
        assert db.get_student_chat(st) is None

    def test_one_to_one(self, db):
        gid = db.add_group('ИС-11')
        db.add_subject('Математика', 32, gid)
        s1 = db.add_student(gid, 'Иванов', 'Иван')
        s2 = db.add_student(gid, 'Петров', 'Пётр')
        db.bind_chat(111, s1)
        with pytest.raises(Exception):
            db.bind_chat(111, s2)  # chat busy
        with pytest.raises(Exception):
            db.bind_chat(222, s1)  # student busy

    def test_list(self, db):
        _, _, st = _seed(db)
        db.bind_chat(111, st)
        rows = [dict(r) for r in db.list_bot_links()]
        assert len(rows) == 1
        assert rows[0]['chat_id'] == 111
        assert rows[0]['last_name'] == 'Иванов'

    def test_find(self, db):
        _seed(db)
        assert len(db.find_students_by_surname('Иван')) == 1
        assert len(db.find_students_by_surname('иван')) == 1  # case-insensitive
        assert db.find_students_by_surname('Сидоров') == []
        assert db.find_students_by_surname('') == []

    def test_find_two_tokens(self, db):
        gid = db.add_group('ИС-11')
        db.add_subject('Математика', 32, gid)
        db.add_student(gid, 'Иванов', 'Иван')
        db.add_student(gid, 'Иванов', 'Пётр')
        assert len(db.find_students_by_surname('Иванов')) == 2
        assert len(db.find_students_by_surname('Иванов Иван')) == 1

    def test_get_student(self, db):
        _, _, st = _seed(db)
        row = db.get_student(st)
        assert row['last_name'] == 'Иванов'
        assert db.get_student(999) is None


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
        assert db.get_chat_link(111) == st
        r2 = process_text('/grades', 111, db)
        assert 'Математика' in r2 and '5' in r2

    def test_squat_refused(self, db):
        _, _, st = _seed(db)
        db.bind_chat(111, st)
        r = process_text('Иванов', 222, db)
        assert 'другому чату' in r
        assert db.get_chat_link(222) is None

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
        db.bind_chat(111, st)
        r = process_text('/today', 111, db)
        assert 'Математика' in r and '4' in r

    def test_today_empty(self, db):
        _, _, st = _seed(db)
        db.bind_chat(111, st)
        assert 'нет' in process_text('/today', 111, db)

    def test_help_unbind(self, db):
        _, _, st = _seed(db)
        assert '/start' in process_text('/help', 111, db)
        db.bind_chat(111, st)
        assert '/grades' in process_text('/help', 111, db)
        assert 'не знаю' in process_text('/nope', 111, db).lower()
        assert 'снята' in process_text('/unbind', 111, db).lower()
        assert db.get_chat_link(111) is None

    def test_no_grades(self, db):
        _, _, st = _seed(db)
        assert 'пока нет' in my_grades_text(db, st)


# ======================== TG CLIENT (fake net) ========================

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


class TestTgClient:
    def test_send_getme(self):
        rec = []
        fake = _fake_urlopen_factory([
            ('json', {'ok': True, 'result': {'username': 'tb'}}),
            ('json', {'ok': True, 'result': [{'update_id': 7}]}),
        ], rec)
        assert tgbot.get_me('t', urlopen=fake)['username'] == 'tb'
        assert tgbot.get_updates('t', 0, urlopen=fake)[0]['update_id'] == 7
        assert rec[0][1].endswith('/getMe')

    def test_send_message_truncate(self):
        rec = []
        fake = _fake_urlopen_factory([('json', {'ok': True, 'result': {}})], rec)
        tgbot.send_message('t', 1, 'x' * 5000, urlopen=fake)
        assert rec[0][0] == 'POST'

    def test_401(self):
        fake = _fake_urlopen_factory([('http401', None)], [])
        with pytest.raises(tgbot.BotError):
            tgbot.get_me('bad', urlopen=fake)

    def test_429(self):
        class Fake429(FakeResp):
            pass

        def fake(req, timeout=None, **kw):
            body = json.dumps({'ok': False, 'parameters': {'retry_after': 3}}).encode()
            raise urllib.error.HTTPError(req.full_url, 429, 'Too Many', {}, io.BytesIO(body))

        with pytest.raises(tgbot.BotRateLimited) as e:
            tgbot.get_me('t', urlopen=fake)
        assert e.value.wait == 3

    def test_run_polling_one_update(self, tmp_path):
        # :memory: нельзя делить между потоками — файловый БД как на устройстве
        path = str(tmp_path / 't.db')
        seed = Database(path)
        gid = seed.add_group('ИС-11')
        sid = seed.add_subject('Математика', 32, gid)
        st = seed.add_student(gid, 'Иванов', 'Иван')
        lid = seed.add_lesson(sid, '2026-09-01', sid, 'held', 1)
        seed.mark_attendance(lid, st, '5')
        seed.close()
        upd = {'update_id': 10, 'message': {'chat': {'id': 111}, 'text': 'Иванов'}}
        calls = []
        stop = threading.Event()

        def fake(req, timeout=None, **kw):
            url = req.full_url
            if url.endswith('/getUpdates'):
                return FakeResp(json.dumps({'ok': True, 'result': [upd]}).encode())
            calls.append(url)
            stop.set()
            return FakeResp(json.dumps({'ok': True, 'result': {}}).encode())

        t = threading.Thread(target=tgbot.run_polling,
                             args=('tok', lambda: Database(path), stop, fake))
        t.start()
        t.join(timeout=10)
        assert not t.is_alive()
        check = Database(path)
        try:
            assert check.get_chat_link(111) == st
        finally:
            check.close()
        assert any(u.endswith('/sendMessage') for u in calls)


# ======================== API ========================

class TestBotAPI:
    def test_settings_crud(self, client):
        assert client.get('/api/settings/bot').json == {'has_token': False, 'enabled': False}
        rv = client.post('/api/settings/bot', json={'token': 'abc', 'enabled': True}).json
        assert rv == {'ok': True, 'has_token': True, 'enabled': True}
        rv = client.get('/api/settings/bot').json
        assert rv == {'has_token': True, 'enabled': True}
        assert 'abc' not in json.dumps(rv)
        assert client.delete('/api/settings/bot').json == {'ok': True}
        assert client.get('/api/settings/bot').json['has_token'] is False

    def test_check_no_token(self, client):
        assert client.get('/api/settings/bot/check').status_code == 400

    def test_check_ok(self, client, monkeypatch):
        import urllib.request
        client.post('/api/settings/bot', json={'token': 't'})
        body = json.dumps({'ok': True, 'result': {'username': 'mybot'}}).encode()

        def fake(req, timeout=None, **kw):
            return FakeResp(body)

        monkeypatch.setattr(urllib.request, 'urlopen', fake)
        rv = client.get('/api/settings/bot/check')
        assert rv.json == {'ok': True, 'username': 'mybot'}

    def test_links(self, client):
        gid = client.post('/api/groups', json={'name': 'ИС-11'}).json['id']
        sid = client.post('/api/subjects', json={
            'name': 'Математика', 'total_hours': 32, 'group_id': gid}).json['id']
        st = get_db().add_student(gid, 'Иванов', 'Иван')
        get_db().bind_chat(111, st)
        rows = client.get('/api/bot/links').json
        assert len(rows) == 1 and rows[0]['chat_id'] == 111
        assert client.delete(f'/api/bot/links/by-student/{st}').json == {'ok': True}
        assert client.get('/api/bot/links').json == []


# ======================== SSL FALLBACK ========================

class TestTgSslFallback:
    def test_cert_failover(self, monkeypatch):
        import urllib.request
        calls = []
        body = json.dumps({'ok': True, 'result': {'username': 'b'}}).encode()

        def fake(req, timeout=None, **kw):
            calls.append(kw.get('context'))
            if len(calls) == 1:
                raise urllib.error.URLError('[SSL: CERTIFICATE_VERIFY_FAILED] boom')
            return FakeResp(body)

        monkeypatch.setattr(urllib.request, 'urlopen', fake)
        assert tgbot.get_me('t') == {'username': 'b'}
        assert len(calls) == 2


# ======================== NATIVE SAVE ========================

class TestNativeSave:
    def _setup_subject(self, client):
        gid = client.post('/api/groups', json={'name': 'Г'}).json['id']
        return client.post('/api/subjects', json={
            'name': 'П', 'total_hours': 1, 'group_id': gid}).json['id']

    def test_grades_ok(self, client, monkeypatch):
        sid = self._setup_subject(client)
        monkeypatch.setattr(_api_module, '_save_to_downloads',
                            lambda data, fn, mt: '/fake/' + fn)
        rv = client.post(f'/api/export/grades/{sid}/to-downloads')
        assert rv.status_code == 200, rv.json
        assert rv.json['path'] == f'/fake/grades_{sid}.xlsx'

    def test_report_ok(self, client, monkeypatch):
        monkeypatch.setattr(_api_module, '_save_to_downloads',
                            lambda data, fn, mt: '/fake/' + fn)
        rv = client.post('/api/export/report/2026-09-01/to-downloads')
        assert rv.status_code == 200

    def test_save_error(self, client, monkeypatch):
        sid = self._setup_subject(client)

        def boom(data, fn, mt):
            raise RuntimeError('denied')

        monkeypatch.setattr(_api_module, '_save_to_downloads', boom)
        rv = client.post(f'/api/export/grades/{sid}/to-downloads')
        assert rv.status_code == 500

    def test_desktop_branch_tmp_home(self, client, monkeypatch, tmp_path):
        import os
        monkeypatch.setenv('HOME', str(tmp_path))
        monkeypatch.setenv('USERPROFILE', str(tmp_path))
        sid = self._setup_subject(client)
        rv = client.post(f'/api/export/grades/{sid}/to-downloads')
        assert rv.status_code == 200, rv.json
        assert os.path.exists(os.path.join(str(tmp_path), 'Downloads', f'grades_{sid}.xlsx'))


class TestNativeShare:
    def _setup_subject(self, client):
        gid = client.post('/api/groups', json={'name': 'Г'}).json['id']
        return client.post('/api/subjects', json={
            'name': 'П', 'total_hours': 1, 'group_id': gid}).json['id']

    def test_share_ok(self, client, monkeypatch):
        sid = self._setup_subject(client)
        seen = {}
        monkeypatch.setattr(_api_module, '_save_to_downloads_full',
                            lambda data, fn, mt: ('/fake/' + fn, 'content://fake/1'))
        monkeypatch.setattr(_api_module, '_share_file',
                            lambda uri, mt, label=None, mode='cast', chooser='title': seen.update(uri=uri, mt=mt))
        rv = client.post(f'/api/export/grades/{sid}/share')
        assert rv.status_code == 200, rv.json
        assert rv.json == {'ok': True, 'path': f'/fake/grades_{sid}.xlsx', 'shared': True}
        assert seen['uri'] == 'content://fake/1'

    def test_share_report_ok(self, client, monkeypatch):
        monkeypatch.setattr(_api_module, '_save_to_downloads_full',
                            lambda data, fn, mt: ('/fake/' + fn, 'content://fake/2'))
        monkeypatch.setattr(_api_module, '_share_file', lambda uri, mt, label=None, mode='clip', chooser='title': None)
        rv = client.post('/api/export/report/2026-09-01/share')
        assert rv.status_code == 200
        assert rv.json['shared'] is True

    def test_share_desktop_no_uri(self, client, monkeypatch):
        sid = self._setup_subject(client)
        monkeypatch.setattr(_api_module, '_save_to_downloads_full',
                            lambda data, fn, mt: ('/fake/' + fn, None))
        rv = client.post(f'/api/export/grades/{sid}/share')
        assert rv.status_code == 400

    def test_share_intent_fail_keeps_file(self, client, monkeypatch):
        sid = self._setup_subject(client)
        monkeypatch.setattr(_api_module, '_save_to_downloads_full',
                            lambda data, fn, mt: ('/fake/' + fn, 'content://fake/3'))

        def boom(uri, mt, label=None, mode='clip', chooser='title'):
            raise RuntimeError('no activity')

        monkeypatch.setattr(_api_module, '_share_file', boom)
        rv = client.post(f'/api/export/grades/{sid}/share')
        assert rv.status_code == 200
        assert rv.json['shared'] is False
        assert rv.json['path'] == f'/fake/grades_{sid}.xlsx'


class TestShareModes:
    def _setup_subject(self, client):
        gid = client.post('/api/groups', json={'name': 'Г'}).json['id']
        return client.post('/api/subjects', json={
            'name': 'П', 'total_hours': 1, 'group_id': gid}).json['id']

    def test_mode_forwarded(self, client, monkeypatch):
        sid = self._setup_subject(client)
        seen = {}
        monkeypatch.setattr(_api_module, '_save_to_downloads_full',
                            lambda data, fn, mt: ('/fake/' + fn, 'content://fake/9'))

        def fake_share(uri, mt, label='vedomost', mode='clip', chooser='title'):
            seen['mode'] = mode

        monkeypatch.setattr(_api_module, '_share_file', fake_share)
        rv = client.post(f'/api/export/grades/{sid}/share?mode=both')
        assert rv.status_code == 200
        assert seen.get('mode') == 'both'

    def test_mode_clip_forwarded(self, client, monkeypatch):
        sid = self._setup_subject(client)
        seen = {}
        monkeypatch.setattr(_api_module, '_save_to_downloads_full',
                            lambda data, fn, mt: ('/fake/' + fn, 'content://fake/9'))

        def fake_share(uri, mt, label='vedomost', mode='clip', chooser='title'):
            seen['mode'] = mode

        monkeypatch.setattr(_api_module, '_share_file', fake_share)
        rv = client.post(f'/api/export/grades/{sid}/share?mode=clip')
        assert rv.status_code == 200
        assert seen.get('mode') == 'clip'

    def test_chooser_forwarded(self, client, monkeypatch):
        sid = self._setup_subject(client)
        seen = {}
        monkeypatch.setattr(_api_module, '_save_to_downloads_full',
                            lambda data, fn, mt: ('/fake/' + fn, 'content://fake/9'))

        def fake_share(uri, mt, label='vedomost', mode='cast', chooser='title'):
            seen['chooser'] = chooser

        monkeypatch.setattr(_api_module, '_share_file', fake_share)
        rv = client.post(f'/api/export/grades/{sid}/share?mode=cast&chooser=none')
        assert rv.status_code == 200
        assert seen.get('chooser') == 'none'

    def test_bad_chooser(self, client):
        sid = self._setup_subject(client)
        rv = client.post(f'/api/export/grades/{sid}/share?chooser=bogus')
        assert rv.status_code == 400

    def test_bad_mode(self, client):
        sid = self._setup_subject(client)
        rv = client.post(f'/api/export/grades/{sid}/share?mode=bogus')
        assert rv.status_code == 400

    def test_diag_no_jnius(self, client):
        # без jnius (ПК/CI): аккуратная структура с провалом первого шага
        rv = client.post('/api/export/diag')
        assert rv.status_code == 200
        body = rv.json
        assert body['ok'] is False
        assert body['steps'][0]['name'] == 'jnius import'
        assert body['steps'][0]['ok'] is False
