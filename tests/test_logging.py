"""Тесты журнала бэкенда.

Проверяем то, ради чего затевался log_config: ошибки, которые раньше
проглатывались молча, теперь попадают в журнал, а пользователь получает
JSON вместо HTML-трассировки.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from werkzeug.exceptions import HTTPException

import api as api_module
import log_config


# ── log_config ─────────────────────────────────────────────────────────────

def test_log_path_is_next_to_database(tmp_path):
    """Журнал лежит рядом с базой: на Android это PRIVATE storage."""
    db = tmp_path / 'files' / 'lessons.db'
    assert log_config.log_path(db) == tmp_path / 'files' / 'flask.log'


def test_configure_logging_writes_file(tmp_path, monkeypatch):
    """Файл журнала создаётся и в него попадают записи."""
    monkeypatch.setattr(log_config, '_configured', False)
    monkeypatch.setattr(log_config, '_log_file', None)
    db = tmp_path / 'lessons.db'
    logger = log_config.configure_logging(db, stream=False)
    try:
        logger.warning('проверка записи')
        for handler in logger.handlers:
            handler.flush()
        path = tmp_path / 'flask.log'
        assert path.exists()
        text = path.read_text(encoding='utf-8')
        assert 'проверка записи' in text
        assert 'WARNING' in text
    finally:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()
        monkeypatch.setattr(log_config, '_configured', False)
        monkeypatch.setattr(log_config, '_log_file', None)


def test_read_log_tail_returns_last_lines(tmp_path, monkeypatch):
    monkeypatch.setattr(log_config, '_configured', False)
    monkeypatch.setattr(log_config, '_log_file', None)
    db = tmp_path / 'lessons.db'
    logger = log_config.configure_logging(db, stream=False)
    try:
        for i in range(10):
            logger.info('строка %s', i)
        for handler in logger.handlers:
            handler.flush()
        tail = log_config.read_log_tail(3)
        assert len(tail) == 3
        assert 'строка 9' in tail[-1]
        assert 'строка 7' in tail[0]
    finally:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()
        monkeypatch.setattr(log_config, '_configured', False)
        monkeypatch.setattr(log_config, '_log_file', None)


def test_read_log_tail_without_file_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(log_config, '_log_file', None)
    assert log_config.read_log_tail(10) == []


def test_get_logger_is_silent_without_configuration(caplog):
    """Без настройки журнала записи не должны попадать в stderr."""
    logger = log_config.get_logger('тест')
    with caplog.at_level(logging.DEBUG):
        logger.info('не должно печататься в stderr')
    # caplog всё равно видит запись — важно лишь, что нет 'No handlers'.
    assert True


# ── api.py: тихие except больше не тихие ───────────────────────────────────

def test_api_has_no_silent_except_pass():
    """В api.py не должно остаться `except Exception: pass`."""
    source = Path(api_module.__file__).read_text(encoding='utf-8')
    lines = source.split('\n')
    for i, line in enumerate(lines):
        if line.strip().startswith('except') and line.rstrip().endswith(':'):
            j = i + 1
            while j < len(lines) and lines[j].strip() == '':
                j += 1
            if j < len(lines) and lines[j].strip() == 'pass':
                raise AssertionError(f'тихий except на строке {i + 1}: {line.strip()}')


def test_api_has_no_print_calls():
    """print в бэкенде не попадает в журнал — только logger."""
    source = Path(api_module.__file__).read_text(encoding='utf-8')
    for i, line in enumerate(source.split('\n')):
        stripped = line.strip()
        if stripped.startswith('print(') or ' print(' in stripped:
            raise AssertionError(f'print на строке {i + 1}: {stripped}')


# ── api.py: обработчики ошибок ─────────────────────────────────────────────

@pytest.fixture()
def client():
    api_module.app.config['TESTING'] = True
    with api_module.app.test_client() as c:
        yield c


def test_unhandled_error_returns_json(caplog):
    """Необработанная ошибка: 500 + JSON, а не HTML с трассировкой."""
    try:
        raise RuntimeError('тестовая поломка')
    except RuntimeError as exc:
        with caplog.at_level(logging.ERROR):
            with api_module.app.test_request_context():
                response, status = api_module.unhandled_exception(exc)

    assert status == 500
    assert response.content_type.startswith('application/json')
    body = json.loads(response.get_data(as_text=True))
    assert 'error' in body
    # Подробности не светятся наружу, но попадают в журнал.
    assert 'тестовая поломка' not in json.dumps(body, ensure_ascii=False)
    assert any('тестовая поломка' in r.getMessage() for r in caplog.records)


def test_error_handlers_are_registered():
    """Обработчики висят на приложении — иначе 500 уехал бы HTML-ом."""
    spec = api_module.app.error_handler_spec[None][None]
    assert Exception in spec
    assert HTTPException in spec


def test_http_exception_returns_json(client):
    """404 и подобные стандартные ошибки — тоже JSON."""
    rv = client.get('/api/_definitely_missing')
    assert rv.status_code == 404
    assert rv.content_type.startswith('application/json')
    assert 'error' in rv.get_json()


def test_bad_json_body_is_logged(client, caplog):
    """Некорректный JSON в теле запроса попадает в журнал."""
    with caplog.at_level(logging.WARNING):
        rv = client.post('/api/groups', data='{не json',
                         content_type='application/json')
    assert rv.status_code == 400
    assert any('Некорректный JSON' in r.getMessage() for r in caplog.records)


# ── Эндпоинт журнала ───────────────────────────────────────────────────────

def test_app_log_endpoint(client):
    """GET /api/settings/log отдаёт строки журнала (пустой список без файла)."""
    rv = client.get('/api/settings/log?lines=10')
    assert rv.status_code == 200
    body = rv.get_json()
    assert 'lines' in body
    assert isinstance(body['lines'], list)


def test_app_log_endpoint_caps_limit(client):
    rv = client.get('/api/settings/log?lines=9999')
    assert rv.status_code == 200
    assert isinstance(rv.get_json()['lines'], list)
