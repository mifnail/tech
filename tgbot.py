"""Telegram-бот «Мои оценки»: read-only просмотр ведомости для студентов.

Только стандартная библиотека (+certifi для CA, если установлен).
Polling идёт в daemon-потоке рядом с Flask — входящие порты/хостинг не нужны.
Логика команд чистая (process_text) — тестируется без сети.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from datetime import date

from botcore import (
    BotError,
    BotRateLimited,
    MAX_TEXT,
    WELCOME,
    _ctx,
    _UNVERIFIED_CTX,
    _fio,
    _fmt_date,
    _read_body,
    open_url_with_fallback,
    retry_on_connection,
)

TG_API = 'https://api.telegram.org'
POLL_TIMEOUT = 25
ERROR_PAUSE = 5
# MAX_TEXT, WELCOME, _fio, _fmt_date, _ctx, _read_body, BotError etc. re-exported from botcore
# Keep aliases identical objects for patch points
HELP_NEW = ('Команды:\n'
            '/start — привязать фамилию\n'
            '/help — эта справка')
HELP_BOUND = ('Команды:\n'
              '/grades — мои оценки\n'
              '/today — занятия сегодня\n'
              '/unbind — отвязать чат\n'
              '/help — эта справка')


def _call(token: str, method: str, params: dict | None = None,
          urlopen=None, timeout: int = 35):
    """Один вызов Bot API. urlopen инжектится ради тестов."""
    payload = json.dumps(params or {}).encode('utf-8')
    req = urllib.request.Request(f'{TG_API}/bot{token}/{method}', data=payload, method='POST')
    req.add_header('Content-Type', 'application/json')
    try:
        body = open_url_with_fallback(req, urlopen=urlopen, timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise BotError('bad bot token (401)')
        if e.code == 429:
            wait = 5
            try:
                wait = int(json.loads(e.read().decode()).get('parameters', {}).get('retry_after', 5))
            except Exception:
                pass
            raise BotRateLimited(wait)
        raise BotError(f'telegram api HTTP {e.code}')
    except urllib.error.URLError as e:
        raise BotError(f'no connection: {e.reason}')
    if not body.get('ok'):
        raise BotError(f"telegram error: {body.get('description', '?')}")
    return body.get('result')


def get_me(token: str, urlopen=None, retries: int = 3):
    """getMe с ретраями при обрывах сети. HTTP-ошибки (401) — сразу наружу."""
    return retry_on_connection(lambda: _call(token, 'getMe', urlopen=urlopen), retries=retries, sleep=2)


def send_message(token: str, chat_id: int, text: str, urlopen=None):
    return _call(token, 'sendMessage',
                 {'chat_id': chat_id, 'text': (text or '')[:MAX_TEXT]}, urlopen=urlopen)


def get_updates(token: str, offset: int = 0, timeout: int = POLL_TIMEOUT, urlopen=None):
    return _call(token, 'getUpdates',
                 {'offset': offset, 'timeout': timeout, 'allowed_updates': ['message']},
                 urlopen=urlopen, timeout=timeout + 10)


# WELCOME already imported; keep HELP etc.

def my_grades_text(db, student_id: int, limit_per_subject: int = 5) -> str:
    rows = [dict(r) for r in db.student_grades(student_id)]
    if not rows:
        return 'Оценок пока нет.'
    by_subj: dict[str, list] = {}
    for r in rows:
        by_subj.setdefault(r.get('subject_name', '?'), []).append(r)
    parts = []
    for subj, rs in by_subj.items():
        lines = [subj + ':']
        for r in rs[:limit_per_subject]:
            lines.append(f"  {_fmt_date(r.get('date', ''))} — {r.get('grade', '')}")
        if len(rs) > limit_per_subject:
            lines.append(f'  …всего {len(rs)}')
        parts.append('\n'.join(lines))
    return '\n\n'.join(parts)


def today_text(db, student) -> str:
    today = date.today().isoformat()
    lessons = [dict(r) for r in db.list_lessons_by_date(today)
               if r['group_id'] == student['group_id']]
    if not lessons:
        return 'Сегодня занятий нет.'
    marks = {}
    for r in db.student_grades(student['id']):
        if r['date'] == today:
            marks[r['lesson_id']] = r['grade']
    lines = []
    for i, l in enumerate(lessons, 1):
        num = f"№{l['lesson_number']} " if l.get('lesson_number') is not None else ''
        g = marks.get(l['id'], '—')
        lines.append(f"{i}. {num}{l.get('actual_subject_name', '')}: {g}")
    return 'Сегодня:\n' + '\n'.join(lines)


def _try_bind(query: str, chat_id: int, db) -> str:
    cands = [dict(r) for r in db.find_students_by_surname(query)]
    if not cands:
        return 'Не нашёл такую фамилию. Проверь написание.'
    if len(cands) == 1:
        s = cands[0]
        if db.get_student_chat(s['id']) is not None:
            return 'Эта фамилия уже привязана к другому чату. Обратись к преподавателю.'
        db.bind_chat(chat_id, s['id'])
        return f"Готово, ты: {_fio(s)}!\n\n" + my_grades_text(db, s['id'])
    names = ', '.join(f"{c['last_name']} {c['first_name']}" for c in cands[:5])
    return f'Нашёл несколько: {names}. Отправь «Фамилия Имя».'


def process_text(text: str, chat_id: int, db) -> str:
    """Чистая логика диалога: вход снаружи, БД — аргументом. Возвращает ответ."""
    t = (text or '').strip()
    low = t.lower()
    sid = db.get_chat_link(chat_id)
    if low in ('/start', 'start', 'начать'):
        if sid:
            st = db.get_student(sid)
            who = _fio(dict(st)) if st else 'студент'
            return f'Ты уже привязан(а): {who}.\n\n' + HELP_BOUND
        return WELCOME
    if low in ('/help', 'help', 'помощь'):
        return HELP_BOUND if sid else HELP_NEW
    if sid is None:
        if t.startswith('/'):
            return 'Сначала привяжись: отправь свою фамилию.'
        return _try_bind(t, chat_id, db)
    if low in ('/grades', 'оценки', 'мои оценки'):
        return my_grades_text(db, sid)
    if low in ('/today', 'сегодня'):
        st = db.get_student(sid)
        if not st:
            return 'Привязка устарела. Отправь фамилию заново.'
        return today_text(db, dict(st))
    if low in ('/unbind', 'отвязать'):
        db.unbind_chat(chat_id)
        return 'Привязка снята. Для новой отправь фамилию.'
    if t.startswith('/'):
        return 'Не знаю такую команду.\n\n' + HELP_BOUND
    return 'Ты уже привязан(а).\n\n' + HELP_BOUND


def _get_offset(db) -> int:
    try:
        return int(db.get_setting('bot_last_update') or 0)
    except (TypeError, ValueError):
        return 0


def run_polling(token: str, db_factory, stop_event=None, urlopen=None):
    """Цикл long-polling. db_factory() -> свежий Database (потокобезопасно)."""
    db0 = db_factory()
    try:
        offset = _get_offset(db0)
    finally:
        db0.close()
    while stop_event is None or not stop_event.is_set():
        try:
            updates = get_updates(token, offset, urlopen=urlopen)
        except BotRateLimited as e:
            time.sleep(e.wait)
            continue
        except BotError:
            time.sleep(ERROR_PAUSE)
            continue
        for u in updates or []:
            try:
                offset = max(offset, int(u.get('update_id', 0)) + 1)
            except (TypeError, ValueError):
                continue
            msg = u.get('message') or {}
            chat = msg.get('chat') or {}
            text = msg.get('text')
            cid = chat.get('id')
            if text is None or cid is None:
                continue
            try:
                cid = int(cid)
            except (TypeError, ValueError):
                continue
            db = db_factory()
            try:
                reply = process_text(text, cid, db)
                db.set_setting('bot_last_update', str(offset))
            except Exception:
                reply = 'Ошибка, попробуй позже.'
            finally:
                db.close()
            try:
                send_message(token, cid, reply, urlopen=urlopen)
            except BotError:
                pass


def start_polling(token: str):
    """Запустить polling в daemon-потоке. Импорты только внутри — модуль без тяжёлых deps."""
    from database import Database

    t = threading.Thread(target=run_polling, args=(token, Database),
                         daemon=True, name='tg-poll')
    t.start()
    return t
