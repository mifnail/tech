"""Состояние поллинга MAX и ручное управление ботом.

Раньше единственным признаком поломки было «студенты пишут, а ответа нет»:
ни времени последнего опроса, ни ошибки, ни способа перезапустить без
переустановки приложения.
"""
import threading

import pytest

import api as _api_module
import maxbot
from database import Database


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


def _with_token(client, enabled: str = '1'):
    db = _api_module.get_db()
    db.set_setting('max_bot_token', 'test-token')
    db.set_setting('max_bot_enabled', enabled)
    return db


class TestStatusEndpoint:
    def test_without_token(self, client, monkeypatch):
        monkeypatch.setattr(maxbot, '_poll_thread', None)
        monkeypatch.setattr(maxbot, '_poll_state', {
            'started_at': None, 'last_poll_ok': None, 'last_update_at': None,
            'updates_total': 0, 'last_error': None, 'last_error_at': None,
            'consecutive_errors': 0,
        })
        j = client.get('/api/settings/maxbot/status').json

        assert j['has_token'] is False
        assert j['enabled'] is False
        assert j['poll']['alive'] is False
        assert j['poll']['updates_total'] == 0

    def test_returns_marker_and_poll_fields(self, client):
        db = _with_token(client)
        db.set_setting('max_last_marker', '25194')

        j = client.get('/api/settings/maxbot/status').json

        assert j['has_token'] is True
        assert j['enabled'] is True
        assert j['marker'] == '25194'
        for key in ('alive', 'last_poll_ok', 'last_update_at', 'last_error', 'consecutive_errors'):
            assert key in j['poll']


class TestRestart:
    def test_requires_token(self, client):
        assert client.post('/api/settings/maxbot/restart').status_code == 400

    def test_requires_enabled_bot(self, client):
        _with_token(client, enabled='0')
        rv = client.post('/api/settings/maxbot/restart')
        assert rv.status_code == 400
        assert 'выключен' in rv.json['error']

    def test_restarts_with_token(self, client, monkeypatch):
        _with_token(client)
        called = []
        monkeypatch.setattr(maxbot, 'restart_polling', lambda tok: called.append(tok))

        rv = client.post('/api/settings/maxbot/restart')

        assert rv.status_code == 200
        assert called == ['test-token']


class TestResetMarker:
    def test_requires_token(self, client):
        assert client.post('/api/settings/maxbot/reset-marker').status_code == 400

    def test_clears_setting_and_restarts(self, client, monkeypatch):
        db = _with_token(client)
        db.set_setting('max_last_marker', '25194')
        called = []
        monkeypatch.setattr(maxbot, 'reset_marker_and_restart', lambda tok: called.append(tok))

        rv = client.post('/api/settings/maxbot/reset-marker')

        assert rv.status_code == 200
        assert called == ['test-token']

    def test_real_reset_clears_marker(self, monkeypatch, tmp_path):
        """Без мока: маркер действительно стирается в базе."""
        path = str(tmp_path / 'journal.db')
        with Database(path) as db:
            db.set_setting('max_last_marker', '25194')

        monkeypatch.setattr('database.Database', lambda *a, **k: Database(path))
        monkeypatch.setattr(maxbot, 'restart_polling', lambda tok: None)

        maxbot.reset_marker_and_restart('test-token')

        with Database(path) as check:
            assert check.get_setting('max_last_marker') in (None, '')


class TestPollFactory:
    def test_second_call_does_not_start_another_thread(self, monkeypatch):
        """Супервизор и ручной перезапуск не должны плодить потоки."""
        calls = []
        started = threading.Event()

        def fake_run(token, db_factory, stop_event=None, urlopen=None):
            calls.append(token)
            started.set()
            while stop_event is not None and not stop_event.is_set():
                stop_event.wait(0.05)

        monkeypatch.setattr(maxbot, 'run_polling', fake_run)
        monkeypatch.setattr(maxbot, '_poll_thread', None)
        monkeypatch.setattr(maxbot, '_poll_stop', None)
        monkeypatch.setattr(maxbot, '_poll_token', 'test-token')

        first = maxbot._poll_factory()
        assert started.wait(2)
        second = maxbot._poll_factory()

        assert first is second
        assert calls == ['test-token']

        maxbot._poll_stop.set()
        first.join(timeout=2)
        monkeypatch.setattr(maxbot, '_poll_thread', None)

    def test_state_reports_not_alive_when_thread_missing(self, monkeypatch):
        monkeypatch.setattr(maxbot, '_poll_thread', None)
        assert maxbot.poll_state()['alive'] is False
