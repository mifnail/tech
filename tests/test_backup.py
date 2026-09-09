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


class TestRestoreLatest:
    def test_restore_latest_ok(self, client, monkeypatch):
        """POST /api/restore/latest replaces DB with found backup."""
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

            def fake_find():
                return valid_data, 'teachhelper_2026-01-01.db'
            monkeypatch.setattr(_api_module, '_find_latest_backup_bytes', fake_find)

            rv = client.post('/api/restore/latest')
            assert rv.status_code == 200
            assert rv.json['ok'] is True
            assert rv.json['name'] == 'teachhelper_2026-01-01.db'
            assert written['data'] == valid_data
        finally:
            for f in (restore_target, restore_target + '-wal', restore_target + '-shm'):
                try:
                    os.unlink(f)
                except OSError:
                    pass

    def test_restore_latest_not_found(self, client, monkeypatch):
        """POST /api/restore/latest returns 404 when no backup exists."""
        def fake_find():
            raise _api_module.BackupNotFound('no backup files found')
        monkeypatch.setattr(_api_module, '_find_latest_backup_bytes', fake_find)

        rv = client.post('/api/restore/latest')
        assert rv.status_code == 404
        assert 'no backup' in rv.json['error']

    def test_restore_latest_corrupt(self, client, monkeypatch):
        """POST /api/restore/latest returns 400 for corrupt backup, original intact."""
        restore_target = tempfile.mktemp(suffix='.db')
        try:
            monkeypatch.setattr(_api_module, '_DB_PATH', restore_target)
            with open(restore_target, 'wb') as f:
                f.write(b'original data')

            def fake_find():
                return b'not sqlite at all', 'teachhelper_bad.db'
            monkeypatch.setattr(_api_module, '_find_latest_backup_bytes', fake_find)

            rv = client.post('/api/restore/latest')
            assert rv.status_code == 400
            assert 'not a SQLite' in rv.json['error']
            with open(restore_target, 'rb') as f:
                assert f.read() == b'original data'
        finally:
            try:
                os.unlink(restore_target)
            except OSError:
                pass


class TestDrainPfd:
    def test_drain_normal(self):
        # write known bytes to temp file, drain via detachFd
        data = b'hello world \x00\xff end'
        fd, path = tempfile.mkstemp()
        try:
            os.write(fd, data)
            os.close(fd)
            fd2 = os.open(path, os.O_RDONLY)
            class Stub:
                def detachFd(self):
                    return fd2
                def close(self):
                    raise AssertionError('close should not be called on success path')
            out = _api_module._drain_pfd(Stub())
            assert out == data
            # fd should be closed after drain
            try:
                os.read(fd2, 1)
                assert False, 'fd should be closed after _drain_pfd'
            except OSError:
                pass
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def test_drain_empty(self):
        fd, path = tempfile.mkstemp()
        try:
            os.close(fd)
            fd2 = os.open(path, os.O_RDONLY)
            class Stub:
                def detachFd(self):
                    return fd2
                def close(self):
                    raise AssertionError('close should not be called on success')
            out = _api_module._drain_pfd(Stub())
            assert out == b''
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def test_detach_raises_calls_close_and_propagates(self):
        closed = {'v': False}
        class Stub:
            def detachFd(self):
                raise RuntimeError('detach fail')
            def close(self):
                closed['v'] = True
        with pytest.raises(RuntimeError, match='detach fail'):
            _api_module._drain_pfd(Stub())
        assert closed['v'] is True


