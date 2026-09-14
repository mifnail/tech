"""Transport core for both bots — stdlib only."""
from __future__ import annotations

import json
import ssl
import threading
import time
import urllib.error
import urllib.request

MAX_TEXT = 4000

WELCOME = ('Привет! Я журнал «Учет занятий».\n'
           'Отправь свою фамилию для привязки — например: Иванов')


class BotError(Exception):
    """Ошибка API / сети."""


class BotRateLimited(BotError):
    def __init__(self, wait: int):
        super().__init__(f'rate limited, retry after {wait}s')
        self.wait = wait


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


# Compatibility alias for older imports. It intentionally verifies certificates.
_UNVERIFIED_CTX = _ctx()


def _read_body(resp) -> dict:
    try:
        raw = resp.read()
    except Exception:
        return {}
    if not raw:
        return {}
    try:
        return json.loads(raw.decode('utf-8'))
    except ValueError:
        return {}


def open_url_with_fallback(req, urlopen=None, timeout: int = 35) -> dict:
    """Read JSON over verified TLS; keep the name for callers and test doubles."""
    with open_raw_with_fallback(req, urlopen=urlopen, timeout=timeout) as resp:
        return _read_body(resp)


def open_raw_with_fallback(req, urlopen=None, timeout: int = 35):
    """Return a raw response; certificate errors fail closed, never downgrade TLS."""
    if urlopen is not None:
        return urlopen(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout, context=_ctx())


def retry_on_connection(fn, retries: int = 3, sleep: int = 2):
    """Calls fn(), retries ONLY errors whose str contains 'no connection', re-raises otherwise (incl. BotRateLimited)."""
    last = None
    for i in range(max(1, retries)):
        try:
            return fn()
        except BotRateLimited:
            raise
        except Exception as e:
            last = e
            if 'no connection' not in str(e) or i == max(1, retries) - 1:
                raise
            time.sleep(sleep)
    raise last  # pragma: no cover


def _fio(row) -> str:
    return f"{row['last_name']} {row['first_name']}".strip()


def _fmt_date(iso: str) -> str:
    if iso and len(iso) >= 10:
        return f'{iso[8:10]}.{iso[5:7]}'
    return iso or ''


def supervise(name, target_factory, interval=60):
    """Start worker via target_factory() and supervise restarts if dead. Returns (worker, supervisor)."""
    worker = None
    try:
        worker = target_factory()
        if isinstance(worker, threading.Thread):
            try:
                worker.name = name
                worker.daemon = True
            except Exception:
                pass
            if not worker.is_alive():
                try:
                    worker.start()
                except Exception:
                    pass
    except Exception:
        pass

    def _sup_loop():
        nonlocal worker
        while True:
            try:
                time.sleep(interval)
            except Exception:
                pass
            try:
                if worker is None or not worker.is_alive():
                    try:
                        new_worker = target_factory()
                    except Exception:
                        continue
                    if isinstance(new_worker, threading.Thread):
                        try:
                            new_worker.name = name
                            new_worker.daemon = True
                        except Exception:
                            pass
                        if not new_worker.is_alive():
                            try:
                                new_worker.start()
                            except Exception:
                                pass
                    worker = new_worker
            except Exception:
                pass

    supervisor = threading.Thread(target=_sup_loop, daemon=True, name=f"{name}-supervisor")
    try:
        supervisor.start()
    except Exception:
        pass
    return (worker, supervisor)
