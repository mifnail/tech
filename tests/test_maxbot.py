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
        raw_body = getattr(req, 'data', None)
        body_data = None
        if raw_body:
            try:
                body_data = json.loads(raw_body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                body_data = raw_body
        record.append((req.get_method(), req.full_url, body_data))
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


# ======================== MULTIPART ENCODE ========================

class TestMultipartEncode:
    def test_shape(self):
        body, ct = maxbot._multipart_encode('data', b'hello world', 'test.txt')
        assert b'test.txt' in body
        assert b'hello world' in body
        assert b'Content-Disposition: form-data; name="data"' in body
        assert 'multipart/form-data' in ct
        assert 'boundary=' in ct

    def test_boundary_matches(self):
        body, ct = maxbot._multipart_encode('data', b'x', 'f.txt')
        boundary = ct.split('boundary=')[1]
        assert boundary.encode() in body


# ======================== UPLOAD FILE ========================

class TestUploadFile:
    def test_two_steps(self):
        rec = []
        fake = _fake_urlopen_factory([
            ('json', {'url': 'https://fu.oneme.ru/upload.do?foo=bar'}),
            ('json', {'token': 'abc123'}),
        ], rec)
        result = maxbot.upload_file('bot_token', b'file content', 'test.pdf', urlopen=fake)
        assert result == 'abc123'
        assert rec[0][0] == 'POST'
        assert '/uploads?type=file' in rec[0][1]
        assert rec[1][0] == 'POST'
        assert 'fu.oneme.ru' in rec[1][1]

    def test_failure_no_url(self):
        rec = []
        fake = _fake_urlopen_factory([('json', {})], rec)
        with pytest.raises(maxbot.MaxError):
            maxbot.upload_file('tok', b'data', 'f.txt', urlopen=fake)

    def test_failure_no_token(self):
        rec = []
        fake = _fake_urlopen_factory([
            ('json', {'url': 'https://fu.oneme.ru/upload.do?x=1'}),
            ('json', {}),
        ], rec)
        with pytest.raises(maxbot.MaxError):
            maxbot.upload_file('tok', b'data', 'f.txt', urlopen=fake)


# ======================== SEND FILE ========================

class TestSendFile:
    def test_json_shape(self):
        rec = []
        fake = _fake_urlopen_factory([('json', {'ok': True})], rec)
        maxbot.send_file('tok', 111, 'file_token_abc', caption='Математика', urlopen=fake)
        assert rec[0][0] == 'POST'
        assert 'chat_id=111' in rec[0][1]
        body = rec[0][2]
        assert body['text'] == 'Математика'
        assert body['attachments'][0]['type'] == 'file'
        assert body['attachments'][0]['payload']['token'] == 'file_token_abc'


# ======================== SEND GRADES WITH BUTTONS ========================

class TestSendGradesWithButtons:
    def test_keyboard_shape(self):
        rec = []
        fake = _fake_urlopen_factory([('json', {'ok': True})], rec)
        maxbot.send_grades_with_buttons('tok', 111, 'Оценки:\n5', urlopen=fake)
        body = rec[0][2]
        assert body['text'] == 'Оценки:\n5'
        kbd = body['attachments'][0]
        assert kbd['type'] == 'inline_keyboard'
        buttons = kbd['payload']['buttons']
        assert len(buttons) == 2
        assert buttons[0][0]['payload'] == '/grades'
        assert buttons[0][1]['payload'] == '/today'
        assert buttons[1][0]['payload'] == '/unbind'


# ======================== ANSWER CALLBACK ========================

class TestAnswerCallback:
    def test_shape(self):
        rec = []
        fake = _fake_urlopen_factory([('json', {'ok': True})], rec)
        maxbot.answer_callback('tok', 'cb_123', 'Готово', urlopen=fake)
        assert rec[0][0] == 'POST'
        assert 'callback_id=cb_123' in rec[0][1]
        body = rec[0][2]
        assert body['notification'] == 'Готово'


# ======================== RUN POLLING — /grades WITH BUTTONS ========================

class TestRunPollingGradesButtons:
    def test_grades_sends_keyboard(self, db):
        gid, sid, st = _seed(db)
        lid = db.add_lesson(sid, '2026-09-01', sid, 'held', 1)
        db.mark_attendance(lid, st, '5')
        db.bind_max(111, st)
        # Prevent db.close() from closing our fixture db
        orig_close = db.close
        db.close = lambda: None
        stop = threading.Event()
        rec = []
        updates_resp = {'updates': [{'type': 'message_created', 'message': {
            'body': {'text': '/grades'},
            'recipient': {'chat_id': 111},
        }}], 'marker': 1}
        responses = iter([
            ('json', updates_resp),     # get_updates
            ('json', {'ok': True}),     # send_grades_with_buttons
        ])
        def fake(req, timeout=None, **kw):
            try:
                kind, payload = next(responses)
            except StopIteration:
                stop.set()
                return FakeResp(json.dumps({'updates': [], 'marker': 99}).encode())
            raw_body = getattr(req, 'data', None)
            body_data = None
            if raw_body:
                try:
                    body_data = json.loads(raw_body)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    body_data = raw_body
            rec.append((req.get_method(), req.full_url, body_data))
            if kind == 'json':
                return FakeResp(json.dumps(payload).encode())
            raise AssertionError
        try:
            t = threading.Thread(target=maxbot.run_polling,
                                 args=('tok', lambda: db, stop, fake))
            t.start()
            t.join(timeout=5)
            assert not t.is_alive()
        finally:
            db.close = orig_close
        # send_grades_with_buttons uses _post → POST to chat_id=111
        send_calls = [r for r in rec
                      if 'chat_id=111' in r[1] and r[0] == 'POST']
        assert len(send_calls) == 1
        body = send_calls[0][2]
        assert body['attachments'][0]['type'] == 'inline_keyboard'


# ======================== RUN POLLING — CALLBACK ========================

class TestRunPollingCallback:
    def test_callback_sends_reply_and_answer(self, db):
        _, _, st = _seed(db)
        db.bind_max(111, st)
        orig_close = db.close
        db.close = lambda: None
        stop = threading.Event()
        rec = []
        cb_update = {'type': 'message_callback', 'callback': {
            'callback_id': 'cb_999',
            'payload': '/help',
            'message': {'recipient': {'chat_id': 111}},
            'user': {'user_id': 111},
        }}
        updates_resp = {'updates': [cb_update], 'marker': 1}
        # get_updates → callback → send_message → answer_callback → get_updates (empty)
        responses = iter([
            ('json', updates_resp),
            ('json', {'ok': True}),   # send_message
            ('json', {'ok': True}),   # answer_callback
        ])
        def fake(req, timeout=None, **kw):
            try:
                kind, payload = next(responses)
            except StopIteration:
                stop.set()
                return FakeResp(json.dumps({'updates': [], 'marker': 99}).encode())
            raw_body = getattr(req, 'data', None)
            body_data = None
            if raw_body:
                try:
                    body_data = json.loads(raw_body)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    body_data = raw_body
            rec.append((req.get_method(), req.full_url, body_data))
            if kind == 'json':
                return FakeResp(json.dumps(payload).encode())
            raise AssertionError
        try:
            t = threading.Thread(target=maxbot.run_polling,
                                 args=('tok', lambda: db, stop, fake))
            t.start()
            t.join(timeout=5)
            assert not t.is_alive()
        finally:
            db.close = orig_close
        # send_message to chat 111
        msg_calls = [r for r in rec
                     if 'chat_id=111' in r[1] and r[0] == 'POST'
                     and 'answers' not in r[1] and 'updates' not in r[1]]
        assert len(msg_calls) == 1
        # answer_callback with callback_id
        ans_calls = [r for r in rec
                     if 'callback_id=cb_999' in r[1]]
        assert len(ans_calls) == 1
        assert ans_calls[0][2]['notification'] == 'Готово'


# ======================== VEDOMOST FLOW ========================

class TestVedomostFlow:
    def test_vedomost_sends_xlsx(self, db, monkeypatch):
        """Test /vedomost sends xlsx files for subjects with grades."""
        gid, sid, st = _seed(db)
        lid = db.add_lesson(sid, '2026-09-01', sid, 'held', 1)
        db.mark_attendance(lid, st, '5')
        db.bind_max(111, st)
        # Fake export_grades_xlsx to avoid openpyxl dependency
        monkeypatch.setattr('report_export.export_grades_xlsx',
                            lambda subj_id, db_=None: b'fake-xlsx-bytes')
        orig_close = db.close
        db.close = lambda: None
        stop = threading.Event()
        rec = []
        updates_resp = {'updates': [{'type': 'message_created', 'message': {
            'body': {'text': '/vedomost'},
            'recipient': {'chat_id': 111},
        }}], 'marker': 1}
        # get_updates → upload1 → upload2 → send_file → get_updates (empty)
        responses = iter([
            ('json', updates_resp),
            ('json', {'url': 'https://fu.oneme.ru/upload.do?x=1'}),
            ('json', {'token': 'file_tok_123'}),
            ('json', {'ok': True}),  # send_file
        ])
        def fake(req, timeout=None, **kw):
            try:
                kind, payload = next(responses)
            except StopIteration:
                stop.set()
                return FakeResp(json.dumps({'updates': [], 'marker': 99}).encode())
            raw_body = getattr(req, 'data', None)
            body_data = None
            if raw_body:
                try:
                    body_data = json.loads(raw_body)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    body_data = raw_body
            rec.append((req.get_method(), req.full_url, body_data))
            if kind == 'json':
                return FakeResp(json.dumps(payload).encode())
            raise AssertionError
        try:
            t = threading.Thread(target=maxbot.run_polling,
                                 args=('tok', lambda: db, stop, fake))
            t.start()
            t.join(timeout=5)
            assert not t.is_alive()
        finally:
            db.close = orig_close
        # upload step 1
        upload_calls = [r for r in rec if 'uploads' in r[1]]
        assert len(upload_calls) == 1
        # upload step 2 (external URL)
        ext_calls = [r for r in rec if 'fu.oneme.ru' in r[1]]
        assert len(ext_calls) == 1
        # send_file to chat 111
        file_calls = [r for r in rec
                      if 'chat_id=111' in r[1] and r[0] == 'POST'
                      and 'uploads' not in r[1] and 'updates' not in r[1]]
        assert len(file_calls) == 1
        body = file_calls[0][2]
        assert body['attachments'][0]['type'] == 'file'
        assert body['attachments'][0]['payload']['token'] == 'file_tok_123'
        assert body['text'] == 'Математика'

    def test_vedomost_no_grades(self, db):
        """Test /vedomost when student has no grades."""
        _, _, st = _seed(db)
        db.bind_max(111, st)
        orig_close = db.close
        db.close = lambda: None
        stop = threading.Event()
        rec = []
        updates_resp = {'updates': [{'type': 'message_created', 'message': {
            'body': {'text': '/vedomost'},
            'recipient': {'chat_id': 111},
        }}], 'marker': 1}
        responses = iter([
            ('json', updates_resp),
            ('json', {'ok': True}),  # send_message "Оценок пока нет."
        ])
        def fake(req, timeout=None, **kw):
            try:
                kind, payload = next(responses)
            except StopIteration:
                stop.set()
                return FakeResp(json.dumps({'updates': [], 'marker': 99}).encode())
            raw_body = getattr(req, 'data', None)
            body_data = None
            if raw_body:
                try:
                    body_data = json.loads(raw_body)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    body_data = raw_body
            rec.append((req.get_method(), req.full_url, body_data))
            if kind == 'json':
                return FakeResp(json.dumps(payload).encode())
            raise AssertionError
        try:
            t = threading.Thread(target=maxbot.run_polling,
                                 args=('tok', lambda: db, stop, fake))
            t.start()
            t.join(timeout=5)
            assert not t.is_alive()
        finally:
            db.close = orig_close
        # send_message with "Оценок пока нет."
        msg_calls = [r for r in rec
                     if 'chat_id=111' in r[1] and r[0] == 'POST'
                     and 'uploads' not in r[1] and 'updates' not in r[1]]
        assert len(msg_calls) == 1
        body = msg_calls[0][2]
        assert 'Оценок пока нет' in body['text']

    def test_vedomost_unbound(self, db):
        """Test /vedomost when student is not bound."""
        _seed(db)
        orig_close = db.close
        db.close = lambda: None
        stop = threading.Event()
        rec = []
        updates_resp = {'updates': [{'type': 'message_created', 'message': {
            'body': {'text': '/vedomost'},
            'recipient': {'chat_id': 111},
        }}], 'marker': 1}
        responses = iter([
            ('json', updates_resp),
            ('json', {'ok': True}),  # send_message "Сначала привяжись"
        ])
        def fake(req, timeout=None, **kw):
            try:
                kind, payload = next(responses)
            except StopIteration:
                stop.set()
                return FakeResp(json.dumps({'updates': [], 'marker': 99}).encode())
            raw_body = getattr(req, 'data', None)
            body_data = None
            if raw_body:
                try:
                    body_data = json.loads(raw_body)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    body_data = raw_body
            rec.append((req.get_method(), req.full_url, body_data))
            if kind == 'json':
                return FakeResp(json.dumps(payload).encode())
            raise AssertionError
        try:
            t = threading.Thread(target=maxbot.run_polling,
                                 args=('tok', lambda: db, stop, fake))
            t.start()
            t.join(timeout=5)
            assert not t.is_alive()
        finally:
            db.close = orig_close
        msg_calls = [r for r in rec
                     if 'chat_id=111' in r[1] and r[0] == 'POST'
                     and 'updates' not in r[1]]
        assert len(msg_calls) == 1
        body = msg_calls[0][2]
        assert 'привяжись' in body['text']

    def test_process_text_vedomost_sentinel(self, db):
        """Test process_text returns VEDOMOST: sentinel for bound user."""
        _, _, st = _seed(db)
        db.bind_max(111, st)
        r = process_text('/vedomost', 111, db)
        assert r == 'VEDOMOST:'

    def test_process_text_vedomost_unbound(self, db):
        """Test /vedomost for unbound user returns bind prompt."""
        _seed(db)
        r = process_text('/vedomost', 111, db)
        assert 'привяжись' in r.lower()

    def test_vedomost_callback(self, db, monkeypatch):
        """/vedomost via callback also sends files."""
        gid, sid, st = _seed(db)
        lid = db.add_lesson(sid, '2026-09-01', sid, 'held', 1)
        db.mark_attendance(lid, st, '5')
        db.bind_max(111, st)
        monkeypatch.setattr('report_export.export_grades_xlsx',
                            lambda subj_id, db_=None: b'fake-xlsx-bytes')
        orig_close = db.close
        db.close = lambda: None
        stop = threading.Event()
        rec = []
        cb_update = {'type': 'message_callback', 'callback': {
            'callback_id': 'cb_v1',
            'payload': '/vedomost',
            'message': {'recipient': {'chat_id': 111}},
            'user': {'user_id': 111},
        }}
        updates_resp = {'updates': [cb_update], 'marker': 1}
        responses = iter([
            ('json', updates_resp),
            ('json', {'url': 'https://fu.oneme.ru/upload.do?x=1'}),
            ('json', {'token': 'ftok_v1'}),
            ('json', {'ok': True}),  # send_file
            ('json', {'ok': True}),  # answer_callback
        ])
        def fake(req, timeout=None, **kw):
            try:
                kind, payload = next(responses)
            except StopIteration:
                stop.set()
                return FakeResp(json.dumps({'updates': [], 'marker': 99}).encode())
            raw_body = getattr(req, 'data', None)
            body_data = None
            if raw_body:
                try:
                    body_data = json.loads(raw_body)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    body_data = raw_body
            rec.append((req.get_method(), req.full_url, body_data))
            if kind == 'json':
                return FakeResp(json.dumps(payload).encode())
            raise AssertionError
        try:
            t = threading.Thread(target=maxbot.run_polling,
                                 args=('tok', lambda: db, stop, fake))
            t.start()
            t.join(timeout=5)
            assert not t.is_alive()
        finally:
            db.close = orig_close
        ext_calls = [r for r in rec if 'fu.oneme.ru' in r[1]]
        assert len(ext_calls) == 1
        ans_calls = [r for r in rec if 'callback_id=cb_v1' in r[1]]
        assert len(ans_calls) == 1
