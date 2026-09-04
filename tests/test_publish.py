import io
import json
import os
import sys
import urllib.error

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import api as _api_module
from database import Database
import yandex_publish as yp


@pytest.fixture
def db():
    d = Database(':memory:')
    yield d
    d.close()


@pytest.fixture
def client():
    _api_module.app.config['TESTING'] = True
    original_db_fn = _api_module.get_db
    _db = Database(':memory:')
    _api_module.get_db = lambda: _db
    with _api_module.app.test_client() as c:
        yield c
    _db.close()
    _api_module.get_db = original_db_fn  # restore


def _setup_subject(client):
    gid = client.post('/api/groups', json={'name': 'ИС-11'}).json['id']
    sid = client.post('/api/subjects', json={
        'name': 'Математика', 'total_hours': 32, 'group_id': gid
    }).json['id']
    return gid, sid


# ======================== SETTINGS (DB) ========================

class TestSettings:
    def test_roundtrip(self, db):
        assert db.get_setting('yandex_token') is None
        db.set_setting('yandex_token', 'tok123')
        assert db.get_setting('yandex_token') == 'tok123'
        db.set_setting('yandex_token', 'tok456')
        assert db.get_setting('yandex_token') == 'tok456'
        db.set_setting('yandex_token', None)
        assert db.get_setting('yandex_token') is None

    def test_isolated_keys(self, db):
        db.set_setting('publish_url_1', 'http://a')
        db.set_setting('publish_url_2', 'http://b')
        assert db.get_setting('publish_url_1') == 'http://a'
        assert db.get_setting('publish_url_2') == 'http://b'


# ======================== YANDEX_PUBLISH (unit, fake net) ========================

class FakeResp:
    def __init__(self, payload: bytes):
        self._p = payload

    def read(self):
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _fake_urlopen_factory(script, record):
    """script: list of (kind, payload) consumed per call in order.
    kind: 'json' | 'empty' | 'http403'... via 'http401' | 'urlerror'."""
    def fake(req, timeout=None):
        record.append((req.get_method(), req.full_url,
                       dict(req.header_items())))
        kind, payload = script.pop(0)
        if kind == 'json':
            return FakeResp(json.dumps(payload).encode())
        if kind == 'empty':
            return FakeResp(b'')
        if kind == 'http401':
            raise urllib.error.HTTPError(req.full_url, 401, 'Unauthorized', {}, None)
        if kind == 'urlerror':
            raise urllib.error.URLError('dns fail')
        raise AssertionError('bad script kind')
    return fake


class TestYandexPublish:
    def test_check_ok(self):
        rec = []
        fake = _fake_urlopen_factory([('json', {'total_space': 10})], rec)
        assert yp.check_token('t', urlopen=fake) == {'total_space': 10}
        assert rec[0][2].get('Authorization') == 'OAuth t' or \
            rec[0][2].get('authorization') == 'OAuth t'

    def test_check_401(self):
        fake = _fake_urlopen_factory([('http401', None)], [])
        with pytest.raises(yp.YandexAuthError):
            yp.check_token('bad', urlopen=fake)

    def test_check_network(self):
        fake = _fake_urlopen_factory([('urlerror', None)], [])
        with pytest.raises(yp.YandexNetworkError):
            yp.check_token('t', urlopen=fake)

    def test_upload_publish_ok(self):
        rec = []
        fake = _fake_urlopen_factory([
            ('json', {'href': 'http://up', 'method': 'PUT'}),
            ('empty', None),
            ('empty', None),
            ('json', {'public_url': 'http://pub/file'}),
        ], rec)
        url = yp.upload_and_publish('t', '/TeachHelper/vedomost-1.xlsx', b'data', urlopen=fake)
        assert url == 'http://pub/file'
        methods = [m for m, _, _ in rec]
        assert methods[:2] == ['GET', 'PUT']

    def test_upload_no_href(self):
        fake = _fake_urlopen_factory([('json', {})], [])
        with pytest.raises(yp.YandexError):
            yp.upload_and_publish('t', '/x', b'd', urlopen=fake)

    def test_publish_no_url(self):
        fake = _fake_urlopen_factory([
            ('json', {'href': 'http://up'}),
            ('empty', None),
            ('empty', None),
            ('json', {}),
            ('json', {}),
        ], [])
        with pytest.raises(yp.YandexError):
            yp.upload_and_publish('t', '/x', b'd', urlopen=fake)


# ======================== API ========================

