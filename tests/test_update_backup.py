"""Перед установкой обновления создаётся снимок базы.

Обновление APK данные не стирает, но новая версия при первом запуске
прогоняет миграции по живой базе. Копия делается до запуска установщика,
чтобы было куда откатиться, если миграция окажется неудачной.
"""
import sqlite3

import pytest

import api as _api_module
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


@pytest.fixture
def db_file(tmp_path):
    path = tmp_path / 'lessons.db'
    with Database(str(path)) as db:
        gid = db.add_group('АДТ-31')
        db.add_subject('МДК', 30, gid)
    return path


def _capture(monkeypatch, tmp_path, captured):
    def fake_save(data, filename, mimetype):
        captured.update(data=data, filename=filename, mimetype=mimetype)
        return str(tmp_path / filename), None

    monkeypatch.setattr(_api_module, '_save_to_downloads_full', fake_save)


class TestBackupBeforeUpdate:
    def test_skips_when_db_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_api_module, '_DB_PATH', str(tmp_path / 'none.db'))
        assert _api_module._backup_before_update() == {'skipped': 'базы ещё нет'}

    def test_snapshot_is_saved_with_timestamped_name(self, db_file, tmp_path, monkeypatch):
        captured: dict = {}
        monkeypatch.setattr(_api_module, '_DB_PATH', str(db_file))
        _capture(monkeypatch, tmp_path, captured)

        res = _api_module._backup_before_update()

        assert res['size'] > 0
        assert res['path'].endswith('.db')
        name = captured['filename']
        assert name.startswith('teachhelper_before_update_')
        assert name.endswith('.db')
        assert captured['mimetype'] == 'application/x-sqlite3'
        assert captured['data'][:16] == b'SQLite format 3\x00'

    def test_snapshot_opens_as_database(self, db_file, tmp_path, monkeypatch):
        captured: dict = {}
        monkeypatch.setattr(_api_module, '_DB_PATH', str(db_file))
        _capture(monkeypatch, tmp_path, captured)

        _api_module._backup_before_update()

        restored = tmp_path / 'restored.db'
        restored.write_bytes(captured['data'])
        conn = sqlite3.connect(str(restored))
        try:
            assert conn.execute('SELECT COUNT(*) FROM groups').fetchone()[0] == 1
            assert conn.execute('SELECT COUNT(*) FROM subjects').fetchone()[0] == 1
        finally:
            conn.close()

    def test_failure_is_reported_not_raised(self, db_file, monkeypatch):
        def boom(*_a, **_kw):
            raise OSError('нет места на диске')

        monkeypatch.setattr(_api_module, '_DB_PATH', str(db_file))
        monkeypatch.setattr(_api_module, '_save_to_downloads_full', boom)

        res = _api_module._backup_before_update()

        assert 'error' in res
        assert 'нет места' in res['error']

    def test_desktop_install_returns_400_without_backup(self, client, monkeypatch):
        """Вне Android установщика нет — и копию делать не нужно."""
        called = []
        monkeypatch.setattr(
            _api_module, '_backup_before_update',
            lambda: called.append(1) or {'path': 'x'},
        )
        rv = client.post('/api/update/install', json={'uri': 'content://x'})
        assert rv.status_code == 400
        assert called == []
