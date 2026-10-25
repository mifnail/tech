"""Сводка куратору и личные сообщения студентам о проведённой паре.

Формат единый: шапка «Дата / Предмет / Номер пары», дальше строки с маркерами.
Куратор видит весь состав, студент — только свою строку.
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
    lid = db.add_lesson(sid, '2026-09-14', status='scheduled', lesson_number=3)
    return gid, sid, lid, a, b, c


class TestCuratorText:
    def test_full_format(self, db):
        _, _, lid, a, b, c = _journal(db)
        db.mark_attendance(lid, a, '5')
        db.mark_attendance(lid, b, '0')  # был без оценки

        text = _api_module._curator_conduct_text(db, lid)

        assert text.split('\n') == [
            'Дата: 14.09',
            'Предмет: МДК 02.01',
            'Номер пары: 3',
            'Присутствовали:',
            f'{_api_module._MARK_GRADED} Иванов И. — 5',
            f'{_api_module._MARK_NOGRADE} Петров П.',
            'Отсутствовали:',
            f'{_api_module._MARK_ABSENT} Сидоров С.',
        ]

    def test_no_absentees_prints_none(self, db):
        _, _, lid, a, b, c = _journal(db)
        for st in (a, b, c):
            db.mark_attendance(lid, st, '4')

        lines = _api_module._curator_conduct_text(db, lid).split('\n')

        assert lines[-2:] == ['Отсутствовали:', 'нет']

    def test_all_absent_prints_none_present(self, db):
        _, _, lid, a, b, c = _journal(db)

        lines = _api_module._curator_conduct_text(db, lid).split('\n')

        assert lines[3:5] == ['Присутствовали:', 'нет']
        assert lines[5] == 'Отсутствовали:'
        assert len(lines) == 9, 'шапка + два раздела и три отсутствующих'

    def test_absent_marker_is_absent(self, db):
        _, _, lid, a, b, c = _journal(db)
        db.mark_attendance(lid, a, 'absent')

        text = _api_module._curator_conduct_text(db, lid)

        assert f'{_api_module._MARK_ABSENT} Иванов И.' in text.split('\n')

    def test_unknown_lesson_returns_empty(self, db):
        assert _api_module._curator_conduct_text(db, 9999) == ''


class TestStudentMessages:
    def _bind_all(self, db, a, b, c):
        db.bind_max(101, a)
        db.bind_max(102, b)
        db.bind_max(103, c)

    def test_first_conduct_notifies_everyone(self, db):
        _, _, lid, a, b, c = _journal(db)
        db.mark_attendance(lid, a, '5')
        db.mark_attendance(lid, b, '0')
        self._bind_all(db, a, b, c)

        header = _api_module._lesson_header(db, lid)
        msgs = dict(_api_module._student_conduct_messages(db, lid, header, False, set()))

        assert msgs[101].split('\n')[-1] == f'{_api_module._MARK_GRADED} Оценка: 5'
        assert msgs[102].split('\n')[-1] == f'{_api_module._MARK_NOGRADE} Без оценки'
        assert msgs[103].split('\n')[-1] == f'{_api_module._MARK_ABSENT} Отсутствие'

    def test_header_matches_curator(self, db):
        _, _, lid, a, b, c = _journal(db)
        db.mark_attendance(lid, a, '4')
        db.bind_max(101, a)

        header = _api_module._lesson_header(db, lid)
        msg = dict(_api_module._student_conduct_messages(db, lid, header, False, set()))[101]

        assert msg.split('\n')[:3] == ['Дата: 14.09', 'Предмет: МДК 02.01', 'Номер пары: 3']

    def test_repeat_conduct_skips_absence_and_nograde(self, db):
        """Повторное «Провести» не дублирует отсутствие и «без оценки»."""
        _, _, lid, a, b, c = _journal(db)
        db.mark_attendance(lid, a, '5')
        db.mark_attendance(lid, b, '0')
        self._bind_all(db, a, b, c)

        header = _api_module._lesson_header(db, lid)
        msgs = dict(_api_module._student_conduct_messages(db, lid, header, True, {a}))

        assert set(msgs) == {101}, 'только изменившаяся оценка'
        assert msgs[101].endswith(f'{_api_module._MARK_GRADED} Оценка: 5')

    def test_unbound_student_is_skipped(self, db):
        _, _, lid, a, b, c = _journal(db)
        db.mark_attendance(lid, a, '5')
        db.bind_max(101, a)  # b и c без привязки

        header = _api_module._lesson_header(db, lid)
        msgs = _api_module._student_conduct_messages(db, lid, header, False, set())

        assert [chat for chat, _ in msgs] == [101]


class TestConductOverHttp:
    @pytest.fixture
    def sent(self, monkeypatch):
        messages = []

        def fake_send_message(token, chat_id, text, urlopen=None):
            messages.append({'chat_id': chat_id, 'text': text})

        class SyncThread:
            def __init__(self, target=None, args=(), kwargs=None, daemon=None):
                self._target, self._args, self._kwargs = target, args, kwargs or {}

            def start(self):
                if self._target:
                    self._target(*self._args, **self._kwargs)

        monkeypatch.setattr('maxbot.send_message', fake_send_message)
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
        lid = db.add_lesson(sid, '2026-09-14', status='scheduled', lesson_number=3)
        return gid, lid, a, b, c

    def test_curator_gets_summary_and_students_get_own_lines(self, client, sent):
        _, lid, a, b, c = self._setup(client)
        db = _api_module.get_db()
        db.bind_max(101, a)
        db.bind_max(103, c)

        rv = client.post(f'/api/lessons/{lid}/conduct', json=[
            {'student_id': a, 'grade': '5'},
            {'student_id': b, 'grade': '0'},
        ])
        assert rv.status_code == 200
        assert rv.json['notified'] == 2, 'двое привязанных студентов'

        by_chat = {m['chat_id']: m['text'] for m in sent}
        assert set(by_chat) == {9999, 101, 103}
        assert by_chat[9999].startswith(
            'Дата: 14.09\nПредмет: МДК 02.01\nНомер пары: 3\nПрисутствовали:')
        assert by_chat[101].endswith('Оценка: 5')
        assert by_chat[103].endswith('Отсутствие')

    def test_lesson_becomes_held(self, client, sent):
        _, lid, a, b, c = self._setup(client)
        client.post(f'/api/lessons/{lid}/conduct', json=[
            {'student_id': a, 'grade': '5'}])
        assert _api_module.get_db().get_lesson(lid)['status'] == 'held'

    def test_second_conduct_does_not_repeat_absence(self, client, sent):
        _, lid, a, b, c = self._setup(client)
        db = _api_module.get_db()
        db.bind_max(101, a)
        db.bind_max(103, c)

        client.post(f'/api/lessons/{lid}/conduct', json=[
            {'student_id': a, 'grade': '5'}])
        sent.clear()

        client.post(f'/api/lessons/{lid}/conduct', json=[
            {'student_id': a, 'grade': '4'}])

        to_students = [m for m in sent if m['chat_id'] != 9999]
        assert [m['chat_id'] for m in to_students] == [101]
        assert to_students[0]['text'].endswith('Оценка: 4')

    def test_second_conduct_without_changes_is_silent(self, client, sent):
        """Перепровели то же самое — ни студентам, ни куратору ничего."""
        _, lid, a, b, c = self._setup(client)
        db = _api_module.get_db()
        db.bind_max(101, a)
        db.bind_max(103, c)

        client.post(f'/api/lessons/{lid}/conduct', json=[
            {'student_id': a, 'grade': '5'}])
        sent.clear()

        rv = client.post(f'/api/lessons/{lid}/conduct', json=[
            {'student_id': a, 'grade': '5'},
            {'student_id': b, 'grade': 'absent'},
            {'student_id': c, 'grade': 'absent'},
        ])

        assert rv.json['notified'] == 0
        assert sent == [], 'куратор и студенты молчат'

    def test_absence_toggled_back_is_not_a_change(self, client, sent):
        """Отметил присутствие и отменил — студент не получает «Отсутствие» снова."""
        _, lid, a, b, c = self._setup(client)
        db = _api_module.get_db()
        db.bind_max(101, a)
        db.bind_max(103, c)

        # первое проведение: c отсутствовал
        client.post(f'/api/lessons/{lid}/conduct', json=[
            {'student_id': a, 'grade': '5'},
            {'student_id': c, 'grade': 'absent'},
        ])
        sent.clear()

        # «поставил присутствие → отменил»: в записи снова absent
        rv = client.post(f'/api/lessons/{lid}/conduct', json=[
            {'student_id': a, 'grade': '5'},
            {'student_id': c, 'grade': 'absent'},
        ])

        assert rv.json['notified'] == 0
        assert sent == []
        assert not any('Отсутствие' in m['text'] for m in sent)

    def test_real_change_still_notifies(self, client, sent):
        """Настоящее изменение пробивается: молчание только когда правда ничего нет."""
        _, lid, a, b, c = self._setup(client)
        db = _api_module.get_db()
        db.bind_max(101, a)

        client.post(f'/api/lessons/{lid}/conduct', json=[
            {'student_id': a, 'grade': '5'},
            {'student_id': c, 'grade': 'absent'},
        ])
        sent.clear()

        # c перевели из отсутствия в присутствие — это изменение
        client.post(f'/api/lessons/{lid}/conduct', json=[
            {'student_id': a, 'grade': '5'},
            {'student_id': c, 'grade': '0'},
        ])

        assert any(m['chat_id'] == 9999 for m in sent), 'куратор должен узнать'
