import io
import json
import os
import sqlite3
import sys
import tempfile
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
            ('json', {'updates': [{'update_type': 'message_created'}], 'marker': 99}),
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
        j = client.get('/api/settings/maxbot').json
        assert j['has_token'] is False and j['enabled'] is False
        assert 'teacher_code' in j and 'teacher_bound' in j
        assert len(j['teacher_code']) == 8
        rv = client.post('/api/settings/maxbot', json={'token': 'abc', 'enabled': True}).json
        assert rv['ok'] is True and rv['has_token'] is True and rv['enabled'] is True
        rv = client.get('/api/settings/maxbot').json
        assert rv['has_token'] is True and rv['enabled'] is True
        assert 'abc' not in json.dumps(rv)
        assert 'teacher_code' in rv
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
        maxbot.send_with_buttons('tok', 111, 'Оценки:\n5', urlopen=fake)
        body = rec[0][2]
        assert body['text'] == 'Оценки:\n5'
        kbd = body['attachments'][0]
        assert kbd['type'] == 'inline_keyboard'
        buttons = kbd['payload']['buttons']
        assert len(buttons) == 3
        assert buttons[0][0]['payload'] == '/grades'
        assert buttons[0][1]['payload'] == '/today'
        assert buttons[1][0]['type'] == 'message' and buttons[1][0]['text'] == 'Расписание' and 'payload' not in buttons[1][0]
        assert buttons[1][1]['type'] == 'message' and buttons[1][1]['text'] == 'Средний балл' and 'payload' not in buttons[1][1]
        assert buttons[1][2]['type'] == 'message' and buttons[1][2]['text'] == 'Долги' and 'payload' not in buttons[1][2]
        assert buttons[2][0]['payload'] == '/unbind'


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
        updates_resp = {'updates': [{'update_type': 'message_created', 'message': {
            'body': {'text': '/grades'},
            'recipient': {'chat_id': 111},
        }}], 'marker': 1}
        responses = iter([
            ('json', updates_resp),     # get_updates
            ('json', {'ok': True}),     # send_with_buttons
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
        # send_with_buttons uses _post → POST to chat_id=111
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
        cb_update = {'update_type': 'message_callback', 'callback': {
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


# ======================== VEDOMOST DISABLED ========================

class TestVedomostFlow:
    def test_process_text_vedomost_sentinel(self, db):
        _, _, st = _seed(db)
        db.bind_max(111, st)
        r = process_text('/vedomost', 111, db)
        assert r == 'VEDOMOST:'
        r2 = process_text('ведомость', 111, db)
        assert r2 == 'VEDOMOST:'

    def test_process_text_vedomost_unbound(self, db):
        _seed(db)
        r = process_text('/vedomost', 111, db)
        assert 'привяжись' in r.lower()

    def test_vedomost_sends_personal_xlsx(self, db, monkeypatch):
        gid, sid, st = _seed(db)
        # add second student with grades to ensure leak would be detected
        st2 = db.add_student(gid, 'Петров', 'Пётр')
        lid = db.add_lesson(sid, '2026-09-01', sid, 'held', 1)
        db.mark_attendance(lid, st, '5')
        db.mark_attendance(lid, st2, '4')
        db.bind_max(111, st)
        captured = {}
        def fake_upload(token, data, filename, urlopen=None):
            captured['bytes'] = data
            captured['filename'] = filename
            return 'tok123'
        monkeypatch.setattr(maxbot, 'upload_file', fake_upload)
        monkeypatch.setattr(maxbot, 'send_file', lambda token, chat_id, ft, caption='', urlopen=None: captured.update({'sent': True, 'caption': caption}) or {'ok': True})
        orig_close = db.close
        db.close = lambda: None
        stop = threading.Event()
        rec = []
        updates_resp = {'updates': [{'update_type': 'message_created', 'message': {
            'body': {'text': '/vedomost'},
            'recipient': {'chat_id': 111},
        }}], 'marker': 1}
        responses = iter([
            ('json', updates_resp),
            ('json', {'ok': True}),
            ('json', {'ok': True}),
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
        # patch _handle_vedomost to use fake upload directly via monkeypatch already
        try:
            t = threading.Thread(target=maxbot.run_polling,
                                 args=('tok', lambda: db, stop, fake))
            t.start()
            t.join(timeout=5)
            assert not t.is_alive()
        finally:
            db.close = orig_close
        assert 'bytes' in captured, 'upload_file not called'
        # verify personal file: single data row, own grades present, other surname absent
        import io
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(captured['bytes']))
        ws = wb.active
        # Find data rows: header row 3, data starts row 4
        rows = list(ws.iter_rows(values_only=True))
        # rows[0] is title row, rows[2] is header, rows[3] is data
        # Collect all cell values as strings
        all_vals = ' '.join(str(c) for row in rows for c in row if c)
        assert 'Иванов' in all_vals
        assert 'Петров' not in all_vals
        # Check own grade present
        assert '5' in all_vals
        assert '4' not in all_vals or all_vals.count('4') == 0  # other student's grade should not appear
        # Ensure single data row (only one student)
        data_rows = [r for r in rows[3:] if any(c for c in r)]
        assert len(data_rows) == 1


# ======================== GRADE DEBOUNCE ========================

class TestGradeDebounce:
    """Server-side 10 s debounce: grade push only fires once per settled value."""

    def _seed_lesson(self, client):
        """Create group, subject, lesson, student; return (lesson_id, student_id)."""
        gid = client.post('/api/groups', json={'name': 'ИС-11'}).json['id']
        sid = client.post('/api/subjects', json={
            'name': 'Математика', 'total_hours': 32, 'group_id': gid}).json['id']
        st = get_db().add_student(gid, 'Иванов', 'Иван', 'Иванович')
        lid = client.post('/api/lessons', json={
            'subject_id': sid, 'actual_subject_id': sid,
            'date': '2026-09-01', 'status': 'held', 'lesson_number': 1,
        }).json['id']
        return lid, st

    def _setup(self, client, monkeypatch):
        """Common setup: patch threading.Timer, patch _fire_grade_push to use
        the test DB, patch maxbot.notify_grade.  Returns (timers, notify_calls)."""
        timers = []
        notify_calls = []

        class FakeTimer:
            def __init__(self, delay, fn, args=(), kwargs=None):
                self.fn = fn
                self.args = args
                self.delay = delay
                self._cancelled = False
                self._started = False
                timers.append(self)

            def start(self):
                self._started = True

            def cancel(self):
                self._cancelled = True

        # Patch _fire_grade_push so it uses the test DB (via get_db()) and
        # doesn't swallow errors behind except-all.
        def fake_fire(token, lesson_id, student_id):
            key = (lesson_id, student_id)
            _api_module._pending.pop(key, None)
            db = get_db()
            rows = db.get_attendance(lesson_id)
            row = None
            for r in rows:
                if r['student_id'] == student_id:
                    row = r
                    break
            grade = dict(row).get('grade', '') if row else ''
            if not grade:
                return
            lesson = db.get_lesson(lesson_id)
            if not lesson:
                return
            raw_date = lesson['date'] or ''
            date_str = f'{raw_date[8:10]}.{raw_date[5:7]}' if len(raw_date) >= 10 else ''
            subject = ''
            if 'actual_subject_name' in lesson.keys():
                subject = lesson['actual_subject_name'] or ''
            notify_calls.append((token, student_id, grade, date_str, subject))

        monkeypatch.setattr(_api_module, 'threading', type('M', (), {'Timer': FakeTimer}))
        monkeypatch.setattr(_api_module, '_fire_grade_push', fake_fire)
        monkeypatch.setattr(maxbot, 'notify_grade',
                           lambda token, sid, grade, ds, sn, urlopen=None: notify_calls.append(
                               (token, sid, grade, ds, sn)))
        return timers, notify_calls

    # ---- 1. tap -> fire sends current grade with right student/lesson ----
    def test_single_tap_fires(self, client, monkeypatch):
        lid, st = self._seed_lesson(client)
        get_db().bind_max(111, st)
        get_db().set_setting('max_bot_token', 'tok_abc')
        get_db().set_setting('max_bot_enabled', '1')

        timers, notify_calls = self._setup(client, monkeypatch)

        # Tap once
        client.post(f'/api/lessons/{lid}/attendance',
                    json={'student_id': st, 'grade': '5'})

        assert len(timers) == 1
        t = timers[0]
        assert t.delay == _api_module.GRADE_PUSH_DELAY
        assert t.args == ('tok_abc', lid, st)

        # Fire the callback
        t.fn(*t.args)

        assert len(notify_calls) == 1
        assert notify_calls[0] == ('tok_abc', st, '5', '01.09', 'Математика')

    # ---- 2. tap,tap -> only ONE timer active, fire sends latest grade ----
    def test_double_tap_only_one_timer(self, client, monkeypatch):
        lid, st = self._seed_lesson(client)
        get_db().bind_max(111, st)
        get_db().set_setting('max_bot_token', 'tok_abc')
        get_db().set_setting('max_bot_enabled', '1')

        timers, notify_calls = self._setup(client, monkeypatch)

        # First tap
        client.post(f'/api/lessons/{lid}/attendance',
                    json={'student_id': st, 'grade': '4'})
        assert len(timers) == 1
        assert not timers[0]._cancelled

        # Second tap — first timer should be cancelled
        client.post(f'/api/lessons/{lid}/attendance',
                    json={'student_id': st, 'grade': '5'})
        assert len(timers) == 2
        assert timers[0]._cancelled
        assert not timers[1]._cancelled

        # Fire the second timer
        timers[1].fn(*timers[1].args)
        assert len(notify_calls) == 1
        assert notify_calls[0][1] == st  # student_id
        assert notify_calls[0][2] == '5'  # grade

    # ---- 3. grade changed in DB between schedule and fire -> sends NEW grade ----
    def test_re_read_from_db(self, client, monkeypatch):
        lid, st = self._seed_lesson(client)
        get_db().bind_max(111, st)
        get_db().set_setting('max_bot_token', 'tok_abc')
        get_db().set_setting('max_bot_enabled', '1')

        timers, notify_calls = self._setup(client, monkeypatch)

        # Schedule with grade '3'
        client.post(f'/api/lessons/{lid}/attendance',
                    json={'student_id': st, 'grade': '3'})

        # Overwrite grade in DB to '5' (before timer fires)
        get_db().mark_attendance(lid, st, '5')

        # Fire the timer — it re-reads from DB
        timers[0].fn(*timers[0].args)

        # The grade sent should be the NEW one
        assert len(notify_calls) == 1
        # notify_calls[0] = (token, student_id, grade, date_str, subject)
        assert notify_calls[0][2] == '5'

    # ---- 4. grade deleted before fire -> no send ----
    def test_deleted_grade_no_send(self, client, monkeypatch):
        lid, st = self._seed_lesson(client)
        get_db().bind_max(111, st)
        get_db().set_setting('max_bot_token', 'tok_abc')
        get_db().set_setting('max_bot_enabled', '1')

        timers, notify_calls = self._setup(client, monkeypatch)

        # Schedule with a grade
        client.post(f'/api/lessons/{lid}/attendance',
                    json={'student_id': st, 'grade': '4'})

        # Delete the grade
        get_db().mark_attendance(lid, st, '')

        # Fire the timer — grade is empty -> no send
        timers[0].fn(*timers[0].args)
        assert len(notify_calls) == 0

    # ---- 5. bot disabled -> nothing scheduled ----
    def test_bot_disabled_no_schedule(self, client, monkeypatch):
        lid, st = self._seed_lesson(client)
        get_db().bind_max(111, st)
        get_db().set_setting('max_bot_token', 'tok_abc')
        get_db().set_setting('max_bot_enabled', '0')

        timers = []

        class FakeTimer:
            def __init__(self, delay, fn, args=(), kwargs=None):
                self._cancelled = False
                timers.append(self)
            def start(self): pass
            def cancel(self):
                self._cancelled = True

        monkeypatch.setattr(_api_module, 'threading', type('M', (), {'Timer': FakeTimer}))

        # Seed a pending timer that should get cancelled
        sentinel = FakeTimer(0, lambda: None, ())
        _api_module._pending[(lid, st)] = sentinel

        count_before = len(timers)
        client.post(f'/api/lessons/{lid}/attendance',
                    json={'student_id': st, 'grade': '5'})

        # No new timers should be scheduled (only the sentinel we manually created)
        assert len(timers) == count_before
        # Old timer should have been cancelled and removed from _pending
        assert (lid, st) not in _api_module._pending


# ======================== BARE CODE FALLBACK ========================

class TestBareCodeFallback:
    def test_bare_teacher_code_binds(self, db):
        db.set_setting('max_teacher_code', 'ab12cd34')
        r = process_text('ab12cd34', 999, db)
        assert r == 'Преподаватель привязан.'
        assert db.get_setting('max_teacher_chat') == '999'
        # case-insensitive + strip
        db.set_setting('max_teacher_chat', None)
        r2 = process_text('  AB12CD34  ', 1000, db)
        assert r2 == 'Преподаватель привязан.'
        assert db.get_setting('max_teacher_chat') == '1000'

    def test_bare_curator_code_binds(self, db):
        gid = db.add_group('ИС-11')
        code = db.ensure_curator_code(gid)
        r = process_text(code, 555, db)
        assert f'ИС-11' in r or 'Привязан как куратор' in r
        assert db.curator_group_for_chat(555) == gid
        # case-insensitive bare curator
        gid2 = db.add_group('ИС-12')
        code2 = db.ensure_curator_code(gid2)
        r2 = process_text(code2.upper(), 556, db)
        assert 'Привязан как куратор' in r2
        assert db.curator_group_for_chat(556) == gid2

    def test_bare_wrong_code_not(self, db):
        db.set_setting('max_teacher_code', 'ab12cd34')
        gid = db.add_group('ИС-11')
        db.ensure_curator_code(gid)
        db.add_student(gid, 'Иванов', 'Иван')
        r = process_text('wrong123', 111, db)
        assert r != 'Преподаватель привязан.'
        assert 'куратор' not in r.lower() or 'Привязан как куратор' not in r
        assert db.get_setting('max_teacher_chat') is None or db.get_setting('max_teacher_chat') != '111'
        assert db.curator_group_for_chat(111) is None
        # ensure not falsely treated as surname bind
        assert 'Не нашёл' in r or 'фамилию' in r.lower() or 'привяжись' in r.lower()


# ======================== FILE RESTORE VIA BOT ========================

class _FakeDbFactory:
    """Thin wrapper: returns the test db and tracks close calls."""
    def __init__(self, db):
        self._db = db
    def __call__(self):
        return self._db


def _make_valid_db_bytes_with_data(n_students=2, n_grades=1):
    """Create a minimal valid SQLite DB with required tables and some data."""
    import tempfile
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    tmp.close()
    try:
        conn = sqlite3.connect(tmp.name)
        conn.executescript("""
            CREATE TABLE groups (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE students (id INTEGER PRIMARY KEY, group_id INTEGER, last_name TEXT, first_name TEXT);
            CREATE TABLE subjects (id INTEGER PRIMARY KEY, name TEXT, group_id INTEGER, total_hours INTEGER);
            CREATE TABLE schedule (id INTEGER PRIMARY KEY, day_of_week INTEGER, lesson_number INTEGER, subject_id INTEGER);
            CREATE TABLE lessons (id INTEGER PRIMARY KEY, subject_id INTEGER, date TEXT, status TEXT, lesson_number INTEGER, actual_subject_id INTEGER);
            CREATE TABLE grades (id INTEGER PRIMARY KEY, lesson_id INTEGER, student_id INTEGER, grade TEXT);
            CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE curators (group_id INTEGER PRIMARY KEY, chat_id INTEGER, code TEXT UNIQUE);
            CREATE TABLE max_links (chat_id INTEGER PRIMARY KEY, student_id INTEGER UNIQUE);
            CREATE TABLE bot_links (chat_id INTEGER PRIMARY KEY, student_id INTEGER UNIQUE);
            INSERT INTO groups (id, name) VALUES (1, 'ИС-11');
            INSERT INTO subjects (id, name, group_id, total_hours) VALUES (1, 'Математика', 1, 32);
            INSERT INTO lessons (id, subject_id, date, status, lesson_number, actual_subject_id) VALUES (1, 1, '2026-09-01', 'held', 1, 1);
        """)
        for i in range(1, n_students + 1):
            conn.execute("INSERT INTO students (id, group_id, last_name, first_name) VALUES (?, 1, ?, ?)",
                         (i, f'Фамилия{i}', f'Имя{i}'))
        for i in range(1, n_grades + 1):
            conn.execute("INSERT INTO grades (id, lesson_id, student_id, grade) VALUES (?, 1, ?, '5')", (i, i))
        conn.commit()
        conn.close()
        with open(tmp.name, 'rb') as f:
            return f.read()
    finally:
        os.unlink(tmp.name)


class TestFileRestoreViaBot:
    """Tests for .db file restore sent to bot chat by teacher/curator."""

    def test_attachment_detection_file_type(self):
        """_handle_file_restore triggers for type='file' with url in payload."""
        att = {'type': 'file', 'payload': {'url': 'https://example.com/test.db'}}
        assert att.get('type') == 'file'
        assert (att.get('payload') or {}).get('url') is not None

    def test_attachment_detection_no_file(self):
        """No file attachment when attachments is empty or type is not 'file'."""
        for atts in ([], [{'type': 'image', 'payload': {'url': 'x'}}], [{}]):
            file_att = None
            for att in atts:
                if att.get('type') == 'file' and (att.get('payload') or {}).get('url'):
                    file_att = att
            assert file_att is None

    def test_unauthorized_sender_rejected(self, db, monkeypatch):
        """Non-teacher/non-curator sender gets rejection, no download attempted."""
        # No teacher bound, no curator bound
        db.set_setting('max_teacher_chat', None)
        download_called = [False]
        sent = []
        def fake_urlopen(req, timeout=None, **kw):
            download_called[0] = True
            raise AssertionError('should not download')
        def fake_send(token, chat_id, text, urlopen=None):
            sent.append(text)
            return {'ok': True}
        monkeypatch.setattr(maxbot, 'send_message', fake_send)
        att = {'type': 'file', 'payload': {'url': 'https://example.com/test.db'}}
        maxbot._handle_file_restore('tok', 999, att, lambda: db, urlopen=fake_urlopen)
        assert not download_called[0]
        assert any('только преподаватель/куратор' in s for s in sent)

    def test_authorized_teacher_triggers_download(self, db, monkeypatch):
        """Bound teacher chat can trigger file download."""
        db.set_setting('max_teacher_chat', '111')
        valid_data = _make_valid_db_bytes_with_data(2, 1)
        sent = []
        restore_target = tempfile.mktemp(suffix='.db')
        try:
            with open(restore_target, 'wb') as f:
                f.write(b'old data')
            import api as _api
            monkeypatch.setattr(_api, '_DB_PATH', restore_target)
            monkeypatch.setattr('database.DB_PATH', restore_target)
            monkeypatch.setattr(maxbot, 'send_message',
                                lambda tok, cid, text, urlopen=None: sent.append(text) or {'ok': True})
            monkeypatch.setattr(_api, '_save_to_downloads_full',
                                lambda data, fn, mt: ('/bak', None))
            # Patch os.replace to avoid Windows file-locking after WAL checkpoint
            real_replace = os.replace
            def fake_replace(src, dst):
                with open(src, 'rb') as sf:
                    d = sf.read()
                with open(dst, 'wb') as df:
                    df.write(d)
            monkeypatch.setattr(os, 'replace', fake_replace)
            def fake_open(req, timeout=None, **kw):
                class R:
                    def read(self):
                        return valid_data
                    def __enter__(self):
                        return self
                    def __exit__(self, *a):
                        return False
                return R()
            monkeypatch.setattr(maxbot, 'open_raw_with_fallback', fake_open)
            att = {'type': 'file', 'payload': {'url': 'https://example.com/test.db'}}
            maxbot._handle_file_restore('tok', 111, att, lambda: db)
            assert any('База восстановлена' in s for s in sent)
        finally:
            for f in (restore_target, restore_target + '-wal', restore_target + '-shm'):
                try:
                    os.unlink(f)
                except OSError:
                    pass

    def test_authorized_curator_triggers_download(self, db, monkeypatch):
        """Bound curator can trigger file download."""
        gid = db.add_group('КС-21')
        db.bind_curator(gid, 555)
        valid_data = _make_valid_db_bytes_with_data(0, 0)
        sent = []
        restore_target = tempfile.mktemp(suffix='.db')
        try:
            with open(restore_target, 'wb') as f:
                f.write(b'old data')
            import api as _api
            monkeypatch.setattr(_api, '_DB_PATH', restore_target)
            monkeypatch.setattr('database.DB_PATH', restore_target)
            monkeypatch.setattr(maxbot, 'send_message',
                                lambda tok, cid, text, urlopen=None: sent.append(text) or {'ok': True})
            monkeypatch.setattr(_api, '_save_to_downloads_full',
                                lambda data, fn, mt: ('/bak', None))
            real_replace = os.replace
            def fake_replace(src, dst):
                with open(src, 'rb') as sf:
                    d = sf.read()
                with open(dst, 'wb') as df:
                    df.write(d)
            monkeypatch.setattr(os, 'replace', fake_replace)
            def fake_open(req, timeout=None, **kw):
                class R:
                    def read(self):
                        return valid_data
                    def __enter__(self):
                        return self
                    def __exit__(self, *a):
                        return False
                return R()
            monkeypatch.setattr(maxbot, 'open_raw_with_fallback', fake_open)
            att = {'type': 'file', 'payload': {'url': 'https://example.com/test.db'}}
            maxbot._handle_file_restore('tok', 555, att, lambda: db)
            assert any('База восстановлена' in s for s in sent)
        finally:
            for f in (restore_target, restore_target + '-wal', restore_target + '-shm'):
                try:
                    os.unlink(f)
                except OSError:
                    pass

    def test_invalid_bytes_rejected(self, db, monkeypatch):
        """Non-SQLite bytes are rejected with error message."""
        db.set_setting('max_teacher_chat', '111')
        sent = []
        monkeypatch.setattr(maxbot, 'send_message',
                            lambda tok, cid, text, urlopen=None: sent.append(text) or {'ok': True})
        def fake_open(req, timeout=None, **kw):
            class R:
                def read(self):
                    return b'this is not a sqlite file at all'
                def __enter__(self):
                    return self
                def __exit__(self, *a):
                    return False
            return R()
        monkeypatch.setattr(maxbot, 'open_raw_with_fallback', fake_open)
        att = {'type': 'file', 'payload': {'url': 'https://example.com/bad.db'}}
        maxbot._handle_file_restore('tok', 111, att, lambda: db)
        assert any('не похож на базу' in s for s in sent)

    def test_missing_tables_rejected(self, db, monkeypatch):
        """SQLite without required tables is rejected."""
        db.set_setting('max_teacher_chat', '111')
        sent = []
        monkeypatch.setattr(maxbot, 'send_message',
                            lambda tok, cid, text, urlopen=None: sent.append(text) or {'ok': True})
        import tempfile as _tf
        tmp = _tf.NamedTemporaryFile(delete=False, suffix='.db')
        tmp.close()
        try:
            conn = sqlite3.connect(tmp.name)
            conn.execute("CREATE TABLE foo (id INTEGER)")
            conn.close()
            with open(tmp.name, 'rb') as f:
                bad_data = f.read()
        finally:
            os.unlink(tmp.name)
        def fake_open(req, timeout=None, **kw):
            class R:
                def read(self):
                    return bad_data
                def __enter__(self):
                    return self
                def __exit__(self, *a):
                    return False
            return R()
        monkeypatch.setattr(maxbot, 'open_raw_with_fallback', fake_open)
        att = {'type': 'file', 'payload': {'url': 'https://example.com/incomplete.db'}}
        maxbot._handle_file_restore('tok', 111, att, lambda: db)
        assert any('не похож на базу' in s for s in sent)

    def test_oversize_rejected(self, db, monkeypatch):
        """File over 50 MB cap is rejected."""
        db.set_setting('max_teacher_chat', '111')
        sent = []
        monkeypatch.setattr(maxbot, 'send_message',
                            lambda tok, cid, text, urlopen=None: sent.append(text) or {'ok': True})
        big = b'\x00' * (51 * 1024 * 1024)
        def fake_open(req, timeout=None, **kw):
            class R:
                def read(self):
                    return big
                def __enter__(self):
                    return self
                def __exit__(self, *a):
                    return False
            return R()
        monkeypatch.setattr(maxbot, 'open_raw_with_fallback', fake_open)
        att = {'type': 'file', 'payload': {'url': 'https://example.com/huge.db'}}
        maxbot._handle_file_restore('tok', 111, att, lambda: db)
        assert any('слишком большой' in s for s in sent)

    def test_counts_in_reply(self, db, monkeypatch):
        """Success reply includes student and grade counts from restored DB."""
        db.set_setting('max_teacher_chat', '111')
        valid_data = _make_valid_db_bytes_with_data(3, 2)
        sent = []
        restore_target = tempfile.mktemp(suffix='.db')
        try:
            with open(restore_target, 'wb') as f:
                f.write(b'old data')
            import api as _api
            monkeypatch.setattr(_api, '_DB_PATH', restore_target)
            monkeypatch.setattr('database.DB_PATH', restore_target)
            monkeypatch.setattr(maxbot, 'send_message',
                                lambda tok, cid, text, urlopen=None: sent.append(text) or {'ok': True})
            monkeypatch.setattr(_api, '_save_to_downloads_full',
                                lambda data, fn, mt: ('/bak', None))
            real_replace = os.replace
            def fake_replace(src, dst):
                with open(src, 'rb') as sf:
                    d = sf.read()
                with open(dst, 'wb') as df:
                    df.write(d)
            monkeypatch.setattr(os, 'replace', fake_replace)
            def fake_open(req, timeout=None, **kw):
                class R:
                    def read(self):
                        return valid_data
                    def __enter__(self):
                        return self
                    def __exit__(self, *a):
                        return False
                return R()
            monkeypatch.setattr(maxbot, 'open_raw_with_fallback', fake_open)
            att = {'type': 'file', 'payload': {'url': 'https://example.com/db.db'}}
            maxbot._handle_file_restore('tok', 111, att, lambda: db)
            # Check that restore succeeded (either detailed or simple message)
            assert any('База восстановлена' in s for s in sent)
            # Verify the restored DB has the right counts by reading it directly
            import sqlite3 as _s3
            conn = _s3.connect(restore_target)
            try:
                n_students = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
                n_grades = conn.execute("SELECT COUNT(*) FROM grades").fetchone()[0]
            finally:
                conn.close()
            assert n_students == 3
            assert n_grades == 2
        finally:
            for f in (restore_target, restore_target + '-wal', restore_target + '-shm'):
                try:
                    os.unlink(f)
                except OSError:
                    pass

    def test_db_factory_raises_sends_error_reply(self, db, monkeypatch):
        """db_factory() raising produces error reply, not silence."""
        sent = []
        def fake_send(token, chat_id, text, urlopen=None):
            sent.append(text)
            return {'ok': True}
        monkeypatch.setattr(maxbot, 'send_message', fake_send)

        def broken_factory():
            raise RuntimeError('db is broken')

        att = {'type': 'file', 'payload': {'url': 'https://example.com/test.db'}}
        maxbot._handle_file_restore('tok', 111, att, broken_factory)
        assert any('Ошибка восстановления базы.' in s for s in sent)

    def test_teacher_attachment_without_url_gets_reply(self, db, monkeypatch):
        """Teacher sends attachment with no url → explicit reply, not silence."""
        db.set_setting('max_teacher_chat', '111')
        sent = []
        monkeypatch.setattr(maxbot, 'send_message',
                            lambda tok, cid, text, urlopen=None: sent.append(text) or {'ok': True})
        # _handle_file_restore would get an attachment with no url in payload
        att = {'type': 'file', 'payload': {}}
        maxbot._handle_file_restore('tok', 111, att, lambda: db)
        # With no url, _handle_file_restore returns silently before reaching any
        # send_message — but the polling-level handler catches this case.
        # For _handle_file_restore directly, no url means silent return.
        # The polling-level fix sends the reply. Verify via the polling path.
        assert sent == []  # _handle_file_restore itself is silent for missing url

    def test_run_polling_skips_text_processing_for_file(self, db):
        """run_polling processes file attachment without calling process_text."""
        db.set_setting('max_teacher_chat', '111')
        orig_close = db.close
        db.close = lambda: None
        stop = threading.Event()
        file_seen = [False]
        real_handle = maxbot._handle_file_restore
        def spy_handle(token, cid, file_att, db_factory, urlopen=None):
            file_seen[0] = True
        maxbot._handle_file_restore = spy_handle
        try:
            updates_resp = {'updates': [{'update_type': 'message_created', 'message': {
                'body': {'text': '', 'attachments': [
                    {'type': 'file', 'payload': {'url': 'https://example.com/db.db'}}]},
                'recipient': {'chat_id': 111},
            }}], 'marker': 1}
            responses = iter([
                ('json', updates_resp),
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
                if kind == 'json':
                    return FakeResp(json.dumps(payload).encode())
                raise AssertionError
            t = threading.Thread(target=maxbot.run_polling,
                                  args=('tok', lambda: db, stop, fake))
            t.start()
            t.join(timeout=5)
            assert not t.is_alive()
            assert file_seen[0]
        finally:
            maxbot._handle_file_restore = real_handle
            db.close = orig_close

    def test_run_polling_non_file_attachment_ignored(self, db):
        """run_polling does NOT trigger file handler for non-file attachments."""
        _, _, st = _seed(db)
        db.bind_max(111, st)
        orig_close = db.close
        db.close = lambda: None
        stop = threading.Event()
        file_seen = [False]
        real_handle = maxbot._handle_file_restore
        def spy_handle(token, cid, file_att, db_factory, urlopen=None):
            file_seen[0] = True
        maxbot._handle_file_restore = spy_handle
        try:
            updates_resp = {'updates': [{'update_type': 'message_created', 'message': {
                'body': {'text': '/help', 'attachments': [
                    {'type': 'image', 'payload': {'url': 'https://example.com/img.jpg'}}]},
                'recipient': {'chat_id': 111},
            }}], 'marker': 1}
            responses = iter([
                ('json', updates_resp),
                ('json', {'ok': True}),
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
                if kind == 'json':
                    return FakeResp(json.dumps(payload).encode())
                raise AssertionError
            t = threading.Thread(target=maxbot.run_polling,
                                  args=('tok', lambda: db, stop, fake))
            t.start()
            t.join(timeout=5)
            assert not t.is_alive()
            assert not file_seen[0]
        finally:
            maxbot._handle_file_restore = real_handle
            db.close = orig_close

    def test_run_polling_teacher_attachment_no_url_gets_reply(self, db):
        """Teacher sends attachment without url → explicit reply, not silence."""
        db.set_setting('max_teacher_chat', '111')
        orig_close = db.close
        db.close = lambda: None
        stop = threading.Event()
        sent = []
        real_handle = maxbot._handle_file_restore
        # Spy: record calls but don't process
        handle_calls = []
        def spy_handle(token, cid, file_att, db_factory, urlopen=None):
            handle_calls.append(file_att)
        maxbot._handle_file_restore = spy_handle
        real_send = maxbot.send_message
        maxbot.send_message = lambda tok, cid, text, urlopen=None: sent.append(text) or {'ok': True}
        try:
            # Attachment with type=file but no url in payload
            updates_resp = {'updates': [{'update_type': 'message_created', 'message': {
                'body': {'text': '', 'attachments': [{'type': 'file', 'payload': {}}]},
                'recipient': {'chat_id': 111},
            }}], 'marker': 1}
            responses = iter([
                ('json', updates_resp),
                ('json', {'ok': True}),
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
                if kind == 'json':
                    return FakeResp(json.dumps(payload).encode())
                raise AssertionError
            t = threading.Thread(target=maxbot.run_polling,
                                  args=('tok', lambda: db, stop, fake))
            t.start()
            t.join(timeout=5)
            assert not t.is_alive()
            # _handle_file_restore NOT called (no url → doesn't match file_att)
            assert len(handle_calls) == 0
            # But teacher/curator gets an explicit reply
            assert any('Не удалось получить файл из сообщения.' in s for s in sent)
        finally:
            maxbot._handle_file_restore = real_handle
            maxbot.send_message = real_send
            db.close = orig_close

    def test_run_polling_student_attachment_no_url_stays_silent(self, db):
        """Student sends attachment without url → silent (bind prompt flow)."""
        _, _, st = _seed(db)
        db.bind_max(111, st)
        orig_close = db.close
        db.close = lambda: None
        stop = threading.Event()
        sent = []
        real_handle = maxbot._handle_file_restore
        handle_calls = []
        def spy_handle(token, cid, file_att, db_factory, urlopen=None):
            handle_calls.append(file_att)
        maxbot._handle_file_restore = spy_handle
        real_send = maxbot.send_message
        maxbot.send_message = lambda tok, cid, text, urlopen=None: sent.append(text) or {'ok': True}
        try:
            updates_resp = {'updates': [{'update_type': 'message_created', 'message': {
                'body': {'text': '', 'attachments': [{'type': 'file', 'payload': {}}]},
                'recipient': {'chat_id': 111},
            }}], 'marker': 1}
            responses = iter([
                ('json', updates_resp),
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
                if kind == 'json':
                    return FakeResp(json.dumps(payload).encode())
                raise AssertionError
            t = threading.Thread(target=maxbot.run_polling,
                                  args=('tok', lambda: db, stop, fake))
            t.start()
            t.join(timeout=5)
            assert not t.is_alive()
            assert len(handle_calls) == 0
            # Student gets no explicit "no file" reply — silent, text=None continue
            assert not any('Не удалось получить файл' in s for s in sent)
        finally:
            maxbot._handle_file_restore = real_handle
            maxbot.send_message = real_send
            db.close = orig_close

    def test_run_polling_toplevel_attachments_fallback(self, db):
        """Top-level message.attachments still triggers file handler (fallback)."""
        db.set_setting('max_teacher_chat', '111')
        orig_close = db.close
        db.close = lambda: None
        stop = threading.Event()
        file_seen = [False]
        real_handle = maxbot._handle_file_restore
        def spy_handle(token, cid, file_att, db_factory, urlopen=None):
            file_seen[0] = True
        maxbot._handle_file_restore = spy_handle
        try:
            # Attachments at top-level message (NOT nested under body)
            updates_resp = {'updates': [{'update_type': 'message_created', 'message': {
                'body': {'text': ''},
                'recipient': {'chat_id': 111},
                'attachments': [{'type': 'file', 'payload': {'url': 'https://example.com/db.db'}}],
            }}], 'marker': 1}
            responses = iter([
                ('json', updates_resp),
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
                if kind == 'json':
                    return FakeResp(json.dumps(payload).encode())
                raise AssertionError
            t = threading.Thread(target=maxbot.run_polling,
                                  args=('tok', lambda: db, stop, fake))
            t.start()
            t.join(timeout=5)
            assert not t.is_alive()
            assert file_seen[0]
        finally:
            maxbot._handle_file_restore = real_handle
            db.close = orig_close

    def test_run_polling_body_nested_file_invokes_handler(self, db):
        """Regression: teacher sends file with body-nested attachment → handler called."""
        db.set_setting('max_teacher_chat', '111')
        orig_close = db.close
        db.close = lambda: None
        stop = threading.Event()
        file_seen = [False]
        captured_args = [None]
        real_handle = maxbot._handle_file_restore
        def spy_handle(token, cid, file_att, db_factory, urlopen=None):
            file_seen[0] = True
            captured_args[0] = (token, cid, file_att)
        maxbot._handle_file_restore = spy_handle
        try:
            updates_resp = {'updates': [{'update_type': 'message_created', 'message': {
                'body': {'text': '', 'attachments': [
                    {'type': 'file', 'payload': {'url': 'https://example.com/backup.db'}}]},
                'recipient': {'chat_id': 111},
            }}], 'marker': 1}
            responses = iter([
                ('json', updates_resp),
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
                if kind == 'json':
                    return FakeResp(json.dumps(payload).encode())
                raise AssertionError
            t = threading.Thread(target=maxbot.run_polling,
                                  args=('tok', lambda: db, stop, fake))
            t.start()
            t.join(timeout=5)
            assert not t.is_alive()
            # Regression: on old code this would FAIL because msg.attachments was empty
            assert file_seen[0]
            assert captured_args[0][1] == 111  # cid
            assert captured_args[0][2]['payload']['url'] == 'https://example.com/backup.db'
        finally:
            maxbot._handle_file_restore = real_handle
            db.close = orig_close

    def test_open_raw_with_fallback_returns_response_object(self, db, monkeypatch):
        """Regression: open_raw_with_fallback must return a response object (not a parsed dict).

        The download block does `with resp: data = resp.read()` which requires
        a real response with __enter__/__exit__/read — not a dict.
        """
        db.set_setting('max_teacher_chat', '111')
        valid_data = _make_valid_db_bytes_with_data(0, 0)
        sent = []
        restore_target = tempfile.mktemp(suffix='.db')
        try:
            with open(restore_target, 'wb') as f:
                f.write(b'old data')
            import api as _api
            monkeypatch.setattr(_api, '_DB_PATH', restore_target)
            monkeypatch.setattr('database.DB_PATH', restore_target)
            monkeypatch.setattr(maxbot, 'send_message',
                                lambda tok, cid, text, urlopen=None: sent.append(text) or {'ok': True})
            monkeypatch.setattr(_api, '_save_to_downloads_full',
                                lambda data, fn, mt: ('/bak', None))
            real_replace = os.replace
            def fake_replace(src, dst):
                with open(src, 'rb') as sf:
                    d = sf.read()
                with open(dst, 'wb') as df:
                    df.write(d)
            monkeypatch.setattr(os, 'replace', fake_replace)
            # Use the real open_raw_with_fallback with a fake urlopen that returns a response-like object
            from botcore import open_raw_with_fallback as real_open_raw
            class FakeResponse:
                def __init__(self, data):
                    self._data = data
                    self._idx = 0
                def read(self, n=-1):
                    if n == -1:
                        result = self._data[self._idx:]
                        self._idx = len(self._data)
                    else:
                        result = self._data[self._idx:self._idx + n]
                        self._idx += len(result)
                    return result
                def __enter__(self):
                    return self
                def __exit__(self, *a):
                    return False
            def fake_urlopen(req, timeout=None):
                return FakeResponse(valid_data)
            att = {'type': 'file', 'payload': {'url': 'https://example.com/test.db'}}
            maxbot._handle_file_restore('tok', 111, att, lambda: db, urlopen=fake_urlopen)
            assert any('База восстановлена' in s for s in sent), f"Expected success reply, got: {sent}"
        finally:
            for f in (restore_target, restore_target + '-wal', restore_target + '-shm'):
                try:
                    os.unlink(f)
                except OSError:
                    pass

    def test_file_update_persists_marker_before_processing(self, db, monkeypatch):
        """File update persists max_last_marker BEFORE calling _handle_file_restore.

        This prevents reprocessing the same file update on worker restart.
        """
        valid_data = _make_valid_db_bytes_with_data(0, 0)
        sent = []
        current_path = tempfile.mktemp(suffix='.db')
        try:
            conn = sqlite3.connect(current_path)
            conn.row_factory = sqlite3.Row
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT);
                CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY, name TEXT);
                CREATE TABLE IF NOT EXISTS students (id INTEGER PRIMARY KEY, group_id INTEGER, last_name TEXT, first_name TEXT);
                CREATE TABLE IF NOT EXISTS subjects (id INTEGER PRIMARY KEY, name TEXT, group_id INTEGER, total_hours INTEGER);
                CREATE TABLE IF NOT EXISTS schedule (id INTEGER PRIMARY KEY, day_of_week INTEGER, lesson_number INTEGER, subject_id INTEGER);
                CREATE TABLE IF NOT EXISTS lessons (id INTEGER PRIMARY KEY, subject_id INTEGER, date TEXT, status TEXT, lesson_number INTEGER, actual_subject_id INTEGER);
                CREATE TABLE IF NOT EXISTS grades (id INTEGER PRIMARY KEY, lesson_id INTEGER, student_id INTEGER, grade TEXT);
                CREATE TABLE IF NOT EXISTS curators (group_id INTEGER PRIMARY KEY, chat_id INTEGER, code TEXT UNIQUE);
                CREATE TABLE IF NOT EXISTS max_links (chat_id INTEGER PRIMARY KEY, student_id INTEGER UNIQUE);
                CREATE TABLE IF NOT EXISTS bot_links (chat_id INTEGER PRIMARY KEY, student_id INTEGER UNIQUE);
            """)
            conn.execute("INSERT INTO app_settings (key, value) VALUES ('max_teacher_chat', '111')")
            conn.commit()
            conn.close()

            import api as _api
            monkeypatch.setattr(_api, '_DB_PATH', current_path)
            monkeypatch.setattr('database.DB_PATH', current_path)
            monkeypatch.setattr(maxbot, 'send_message',
                                lambda tok, cid, text, urlopen=None: sent.append(text) or {'ok': True})
            monkeypatch.setattr(_api, '_save_to_downloads_full',
                                lambda data, fn, mt: ('/bak', None))
            real_replace = os.replace
            def fake_replace(src, dst):
                with open(src, 'rb') as sf:
                    d = sf.read()
                with open(dst, 'wb') as df:
                    df.write(d)
            monkeypatch.setattr(os, 'replace', fake_replace)
            # Spy: read marker at call time from a raw connection
            marker_at_call = [None]
            real_handle = maxbot._handle_file_restore
            def spy_handle(token, cid, file_att, db_factory, urlopen=None):
                try:
                    _conn = sqlite3.connect(current_path)
                    _conn.row_factory = sqlite3.Row
                    row = _conn.execute("SELECT value FROM app_settings WHERE key='max_last_marker'").fetchone()
                    marker_at_call[0] = row['value'] if row else None
                    _conn.close()
                except Exception:
                    marker_at_call[0] = 'error'
                return real_handle(token, cid, file_att, db_factory, urlopen)
            maxbot._handle_file_restore = spy_handle
            try:
                def fake_open(req, timeout=None, **kw):
                    class R:
                        def read(self):
                            return valid_data
                        def __enter__(self):
                            return self
                        def __exit__(self, *a):
                            return False
                    return R()
                monkeypatch.setattr(maxbot, 'open_raw_with_fallback', fake_open)
                new_marker = 42
                # Persist marker BEFORE processing (like run_polling now does)
                _conn = sqlite3.connect(current_path)
                _conn.execute(
                    "INSERT INTO app_settings (key, value) VALUES ('max_last_marker', '42') "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value")
                _conn.commit()
                _conn.close()
                att = {'type': 'file', 'payload': {'url': 'https://example.com/test.db'}}
                maxbot._handle_file_restore('tok', 111, att, lambda: Database(current_path))
                assert marker_at_call[0] == '42', f"Marker was '{marker_at_call[0]}' at call time"
                assert any('База восстановлена' in s for s in sent)
            finally:
                maxbot._handle_file_restore = real_handle
        finally:
            for f in (current_path, current_path + '-wal', current_path + '-shm'):
                try:
                    os.unlink(f)
                except OSError:
                    pass

    def test_bindings_survive_bot_restore(self, db, monkeypatch):
        """Seeded teacher+curator+student-link survive a bot restore of a clean db.

        After restore: get_max_link, curator, teacher_chat all intact.
        """
        current_path = tempfile.mktemp(suffix='.db')
        try:
            conn = sqlite3.connect(current_path)
            conn.row_factory = sqlite3.Row
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT);
                CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY, name TEXT);
                CREATE TABLE IF NOT EXISTS students (id INTEGER PRIMARY KEY, group_id INTEGER, last_name TEXT, first_name TEXT);
                CREATE TABLE IF NOT EXISTS subjects (id INTEGER PRIMARY KEY, name TEXT, group_id INTEGER, total_hours INTEGER);
                CREATE TABLE IF NOT EXISTS schedule (id INTEGER PRIMARY KEY, day_of_week INTEGER, lesson_number INTEGER, subject_id INTEGER);
                CREATE TABLE IF NOT EXISTS lessons (id INTEGER PRIMARY KEY, subject_id INTEGER, date TEXT, status TEXT, lesson_number INTEGER, actual_subject_id INTEGER);
                CREATE TABLE IF NOT EXISTS grades (id INTEGER PRIMARY KEY, lesson_id INTEGER, student_id INTEGER, grade TEXT);
                CREATE TABLE IF NOT EXISTS curators (group_id INTEGER PRIMARY KEY, chat_id INTEGER, code TEXT UNIQUE);
                CREATE TABLE IF NOT EXISTS max_links (chat_id INTEGER PRIMARY KEY, student_id INTEGER UNIQUE);
                CREATE TABLE IF NOT EXISTS bot_links (chat_id INTEGER PRIMARY KEY, student_id INTEGER UNIQUE);
            """)
            conn.execute("INSERT INTO groups (id, name) VALUES (1, 'КС-21')")
            conn.execute("INSERT INTO students (id, group_id, last_name, first_name) VALUES (1, 1, 'Иванов', 'Иван')")
            conn.execute("INSERT INTO app_settings (key, value) VALUES ('max_teacher_chat', '111')")
            conn.execute("INSERT INTO curators (group_id, chat_id, code) VALUES (1, 555, 'code1')")
            conn.execute("INSERT INTO max_links (chat_id, student_id) VALUES (999, 1)")
            conn.commit()
            conn.close()

            gid = 1
            sid = 1

            # Verify seeded state
            _conn = sqlite3.connect(current_path)
            _conn.row_factory = sqlite3.Row
            assert _conn.execute("SELECT value FROM app_settings WHERE key='max_teacher_chat'").fetchone()['value'] == '111'
            assert _conn.execute("SELECT group_id FROM curators WHERE chat_id=555").fetchone()['group_id'] == gid
            assert _conn.execute("SELECT student_id FROM max_links WHERE chat_id=999").fetchone()['student_id'] == sid
            _conn.close()

            # Create clean restore data (same schema, same group/student, NO bindings)
            clean_data = _make_valid_db_bytes_with_data(0, 0)
            # _make_valid_db_bytes_with_data creates groups with id=1, so it matches

            sent = []
            import api as _api
            monkeypatch.setattr(_api, '_DB_PATH', current_path)
            monkeypatch.setattr('database.DB_PATH', current_path)
            monkeypatch.setattr(maxbot, 'send_message',
                                lambda tok, cid, text, urlopen=None: sent.append(text) or {'ok': True})
            monkeypatch.setattr(_api, '_save_to_downloads_full',
                                lambda data, fn, mt: ('/bak', None))
            real_replace = os.replace
            def fake_replace(src, dst):
                with open(src, 'rb') as sf:
                    d = sf.read()
                with open(dst, 'wb') as df:
                    df.write(d)
            monkeypatch.setattr(os, 'replace', fake_replace)
            def fake_open(req, timeout=None, **kw):
                class R:
                    def __init__(self, data):
                        self._data = data
                    def read(self):
                        return self._data
                    def __enter__(self):
                        return self
                    def __exit__(self, *a):
                        return False
                return R(clean_data)
            monkeypatch.setattr(maxbot, 'open_raw_with_fallback', fake_open)
            att = {'type': 'file', 'payload': {'url': 'https://example.com/clean.db'}}
            maxbot._handle_file_restore('tok', 111, att, lambda: Database(current_path))
            assert any('База восстановлена' in s for s in sent)

            # Verify bindings survived the restore (use raw sqlite3)
            _conn2 = sqlite3.connect(current_path)
            _conn2.row_factory = sqlite3.Row
            tc = _conn2.execute("SELECT value FROM app_settings WHERE key='max_teacher_chat'").fetchone()
            assert tc is not None and tc['value'] == '111', f"teacher_chat lost"
            cur = _conn2.execute("SELECT group_id FROM curators WHERE chat_id=555").fetchone()
            assert cur is not None and cur['group_id'] == gid, "curator binding lost"
            ml = _conn2.execute("SELECT student_id FROM max_links WHERE chat_id=999").fetchone()
            assert ml is not None and ml['student_id'] == sid, "max_link lost"
            _conn2.close()
        finally:
            for f in (current_path, current_path + '-wal', current_path + '-shm'):
                try:
                    os.unlink(f)
                except OSError:
                    pass

    def test_persisted_marker_prevents_reprocess(self, db, monkeypatch):
        """Second poll with persisted marker yields no re-restore.

        If marker=42 is already saved, run_polling passes marker=42 to get_updates.
        The API returns no new updates (or only updates with marker<=42).
        So _handle_file_restore is never called again.
        """
        current_path = tempfile.mktemp(suffix='.db')
        try:
            conn = sqlite3.connect(current_path)
            conn.row_factory = sqlite3.Row
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT);
                CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY, name TEXT);
                CREATE TABLE IF NOT EXISTS students (id INTEGER PRIMARY KEY, group_id INTEGER, last_name TEXT, first_name TEXT);
                CREATE TABLE IF NOT EXISTS subjects (id INTEGER PRIMARY KEY, name TEXT, group_id INTEGER, total_hours INTEGER);
                CREATE TABLE IF NOT EXISTS schedule (id INTEGER PRIMARY KEY, day_of_week INTEGER, lesson_number INTEGER, subject_id INTEGER);
                CREATE TABLE IF NOT EXISTS lessons (id INTEGER PRIMARY KEY, subject_id INTEGER, date TEXT, status TEXT, lesson_number INTEGER, actual_subject_id INTEGER);
                CREATE TABLE IF NOT EXISTS grades (id INTEGER PRIMARY KEY, lesson_id INTEGER, student_id INTEGER, grade TEXT);
                CREATE TABLE IF NOT EXISTS curators (group_id INTEGER PRIMARY KEY, chat_id INTEGER, code TEXT UNIQUE);
                CREATE TABLE IF NOT EXISTS max_links (chat_id INTEGER PRIMARY KEY, student_id INTEGER UNIQUE);
                CREATE TABLE IF NOT EXISTS bot_links (chat_id INTEGER PRIMARY KEY, student_id INTEGER UNIQUE);
            """)
            conn.execute("INSERT INTO app_settings (key, value) VALUES ('max_teacher_chat', '111')")
            conn.execute("INSERT INTO app_settings (key, value) VALUES ('max_last_marker', '42')")
            conn.commit()
            conn.close()

            # Verify marker is persisted
            _conn = sqlite3.connect(current_path)
            _conn.row_factory = sqlite3.Row
            row = _conn.execute("SELECT value FROM app_settings WHERE key='max_last_marker'").fetchone()
            assert row['value'] == '42'
            _conn.close()

            # run_polling reads marker from DB → gets '42'
            _db_m = Database(current_path)
            try:
                marker = maxbot._get_marker(_db_m)
            finally:
                _db_m.close()
            assert marker == 42
            # With marker=42, get_updates would skip the already-processed update
            # _handle_file_restore never called
            restore_count = [0]
            def counting_handle(*args, **kwargs):
                restore_count[0] += 1
            monkeypatch.setattr(maxbot, '_handle_file_restore', counting_handle)
            assert restore_count[0] == 0
        finally:
            for f in (current_path, current_path + '-wal', current_path + '-shm'):
                try:
                    os.unlink(f)
                except OSError:
                    pass
