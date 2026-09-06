"""MAX-бот «Мои оценки»: read-only просмотр ведомости для студентов.

Только стандартная библиотека (+certifi для CA, если установлен).
Polling идёт в daemon-потоке рядом с Flask — входящие порты/хостинг не нужны.
Логика команд чистая (process_text) — тестируется без сети.
"""

from __future__ import annotations

import json
import ssl
import threading
import time
import urllib.error
import urllib.request
from datetime import date, timedelta

MAX_API = 'https://platform-api2.max.ru'
POLL_TIMEOUT = 25
ERROR_PAUSE = 5
MAX_TEXT = 4000


class MaxError(Exception):
    """Ошибка MAX API / сети."""


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


_UNVERIFIED_CTX = ssl._create_unverified_context()


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


def _get(path: str, token: str, urlopen=None, timeout: int = 35):
    """GET-запрос к MAX API. urlopen инжектится ради тестов."""
    req = urllib.request.Request(f'{MAX_API}{path}')
    req.add_header('Authorization', token)
    try:
        if urlopen is not None:
            resp = urlopen(req, timeout=timeout)
        else:
            resp = urllib.request.urlopen(req, timeout=timeout, context=_ctx())
        with resp:
            return _read_body(resp)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise MaxError('bad bot token (401)')
        raise MaxError(f'max api HTTP {e.code}')
    except urllib.error.URLError as e:
        if 'CERTIFICATE_VERIFY_FAILED' in str(e.reason) and urlopen is None:
            try:
                with urllib.request.urlopen(req, timeout=timeout, context=_UNVERIFIED_CTX) as resp2:
                    return _read_body(resp2)
            except Exception as e2:
                raise MaxError(f'no connection: {e2}')
        else:
            raise MaxError(f'no connection: {e.reason}')


def _post(path: str, token: str, data: dict, urlopen=None, timeout: int = 35):
    """POST-запрос к MAX API. urlopen инжектится ради тестов."""
    payload = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(f'{MAX_API}{path}', data=payload, method='POST')
    req.add_header('Authorization', token)
    req.add_header('Content-Type', 'application/json')
    try:
        if urlopen is not None:
            resp = urlopen(req, timeout=timeout)
        else:
            resp = urllib.request.urlopen(req, timeout=timeout, context=_ctx())
        with resp:
            return _read_body(resp)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise MaxError('bad bot token (401)')
        raise MaxError(f'max api HTTP {e.code}')
    except urllib.error.URLError as e:
        if 'CERTIFICATE_VERIFY_FAILED' in str(e.reason) and urlopen is None:
            try:
                with urllib.request.urlopen(req, timeout=timeout, context=_UNVERIFIED_CTX) as resp2:
                    return _read_body(resp2)
            except Exception as e2:
                raise MaxError(f'no connection: {e2}')
        else:
            raise MaxError(f'no connection: {e.reason}')


def check(token: str, urlopen=None):
    """Проверить токен: GET updates?timeout=0&limit=1. Возвращает True-ish dict при успехе."""
    body = _get('/messages/updates?timeout=0&limit=1', token, urlopen=urlopen)
    if body:
        return body
    return {'ok': True}


def send_message(token: str, chat_id: int, text: str, urlopen=None):
    """Отправить текстовое сообщение в чат MAX."""
    return _post(f'/messages?chat_id={chat_id}', token,
                 {'text': (text or '')[:MAX_TEXT], 'format': 'markdown', 'notify': True},
                 urlopen=urlopen)


def get_updates(token: str, marker=None, timeout: int = POLL_TIMEOUT, urlopen=None):
    """Получить обновления. Возвращает (updates, marker)."""
    path = f'/messages/updates?limit=100&timeout={timeout}'
    if marker is not None:
        path += f'&marker={marker}'
    body = _get(path, token, urlopen=urlopen, timeout=timeout + 10)
    updates = body.get('updates', [])
    new_marker = body.get('marker', marker)
    return updates, new_marker


WELCOME = ('Привет! Я журнал TeachHelper.\n'
            'Отправь свою фамилию для привязки — например: Иванов')
HELP_NEW = ('Команды:\n'
            '/start — привязать фамилию\n'
            '/help — эта справка')
HELP_BOUND = ('Команды:\n'
              '/grades — мои оценки\n'
              '/today — занятия сегодня\n'
              '/unbind — отвязать чат\n'
              '/help — эта справка')


def process_text(text: str, chat_id: int, db) -> str:
    """Чистая логика диалога: вход снаружи, БД — аргументом. Возвращает ответ."""
    from tgbot import my_grades_text, today_text
    from tgbot import _fio

    t = (text or '').strip()
    low = t.lower()
    sid = db.get_max_link(chat_id)
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
        # Попытка привязки по фамилии
        cands = [dict(r) for r in db.find_students_by_surname(t)]
        if not cands:
            return 'Не нашёл такую фамилию. Проверь написание.'
        if len(cands) == 1:
            s = cands[0]
            if db.get_max_student_chat(s['id']) is not None:
                return 'Эта фамилия уже привязана к другому чату. Обратись к преподавателю.'
            db.bind_max(chat_id, s['id'])
            return f"Готово, ты: {_fio(s)}!\n\n" + my_grades_text(db, s['id'])
        names = ', '.join(f"{c['last_name']} {c['first_name']}" for c in cands[:5])
        return f'Нашёл несколько: {names}. Отправь «Фамилия Имя».'
    if low in ('/grades', 'оценки', 'мои оценки'):
        return my_grades_text(db, sid)
    if low in ('/today', 'сегодня'):
        st = db.get_student(sid)
        if not st:
            return 'Привязка устарела. Отправь фамилию заново.'
        return today_text(db, dict(st))
    if low in ('/unbind', 'отвязать'):
        db.unbind_max(chat_id)
        return 'Привязка снята. Для новой отправь фамилию.'
    if t.startswith('/'):
        return 'Не знаю такую команду.\n\n' + HELP_BOUND
    return 'Ты уже привязан(а).\n\n' + HELP_BOUND


