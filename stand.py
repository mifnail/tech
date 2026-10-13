#!/usr/bin/env python3
"""stand.py — раннер автоматического тестового стенда TeachHelper4.

Фазы:
    --phase=static | backend | api | e2e | all   (по умолчанию all)

    static  tsc --noEmit + vite build (npx, mobile-teacher-app-redesign)
            + esprima.parseScript(static/app.js) + node --test tests/*.cjs
    backend python -m pytest tests -q (cwd = проект); красный, если
            passed < 239 (BASELINE_MIN_PASSED)
    api     Flask из main.py на 127.0.0.1:5111 с TEACHHELPER_NO_BOT=1 и
            ВРЕМЕННОЙ БД (HOME/USERPROFILE в tmp, database.DB_PATH подменяется
            до import api) + сценарный HTTP-прогон на stdlib urllib.
            УprojectId lessons.db проекта не открывается и не пишется.
    e2e     npx playwright test (каталог mobile-teacher-app-redesign); если
            playwright не установлен → подсказка и exit 3

all: static → backend → api → e2e, первый красный → exit 1.
Только stdlib + зависимости проекта; Windows (subprocess shell=False,
CREATE_NO_WINDOW).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import date, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.join(BASE, 'mobile-teacher-app-redesign')
STATIC_APP_JS = os.path.join(BASE, 'static', 'app.js')

# Консоль/pipe на Windows часто cp1251 — не умеет стрелки и часть кириллицы.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:  # noqa: BLE001 — поток может быть заморожен/заменён
        pass

PY = sys.executable
NODE = shutil.which('node') or 'node'
NPX = shutil.which('npx.cmd') or shutil.which('npx') or 'npx.cmd'

HOST = '127.0.0.1'
PORT = 5111
BASE_URL = f'http://{HOST}:{PORT}'
PROJECT_DB = os.path.join(BASE, 'lessons.db')  # проектный lessons.db (tripwire-цель)

BASELINE_MIN_PASSED = 239          # порог backend-фазы
PHASES = ('static', 'backend', 'api', 'e2e')

_NOWINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
_NEWGROUP = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)

ESPRIMA_CODE = (
    'import io, sys, esprima\n'
    'src = io.open(sys.argv[1], encoding="utf-8").read()\n'
    'tree = esprima.parseScript(src)\n'
    'print("esprima OK: %d bytes, %d top-level statements" % (len(src), len(tree.body)))\n'
)

# Bootstrap сервера: путь к БД подменяется ДО import api, поэтому проектный
# lessons.db не открывается ни чтением, ни записью (паттерн tests/conftest.py).
SERVER_BOOTSTRAP = r'''
import os, runpy, sys
base, db_path = sys.argv[1], sys.argv[2]
sys.path.insert(0, base)
import database
database.DB_PATH = db_path
with database.Database(db_path):
    pass
import api
api._DB_PATH = db_path
main_path = os.path.join(base, "main.py")
sys.argv = [main_path, "--prod"]
runpy.run_path(main_path, run_name="__main__")
'''


# --------------------------------------------------------------------------- #
# общие помощники
# --------------------------------------------------------------------------- #
def _child_env(extra: dict | None = None) -> dict:
    env = os.environ.copy()
    env['PYTHONUTF8'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    if extra:
        env.update(extra)
    return env


def run(cmd, cwd: str | None = None, env: dict | None = None,
        timeout: int = 900, echo: bool = True) -> tuple[int, str]:
    """Запуск без shell; печатает вывод; возвращает (код_возврата, текст)."""
    pretty = ' '.join(str(c) for c in cmd)
    if echo:
        print(f'  $ {pretty}' + (f'    [cwd={cwd}]' if cwd else ''))
    try:
        proc = subprocess.run(
            list(cmd), cwd=cwd, env=env, shell=False,
            capture_output=True, timeout=timeout,
            creationflags=_NOWINDOW)
    except FileNotFoundError as exc:
        print(f'  ! команда не найдена: {exc}')
        return 127, str(exc)
    except subprocess.TimeoutExpired:
        print(f'  ! таймаут {timeout}s')
        return 124, ''
    text = ((proc.stdout or b'') + b'\n' + (proc.stderr or b'')).decode('utf-8', 'replace')
    if echo and text.strip():
        for line in text.splitlines():
            print('  | ' + line)
    if echo:
        print(f'  -> exit {proc.returncode}')
    return proc.returncode, text


def _count(pattern: str, text: str) -> int | None:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else None


# --------------------------------------------------------------------------- #
# фаза static
# --------------------------------------------------------------------------- #
def phase_static() -> int:
    if not os.path.isdir(os.path.join(FRONTEND, 'node_modules')):
        print('  ! нет mobile-teacher-app-redesign/node_modules → выполните npm install')
        return 1

    failed: list[str] = []

    rc, _ = run([NPX, 'tsc', '--noEmit'], cwd=FRONTEND, timeout=600)
    if rc != 0:
        failed.append('tsc --noEmit')

    rc, _ = run([NPX, 'vite', 'build'], cwd=FRONTEND, timeout=600)
    if rc != 0:
        failed.append('vite build')

    if not os.path.isfile(STATIC_APP_JS):
        print(f'  ! нет {STATIC_APP_JS}')
        failed.append('static/app.js')
    else:
        rc, _ = run([PY, '-c', ESPRIMA_CODE, STATIC_APP_JS], cwd=BASE, timeout=300)
        if rc != 0:
            failed.append('esprima static/app.js')

    cjs = sorted(glob.glob(os.path.join(FRONTEND, 'tests', '*.cjs')))
    if not cjs:
        print('  ! не найдено mobile-teacher-app-redesign/tests/*.cjs')
        failed.append('node --test')
    else:
        rc, text = run([NODE, '--test', *cjs], cwd=FRONTEND, timeout=900)
        passed = _count(r'\bpass\s+(\d+)', text)
        fails = _count(r'\bfail\s+(\d+)', text)
        if passed is not None or fails is not None:
            print(f'  -> node --test: pass={passed} fail={fails}')
        if rc != 0:
            failed.append('node --test')

    if failed:
        print(f'  СТАТИКА КРАСНАЯ: {", ".join(failed)}')
        return 1
    print('  статика зелёная: tsc, vite build, esprima, node --test')
    return 0


# --------------------------------------------------------------------------- #
# фаза backend
# --------------------------------------------------------------------------- #
def phase_backend() -> int:
    rc, text = run([PY, '-m', 'pytest', 'tests', '-q'], cwd=BASE, timeout=1200)
    passed = _count(r'(\d+) passed', text) or 0
    failed = _count(r'(\d+) failed', text) or 0
    errors = _count(r'(\d+) error', text) or 0
    print(f'  -> pytest: passed={passed} failed={failed} errors={errors} exit={rc}')
    if failed or errors or rc != 0:
        print('  БЭКЕНД КРАСНЫЙ: pytest завершился с ошибками')
        return 1
    if passed < BASELINE_MIN_PASSED:
        print(f'  БЭКЕНД КРАСНЫЙ: passed={passed} < порога {BASELINE_MIN_PASSED}')
        return 1
    print(f'  бэкенд зелёный: {passed} passed (порог {BASELINE_MIN_PASSED})')
    return 0


# --------------------------------------------------------------------------- #
# фаза api
# --------------------------------------------------------------------------- #
def http(method: str, path: str, payload=None) -> tuple[int, object]:
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    headers = {'Content-Type': 'application/json'} if data else {}
    req = urllib.request.Request(BASE_URL + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode('utf-8', 'replace')
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode('utf-8', 'replace')
        try:
            body = json.loads(raw) if raw else None
        except ValueError:
            body = raw
        return exc.code, body
    except Exception as exc:  # noqa: BLE001 — любой сетевой сбой = красный шаг
        return 0, f'{type(exc).__name__}: {exc}'


def _port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex((HOST, port)) == 0


def _wait_ready(proc: subprocess.Popen, timeout: float = 45.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        status, _body = http('GET', '/api/version')
        if status == 200:
            return True
        time.sleep(0.4)
    return False


def _tail(path: str, lines: int = 25) -> str:
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as fh:
            return ''.join(fh.readlines()[-lines:])
    except OSError:
        return ''


def _db_stat(path: str) -> tuple[float, int] | None:
    """(mtime, size) файла или None, если файла нет — для tripwire lessons.db."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_mtime, st.st_size)


