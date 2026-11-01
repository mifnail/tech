"""Вычитка предмета: закрытие и возврат в расписание.

Предмет вычитан → плановые строки шаблона после даты закрытия не показываются.
Закрытие обратимо: часы могли поправить или пару отменить.
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


def _setup(client, hours=30):
    gid = client.post('/api/groups', json={'name': 'АДТ-31'}).json['id']
    sid = client.post('/api/subjects', json={
        'name': 'МДК 01.01', 'total_hours': hours, 'group_id': gid}).json['id']
    return gid, sid


class TestCloseSubject:
    def test_close_sets_date(self, client):
        _, sid = _setup(client)

        rv = client.post(f'/api/subjects/{sid}/close', json={'date': '2026-10-30'})

        assert rv.status_code == 200
        assert rv.json['closed_at'] == '2026-10-30'
        assert _api_module.get_db().get_subject(sid)['closed_at'] == '2026-10-30'

    def test_close_defaults_to_today(self, client):
        _, sid = _setup(client)

        rv = client.post(f'/api/subjects/{sid}/close', json={})

        assert rv.status_code == 200
        assert rv.json['closed_at'] == time.strftime('%Y-%m-%d')

    def test_bad_date(self, client):
        _, sid = _setup(client)
        assert client.post(f'/api/subjects/{sid}/close', json={'date': 'вчера'}).status_code == 400

    def test_unknown_subject(self, client):
        assert client.post('/api/subjects/9999/close', json={}).status_code == 404

    def test_appears_in_subjects_list(self, client):
        _, sid = _setup(client)
        client.post(f'/api/subjects/{sid}/close', json={'date': '2026-10-30'})

        rows = client.get('/api/subjects').json
        row = [r for r in rows if r['id'] == sid][0]

        assert row['closed_at'] == '2026-10-30'


class TestReopenSubject:
    def test_reopen_clears_date(self, client):
        _, sid = _setup(client)
        client.post(f'/api/subjects/{sid}/close', json={'date': '2026-10-30'})

        rv = client.post(f'/api/subjects/{sid}/reopen')

        assert rv.status_code == 200
        assert _api_module.get_db().get_subject(sid)['closed_at'] is None

    def test_reopen_unknown_subject(self, client):
        assert client.post('/api/subjects/9999/reopen').status_code == 404

    def test_reopen_is_idempotent(self, client):
        _, sid = _setup(client)
        assert client.post(f'/api/subjects/{sid}/reopen').status_code == 200
        assert client.post(f'/api/subjects/{sid}/reopen').status_code == 200