def _get_marker(db) -> int | None:
    try:
        v = db.get_setting('max_last_marker')
        return int(v) if v else None
    except (TypeError, ValueError):
        return None


def run_polling(token: str, db_factory, stop_event=None, urlopen=None):
    """Цикл long-polling. db_factory() -> свежий Database (потокобезопасно)."""
    db0 = db_factory()
    try:
        marker = _get_marker(db0)
    finally:
        db0.close()
    while stop_event is None or not stop_event.is_set():
        try:
            updates, new_marker = get_updates(token, marker, urlopen=urlopen)
        except MaxError:
            time.sleep(ERROR_PAUSE)
            continue
        for u in updates or []:
            # message_created: update.message.body.text, update.message.recipient.chat_id
            msg_type = u.get('type')
            if msg_type == 'message_created':
                msg = u.get('message') or {}
                body = msg.get('body') or {}
                text = body.get('text')
                recipient = msg.get('recipient') or {}
                cid = recipient.get('chat_id')
                if text is None or cid is None:
                    continue
                try:
                    cid = int(cid)
                except (TypeError, ValueError):
                    continue
                db = db_factory()
                try:
                    reply = process_text(text, cid, db)
                    db.set_setting('max_last_marker', str(new_marker))
                except Exception:
                    reply = 'Ошибка, попробуй позже.'
                finally:
                    db.close()
                try:
                    send_message(token, cid, reply, urlopen=urlopen)
                except MaxError:
                    pass
            elif msg_type == 'bot_started':
                cid = u.get('chat_id')
                if cid is None:
                    continue
                try:
                    cid = int(cid)
                except (TypeError, ValueError):
                    continue
                db = db_factory()
                try:
                    reply = process_text('/start', cid, db)
                    db.set_setting('max_last_marker', str(new_marker))
                except Exception:
                    reply = 'Ошибка, попробуй позже.'
                finally:
                    db.close()
                try:
                    send_message(token, cid, reply, urlopen=urlopen)
                except MaxError:
                    pass
            if new_marker is not None:
                marker = new_marker


def start_polling(token: str):
    """Запустить polling в daemon-потоке. Импорты только внутри — модуль без тяжёлых deps."""
    from database import Database

    t = threading.Thread(target=run_polling, args=(token, Database),
                         daemon=True, name='max-poll')
    t.start()
    return t


# ---- Reminders ----

def due_reminder(hour: int, last_sent: str | None, today: str) -> bool:
    """True если сейчас часы 17 или 18 и сегодня ещё не отправляли."""
    return hour in (17, 18) and last_sent != today


def _fmt_date_short(iso: str) -> str:
    if iso and len(iso) >= 10:
        return f'{iso[8:10]}.{iso[5:7]}'
    return iso or ''


def reminder_targets(db, tomorrow_iso: str) -> list[tuple[int, str]]:
    """Сформировать список (chat_id, text) для напоминания о завтрашних занятиях."""
    lessons = [dict(r) for r in db.list_lessons_by_date(tomorrow_iso)]
    if not lessons:
        return []
    # Группировка по group_id
    by_group: dict[int, list] = {}
    for l in lessons:
        gid = l.get('group_id')
        if gid is not None:
            by_group.setdefault(gid, []).append(l)
    targets = []
    date_label = _fmt_date_short(tomorrow_iso)
    for gid, group_lessons in by_group.items():
        subjects = ', '.join(
            l.get('actual_subject_name', '?') for l in group_lessons)
        text = f'Завтра {date_label}: {subjects}'
        for st in db.list_students(gid):
            chat_id = db.get_max_student_chat(st['id'])
            if chat_id is not None:
                targets.append((chat_id, text))
    return targets


def run_reminders(token: str, db_factory, stop_event=None):
    """Цикл напоминаний: каждые 600 секунд."""
    while stop_event is None or not stop_event.is_set():
        try:
            today_str = date.today().isoformat()
            tomorrow = date.today() + timedelta(days=1)
            tomorrow_iso = tomorrow.isoformat()
            db = db_factory()
            try:
                last_sent = db.get_setting('max_last_reminder')
                now_hour = date.today().hour  # approximation
                from datetime import datetime as _dt
                now_hour = _dt.now().hour
                if due_reminder(now_hour, last_sent, today_str):
                    targets = reminder_targets(db, tomorrow_iso)
                    for chat_id, text in targets:
                        try:
                            send_message(token, chat_id, text)
                        except MaxError:
                            pass
                    db.set_setting('max_last_reminder', today_str)
            except Exception:
                pass
            finally:
                try:
                    db.close()
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(600)


def start_reminders(token: str):
    """Запустить reminders в daemon-потоке."""
    from database import Database

    t = threading.Thread(target=run_reminders, args=(token, Database),
                         daemon=True, name='max-reminder')
    t.start()
    return t


def notify_grade(token: str, student_id: int, grade, date_str: str,
                 subject_name: str, urlopen=None):
    """Best-effort отправка уведомления о новой оценке. Поглощает все ошибки."""
    try:
        from database import Database
        db = Database()
        try:
            chat_id = db.get_max_student_chat(student_id)
            if chat_id is None:
                return
            from tgbot import _fmt_date
            date_label = _fmt_date(date_str)
            text = f"Новая оценка: {subject_name} — {grade} ({date_label})"
            send_message(token, chat_id, text, urlopen=urlopen)
        except Exception:
            pass
        finally:
            try:
                db.close()
            except Exception:
                pass
    except Exception:
        pass
