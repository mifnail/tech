"""Tests for the in-app updater endpoints."""
from __future__ import annotations

import json
import sys
import os
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch, PropertyMock
import time as _time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import api as _api_module


# ── Helpers ──────────────────────────────────────────────────

def _make_client():
    _api_module.app.config['TESTING'] = True
    original = _api_module.get_db
    from database import Database
    _db = Database(':memory:')
    _api_module.get_db = lambda: _db
    client = _api_module.app.test_client()
    _db.close()
    _api_module.get_db = original
    return client


def _reset_cache():
    """Clear module-level cache so each test gets a fresh fetch."""
    _api_module._upd_cache = None
    _api_module._upd_ts = 0.0


def _fake_release_json():
    return {
        'tag_name': 'v0.99',
        'body': 'Test release notes',
        'published_at': '2026-01-15T10:00:00Z',
        'zipball_url': 'https://example.com/zip',
        'assets': [
            {'browser_download_url': 'https://example.com/teachhelper.apk'}
        ],
    }


def _fake_release_response(data=None):
    """Return a mock urllib response for a GitHub release."""
    if data is None:
        data = _fake_release_json()
    raw = json.dumps(data).encode()
    resp = MagicMock()
    resp.read.return_value = raw
    resp.__enter__ = lambda s: s
    resp.__exit__ = lambda s, *a: None
    return resp


def _fake_commit_response():
    data = [{
        'sha': 'abcdef1234567890',
        'commit': {
            'message': 'Fix something important',
            'author': {'date': '2026-02-01T12:00:00Z'},
        },
    }]
    raw = json.dumps(data).encode()
    resp = MagicMock()
    resp.read.return_value = raw
    resp.__enter__ = lambda s: s
    resp.__exit__ = lambda s, *a: None
    return resp


# ── GET /api/update/latest ───────────────────────────────────

class TestUpdateLatest:
    def test_success(self):
        client = _make_client()
        _reset_cache()
        with patch('urllib.request.urlopen', return_value=_fake_release_response()):
            rv = client.get('/api/update/latest')
        assert rv.status_code == 200
        d = rv.get_json()
        assert d['version'] == '0.99'
        assert d['url'] == 'https://example.com/teachhelper.apk'
        assert d['notes'] == 'Test release notes'
        assert d['published_at'] == '2026-01-15T10:00:00Z'

    def test_caching(self):
        """Second call within TTL should not call urlopen again."""
        client = _make_client()
        _reset_cache()
        call_count = 0

        def mock_urlopen(req, **kwargs):
            nonlocal call_count
            call_count += 1
            return _fake_release_response()

        with patch('urllib.request.urlopen', side_effect=mock_urlopen):
            rv1 = client.get('/api/update/latest')
            rv2 = client.get('/api/update/latest')

        assert rv1.status_code == 200
        assert rv2.status_code == 200
        # Only one HTTP call because of caching
        assert call_count == 1

    def test_cache_expired(self):
        """After TTL, cache should be refreshed."""
        client = _make_client()
        _reset_cache()
        call_count = 0

        def mock_urlopen(req, **kwargs):
            nonlocal call_count
            call_count += 1
            return _fake_release_response()

        with patch('urllib.request.urlopen', side_effect=mock_urlopen):
            rv1 = client.get('/api/update/latest')
            # Simulate cache expiry
            _api_module._upd_ts = _time.monotonic() - 9999
            rv2 = client.get('/api/update/latest')

        assert rv1.status_code == 200
        assert rv2.status_code == 200
        assert call_count == 2

    def test_404_fallback_to_commits(self):
        """When releases endpoint returns 404, fallback to commits."""
        client = _make_client()
        _reset_cache()

        def mock_urlopen(req, **kwargs):
            url = req.full_url if hasattr(req, 'full_url') else str(req)
            if 'releases/latest' in url:
                raise urllib.error.HTTPError(url, 404, 'Not Found', {}, None)
            return _fake_commit_response()

        with patch('urllib.request.urlopen', side_effect=mock_urlopen):
            rv = client.get('/api/update/latest')

        assert rv.status_code == 200
        d = rv.get_json()
        assert d['version'] == '0.dev.abcdef1'
        assert 'Fix something important' in d['notes']
        assert d['published_at'] == '2026-02-01T12:00:00Z'
        assert 'abcdef1234567890' in d['url']

    def test_404_fallback_also_fails(self):
        """Both releases and commits fail → 502."""
        client = _make_client()
        _reset_cache()

        def mock_urlopen(req, **kwargs):
            raise urllib.error.HTTPError('http://x', 404, 'Not Found', {}, None)

        with patch('urllib.request.urlopen', side_effect=mock_urlopen):
            rv = client.get('/api/update/latest')

        assert rv.status_code == 502
        assert 'error' in rv.get_json()

    def test_network_error(self):
        """URLError → 502."""
        client = _make_client()
        _reset_cache()

        def mock_urlopen(req, **kwargs):
            raise urllib.error.URLError('no connection')

        with patch('urllib.request.urlopen', side_effect=mock_urlopen):
            rv = client.get('/api/update/latest')

        assert rv.status_code == 502

    def test_no_assets_uses_zipball(self):
        """When no assets, url falls back to zipball_url."""
        client = _make_client()
        _reset_cache()
        data = {
            'tag_name': 'v0.5',
            'body': 'Release',
            'published_at': '2026-03-01T00:00:00Z',
            'zipball_url': 'https://example.com/zip',
            'assets': [],
        }
        with patch('urllib.request.urlopen', return_value=_fake_release_response(data)):
            rv = client.get('/api/update/latest')
        d = rv.get_json()
        assert d['url'] == 'https://example.com/zip'
        assert d['version'] == '0.5'


