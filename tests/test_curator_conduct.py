"""Сводка куратору о проведённой паре: присутствующие и отсутствующие.

Раньше сообщение собиралось из изменённых оценок, поэтому:
  * список отсутствующих всегда был пустым (заголовок без строк);
  * если оценки не ставили, а только отмечали посещаемость, куратор
    не получал ничего.
Теперь текст строится по всему составу группы и уходит всегда.
"""
import pytest

import api as _api_module
from database import Database


@pytest.fixture
def db():
    with Database(':memory:') as database:
        yield database


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


def _journal(db):
    gid = db.add_group('ИТС-31')
    sid = db.add_subject('МДК 02.01', 40, gid)
    a = db.add_student(gid, 'Иванов', 'Иван')
    b = db.add_student(gid, 'Петров', 'Пётр')
    c = db.add_student(gid, 'Сидоров', 'Семён')
    lid = db.add_lesson(sid, '2026-09-14', status='held', lesson_number=1)
    return gid, sid, lid, a, b, c


class TestCuratorText:
    def test_lists_present_with_grade_and_absent_by_name(self, db):
        _, _, lid, a, b, c = _journal(db)
        db.mark_attendance(lid, a, '5')
        db.mark_attendance(lid, b, '0')  # был без оценки
        # c — строки нет → отсутствовал

        text = _api_module._curator_conduct_text(db, lid)
        lines = text.split('\n')

        assert 'Дата: 14.09' in lines
        assert 'Номер пары: 1' in lines
        assert f'{_api_module._MARK_GRADED} Иванов И. - 5' in lines
        assert f'{_api_module._MARK_NOGRADE} Петров П. - —' in lines, \
            'нулевая оценка показывается прочерком с серым маркером'

        idx = lines.index('Ниже список отсутствующих:')
        assert lines[idx + 1:] == [f'{_api_module._MARK_ABSENT} Сидоров С.']

    def test_all_absent_still_produces_message(self, db):
        _, _, lid, a, b, c = _journal(db)
        # ни одной строки — все отсутствовали
        text = _api_module._curator_conduct_text(db, lid)
        lines = text.split('\n')
        idx = lines.index('Ниже список отсутствующих:')
        mark = _api_module._MARK_ABSENT
        assert lines[idx + 1:] == [
            f'{mark} Иванов И.', f'{mark} Петров П.', f'{mark} Сидоров С.',
        ]

    def test_no_absentees_prints_none(self, db):
        _, _, lid, a, b, c = _journal(db)
        for st in (a, b, c):
            db.mark_attendance(lid, st, '4')
        text = _api_module._curator_conduct_text(db, lid)
        assert text.split('\n')[-1] == 'нет'

    def test_absent_marker_is_treated_as_absent(self, db):
        _, _, lid, a, b, c = _journal(db)
        db.mark_attendance(lid, a, 'absent')
        text = _api_module._curator_conduct_text(db, lid)
        lines = text.split('\n')
        idx = lines.index('Ниже список отсутствующих:')
        assert f'{_api_module._MARK_ABSENT} Иванов И.' in lines[idx + 1:]

    def test_unknown_lesson_returns_empty(self, db):
        assert _api_module._curator_conduct_text(db, 9999) == ''


class TestConductSendsCuratorSummary:
    """Проверка через HTTP: сообщение уходит, даже если оценки не изменились."""

    @pytest.fixture
    def sent(self, monkeypatch):
        messages = []

        def fake_send_message(token, chat_id, text, urlopen=None):
            messages.append({'token': token, 'chat_id': chat_id, 'text': text})

        class SyncThread:
            def __init__(self, target=None, args=(), kwargs=None, daemon=None):
                self._target, self._args, self._kwargs = target, args, kwargs or {}

            def start(self):
                if self._target:
                    self._target(*self._args, **self._kwargs)

        monkeypatch.setattr('maxbot.send_message', fake_send_message)
        monkeypatch.setattr('maxbot.notify_grade', lambda *a, **k: None)
        monkeypatch.setattr(_api_module.threading, 'Thread', SyncThread)
        return messages

    def _setup(self, client):
        gid = client.post('/api/groups', json={'name': 'ИТС-31'}).json['id']
        sid = client.post('/api/subjects', json={
            'name': 'МДК 02.01', 'total_hours': 40, 'group_id': gid}).json['id']
        db = _api_module.get_db()
        db.set_setting('max_bot_token', 'fake-token')
        db.set_setting('max_bot_enabled', '1')
        db.bind_curator(gid, 9999)
        a = db.add_student(gid, 'Иванов', 'Иван')
        b = db.add_student(gid, 'Петров', 'Пётр')
        c = db.add_student(gid, 'Сидоров', 'Семён')
        lid = db.add_lesson(sid, '2026-09-14', status='scheduled', lesson_number=1)
        return gid, lid, a, b, c

    def test_sends_when_nothing_changed(self, client, sent):
        _, lid, a, b, c = self._setup(client)
        db = _api_module.get_db()
        # Состояние уже записано: у a и b «был без оценки», c отсутствует.
        db.mark_attendance(lid, a, '0')
        db.mark_attendance(lid, b, '0')

        rv = client.post(f'/api/lessons/{lid}/conduct', json=[
            {'student_id': a, 'grade': '0'},
            {'student_id': b, 'grade': '0'},
        ])
        assert rv.status_code == 200
        assert rv.json['notified'] == 0, 'оценки не менялись'

        assert len(sent) == 1, 'куратор должен получить сводку'
        text = sent[0]['text']
        assert sent[0]['chat_id'] == 9999
        assert f'{_api_module._MARK_NOGRADE} Иванов И. - —' in text
        assert 'Ниже список отсутствующих:' in text
        assert text.rstrip().endswith(f'{_api_module._MARK_ABSENT} Сидоров С.')

    def test_lesson_becomes_held(self, client, sent):
        _, lid, a, b, c = self._setup(client)
        client.post(f'/api/lessons/{lid}/conduct', json=[
            {'student_id': a, 'grade': '5'}])
        assert _api_module.get_db().get_lesson(lid)['status'] == 'held'
