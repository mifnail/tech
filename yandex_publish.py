"""Публикация ведомостей на Яндекс Диск.

Только стандартная библиотека (urllib) — новых зависимостей в APK нет.
Каждый преподаватель подключает СВОЙ Диск: токен вводится в настройках
приложения (oauth.yandex.ru) и хранится локально в БД телефона.

Схема: upload (PUT по href) -> publish -> public_url (постоянная ссылка).
Файл перезаписывается, ссылка не меняется.
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request

API = 'https://cloud-api.yandex.net/v1/disk'

def _ssl_ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        try:
            return ssl.create_default_context()
        except Exception:
            return ssl._create_unverified_context()

_CTX = _ssl_ctx()
_UNVERIFIED_CTX = ssl._create_unverified_context()


class YandexError(Exception):
    """Общая ошибка Диска (4xx/5xx, нет ссылки и т.п.)."""


class YandexAuthError(YandexError):
    """Неверный/отозванный токен (401)."""


class YandexNetworkError(YandexError):
    """Нет связи (DNS/timeout/сеть)."""


def _open(req, *, timeout=30, urlopen=None, ctx=None):
    if urlopen is not None:
        return urlopen(req, timeout=timeout)
    if ctx is not None:
        return urllib.request.urlopen(req, timeout=timeout, context=ctx)
    return urllib.request.urlopen(req, timeout=timeout, context=_CTX)

def _call(method: str, url: str, token: str, data: bytes | None = None,
          content_type: str | None = None, urlopen=None) -> dict:
    """Один HTTP-вызов к Disk API. urlopen инжектится ради тестов."""
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Authorization', f'OAuth {token}')
    req.add_header('Accept', 'application/json')
    if content_type:
        req.add_header('Content-Type', content_type)
    try:
        with _open(req, timeout=30, urlopen=urlopen) as resp:
            raw = resp.read()
            if not raw:
                return {}
            try:
                return json.loads(raw.decode('utf-8'))
            except ValueError:
                return {}
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise YandexAuthError('bad yandex token (401)')
        if e.code == 404:
            raise YandexError('not found on disk (404)')
        if e.code == 409:
            raise YandexError('disk conflict (409)')
        raise YandexError(f'yandex api error: HTTP {e.code}')
    except urllib.error.URLError as e:
        reason = str(e.reason)
        # На Android часто нет системных CA — пробуем без проверки сертификата
        if 'CERTIFICATE_VERIFY_FAILED' in reason and urlopen is None:
            try:
                with _open(req, timeout=30, urlopen=None, ctx=_UNVERIFIED_CTX) as resp:
                    raw = resp.read()
                    if not raw:
                        return {}
                    try:
                        return json.loads(raw.decode('utf-8'))
                    except ValueError:
                        return {}
            except Exception as e2:
                raise YandexNetworkError(f'no connection: {e2}')
        raise YandexNetworkError(f'no connection: {e.reason}')


def check_token(token: str, urlopen=None) -> dict:
    """Проверка токена: GET /v1/disk/ (инфо о Диске). 401 -> YandexAuthError."""
    return _call('GET', API + '/', token, urlopen=urlopen)


def _enc(path: str) -> str:
    return urllib.parse.quote(path, safe='')


def upload_and_publish(token: str, remote_path: str, data: bytes, urlopen=None) -> str:
    """Залить байты с перезаписью, опубликовать, вернуть постоянную public_url."""
    up = _call('GET', API + '/resources/upload?path=' + _enc(remote_path) + '&overwrite=true',
               token, urlopen=urlopen)
    href = up.get('href')
    if not href:
        raise YandexError('no upload href from disk')
    _call('PUT', href, token, data=data,
          content_type='application/octet-stream', urlopen=urlopen)
    _call('PUT', API + '/resources/publish?path=' + _enc(remote_path), token, urlopen=urlopen)
    info = _call('GET', API + '/resources?path=' + _enc(remote_path), token, urlopen=urlopen)
    url = info.get('public_url')
    if not url:
        # Публикация иногда применяется с задержкой — одна повторная проверка.
        info = _call('GET', API + '/resources?path=' + _enc(remote_path), token, urlopen=urlopen)
        url = info.get('public_url')
    if not url:
        raise YandexError('published but no public_url')
    return url