def _shutdown(proc: subprocess.Popen | None) -> None:
    """Погасить сервер вместе с деревом процессов (Windows: taskkill /T)."""
    if proc is None:
        return
    if proc.poll() is not None:
        return
    if os.name == 'nt':
        subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'],
                       capture_output=True, creationflags=_NOWINDOW)
    else:
        proc.terminate()
    try:
        proc.wait(timeout=15)
    except Exception:  # noqa: BLE001
        try:
            proc.kill()
            proc.wait(timeout=10)
        except Exception:  # noqa: BLE001
            pass


def phase_api() -> int:
    if _port_busy(PORT):
        print(f'  ! порт {PORT} уже занят — сначала освободите его')
        return 1

    tmp = tempfile.mkdtemp(prefix='stand_api_')
    home = os.path.join(tmp, 'home')
    os.makedirs(os.path.join(home, 'Downloads'), exist_ok=True)
    db_path = os.path.join(tmp, 'stand_api.db')
    log_out, log_err = os.path.join(tmp, 'server.out.log'), os.path.join(tmp, 'server.err.log')

    # Tripwire: проектный lessons.db НЕ должен меняться во время фазы api.
    db_before = _db_stat(PROJECT_DB)

    checks: list[tuple[str, bool]] = []

    def check(name: str, ok: bool, detail: object = '') -> None:
        checks.append((name, bool(ok)))
        suffix = f' — {detail}' if detail not in ('', None) else ''
        print(f"  [{'OK  ' if ok else 'FAIL'}] {name}{suffix}")

    env = _child_env({
        'HOME': home,
        'USERPROFILE': home,
        'TEACHHELPER_NO_BOT': '1',
        'PORT': str(PORT),
        'PYTHONPATH': BASE,
    })
    env.pop('WERKZEUG_RUN_MAIN', None)

    proc: subprocess.Popen | None = None
    out_fh = err_fh = None
    rc = 1
    try:
        def body() -> int:
            """Сценарный прогон; возвращает 0/1. Все return — только отсюда,
            чтобы finally с tripwire успел скорректировать общий rc."""
            nonlocal proc, out_fh, err_fh
            out_fh = open(log_out, 'wb')
            err_fh = open(log_err, 'wb')
            print(f'  старт Flask из main.py на {BASE_URL}, временная БД {db_path}')
            proc = subprocess.Popen(
                [PY, '-c', SERVER_BOOTSTRAP, BASE, db_path],
                cwd=BASE, env=env, shell=False,
                stdout=out_fh, stderr=err_fh,
                creationflags=_NOWINDOW | _NEWGROUP)

            if not _wait_ready(proc):
                print('  ! сервер не поднялся за 45s; хвост лога:')
                print('    ' + _tail(log_err).replace('\n', '\n    '))
                return 1
            print(f'  сервер поднялся: {BASE_URL} (pid={proc.pid})')

            # ---- подготовка: группа, студенты, два предмета одной группы ----
            status, _body = http('GET', '/api/version')
            check('GET /api/version → 200', status == 200, status)

            status, body_resp = http('POST', '/api/groups', {'name': 'СТ-01'})
            group_id = body_resp.get('id') if isinstance(body_resp, dict) else None
            check('POST /api/groups → 201', status == 201 and group_id, status)

            status, body_resp = http('POST', '/api/students/bulk', {
                'group_id': group_id,
                'students': [
                    {'last_name': 'Стендов', 'first_name': 'Антон', 'middle_name': 'Игоревич'},
                    {'last_name': 'Контроль', 'first_name': 'Кира', 'middle_name': 'Олеговна'},
                    {'last_name': 'Пробник', 'first_name': 'Пётр', 'middle_name': 'Васильевич'},
                ]})
            check('POST /api/students/bulk → 201', status == 201, status)

            status, body_resp = http('POST', '/api/subjects',
                                     {'name': 'Информатика', 'total_hours': 72, 'group_id': group_id})
            subject_a = body_resp.get('id') if isinstance(body_resp, dict) else None
            check('POST /api/subjects (Информатика) → 201', status == 201 and subject_a, status)

            status, body_resp = http('POST', '/api/subjects',
                                     {'name': 'Базы данных', 'total_hours': 68, 'group_id': group_id})
            subject_b = body_resp.get('id') if isinstance(body_resp, dict) else None
            check('POST /api/subjects (Базы данных) → 201', status == 201 and subject_b, status)

            if not (group_id and subject_a and subject_b):
                print('  подготовка не удалась — сценарии пропускаются')
                return 1

            status, body_resp = http('GET', f'/api/students?group_id={group_id}')
            student_ids = [row.get('id') for row in body_resp
                           if isinstance(row, dict) and row.get('id')] \
                if status == 200 and isinstance(body_resp, list) else []
            check('GET /api/students → 200 со списком', status == 200 and len(student_ids) >= 2,
                  f'{status} n={len(student_ids)}')

            today = date.today()
            past_payload = {
                'subject_id': subject_a,
                'date': (today - timedelta(days=3)).isoformat(),
                'status': 'held',
                'lesson_number': 1,
            }

            # 1) прошедшая дата → 201
            status, body_resp = http('POST', '/api/lessons', past_payload)
            lesson_id = body_resp.get('id') if isinstance(body_resp, dict) else None
            check('POST /api/lessons (прошедшая дата) → 201', status == 201 and lesson_id, status)

            # 2) будущая дата → 400
            future_payload = dict(past_payload, date=(today + timedelta(days=3)).isoformat(), lesson_number=2)
            status, body_resp = http('POST', '/api/lessons', future_payload)
            check('POST /api/lessons (будущая дата) → 400', status == 400, status)

            # 3) дедуп двойного тапа: тот же payload повторно → 200 deduped
            status, body_resp = http('POST', '/api/lessons', past_payload)
            check('POST /api/lessons (дубль) → 200 deduped',
                  status == 200 and isinstance(body_resp, dict) and body_resp.get('deduped') is True
                  and body_resp.get('id') == lesson_id,
                  f'{status} {body_resp}')

            # 4) conduct: notified >= 0, повтор → 0
            if student_ids:
                records = [{'student_id': sid, 'grade': grade}
                           for sid, grade in zip(student_ids[:2], ('5', '4'))]
            else:
                records = []
            status, body_resp = http('POST', f'/api/lessons/{lesson_id}/conduct', records)
            notified_1 = body_resp.get('notified') if isinstance(body_resp, dict) else None
            check('POST /api/lessons/:id/conduct → ok, notified>=0',
                  status == 200 and isinstance(body_resp, dict) and body_resp.get('ok') is True
                  and isinstance(notified_1, int) and notified_1 >= 0,
                  f'{status} notified={notified_1}')

            status, body_resp = http('POST', f'/api/lessons/{lesson_id}/conduct', records)
            notified_2 = body_resp.get('notified') if isinstance(body_resp, dict) else None
            check('повтор conduct → notified == 0',
                  status == 200 and isinstance(body_resp, dict) and notified_2 == 0,
                  f'{status} notified={notified_2}')

            if records:
                status, body_resp = http('GET', f'/api/lessons/{lesson_id}/attendance')
                written = len(body_resp.get('attendance', [])) if isinstance(body_resp, dict) else -1
                check('посещаемость записана в БД', status == 200 and written == len(records),
                      f'{status} attendance={written}')

            # 5) substitute → ok
            status, body_resp = http('PATCH', f'/api/lessons/{lesson_id}/substitute',
                                     {'new_subject_id': subject_b})
            new_lesson_id = body_resp.get('new_lesson_id') if isinstance(body_resp, dict) else None
            check('PATCH substitute → ok', status == 200 and isinstance(body_resp, dict)
                  and body_resp.get('ok') is True and new_lesson_id, f'{status} {body_resp}')

            # 6) cancel → ok
            status, body_resp = http('PATCH', f'/api/lessons/{new_lesson_id}/cancel')
            check('PATCH cancel → ok',
                  status == 200 and isinstance(body_resp, dict) and body_resp.get('ok') is True,
                  f'{status} {body_resp}')

            # временная БД должна существовать и быть непустой; tripwire lessons.db
            # проекта сверяется ниже, в finally, до rmtree.
            check('временная БД создана и непустая (size>0)',
                  os.path.isfile(db_path) and os.path.getsize(db_path) > 0)

            bad = [name for name, ok in checks if not ok]
            if bad:
                print(f'  API-ПРОГОН КРАСНЫЙ: {len(bad)} из {len(checks)} шагов')
                return 1
            print(f'  api зелёный: {len(checks)} проверок')
            return 0

        rc = body()
    finally:
        _shutdown(proc)
        for fh in (out_fh, err_fh):
            try:
                if fh:
                    fh.close()
            except Exception:  # noqa: BLE001
                pass
        # Tripwire: проектный lessons.db изменился во время фазы → фаза красная.
        db_after = _db_stat(PROJECT_DB)
        if db_after != db_before:
            print(f'  TRIPWIRE: {PROJECT_DB} изменился во время фазы api '
                  f'(mtime/size {db_before} → {db_after}) — это баг стенда!')
            rc = 1
        shutil.rmtree(tmp, ignore_errors=True)
    return rc


