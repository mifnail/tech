"""Пара расписания действует только с даты, когда её завели.

Баг: новая пара «задним числом» появлялась в сетке прошедших дней, где её
никогда не было, и выглядела как пропущенное занятие.
"""
import time

import pytest

import api as _api_module
from database import Database


def _today() -> str:
    return time.strftime('%Y-%m-%d')


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


class TestValidFrom:
    def test_default_is_today(self, db):
        gid = db.add_group('АДТ-31')
        sid = db.add_subject('МДК', 30, gid)
        eid = db.add_schedule_entry(1, 1, sid, 0)
        row = db.conn.execute(
            "SELECT valid_from FROM schedule WHERE id = ?", (eid,)).fetchone()
        assert row['valid_from'] == _today()

    def test_explicit_date_is_stored(self, db):
        gid = db.add_group('АДТ-31')
        sid = db.add_subject('МДК', 30, gid)
        eid = db.add_schedule_entry(1, 1, sid, 0, valid_from='2026-09-01')
        row = db.conn.execute(
            "SELECT valid_from FROM schedule WHERE id = ?", (eid,)).fetchone()
        assert row['valid_from'] == '2026-09-01'

    def test_update_keeps_valid_from(self, db):
        gid = db.add_group('АДТ-31')
        sid = db.add_subject('МДК', 30, gid)
        eid = db.add_schedule_entry(1, 1, sid, 0, valid_from='2026-09-01')
        db.update_schedule_entry(eid, 2, 3, sid, 0)
        row = db.conn.execute(
            "SELECT valid_from, day_of_week, lesson_number FROM schedule WHERE id = ?",
            (eid,)).fetchone()
        assert row['valid_from'] == '2026-09-01'
        assert (row['day_of_week'], row['lesson_number']) == (2, 3)


class TestScheduleApi:
    def _subject(self, client):
        gid = client.post('/api/groups', json={'name': 'АДТ-31'}).json['id']
        return client.post('/api/subjects', json={
            'name': 'МДК', 'total_hours': 30, 'group_id': gid}).json['id']

    def test_post_sets_valid_from_today(self, client):
        sid = self._subject(client)
        rv = client.post('/api/schedule', json={
            'day_of_week': 1, 'lesson_number': 1, 'subject_id': sid, 'week_type': 0})
        assert rv.status_code == 201
        rows = client.get('/api/schedule').json
        assert len(rows) == 1
        assert rows[0]['valid_from'] == _today()

    def test_post_accepts_explicit_valid_from(self, client):
        sid = self._subject(client)
        client.post('/api/schedule', json={
            'day_of_week': 1, 'lesson_number': 1, 'subject_id': sid,
            'week_type': 0, 'valid_from': '2026-11-01'})
        rows = client.get('/api/schedule').json
        assert rows[0]['valid_from'] == '2026-11-01'

    def test_patch_does_not_reset_valid_from(self, client):
        sid = self._subject(client)
        client.post('/api/schedule', json={
            'day_of_week': 1, 'lesson_number': 1, 'subject_id': sid,
            'week_type': 0, 'valid_from': '2026-11-01'})
        eid = client.get('/api/schedule').json[0]['id']
        rv = client.patch(f'/api/schedule/{eid}', json={
            'day_of_week': 2, 'lesson_number': 3, 'subject_id': sid, 'week_type': 0})
        assert rv.status_code == 200
        rows = client.get('/api/schedule').json
        assert rows[0]['valid_from'] == '2026-11-01'
        assert rows[0]['day_of_week'] == 2