class TestPublishAPI:
    def test_no_token(self, client):
        _, sid = _setup_subject(client)
        rv = client.post(f'/api/publish/{sid}')
        assert rv.status_code == 400

    def test_touch_and_status(self, client):
        _, sid = _setup_subject(client)
        assert client.post(f'/api/publish/{sid}/touch').json == {'ok': True}
        st = client.get(f'/api/publish/{sid}/status').json
        assert st['pending'] is True
        assert st['url'] is None
        assert st['has_token'] is False

    def test_success_xlsx(self, client, monkeypatch):
        _, sid = _setup_subject(client)
        client.post('/api/settings/yandex', json={'token': 'tok', 'folder': '/T'})
        seen = {}

        def fake_upload(token, remote, data, urlopen=None):
            seen.update(token=token, remote=remote, data=data)
            return 'http://pub/vedomost'

        monkeypatch.setattr(_api_module, 'upload_and_publish', fake_upload)
        monkeypatch.setattr(_api_module, 'export_grades_xlsx', lambda sid_, db: b'XLSX')
        rv = client.post(f'/api/publish/{sid}')
        assert rv.status_code == 200, rv.json
        assert rv.json['url'] == 'http://pub/vedomost'
        assert seen['token'] == 'tok'
        assert seen['remote'] == '/T/vedomost-%d.xlsx' % sid
        assert seen['data'] == b'XLSX'
        st = client.get(f'/api/publish/{sid}/status').json
        assert st['url'] == 'http://pub/vedomost'
        assert st['pending'] is False
        assert st['time']

    def test_fallback_csv_without_openpyxl(self, client, monkeypatch):
        _, sid = _setup_subject(client)
        client.post('/api/settings/yandex', json={'token': 'tok'})

        def boom(sid_, db):
            raise RuntimeError('openpyxl not installed')

        seen = {}
        monkeypatch.setattr(_api_module, 'export_grades_xlsx', boom)
        monkeypatch.setattr(
            _api_module, 'upload_and_publish',
            lambda token, remote, data, urlopen=None: seen.update(remote=remote) or 'http://pub/c')
        rv = client.post(f'/api/publish/{sid}')
        assert rv.status_code == 200, rv.json
        assert seen['remote'].endswith('.csv')

    def test_auth_error(self, client, monkeypatch):
        _, sid = _setup_subject(client)
        client.post('/api/settings/yandex', json={'token': 'bad'})

        def bad(token, remote, data, urlopen=None):
            raise yp.YandexAuthError('bad yandex token (401)')

        monkeypatch.setattr(_api_module, 'upload_and_publish', bad)
        monkeypatch.setattr(_api_module, 'export_grades_xlsx', lambda sid_, db: b'X')
        rv = client.post(f'/api/publish/{sid}')
        assert rv.status_code == 401

    def test_network_error_sets_pending(self, client, monkeypatch):
        _, sid = _setup_subject(client)
        client.post('/api/settings/yandex', json={'token': 'tok'})

        def down(token, remote, data, urlopen=None):
            raise yp.YandexNetworkError('no connection')

        monkeypatch.setattr(_api_module, 'upload_and_publish', down)
        monkeypatch.setattr(_api_module, 'export_grades_xlsx', lambda sid_, db: b'X')
        rv = client.post(f'/api/publish/{sid}')
        assert rv.status_code == 502
        st = client.get(f'/api/publish/{sid}/status').json
        assert st['pending'] is True


class TestYandexSettingsAPI:
    def test_crud_no_leak(self, client):
        rv = client.get('/api/settings/yandex').json
        assert rv == {'has_token': False, 'folder': '/TeachHelper'}
        rv = client.post('/api/settings/yandex',
                         json={'token': ' secret ', 'folder': 'MyDir'}).json
        assert rv == {'ok': True, 'has_token': True, 'folder': '/MyDir'}
        rv = client.get('/api/settings/yandex').json
        assert rv == {'has_token': True, 'folder': '/MyDir'}
        assert 'secret' not in json.dumps(rv)
        assert client.delete('/api/settings/yandex').json == {'ok': True}
        assert client.get('/api/settings/yandex').json['has_token'] is False

    def test_check_ok(self, client, monkeypatch):
        client.post('/api/settings/yandex', json={'token': 'tok'})
        monkeypatch.setattr(_api_module, 'yandex_check_token',
                            lambda token, urlopen=None: {'total_space': 1})
        rv = client.get('/api/settings/yandex/check')
        assert rv.json['ok'] is True

    def test_check_no_token(self, client):
        rv = client.get('/api/settings/yandex/check')
        assert rv.status_code == 400
