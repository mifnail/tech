import io
import os
import sqlite3
import sys
import tempfile
from datetime import date

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
            assert 'file too small' in rv.json['error']
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
            assert 'file too small' in rv.json['error']
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
            assert set(entries[0].keys()) == {'name', 'size', 'mtime', 'path'}
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

    def test_list_backup_files_broadened_and_sorted(self, monkeypatch):
        """Any *.db is found; teachhelper_* still sort before other *.db files."""
        d = tempfile.mkdtemp()
        p_th_old = os.path.join(d, 'teachhelper_2026-01-01.db')
        p_th_new = os.path.join(d, 'teachhelper_2026-01-02.db')
        p_other = os.path.join(d, 'other.db')
        try:
            for p, data in ((p_th_old, b'aa'), (p_th_new, b'bbb'), (p_other, b'cccc')):
                with open(p, 'wb') as f:
                    f.write(data)
            os.utime(p_th_old, (1000, 1000))
            os.utime(p_th_new, (2000, 2000))
            # other.db is newest overall but must still sort after teachhelper_*.
            os.utime(p_other, (3000, 3000))
            monkeypatch.setattr(_api_module, '_is_android', lambda: False)
            monkeypatch.setattr(_api_module._glob, 'glob',
                                lambda pattern: [p_other, p_th_old, p_th_new])

            entries = _api_module._list_backup_files()
            names = [e['name'] for e in entries]
            assert set(names) == {'teachhelper_2026-01-01.db',
                                  'teachhelper_2026-01-02.db', 'other.db'}
            assert names == ['teachhelper_2026-01-02.db',
                             'teachhelper_2026-01-01.db', 'other.db']
            assert entries[0]['path'] == p_th_new
            assert entries[2]['path'] == p_other
            assert set(entries[0].keys()) == {'name', 'size', 'mtime', 'path'}
        finally:
            for f in (p_th_old, p_th_new, p_other):
                try:
                    os.unlink(f)
                except OSError:
                    pass
            try:
                os.rmdir(d)
            except OSError:
                pass

    def test_valid_backup_name_broadened(self):
        """Any plain *.db basename is accepted; paths / non-.db are rejected."""
        assert _api_module._valid_backup_name('other.db') is True
        assert _api_module._valid_backup_name('teachhelper_2026-01-01.db') is True
        for bad in ('../evil.db', '/abs.db', 'x.txt', 'sub/evil.db',
                    '..evil.db', '.', '', None, 123, 'a\\b.db'):
            assert _api_module._valid_backup_name(bad) is False, bad


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
        """POST /api/restore/named returns 400 for non-basename / non-.db names."""
        for bad in ['../teachhelper_x.db', 'teachhelper',
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

    def test_restore_named_non_teachhelper(self, client, monkeypatch):
        """POST /api/restore/named accepts any valid *.db basename."""
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

            rv = client.post('/api/restore/named', json={'name': 'other.db'})
            assert rv.status_code == 200
            assert rv.json['ok'] is True
            assert rv.json['name'] == 'other.db'
            assert written['data'] == valid_data
        finally:
            for f in (restore_target, restore_target + '-wal', restore_target + '-shm'):
                try:
                    os.unlink(f)
                except OSError:
                    pass


class TestRestorePick:
    def test_restore_pick_desktop_400(self, client, monkeypatch):
        """POST /api/restore/pick is Android-only: 400 without a device module."""
        monkeypatch.setattr(_api_module, '_is_android', lambda: False)
        rv = client.post('/api/restore/pick', json={})
        assert rv.status_code == 400
        assert rv.json['error'] == 'Доступно только на Android'

    def test_on_pick_result_stores_uri_not_bytes(self, monkeypatch):
        """Activity-result callback stores the URI + name only (no byte read)."""
        class FakeUri:
            def getLastPathSegment(self):
                return 'picked.db'
        class FakeIntent:
            def getData(self):
                return FakeUri()
        class DummyResolver:
            def query(self, *a, **k):
                return None
        _api_module._file_pick.update({'code': -1, 'uri': None, 'name': None,
                                      'error': None, 'stage': None})
        _api_module._file_pick['event'].clear()
        monkeypatch.setattr(_api_module, '_android_resolver', lambda: DummyResolver())

        def must_not_read(uri):
            raise AssertionError('must not read bytes on the UI thread')
        monkeypatch.setattr(_api_module, '_read_picked_uri', must_not_read)

        _api_module._on_pick_result(_api_module._REQUEST_CODE, -1, FakeIntent())
        assert _api_module._file_pick['code'] == 4242
        assert _api_module._file_pick['uri'] is not None
        assert _api_module._file_pick['name'] == 'picked.db'
        assert _api_module._file_pick['event'].is_set()

    def test_restore_pick_roundtrip(self, client, monkeypatch):
        """Handler reads bytes (mocked) from the coordinator URI and restores."""
        valid_data = _make_valid_db_bytes()
        restore_target = tempfile.mktemp(suffix='.db')
        try:
            monkeypatch.setattr(_api_module, '_DB_PATH', restore_target)
            with open(restore_target, 'wb') as f:
                f.write(b'old data')

            captured = {}
            real_replace = os.replace
            def fake_replace(src, dst):
                with open(src, 'rb') as f:
                    captured['data'] = f.read()
                real_replace(src, dst)
            monkeypatch.setattr(os, 'replace', fake_replace)
            monkeypatch.setattr(_api_module, '_save_to_downloads_full',
                                lambda data, fn, mt: ('/bak', None))
            monkeypatch.setattr(_api_module, '_is_android', lambda: True)
            monkeypatch.setattr(_api_module, '_picker_available', lambda: True)
            monkeypatch.setattr(_api_module, '_restore_from_bytes',
                                lambda data: captured.update(data=data))
            monkeypatch.setattr(_api_module, '_read_picked_uri', lambda uri: valid_data)

            def fake_start():
                _api_module._file_pick['uri'] = object()
                _api_module._file_pick['name'] = 'picked.db'
                _api_module._file_pick['event'].set()
            monkeypatch.setattr(_api_module, '_start_picker', fake_start)

            rv = client.post('/api/restore/pick', json={})
            assert rv.status_code == 200
            assert rv.json['ok'] is True
            assert rv.json['name'] == 'picked.db'
            assert captured['data'] == valid_data
        finally:
            for f in (restore_target, restore_target + '-wal', restore_target + '-shm'):
                try:
                    os.unlink(f)
                except OSError:
                    pass

    def test_restore_pick_timeout_504(self, client, monkeypatch):
        """No callback before the timeout returns 504."""
        monkeypatch.setattr(_api_module, '_is_android', lambda: True)
        monkeypatch.setattr(_api_module, '_picker_available', lambda: True)
        monkeypatch.setattr(_api_module, '_PICK_TIMEOUT', 0)
        monkeypatch.setattr(_api_module, '_start_picker', lambda: None)

        rv = client.post('/api/restore/pick', json={})
        assert rv.status_code == 504
        assert 'picker: timeout' in rv.json['error']

    def test_restore_pick_cancelled_404(self, client, monkeypatch):
        """A cancelled pick (no URI, no error) returns 404."""
        monkeypatch.setattr(_api_module, '_is_android', lambda: True)
        monkeypatch.setattr(_api_module, '_picker_available', lambda: True)

        def fake_start():
            _api_module._file_pick['stage'] = 'result'
            _api_module._file_pick['event'].set()
        monkeypatch.setattr(_api_module, '_start_picker', fake_start)

        rv = client.post('/api/restore/pick', json={})
        assert rv.status_code == 404
        assert 'отменён' in rv.json['error']

    def test_restore_pick_read_error_500(self, client, monkeypatch):
        """A byte-read failure in the handler is surfaced with stage='read'."""
        monkeypatch.setattr(_api_module, '_is_android', lambda: True)
        monkeypatch.setattr(_api_module, '_picker_available', lambda: True)

        def fake_start():
            _api_module._file_pick['uri'] = object()
            _api_module._file_pick['event'].set()
        monkeypatch.setattr(_api_module, '_start_picker', fake_start)

        def boom(uri):
            raise RuntimeError('cannot read stream')
        monkeypatch.setattr(_api_module, '_read_picked_uri', boom)

        rv = client.post('/api/restore/pick', json={})
        assert rv.status_code == 500
        assert rv.json['error'] == 'picker: read: cannot read stream'

    def test_restore_pick_diag_desktop(self, client, monkeypatch):
        """GET /api/restore/pick/diag reports {'android': False} off-device."""
        monkeypatch.setattr(_api_module, '_is_android', lambda: False)
        rv = client.get('/api/restore/pick/diag')
        assert rv.status_code == 200
        assert rv.json == {'android': False}

    def test_restore_pick_surfaces_error(self, client, monkeypatch):
        """The handler returns 500 with the exact stage + error text."""
        monkeypatch.setattr(_api_module, '_is_android', lambda: True)
        monkeypatch.setattr(_api_module, '_picker_available', lambda: True)

        def fake_start():
            _api_module._file_pick['stage'] = 'launch'
            _api_module._file_pick['error'] = 'boom launch'
            _api_module._file_pick['event'].set()
        monkeypatch.setattr(_api_module, '_start_picker', fake_start)

        rv = client.post('/api/restore/pick', json={})
        assert rv.status_code == 500
        assert rv.json['error'] == 'picker: launch: boom launch'

    def test_restore_pick_unavailable_503(self, client, monkeypatch):
        """When the picker is unavailable the route returns 503 JSON."""
        monkeypatch.setattr(_api_module, '_is_android', lambda: True)
        monkeypatch.setattr(_api_module, '_picker_available', lambda: False)
        rv = client.post('/api/restore/pick', json={})
        assert rv.status_code == 503
        assert rv.json['picker'] is False
        assert 'недоступен' in rv.json['error']

    def test_restore_pick_start_raises_returns_json(self, client, monkeypatch):
        """A raising _start_picker becomes a JSON 500, never HTML."""
        monkeypatch.setattr(_api_module, '_is_android', lambda: True)
        monkeypatch.setattr(_api_module, '_picker_available', lambda: True)

        def boom():
            raise RuntimeError('kaboom')
        monkeypatch.setattr(_api_module, '_start_picker', boom)

        rv = client.post('/api/restore/pick', json={})
        assert rv.status_code == 500
        assert rv.json['error'] == 'picker: launch: kaboom'
        assert rv.content_type.startswith('application/json')

    def test_restore_pick_diag_android_shape(self, client, monkeypatch):
        """Android-path diag exposes picker_available + activity_source."""
        monkeypatch.setattr(_api_module, '_is_android', lambda: True)
        rv = client.get('/api/restore/pick/diag')
        assert rv.status_code == 200
        body = rv.json
        for key in ('android', 'bind', 'ui_thread', 'activity',
                    'picker_bound', 'picker_available', 'activity_source'):
            assert key in body, key
        assert body['android'] is True
        # No android/jnius modules on desktop, so the picker is unavailable.
        assert body['picker_available'] is False


class TestLatestExcludesAutobackup:
    def test_find_latest_skips_autobackup(self, monkeypatch):
        """_find_latest_backup_bytes ignores teachhelper_backup_* autobackups."""
        entries = [
            {'name': 'teachhelper_backup_20260103_120000.db', 'size': 1,
             'mtime': 3000, 'path': None},
            {'name': 'teachhelper_2026-01-02.db', 'size': 2, 'mtime': 2000, 'path': None},
        ]
        monkeypatch.setattr(_api_module, '_list_backup_files', lambda: entries)
        read = {}
        def fake_read(name):
            read['name'] = name
            return b'DATA'
        monkeypatch.setattr(_api_module, '_read_backup_bytes', fake_read)

        data, name = _api_module._find_latest_backup_bytes()
        assert name == 'teachhelper_2026-01-02.db'
        assert read['name'] == 'teachhelper_2026-01-02.db'
        assert data == b'DATA'

    def test_find_latest_only_autobackups_raises(self, monkeypatch):
        """If only autobackups exist, latest raises BackupNotFound."""
        entries = [
            {'name': 'teachhelper_backup_20260103_120000.db', 'size': 1,
             'mtime': 3000, 'path': None},
        ]
        monkeypatch.setattr(_api_module, '_list_backup_files', lambda: entries)
        with pytest.raises(_api_module.BackupNotFound):
            _api_module._find_latest_backup_bytes()

    def test_backup_list_includes_autobackup(self, client, monkeypatch):
        """GET /api/backup/list still shows autobackups."""
        monkeypatch.setattr(_api_module, '_list_backup_files', lambda: [
            {'name': 'teachhelper_backup_20260103_120000.db', 'size': 1,
             'mtime': 3000, 'path': None},
        ])
        rv = client.get('/api/backup/list')
        assert rv.status_code == 200
        assert rv.json['backups'][0]['name'] == 'teachhelper_backup_20260103_120000.db'


class TestAllFilesAccess:
    def test_has_all_files_access_desktop_false(self):
        """Without jnius (desktop) all-files access is reported False."""
        assert _api_module._has_all_files_access() is False

    def test_restore_access_desktop_granted_true(self, client, monkeypatch):
        """GET /api/restore/access is granted on desktop (no UI nagging)."""
        monkeypatch.setattr(_api_module, '_is_android', lambda: False)
        rv = client.get('/api/restore/access')
        assert rv.status_code == 200
        assert rv.json == {'granted': True}

    def test_restore_request_access_desktop_400(self, client, monkeypatch):
        """POST /api/restore/request-access is Android-only."""
        monkeypatch.setattr(_api_module, '_is_android', lambda: False)
        rv = client.post('/api/restore/request-access', json={})
        assert rv.status_code == 400
        assert rv.json['error'] == 'Доступно только на Android'


class TestBackupShare:
    """Tests for POST /api/backup/share."""

    def test_share_saves_and_returns_shared_true(self, client, monkeypatch):
        """On Android with URI, saves file and returns shared=True."""
        captured = {}
        def fake_save(data, filename, mimetype):
            captured['data'] = data
            captured['filename'] = filename
            return '/fake/path/' + filename, 'content://media/123'
        monkeypatch.setattr(_api_module, '_save_to_downloads_full', fake_save)
        share_called = [False]
        def fake_share(uri, mime, label):
            share_called[0] = True
            assert uri == 'content://media/123'
            assert mime == 'application/x-sqlite3'
        monkeypatch.setattr(_api_module, '_share_file', fake_share)

        rv = client.post('/api/backup/share')
        assert rv.status_code == 200
        body = rv.json
        assert body['ok'] is True
        assert body['shared'] is True
        assert body['path'] == f"/fake/path/teachhelper_{date.today().isoformat()}.db"
        assert captured['data'][:16] == b'SQLite format 3\x00'
        assert 'teachhelper_' in captured['filename']
        assert share_called[0]

    def test_share_no_uri_returns_shared_false(self, client, monkeypatch):
        """On desktop (uri=None), saves file but shared=False."""
        def fake_save(data, filename, mimetype):
            return '/fake/path/' + filename, None
        monkeypatch.setattr(_api_module, '_save_to_downloads_full', fake_save)

        rv = client.post('/api/backup/share')
        assert rv.status_code == 200
        body = rv.json
        assert body['ok'] is True
        assert body['shared'] is False
        assert 'path' in body

    def test_share_exception_returns_shared_false(self, client, monkeypatch):
        """When share fails, still returns ok with shared=False and error."""
        def fake_save(data, filename, mimetype):
            return '/fake/path/' + filename, 'content://media/456'
        monkeypatch.setattr(_api_module, '_save_to_downloads_full', fake_save)
        def fake_share(uri, mime, label):
            raise RuntimeError('share failed')
        monkeypatch.setattr(_api_module, '_share_file', fake_share)

        rv = client.post('/api/backup/share')
        assert rv.status_code == 200
        body = rv.json
        assert body['ok'] is True
        assert body['shared'] is False
        assert 'error' in body
        assert 'share failed' in body['error']

    def test_share_read_error(self, client, monkeypatch):
        """Handles DB read error gracefully."""
        real_open = open
        def bad_open(path, *args, **kwargs):
            if isinstance(path, str) and path == _api_module._DB_PATH and args and args[0] == 'rb':
                raise PermissionError('nope')
            return real_open(path, *args, **kwargs)
        monkeypatch.setattr('builtins.open', bad_open)
        rv = client.post('/api/backup/share')
        assert rv.status_code == 500
        assert 'error' in rv.json