class TestListBackupFiles:
    def test_list_backup_files_desktop(self, monkeypatch):
        """Desktop enumeration finds >0 backups and returns them newest-first."""
        d = tempfile.mkdtemp()
        p_old = os.path.join(d, 'teachhelper_2026-01-01.db')
        p_new = os.path.join(d, 'teachhelper_2026-01-02.db')
        try:
            with open(p_old, 'wb') as f:
                f.write(b'11111')
            with open(p_new, 'wb') as f:
                f.write(b'222')
            os.utime(p_old, (1000, 1000))
            os.utime(p_new, (2000, 2000))
            monkeypatch.setattr(_api_module, '_is_android', lambda: False)
            monkeypatch.setattr(_api_module._glob, 'glob', lambda pattern: [p_old, p_new])

            entries = _api_module._list_backup_files()
            assert len(entries) == 2
            assert entries[0]['name'] == 'teachhelper_2026-01-02.db'
            assert entries[1]['name'] == 'teachhelper_2026-01-01.db'
            assert entries[0]['size'] == 3
            assert entries[1]['size'] == 5
            assert entries[0]['mtime'] == 2000.0
            assert entries[1]['mtime'] == 1000.0
            # sorted newest-first by mtime
            assert entries[0]['mtime'] > entries[1]['mtime']
            assert set(entries[0].keys()) == {'name', 'size', 'mtime'}
        finally:
            for f in (p_old, p_new):
                try:
                    os.unlink(f)
                except OSError:
                    pass
            try:
                os.rmdir(d)
            except OSError:
                pass

    def test_list_backup_files_desktop_empty(self, monkeypatch):
        """Desktop enumeration returns [] when matching files do not exist."""
        monkeypatch.setattr(_api_module, '_is_android', lambda: False)
        monkeypatch.setattr(_api_module._glob, 'glob', lambda pattern: [])
        assert _api_module._list_backup_files() == []


class TestBackupList:
    def test_backup_list_shape(self, client, monkeypatch):
        """GET /api/backup/list returns {backups:[{name,size,mtime}]}."""
        monkeypatch.setattr(_api_module, '_list_backup_files', lambda: [
            {'name': 'teachhelper_2026-01-02.db', 'size': 12, 'mtime': 2000.0},
            {'name': 'teachhelper_2026-01-01.db', 'size': 5, 'mtime': 1000.0},
        ])
        rv = client.get('/api/backup/list')
        assert rv.status_code == 200
        assert rv.json == {'backups': [
            {'name': 'teachhelper_2026-01-02.db', 'size': 12, 'mtime': 2000.0},
            {'name': 'teachhelper_2026-01-01.db', 'size': 5, 'mtime': 1000.0},
        ]}

    def test_backup_list_empty(self, client, monkeypatch):
        """GET /api/backup/list returns an empty array when no backups exist."""
        monkeypatch.setattr(_api_module, '_list_backup_files', lambda: [])
        rv = client.get('/api/backup/list')
        assert rv.status_code == 200
        assert rv.json == {'backups': []}


class TestRestoreNamed:
    def test_restore_named_ok(self, client, monkeypatch):
        """POST /api/restore/named replaces the DB with the named backup."""
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
            monkeypatch.setattr(_api_module, '_read_backup_bytes', lambda name: valid_data)

            rv = client.post('/api/restore/named', json={'name': 'teachhelper_2026-01-01.db'})
            assert rv.status_code == 200
            assert rv.json['ok'] is True
            assert rv.json['name'] == 'teachhelper_2026-01-01.db'
            assert written['data'] == valid_data
        finally:
            for f in (restore_target, restore_target + '-wal', restore_target + '-shm'):
                try:
                    os.unlink(f)
                except OSError:
                    pass

    def test_restore_named_invalid(self, client, monkeypatch):
        """POST /api/restore/named returns 400 for non-basename names."""
        for bad in ['../teachhelper_x.db', 'teachhelper', 'evil.db',
                    'teachhelper_2026.db/..', '', 'a/b.db',
                    'teachhelper_2026-01-01.dbc', 123, None]:
            rv = client.post('/api/restore/named', json={'name': bad})
            assert rv.status_code == 400, bad

    def test_restore_named_not_found(self, client, monkeypatch):
        """POST /api/restore/named returns 404 when the backup is missing."""
        def fake_read(name):
            raise _api_module.BackupNotFound('no backup file: teachhelper_none.db')
        monkeypatch.setattr(_api_module, '_read_backup_bytes', fake_read)
        rv = client.post('/api/restore/named', json={'name': 'teachhelper_none.db'})
        assert rv.status_code == 404
        assert 'no backup' in rv.json['error']