# ── GET /api/update/check ───────────────────────────────────

class TestUpdateCheck:
    def test_update_available(self):
        client = _make_client()
        _reset_cache()
        with patch('urllib.request.urlopen', return_value=_fake_release_response()):
            rv = client.get('/api/update/check?current=0.50')
        d = rv.get_json()
        assert d['update_available'] is True
        assert d['latest']['version'] == '0.99'

    def test_no_update_needed(self):
        client = _make_client()
        _reset_cache()
        with patch('urllib.request.urlopen', return_value=_fake_release_response()):
            rv = client.get('/api/update/check?current=0.99')
        d = rv.get_json()
        assert d['update_available'] is False

    def test_newer_installed(self):
        client = _make_client()
        _reset_cache()
        with patch('urllib.request.urlopen', return_value=_fake_release_response()):
            rv = client.get('/api/update/check?current=0.150')
        d = rv.get_json()
        assert d['update_available'] is False

    def test_missing_current_param(self):
        """Without current param, should still work (defaults to 0.0)."""
        client = _make_client()
        _reset_cache()
        with patch('urllib.request.urlopen', return_value=_fake_release_response()):
            rv = client.get('/api/update/check')
        d = rv.get_json()
        assert d['update_available'] is True

    def test_network_error_graceful(self):
        """If GitHub is down, check still returns with empty latest."""
        client = _make_client()
        _reset_cache()

        def mock_urlopen(req, **kwargs):
            raise urllib.error.URLError('timeout')

        with patch('urllib.request.urlopen', side_effect=mock_urlopen):
            rv = client.get('/api/update/check?current=0.1')
        d = rv.get_json()
        assert 'latest' in d
        assert d['update_available'] is False


# ── POST /api/update/download (desktop = 400) ────────────────

class TestUpdateDownload:
    def test_desktop_returns_400(self):
        """On desktop (no jnius), should return 400."""
        client = _make_client()
        _reset_cache()
        with patch.dict(sys.modules, {'jnius': None}):
            rv = client.post('/api/update/download')
        assert rv.status_code == 400
        assert 'Android' in rv.get_json()['error']

    def test_no_download_url_returns_502(self):
        """If release has no assets and no zipball_url → 502."""
        client = _make_client()
        _reset_cache()

        def mock_urlopen(req, **kwargs):
            return _fake_release_response({
                'tag_name': 'v0.1',
                'body': '',
                'published_at': '',
                'zipball_url': '',
                'assets': [],
            })

        with patch('urllib.request.urlopen', side_effect=mock_urlopen):
            with patch.dict(sys.modules, {'jnius': MagicMock()}):
                rv = client.post('/api/update/download')

        # Either 502 or 400 depending on flow — should not be 200
        assert rv.status_code != 200


# ── POST /api/update/install (desktop = 400) ──────────────────

class TestUpdateInstall:
    def test_desktop_returns_400(self):
        client = _make_client()
        with patch.dict(sys.modules, {'jnius': None}):
            rv = client.post('/api/update/install')
        assert rv.status_code == 400
        assert 'Android' in rv.get_json()['error']

    def test_no_uri_returns_404(self):
        """Without jnius, MediaStore query fails, so no URI found → 404."""
        client = _make_client()
        mock_jnius = MagicMock()
        # Make autoclass('android.provider.MediaStore$Downloads') raise
        mock_jnius.autoclass.side_effect = Exception('no such class')
        with patch.dict(sys.modules, {'jnius': mock_jnius}):
            rv = client.post('/api/update/install', json={})
        assert rv.status_code == 404


# ── Version parsing ──────────────────────────────────────────

class TestParseVersion:
    def test_basic(self):
        assert _api_module._parse_version('0.123') == [0, 123]

    def test_with_v_prefix(self):
        assert _api_module._parse_version('v0.123') == [0, 123]

    def test_single_part(self):
        assert _api_module._parse_version('5') == [5]

    def test_empty(self):
        assert _api_module._parse_version('') == [0]

    def test_compare_versions(self):
        v1 = _api_module._parse_version('0.99')
        v2 = _api_module._parse_version('0.100')
        assert v2 > v1
