import io
import os
import sqlite3
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import api as _api_module
from database import Database, DB_PATH


@pytest.fixture
def client():
    _api_module.app.config['TESTING'] = True
    with _api_module.app.test_client() as c:
        yield c


def _make_valid_db_bytes():
    """Create a minimal valid SQLite DB with all required tables."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    tmp.close()
    try:
        conn = sqlite3.connect(tmp.name)
        conn.executescript("""
            CREATE TABLE groups (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE students (id INTEGER PRIMARY KEY, group_id INTEGER, last_name TEXT, first_name TEXT);
            CREATE TABLE subjects (id INTEGER PRIMARY KEY, name TEXT, group_id INTEGER, total_hours INTEGER);
            CREATE TABLE schedule (id INTEGER PRIMARY KEY, day_of_week INTEGER, lesson_number INTEGER, subject_id INTEGER);
            CREATE TABLE lessons (id INTEGER PRIMARY KEY, subject_id INTEGER, date TEXT, status TEXT, lesson_number INTEGER);
            CREATE TABLE grades (id INTEGER PRIMARY KEY, lesson_id INTEGER, student_id INTEGER, grade TEXT);
            CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT);
        """)
        conn.close()
        with open(tmp.name, 'rb') as f:
            return f.read()
    finally:
        os.unlink(tmp.name)


class TestBackup:
    def test_backup_returns_sqlite(self, client, monkeypatch):
        """Backup endpoint returns data with SQLite header."""
        captured = {}
        def fake_save(data, filename, mimetype):
            captured['data'] = data
            captured['filename'] = filename
            return '/fake/path/' + filename, None
        monkeypatch.setattr(_api_module, '_save_to_downloads_full', fake_save)

        rv = client.post('/api/backup')
        assert rv.status_code == 200
        body = rv.json
        assert body['ok'] is True
        assert 'path' in body
        assert captured['data'][:16] == b'SQLite format 3\x00'
        assert len(captured['data']) > 0
        assert 'teachhelper_' in captured['filename']
        assert captured['filename'].endswith('.db')

    def test_backup_read_error(self, client, monkeypatch):
        """Backup handles read error gracefully."""
        real_open = open
        def bad_open(path, *args, **kwargs):
            if isinstance(path, str) and path == _api_module._DB_PATH and args and args[0] == 'rb':
                raise PermissionError('nope')
            return real_open(path, *args, **kwargs)
        monkeypatch.setattr('builtins.open', bad_open)
        rv = client.post('/api/backup')
        assert rv.status_code == 500
        assert 'error' in rv.json


class TestRestore:
    def test_restore_valid(self, client, monkeypatch):
        """Restore with a valid DB file succeeds."""
        valid_data = _make_valid_db_bytes()
        restore_target = tempfile.mktemp(suffix='.db')
        try:
            monkeypatch.setattr(_api_module, '_DB_PATH', restore_target)
            with open(restore_target, 'wb') as f:
                f.write(b'old data')

            written = {}
            real_replace = os.replace
            def fake_replace(src, dst):
                with open(src, 'rb') as f:
                    written['data'] = f.read()
                real_replace(src, dst)
            monkeypatch.setattr(os, 'replace', fake_replace)
            monkeypatch.setattr(_api_module, '_save_to_downloads_full',
                                lambda data, fn, mt: ('/bak', None))

            rv = client.post('/api/restore', data={
                'file': (io.BytesIO(valid_data), 'restore.db')
            }, content_type='multipart/form-data')
            assert rv.status_code == 200
            assert rv.json['ok'] is True
            assert written['data'] == valid_data
        finally:
            for f in (restore_target, restore_target + '-wal', restore_target + '-shm'):
                try:
                    os.unlink(f)
                except OSError:
                    pass

    def test_restore_no_file(self, client):
        """Restore without file returns 400."""
        rv = client.post('/api/restore', data={}, content_type='multipart/form-data')
        assert rv.status_code == 400
        assert rv.json['error'] == 'no file'

    def test_restore_not_sqlite(self, client, monkeypatch):
        """Restore with non-SQLite file returns 400."""
        restore_target = tempfile.mktemp(suffix='.db')
        try:
            monkeypatch.setattr(_api_module, '_DB_PATH', restore_target)
            with open(restore_target, 'wb') as f:
                f.write(b'original data')

            rv = client.post('/api/restore', data={
                'file': (io.BytesIO(b'not sqlite at all'), 'bad.db')
            }, content_type='multipart/form-data')
            assert rv.status_code == 400
            assert 'not a SQLite' in rv.json['error']
            with open(restore_target, 'rb') as f:
                assert f.read() == b'original data'
        finally:
            try:
                os.unlink(restore_target)
            except OSError:
                pass

    def test_restore_too_small(self, client, monkeypatch):
        """Restore with tiny file returns 400."""
        restore_target = tempfile.mktemp(suffix='.db')
        try:
            monkeypatch.setattr(_api_module, '_DB_PATH', restore_target)
            with open(restore_target, 'wb') as f:
                f.write(b'original')

            rv = client.post('/api/restore', data={
                'file': (io.BytesIO(b'small'), 'tiny.db')
            }, content_type='multipart/form-data')
            assert rv.status_code == 400
            assert 'too small' in rv.json['error']
            with open(restore_target, 'rb') as f:
                assert f.read() == b'original'
        finally:
            try:
                os.unlink(restore_target)
            except OSError:
                pass

    def test_restore_missing_tables(self, client, monkeypatch):
        """Restore with SQLite missing required tables returns 400."""
        restore_target = tempfile.mktemp(suffix='.db')
        try:
            monkeypatch.setattr(_api_module, '_DB_PATH', restore_target)
            with open(restore_target, 'wb') as f:
                f.write(b'original data')

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
            tmp.close()
            try:
                conn = sqlite3.connect(tmp.name)
                conn.execute("CREATE TABLE foo (id INTEGER)")
                conn.close()
                with open(tmp.name, 'rb') as f:
                    incomplete_data = f.read()
            finally:
                os.unlink(tmp.name)

            rv = client.post('/api/restore', data={
                'file': (io.BytesIO(incomplete_data), 'incomplete.db')
            }, content_type='multipart/form-data')
            assert rv.status_code == 400
            assert 'missing tables' in rv.json['error']
            with open(restore_target, 'rb') as f:
                assert f.read() == b'original data'
        finally:
            try:
                os.unlink(restore_target)
            except OSError:
                pass

    def test_restore_auto_backup(self, client, monkeypatch):
        """Restore creates auto-backup before replacing."""
        valid_data = _make_valid_db_bytes()
        restore_target = tempfile.mktemp(suffix='.db')
        backup_calls = []
        try:
            monkeypatch.setattr(_api_module, '_DB_PATH', restore_target)
            with open(restore_target, 'wb') as f:
                f.write(b'old db content')

            def fake_backup(data, fn, mt):
                backup_calls.append((data, fn))
                return '/fake/' + fn, None
            monkeypatch.setattr(_api_module, '_save_to_downloads_full', fake_backup)

            real_replace = os.replace
            def fake_replace(src, dst):
                with open(src, 'rb') as src_f:
                    src_data = src_f.read()
                with open(dst, 'wb') as dst_f:
                    dst_f.write(src_data)
            monkeypatch.setattr(os, 'replace', fake_replace)

            rv = client.post('/api/restore', data={
                'file': (io.BytesIO(valid_data), 'restore.db')
            }, content_type='multipart/form-data')
            assert rv.status_code == 200
            assert len(backup_calls) == 1
            assert backup_calls[0][0] == b'old db content'
            assert 'teachhelper_backup_' in backup_calls[0][1]
        finally:
            for f in (restore_target, restore_target + '-wal', restore_target + '-shm'):
                try:
                    os.unlink(f)
                except OSError:
                    pass
