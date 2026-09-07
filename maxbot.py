"""MAX-бот «Мои оценки»: read-only просмотр ведомости для студентов.

Только стандартная библиотека (+certifi для CA, если установлен).
Polling идёт в daemon-потоке рядом с Flask — входящие порты/хостинг не нужны.
Логика команд чистая (process_text) — тестируется без сети.
"""

from __future__ import annotations

import json
import random
import string
import threading
import time
import urllib.error
import urllib.request
from datetime import date, timedelta

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

MAX_API = 'https://platform-api2.max.ru'
POLL_TIMEOUT = 25
ERROR_PAUSE = 5
# Re-exported from botcore: WELCOME, MAX_TEXT, _fio, _fmt_date, _ctx, _read_body, BotError
MaxError = BotError
# Alias for compat: BotError name also available
BotError = BotError  # noqa: keep for patch points
BotRateLimited = BotRateLimited


def _get(path: str, token: str, urlopen=None, timeout: int = 35):
    """GET-запрос к MAX API. urlopen инжектится ради тестов."""
    req = urllib.request.Request(f'{MAX_API}{path}')
    req.add_header('Authorization', token)
    try:
        body = open_url_with_fallback(req, urlopen=urlopen, timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise MaxError('bad bot token (401)')
        raise MaxError(f'max api HTTP {e.code}')
    except urllib.error.URLError as e:
        raise MaxError(f'no connection: {e.reason}')
    return body


def _post(path: str, token: str, data: dict, urlopen=None, timeout: int = 35):
    """POST-запрос к MAX API. urlopen инжектится ради тестов."""
    payload = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(f'{MAX_API}{path}', data=payload, method='POST')
    req.add_header('Authorization', token)
    req.add_header('Content-Type', 'application/json')
    try:
        body = open_url_with_fallback(req, urlopen=urlopen, timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise MaxError('bad bot token (401)')
        raise MaxError(f'max api HTTP {e.code}')
    except urllib.error.URLError as e:
        raise MaxError(f'no connection: {e.reason}')
    return body


def check(token: str, urlopen=None):
    """Проверить токен: GET updates?timeout=0&limit=1. Возвращает True-ish dict при успехе."""
    def _do():
        body = _get('/updates?timeout=0&limit=1', token, urlopen=urlopen)
        if body:
            return body
        return {'ok': True}
    return retry_on_connection(_do, retries=3, sleep=2)


def send_message(token: str, chat_id: int, text: str, urlopen=None):
    """Отправить текстовое сообщение в чат MAX."""
    return _post(f'/messages?chat_id={chat_id}', token,
                 {'text': (text or '')[:MAX_TEXT], 'format': 'markdown', 'notify': True},
                 urlopen=urlopen)


def _multipart_encode(field: str, data: bytes, filename: str) -> tuple[bytes, str]:
    """Закодировать файл в multipart/form-data. Возвращает (body, content_type)."""
    boundary = '----FormBoundary' + ''.join(
        random.choices(string.ascii_letters + string.digits, k=16))
    parts = []
    parts.append(f'--{boundary}\r\n'.encode())
    parts.append(
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'.encode())
    parts.append(b'Content-Type: application/octet-stream\r\n\r\n')
    parts.append(data)
    parts.append(f'\r\n--{boundary}--\r\n'.encode())
    body = b''.join(parts)
    return body, f'multipart/form-data; boundary={boundary}'


def upload_file(token: str, data: bytes, filename: str, urlopen=None) -> str:
    """Загрузить файл в MAX: шаг 1 — получить URL, шаг 2 — загрузить. Возвращает токен файла."""
    # Шаг 1: POST /uploads?type=file (без тела)
    req1 = urllib.request.Request(f'{MAX_API}/uploads?type=file', method='POST')
    req1.add_header('Authorization', token)
    try:
        body1 = open_url_with_fallback(req1, urlopen=urlopen, timeout=35)
    except urllib.error.HTTPError as e:
        raise MaxError(f'upload step1 HTTP {e.code}')
    except urllib.error.URLError as e:
        raise MaxError(f'upload step1: {e.reason}')
    except MaxError:
        raise
    upload_url = body1.get('url')
    if not upload_url:
        raise MaxError('upload step1: no url')
    # Шаг 2: POST multipart/form-data на URL загрузки
    body_bytes, content_type = _multipart_encode('data', data, filename)
    req2 = urllib.request.Request(upload_url, data=body_bytes, method='POST')
    req2.add_header('Authorization', token)
    req2.add_header('Content-Type', content_type)
    try:
        if urlopen is not None:
            resp2 = urlopen(req2, timeout=60)
        else:
            resp2 = urllib.request.urlopen(req2, timeout=60, context=_ctx())
        with resp2:
            body2 = _read_body(resp2)
    except urllib.error.HTTPError as e:
        raise MaxError(f'upload step2 HTTP {e.code}')
    except urllib.error.URLError as e:
        if 'CERTIFICATE_VERIFY_FAILED' in str(e.reason) and urlopen is None:
            try:
                with urllib.request.urlopen(req2, timeout=60, context=_UNVERIFIED_CTX) as r:
                    body2 = _read_body(r)
            except Exception as e2:
                raise MaxError(f'upload step2: {e2}')
        else:
            raise MaxError(f'upload step2: {e.reason}')
    file_token = body2.get('token')
    if not file_token:
        raise MaxError('upload step2: no token')
    return file_token


def send_file(token: str, chat_id: int, file_token: str, caption: str = '', urlopen=None):
    """Отправить файл в чат MAX."""
    attachments = [{'type': 'file', 'payload': {'token': file_token}}]
    return _post(f'/messages?chat_id={chat_id}', token,
                 {'text': caption, 'attachments': attachments},
                 urlopen=urlopen)


def send_with_buttons(token: str, chat_id: int, text: str, urlopen=None):
    """Отправить текст с инлайн-клавиатурой (кнопки-команды)."""
    keyboard = [[
        {'type': 'callback', 'text': 'Оценки', 'payload': '/grades'},
        {'type': 'callback', 'text': 'Сегодня', 'payload': '/today'},
    ], [
        {'type': 'message', 'text': 'Расписание'},
        {'type': 'message', 'text': 'Средний балл'},
        {'type': 'message', 'text': 'Долги'},
    ], [
        {'type': 'callback', 'text': 'Отвязать', 'payload': '/unbind'},
    ]]
    attachments = [{'type': 'inline_keyboard', 'payload': {'buttons': keyboard}}]
    return _post(f'/messages?chat_id={chat_id}', token,
                 {'text': text, 'attachments': attachments},
                 urlopen=urlopen)


def answer_callback(token: str, callback_id: str, notification: str = '', urlopen=None):
    """Подтвердить callback уведомлением."""
    return _post(f'/answers?callback_id={callback_id}', token,
                 {'notification': notification},
                 urlopen=urlopen)


def get_updates(token: str, marker=None, timeout: int = POLL_TIMEOUT, urlopen=None):
    """Получить обновления. Возвращает (updates, marker)."""
    path = f'/updates?limit=100&timeout={timeout}'
    if marker is not None:
        path += f'&marker={marker}'
    body = _get(path, token, urlopen=urlopen, timeout=timeout + 10)
    updates = body.get('updates', [])
    new_marker = body.get('marker', marker)
    return updates, new_marker


WELCOME = WELCOME
HELP_NEW = ('Команды:\n'
            '/start — привязать фамилию\n'
            '/help — эта справка')
HELP_BOUND = ('Команды:\n'
              '/grades — мои оценки\n'
              '/today — занятия сегодня\n'
              '/vedomost — ведомость файлом\n'
              '/unbind — отвязать чат\n'
              '/help — эта справка')
CURATOR_HELP = ('Команды куратора:\n'
                '/vedomost — ведомость группы\n'
                '/help — справка\n'
                '/unbind — отвязать')


def _fmt_avg(v: float) -> str:
    s = f"{v:.2f}"
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s


def schedule_text(db, student_id: int) -> str:
    """Pure builder for /schedule: next 7 days from tomorrow."""
    st = db.get_student(student_id)
    if not st:
        return 'Расписание пусто.'
    group_id = st['group_id']
    from datetime import date as _date, timedelta as _td
    today = _date.today()
    lines = []
    for delta in range(1, 8):
        d = today + _td(days=delta)
        iso = d.isoformat()
        isow = d.isoweekday()
        week_num = d.isocalendar()[1]
        week_type = 1 if week_num % 2 == 1 else 2
        try:
            rows = db.get_schedule_for_day(isow, week_type)
        except Exception:
            rows = []
        filtered = [dict(r) for r in rows if r['group_id'] == group_id]
        if filtered:
            # filtered already ordered by lesson_number
            names = ', '.join(f.get('subject_name', '?') for f in filtered)
            ddmm = f"{iso[8:10]}.{iso[5:7]}"
            lines.append(f"{ddmm}: {names}")
    if not lines:
        return 'Расписание пусто.'
    return "Расписание:\n" + "\n".join(lines)


def avg_text(db, student_id: int) -> str:
    """Per-subject numeric average of 2-5."""
    rows = [dict(r) for r in db.student_grades(student_id)]
    per_subj: dict[str, list[int]] = {}
    for r in rows:
        g_raw = r.get('grade')
        if g_raw is None:
            continue
        g_str = str(g_raw).strip()
        try:
            g = int(g_str)
        except Exception:
            continue
        if g < 2 or g > 5:
            continue
        subj = r.get('subject_name') or '?'
        per_subj.setdefault(subj, []).append(g)
    if not per_subj:
        return 'Оценок пока нет.'
    lines = []
    all_vals: list[int] = []
    for subj, vals in per_subj.items():
        avg = sum(vals) / len(vals)
        fmt = _fmt_avg(avg)
        lines.append(f"{subj}: {fmt}")
        all_vals.extend(vals)
    overall = sum(all_vals) / len(all_vals) if all_vals else 0
    overall_fmt = _fmt_avg(overall)
    return "Средний балл:\n" + "\n".join(lines) + f"\nОбщий: {overall_fmt}"


# alias names for tests that may use different names
average_text = avg_text
avg_builder = avg_text


def debts_text(db, student_id: int) -> str:
    st = db.get_student(student_id)
    if not st:
        return 'Долгов нет.'
    group_id = st['group_id']
    try:
        subjects = [dict(r) for r in db.list_subjects(group_id)]
    except Exception:
        subjects = []
    debts = []
    for subj in subjects:
        try:
            grades = db.student_grades(student_id, subj['id'])
        except Exception:
            grades = []
        if not grades:
            debts.append(subj['name'])
    if not debts:
        return 'Долгов нет.'
    return "Долги:\n" + "\n".join(debts)


# alias
debt_text = debts_text


def process_text(text: str, chat_id: int, db) -> str:
    """Чистая логика диалога: вход снаружи, БД — аргументом. Возвращает ответ."""
    from tgbot import my_grades_text, today_text
    from tgbot import _fio

    t = (text or '').strip()
    low = t.lower()
    # curator bind first (like /teacher)
    if low.startswith('/curator') or low.startswith('curator') or low.startswith('куратор') or low.startswith('/куратор'):
        parts = t.split(None, 1)
        if len(parts) < 2 or not parts[1].strip():
            return 'Укажи код: /curator КОД'
        code = parts[1].strip()
        row = db.find_curator_by_code(code)
        if row:
            gid = row['group_id']
            db.bind_curator(gid, chat_id)
            grp = db.conn.execute("SELECT name FROM groups WHERE id=?", (gid,)).fetchone()
            name = grp['name'] if grp else str(gid)
            return f'Привязан как куратор группы {name}.'
        else:
            return 'Неверный код — смотри страницу группы'
    # teacher command early - works regardless of binding
    if low.startswith('/teacher') or low.startswith('teacher') or low.startswith('учитель') or low.startswith('/учитель'):
        # extract code part
        parts = t.split(None, 1)
        if len(parts) < 2 or not parts[1].strip():
            return 'Укажи код: /teacher КОД'
        code = parts[1].strip()
        expected = db.get_setting('max_teacher_code')
        if expected is None:
            import uuid
            expected = uuid.uuid4().hex[:8]
            db.set_setting('max_teacher_code', expected)
        if code.strip().lower() == expected.lower():
            db.set_setting('max_teacher_chat', str(chat_id))
            return 'Преподаватель привязан.'
        else:
            return 'Неверный код — смотри Настройки'
    # curator-bound chats BEFORE student flow
    cur_gid = db.curator_group_for_chat(chat_id)
    if cur_gid is not None:
        if low in ('/vedomost', 'ведомость'):
            return 'VEDOMOST_CURATOR:'
        if low in ('/help', 'help', 'помощь'):
            return CURATOR_HELP
        if low in ('/unbind', 'отвязать'):
            db.unbind_curator(cur_gid)
            return 'Отвязка выполнена.'
        return CURATOR_HELP
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
    if low in ('/schedule', 'schedule', 'расписание', '/расписание'):
        return schedule_text(db, sid)
    if low in ('/avg', 'avg', 'средний балл', 'средняя', '/средний', '/средняя'):
        return avg_text(db, sid)
    if low in ('/debts', 'debts', 'долги', '/долги'):
        return debts_text(db, sid)
    if low in ('/unbind', 'отвязать'):
        db.unbind_max(chat_id)
        return 'Привязка снята. Для новой отправь фамилию.'
    if low in ('/vedomost', 'ведомость'):
        if sid is None:
            return 'Сначала привяжись: отправь свою фамилию.'
        return 'VEDOMOST:'
    if t.startswith('/'):
        return 'Не знаю такую команду.\n\n' + HELP_BOUND
    return 'Ты уже привязан(а).\n\n' + HELP_BOUND


def _get_marker(db) -> int | None:
    try:
        v = db.get_setting('max_last_marker')
        return int(v) if v else None
    except (TypeError, ValueError):
        return None


def _handle_vedomost(token: str, chat_id: int, db_factory, urlopen=None):
    """Отправить xlsx-файлы ведомости по предметам (после /vedomost)."""
    from report_export import export_student_grades_xlsx
    db = db_factory()
    try:
        sid = db.get_max_link(chat_id)
        if sid is None:
            send_message(token, chat_id, 'Сначала привяжись.', urlopen=urlopen)
            return
        st = db.get_student(sid)
        if not st:
            send_message(token, chat_id, 'Привязка устарела.', urlopen=urlopen)
            return
        group_id = st['group_id']
        subjects = [dict(r) for r in db.list_subjects(group_id)]
        sent_any = False
        for subj in subjects:
            grades = db.student_grades(sid, subj['id'])
            if not grades:
                continue
            xlsx_bytes = export_student_grades_xlsx(subj['id'], sid, db)
            ft = upload_file(token, xlsx_bytes,
                             f"{subj['name']}.xlsx", urlopen=urlopen)
            send_file(token, chat_id, ft,
                      caption=subj['name'], urlopen=urlopen)
            sent_any = True
            time.sleep(0.6)
        if not sent_any:
            send_message(token, chat_id, 'Оценок пока нет.', urlopen=urlopen)
    except Exception:
        try:
            send_message(token, chat_id,
                         'Ошибка при формировании ведомости.', urlopen=urlopen)
        except MaxError:
            pass
    finally:
        db.close()


def _handle_curator_vedomost(token: str, chat_id: int, db_factory, urlopen=None):
    """Отправить GROUP xlsx для куратора — полный файл группы."""
    from report_export import export_grades_xlsx
    db = db_factory()
    try:
        gid = db.curator_group_for_chat(chat_id)
        if gid is None:
            send_message(token, chat_id, 'Не привязан как куратор.', urlopen=urlopen)
            return
        subjects = [dict(r) for r in db.list_subjects(gid)]
        sent_any = False
        for subj in subjects:
            try:
                cnt = db.conn.execute(
                    "SELECT COUNT(*) FROM grades JOIN lessons ON grades.lesson_id=lessons.id WHERE lessons.actual_subject_id=? AND lessons.status NOT IN ('cancelled','replaced')",
                    (subj['id'],)).fetchone()[0]
            except Exception:
                cnt = 0
            if cnt == 0:
                continue
            xlsx_bytes = export_grades_xlsx(subj['id'], db)
            ft = upload_file(token, xlsx_bytes, f"{subj['name']}.xlsx", urlopen=urlopen)
            send_file(token, chat_id, ft, caption=subj['name'], urlopen=urlopen)
            sent_any = True
            time.sleep(0.6)
        if not sent_any:
            send_message(token, chat_id, 'Оценок пока нет.', urlopen=urlopen)
    except Exception:
        try:
            send_message(token, chat_id, 'Ошибка при формировании ведомости.', urlopen=urlopen)
        except MaxError:
            pass
    finally:
        db.close()


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
            msg_type = u.get('update_type') or u.get('type')
            # ---- message_created ----
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
                teacher_notify = None
                try:
                    sid_before = db.get_max_link(cid)
                    reply = process_text(text, cid, db)
                    sid_after = db.get_max_link(cid)
                    if sid_before is None and sid_after is not None:
                        try:
                            teacher = db.get_setting('max_teacher_chat')
                            if teacher:
                                st = db.get_student(sid_after)
                                if st:
                                    txt = f"Привязался: {st['last_name']} {st['first_name']}"
                                    try:
                                        gid = st['group_id']
                                        grp = db.conn.execute("SELECT name FROM groups WHERE id=?", (gid,)).fetchone()
                                        if grp and grp['name']:
                                            txt += f" ({grp['name']})"
                                    except Exception:
                                        pass
                                    teacher_notify = (teacher, txt)
                        except Exception:
                            pass
                    db.set_setting('max_last_marker', str(new_marker))
                except Exception:
                    reply = 'Ошибка, попробуй позже.'
                finally:
                    db.close()
                try:
                    if reply.startswith('VEDOMOST_CURATOR:'):
                        _handle_curator_vedomost(token, cid, db_factory, urlopen)
                    elif reply.startswith('VEDOMOST:'):
                        _handle_vedomost(token, cid, db_factory, urlopen)
                    else:
                        send_with_buttons(token, cid, reply, urlopen=urlopen)
                except MaxError:
                    pass
                if teacher_notify:
                    try:
                        t_chat, t_text = teacher_notify
                        send_message(token, int(t_chat), t_text, urlopen=urlopen)
                    except Exception:
                        pass
            # ---- message_callback ----
            elif msg_type == 'message_callback':
                cb = u.get('callback') or {}
                callback_id = cb.get('callback_id')
                payload = cb.get('payload')
                cb_msg = cb.get('message') or {}
                cb_recipient = cb_msg.get('recipient') or {}
                cb_user = cb.get('user') or {}
                cid = cb_recipient.get('chat_id')
                if cid is None:
                    cid = cb_user.get('user_id')
                if payload is None or cid is None:
                    continue
                try:
                    cid = int(cid)
                except (TypeError, ValueError):
                    continue
                db = db_factory()
                try:
                    reply = process_text(payload, cid, db)
                    db.set_setting('max_last_marker', str(new_marker))
                except Exception:
                    reply = 'Ошибка, попробуй позже.'
                finally:
                    db.close()
                try:
                    if reply.startswith('VEDOMOST_CURATOR:'):
                        _handle_curator_vedomost(token, cid, db_factory, urlopen)
                    elif reply.startswith('VEDOMOST:'):
                        _handle_vedomost(token, cid, db_factory, urlopen)
                    else:
                        send_with_buttons(token, cid, reply, urlopen=urlopen)
                except MaxError:
                    pass
                if callback_id:
                    try:
                        answer_callback(
                            token, callback_id, 'Готово', urlopen=urlopen)
                    except MaxError:
                        pass
            # ---- bot_started ----
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
                    send_with_buttons(token, cid, reply, urlopen=urlopen)
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


def due_teacher_digest(hour: int, last_sent: str | None, today: str) -> bool:
    """True when hour==7 and not sent today."""
    return hour == 7 and last_sent != today


def teacher_targets(db, today_iso: str) -> str:
    """List today's held lessons with marks count."""
    # held lessons for today
    lessons = [dict(r) for r in db.list_lessons_by_date(today_iso)]
    # filter held
    held = [l for l in lessons if l.get('status') == 'held']
    if not held:
        return 'Сегодня занятий нет.'
    lines = []
    date_label = _fmt_date_short(today_iso)
    header = f"Дайджест {date_label}:" if date_label else "Дайджест:"
    # group? just list each
    for l in held:
        subj = l.get('actual_subject_name') or l.get('planned_subject') or l.get('subject_name') or '?'
        try:
            cnt = db.attendance_count(l['id'])
        except Exception:
            cnt = 0
        if cnt == 0:
            lines.append(f"• {subj}: ПУСТО")
        else:
            lines.append(f"• {subj}: {cnt} оценок")
    return header + "\n" + "\n".join(lines)


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
                # teacher morning digest
                teacher_last = db.get_setting('max_teacher_digest_date')
                if due_teacher_digest(now_hour, teacher_last, today_str):
                    # only if bot enabled
                    try:
                        bot_token = db.get_setting('max_bot_token')
                        enabled = db.get_setting('max_bot_enabled')
                        if bot_token and enabled == '1':
                            chat_raw = db.get_setting('max_teacher_chat')
                            if chat_raw:
                                try:
                                    t_chat = int(chat_raw)
                                    text = teacher_targets(db, today_str)
                                    send_message(token, t_chat, text)
                                except Exception:
                                    pass
                        db.set_setting('max_teacher_digest_date', today_str)
                    except Exception:
                        try:
                            db.set_setting('max_teacher_digest_date', today_str)
                        except Exception:
                            pass
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