# --------------------------------------------------------------------------- #
# фаза e2e
# --------------------------------------------------------------------------- #
def phase_e2e() -> int:
    playwright_dir = os.path.join(FRONTEND, 'node_modules', '@playwright', 'test')
    if not os.path.isdir(playwright_dir):
        print('  ! Playwright в проекте не установлен.')
        print('    Подсказка по установке:')
        print('        npm i -D @playwright/test && npx playwright install chromium')
        return 3
    if _port_busy(PORT):
        # reuseExistingServer:true в playwright.config.ts молча подхватил бы
        # чужой сервер — это маскирует чужие данные/БД. Громкий fail, чужой
        # процесс НЕ убиваем.
        print(f'  ! порт {PORT} занят чужим процессом — завершите его или запустите e2e вручную через npx playwright test')
        return 1
    rc, text = run([NPX, 'playwright', 'test'], cwd=FRONTEND, timeout=1800)
    passed = _count(r'(\d+) passed', text)
    failed = _count(r'(\d+) failed', text)
    if passed is not None or failed is not None:
        print(f'  -> playwright: passed={passed} failed={failed}')
    if 'No tests found' in text:
        print('  ! Playwright запущен, но спецификаций нет: каталог e2e/ и')
        print('    playwright.config.* создаёт параллельная лента — до их')
        print('    появления фаза остаётся красной (playwright установлен, exit 1).')
    if rc != 0:
        print('  E2E КРАСНЫЙ')
        return 1
    print('  e2e зелёный')
    return 0


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #
def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description='Раннер тестового стенда TeachHelper4')
    parser.add_argument('--phase', default='all',
                        choices=list(PHASES) + ['all'],
                        help='фаза запуска (по умолчанию all)')
    args = parser.parse_args(argv[1:])

    order = list(PHASES) if args.phase == 'all' else [args.phase]
    runners = {
        'static': phase_static,
        'backend': phase_backend,
        'api': phase_api,
        'e2e': phase_e2e,
    }

    results: dict[str, str] = {}
    exit_code = 0
    for index, name in enumerate(order, start=1):
        print('=' * 64)
        print(f'[{index}/{len(order)}] ФАЗА: {name.upper()}')
        print('=' * 64)
        code = runners[name]()
        results[name] = 'PASS' if code == 0 else f'FAIL (exit {code})'
        if code != 0:
            exit_code = 3 if (name == 'e2e' and code == 3) else 1
            break

    print('=' * 64)
    print('СВОДКА СТЕНДА')
    print('=' * 64)
    for name in PHASES:
        if name in results:
            state = results[name]
        elif name in order:
            state = 'SKIP (остановлено после красной фазы)'
        else:
            state = 'SKIP (не запрошена)'
        print(f'  {name:<8} {state}')
    print(f'  итог    {"PASS" if exit_code == 0 else f"FAIL (exit {exit_code})"}')
    return exit_code


if __name__ == '__main__':
    sys.exit(main(sys.argv))
