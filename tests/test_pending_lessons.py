"""Незаполненные прошедшие занятия.

Правило: у прошедшей пары может быть только «проведено» или «отменено».
Всё остальное приложение показывает преподавателю при запуске со ссылкой,
чтобы он либо заполнил ведомость, либо отменил пару.
"""
import time

import pytest

import api as _api_module
from database import Database


def _shift(days: int) -> str:
    return time.strftime('%Y-%m-%d', time.localtime(time.time() + days * 86400))


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


def _setup(client):
    gid = client.post('/api/groups', json={'name': 'АДТ-31'}).json['id']
    sid = client.post('/api/subjects', json={
        'name': 'МДК 01.01', 'total_hours': 30, 'group_id': gid}).json['id']
    return gid, sid, _api_module.get_db()


class TestPendingLessons:
    def test_only_past_unfilled(self, client):
        _, sid, db = _setup(client)
        db.add_lesson(sid, _shift(-3), status='held')
        db.add_lesson(sid, _shift(-3), status='cancelled')
        pending = db.add_lesson(sid, _shift(-2), status='scheduled')
        db.add_lesson(sid, _shift(0), status='scheduled')   # сегодня — ещё не прошедшее
        db.add_lesson(sid, _shift(2), status='scheduled')   # будущее

        rows = client.get('/api/lessons/pending').json

        assert [r['id'] for r in rows] == [pending]

    def test_row_carries_what_the_list_needs(self, client):
        _, sid, db = _setup(client)
        lid = db.add_lesson(sid, _shift(-1), status='scheduled', lesson_number=3)

        row = client.get('/api/lessons/pending').json[0]

        assert row['id'] == lid
        assert row['date'] == _shift(-1)
        assert row['lesson_number'] == 3
        assert row['group_name'] == 'АДТ-31'
        assert row['subject_name'] == 'МДК 01.01'

    def test_newest_first(self, client):
        _, sid, db = _setup(client)
        old = db.add_lesson(sid, _shift(-10), status='scheduled')
        recent = db.add_lesson(sid, _shift(-1), status='scheduled')

        ids = [r['id'] for r in client.get('/api/lessons/pending').json]

        assert ids == [recent, old]

    def test_empty_when_everything_closed(self, client):
        _, sid, db = _setup(client)
        db.add_lesson(sid, _shift(-2), status='held')
        db.add_lesson(sid, _shift(-1), status='cancelled')

        assert client.get('/api/lessons/pending').json == []

    def test_conducted_lesson_disappears(self, client):
        """Провели — из списка ушло."""
        _, sid, db = _setup(client)
        student = db.add_student(db.conn.execute(
            'SELECT group_id FROM subjects WHERE id = ?', (sid,)).fetchone()['group_id'],
            'Иванов', 'Иван')
        lid = db.add_lesson(sid, _shift(-1), status='scheduled')

        assert len(client.get('/api/lessons/pending').json) == 1
        client.post(f'/api/lessons/{lid}/conduct', json=[
            {'student_id': student, 'grade': '5'}])

        assert client.get('/api/lessons/pending').json == []

    def test_cancelled_lesson_disappears(self, client):
        """Отменили — тоже ушло."""
        _, sid, db = _setup(client)
        lid = db.add_lesson(sid, _shift(-1), status='scheduled')

        assert len(client.get('/api/lessons/pending').json) == 1
        client.patch(f'/api/lessons/{lid}/status', json={'status': 'cancelled'})

        assert client.get('/api/lessons/pending').json == []
