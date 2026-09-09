from __future__ import annotations
import functools
import glob as _glob
import io
import json as _json
import tempfile
import threading
import time as _time
import uuid
from datetime import date, datetime
from typing import Any
import os
import re as _re

import sqlite3

from report_export import export_grades_xlsx, export_report_xlsx

# Server-side debounce for grade-push via MAX bot.
# Each tap on a grade cell resets a 10 s timer; only the settled grade
# is re-read from DB and sent to the student.
GRADE_PUSH_DELAY = 10.0  # seconds

# Registry of active timers keyed by (lesson_id, student_id).
# When a timer fires it is automatically removed.
_pending: dict[tuple[int, int], threading.Timer] = {}

CURATOR_PUSH_DELAY = 180.0
_pending_curator: dict[tuple[int, int], threading.Timer] = {}

from flask import Flask, Blueprint, Response, request, jsonify, send_from_directory, send_file

from database import Database

app = Flask(__name__, static_folder='static', template_folder='templates')

def get_db() -> Database:
    return Database()


def require_fields(*fields: str) -> Any:
    """Decorator: return 400 if request.json lacks any of the required fields."""
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            data = request.json or {}
            missing = [f for f in fields if f not in data or data[f] is None]
            if missing:
                return jsonify({'error': f'missing fields: {", ".join(missing)}'}), 400
            return f(*args, **kwargs)
        return wrapper
    return decorator


def optional_int(value: Any, default: Any = None) -> Any:
    """Convert query param to int or return default."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def dict_row(row) -> dict:
    return dict(row) if row else None


def row_get(row, key, default=''):
    """Helper for sqlite3.Row — defensive .keys() check."""
    if row is None:
        return default
    try:
        if key in row.keys():
            v = row[key]
            return v if v is not None else default
        return default
    except Exception:
        try:
            v = row[key]
            return v if v is not None else default
        except Exception:
            return default


def _lesson_notify_context(db, lesson_id):
    """Centralize Row .keys() defensive dance; return (ddmm, subject_name, group_id)."""
    try:
        lesson = db.get_lesson(lesson_id)
        if not lesson:
            return ('', '', None)
        subject_name = row_get(lesson, 'actual_subject_name', '')
        if not subject_name:
            subject_name = row_get(lesson, 'planned_subject', '')
        date_iso = row_get(lesson, 'date', '')
        ddmm = f"{date_iso[8:10]}.{date_iso[5:7]}" if date_iso and len(date_iso) >= 10 else ''
        group_id = None
        try:
            if 'group_id' in lesson.keys():
                group_id = lesson['group_id']
        except Exception:
            pass
        if group_id is None:
            try:
                sid = row_get(lesson, 'subject_id', None)
                if sid is not None and sid != '':
                    r = db.conn.execute("SELECT group_id FROM subjects WHERE id=?", (sid,)).fetchone()
                    if r:
                        group_id = r['group_id']
            except Exception:
                pass
        return (ddmm, subject_name or '', group_id)
    except Exception:
        return ('', '', None)


def _is_bot_active(db, token_key='max_bot_token', enabled_key='max_bot_enabled'):
    """Token truthy and enabled=='1'."""
    try:
        return bool(db.get_setting(token_key)) and db.get_setting(enabled_key) == '1'
    except Exception:
        return False


def _notify_group_chats(db, group_id, token, enabled, msg_text):
    """Best-effort daemon thread with 0.6s gaps; lazy imports inside."""
    try:
        if group_id is None:
            return
        if not token or enabled != '1':
            return
        chat_ids = []
        try:
            for st in db.list_students(group_id):
                try:
                    cid = db.get_max_student_chat(st['id'])
                    if cid is not None:
                        chat_ids.append(cid)
                except Exception:
                    continue
        except Exception:
            return
        if not chat_ids:
            return

        def _run():
            try:
                import time as _time
                import maxbot as _maxbot
                for cid in chat_ids:
                    try:
                        _maxbot.send_message(token, cid, msg_text)
                    except Exception:
                        pass
                    _time.sleep(0.6)
            except Exception:
                pass

        threading.Thread(target=_run, daemon=True).start()
    except Exception:
        pass


# ---- SPA shell ----
def _static_ver() -> str:
    """Версия статики по mtime bundle: новый APK = новый URL = WebView не отдаст кэш."""
    try:
        base = os.path.join(os.path.dirname(__file__), 'static')
        m = max(os.path.getmtime(os.path.join(base, f)) for f in ('app.js', 'style.css'))
        return str(int(m))
    except Exception:
        return '1'


STATIC_VER = _static_ver()


@app.route('/')
def index():
    with open(os.path.join(os.path.dirname(__file__), 'templates', 'index.html'),
              encoding='utf-8') as f:
        html = f.read()
    html = html.replace('/static/app.js', f'/static/app.js?v={STATIC_VER}')
    html = html.replace('/static/style.css', f'/static/style.css?v={STATIC_VER}')
    return Response(html, mimetype='text/html')


@app.route('/static/<path:path>')
def serve_static(path: str):
    resp = send_from_directory('static', path)
    resp.headers['Cache-Control'] = 'no-store'
    return resp


@app.route('/api/version', methods=['GET'])
def app_version():
    return jsonify({'ver': STATIC_VER})


# ---- Groups ----
groups_bp = Blueprint('groups', __name__, url_prefix='/api/groups')


@groups_bp.route('', methods=['GET'])
def list_groups():
    return jsonify([dict(r) for r in get_db().list_groups()])


@groups_bp.route('', methods=['POST'])
@require_fields('name')
def create_group():
    try:
        gid = get_db().add_group(request.json['name'])
    except sqlite3.IntegrityError as e:
        return jsonify({'error': 'duplicate or invalid group', 'detail': str(e)}), 400
    return jsonify({'id': gid}), 201


@groups_bp.route('/<int:group_id>', methods=['DELETE'])
def delete_group(group_id: int):
    get_db().delete_group(group_id)
    return jsonify({'ok': True})


@groups_bp.route('/<int:group_id>', methods=['PATCH'])
def update_group(group_id: int):
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'error': 'name is required'}), 400
    try:
        get_db().update_group(group_id, data['name'])
    except sqlite3.IntegrityError as e:
        return jsonify({'error': 'duplicate or invalid group', 'detail': str(e)}), 400
    return jsonify({'ok': True})


@groups_bp.route('/<int:group_id>/curator', methods=['GET'])
def get_group_curator(group_id: int):
    db = get_db()
    # Optional: verify group exists? Return 404 if not? For now ensure code
    # If group doesn't exist, ensure will still create row but FK will fail? Better check.
    # Check group exists
    exists = db.conn.execute("SELECT 1 FROM groups WHERE id=?", (group_id,)).fetchone()
    if not exists:
        return jsonify({'error': 'group not found'}), 404
    code = db.ensure_curator_code(group_id)
    bound = db.get_curator_chat(group_id) is not None
    return jsonify({'code': code, 'bound': bound})


@groups_bp.route('/<int:group_id>/curator', methods=['DELETE'])
def delete_group_curator(group_id: int):
    db = get_db()
    db.unbind_curator(group_id)
    return jsonify({'ok': True})


app.register_blueprint(groups_bp)


# ---- Students ----
students_bp = Blueprint('students', __name__, url_prefix='/api/students')


@students_bp.route('', methods=['GET'])
def list_students():
    group_id = optional_int(request.args.get('group_id'))
    return jsonify([dict(r) for r in get_db().list_students(group_id)])


@students_bp.route('/bulk', methods=['POST'])
@require_fields('group_id', 'students')
def add_students_bulk():
    data = request.json
    count = get_db().add_students_bulk(data['group_id'], data['students'])
    return jsonify({'added': count}), 201


@students_bp.route('/<int:student_id>/grades', methods=['GET'])
def student_grades(student_id: int):
    subject_id = optional_int(request.args.get('subject_id'))
    return jsonify([dict(r) for r in get_db().student_grades(student_id, subject_id)])


@students_bp.route('/<int:student_id>', methods=['DELETE'])
def delete_student(student_id: int):
    get_db().delete_student(student_id)
    return jsonify({'ok': True})


@students_bp.route('/<int:student_id>', methods=['PATCH'])
def update_student(student_id: int):
    data = request.get_json()
    if not data or 'last_name' not in data or 'first_name' not in data:
        return jsonify({'error': 'last_name and first_name are required'}), 400
    try:
        get_db().update_student(
            student_id,
            data['last_name'],
            data['first_name'],
            data.get('middle_name', '')
        )
    except sqlite3.IntegrityError as e:
        return jsonify({'error': 'duplicate or invalid student', 'detail': str(e)}), 400
    return jsonify({'ok': True})


app.register_blueprint(students_bp)


# ---- Subjects ----
subjects_bp = Blueprint('subjects', __name__, url_prefix='/api/subjects')


@subjects_bp.route('', methods=['GET'])
def list_subjects():
    group_id = optional_int(request.args.get('group_id'))
    include_free = bool(optional_int(request.args.get('include_free'), 0))
    return jsonify([dict(r) for r in get_db().list_subjects(group_id, include_free)])


@subjects_bp.route('', methods=['POST'])
@require_fields('name', 'total_hours', 'group_id')
def create_subject():
    data = request.json
    try:
        sid = get_db().add_subject(data['name'], data['total_hours'], data['group_id'])
    except sqlite3.IntegrityError as e:
        return jsonify({'error': 'duplicate or invalid subject', 'detail': str(e)}), 400
    return jsonify({'id': sid}), 201


@subjects_bp.route('/<int:subject_id>', methods=['DELETE'])
def delete_subject(subject_id: int):
    get_db().delete_subject(subject_id)
    return jsonify({'ok': True})


@subjects_bp.route('/<int:subject_id>', methods=['PATCH'])
def update_subject(subject_id: int):
    data = request.get_json()
    if not data or 'name' not in data or 'total_hours' not in data:
        return jsonify({'error': 'name and total_hours are required'}), 400
    try:
        get_db().update_subject(subject_id, data['name'], data['total_hours'])
    except sqlite3.IntegrityError as e:
        return jsonify({'error': 'duplicate or invalid subject', 'detail': str(e)}), 400
    return jsonify({'ok': True})


@subjects_bp.route('/<int:subject_id>/gradebook')
def subject_gradebook(subject_id: int):
    db = get_db()
    students, lessons, grades = db.subject_gradebook(subject_id)
    return jsonify({
        'summary': dict_row(db.subject_summary(subject_id)),
        'students': students,
        'lessons': lessons,
        'grades': grades
    })


@subjects_bp.route('/<int:subject_id>/substitution-list', methods=['GET'])
def substitution_list(subject_id: int):
    db = get_db()
    subj = db.conn.execute("SELECT * FROM subjects WHERE id = ?", (subject_id,)).fetchone()
    if not subj:
        return jsonify([])
    return jsonify([dict(r) for r in db.list_subjects(subj['group_id'])])


@subjects_bp.route('/<int:subject_id>/lessons', methods=['GET'])
def subject_lessons(subject_id: int):
    return jsonify([dict(r) for r in get_db().list_lessons_for_subject(subject_id)])


app.register_blueprint(subjects_bp)


# ---- Schedule ----
schedule_bp = Blueprint('schedule', __name__, url_prefix='/api/schedule')


@schedule_bp.route('', methods=['GET'])
def get_schedule():
    return jsonify([dict(r) for r in get_db().list_schedule()])


@schedule_bp.route('', methods=['POST'])
@require_fields('day_of_week', 'lesson_number', 'subject_id')
def add_schedule_entry():
    data = request.json
    eid = get_db().add_schedule_entry(
        data['day_of_week'], data['lesson_number'],
        data['subject_id'], data.get('week_type', 0))
    return jsonify({'id': eid}), 201


@schedule_bp.route('/<int:entry_id>', methods=['DELETE'])
def delete_schedule_entry(entry_id: int):
    get_db().delete_schedule_entry(entry_id)
    return jsonify({'ok': True})


@schedule_bp.route('/<int:entry_id>', methods=['PATCH'])
@require_fields('day_of_week', 'lesson_number', 'subject_id', 'week_type')
def update_schedule_entry(entry_id: int):
    data = request.json
    get_db().update_schedule_entry(
        entry_id, data['day_of_week'], data['lesson_number'],
        data['subject_id'], data['week_type'])
    return jsonify({'ok': True})


@schedule_bp.route('/today', methods=['GET'])
def schedule_today():
    today = date.today()
    day = today.isoweekday()
    week_num = today.isocalendar()[1]
    week_type = 1 if week_num % 2 == 1 else 2
    db = get_db()
    lessons = []
    for r in db.list_lessons_by_date(today.isoformat()):
        ld = dict(r)
        ld['needs_attention'] = ld['status'] != 'cancelled' and db.attendance_count(ld['id']) == 0
        lessons.append(ld)
    return jsonify({
        'date': today.isoformat(),
        'formatted_date': today.strftime('%d.%m.%Y'),
        'day_of_week': day,
        'schedule': [dict(r) for r in db.get_schedule_for_day(day, week_type)],
        'lessons': lessons
    })


app.register_blueprint(schedule_bp)


# ---- Lessons ----
lessons_bp = Blueprint('lessons', __name__, url_prefix='/api/lessons')


@lessons_bp.route('', methods=['POST'])
@require_fields('subject_id')
def create_lesson():
    data = request.json
    db = get_db()
    raw_date = data.get('date')
    if raw_date:
        try:
            lesson_date = date.fromisoformat(raw_date)
        except ValueError:
            return jsonify({'error': 'bad date'}), 400
        if lesson_date > date.today():
            return jsonify({'error': 'date in future'}), 400
        lesson_date = lesson_date.isoformat()
    else:
        lesson_date = date.today().isoformat()
    lesson_number = data.get('lesson_number')
    # Дедуп: двойной тап «Начать занятие» не должен плодить дубли —
    # возвращаем уже созданное проведённое занятие за сегодня.
    if data.get('status', 'held') == 'held' and lesson_number is not None:
        existing = db.find_held_lesson(data['subject_id'], lesson_date, lesson_number)
        if existing:
            return jsonify({'id': existing['id'], 'deduped': True}), 200
    lid = db.add_lesson(
        data['subject_id'],
        lesson_date,
        data.get('actual_subject_id'),
        data.get('status', 'held'),
        lesson_number)
    return jsonify({'id': lid}), 201


@lessons_bp.route('/<int:lesson_id>', methods=['GET'])
def get_lesson(lesson_id: int):
    lesson = get_db().get_lesson(lesson_id)
    if not lesson:
        return jsonify({'error': 'not found'}), 404
    lesson_dict = dict(lesson)
    # Add formatted_date for frontend convenience
    if lesson_dict.get('date'):
        try:
            dt = datetime.strptime(lesson_dict['date'], '%Y-%m-%d')
            lesson_dict['formatted_date'] = dt.strftime('%d.%m.%Y')
        except ValueError:
            lesson_dict['formatted_date'] = lesson_dict['date']
    return jsonify(lesson_dict)


@lessons_bp.route('/<int:lesson_id>/substitute', methods=['PATCH'])
@require_fields('new_subject_id')
def substitute_lesson(lesson_id: int):
    db = get_db()
    ddmm, old_name, group_id = _lesson_notify_context(db, lesson_id)
    new_subject_id = request.json['new_subject_id']
    try:
        new_row = db.conn.execute("SELECT name FROM subjects WHERE id=?", (new_subject_id,)).fetchone()
        new_name = row_get(new_row, 'name', '')
    except Exception:
        new_name = ''
    msg_text = f"Замена {ddmm}: {old_name} → {new_name}" if ddmm else f"Замена: {old_name} → {new_name}"
    new_id = db.substitute_lesson(lesson_id, new_subject_id)
    try:
        token = db.get_setting('max_bot_token')
        enabled = db.get_setting('max_bot_enabled')
        if _is_bot_active(db, 'max_bot_token', 'max_bot_enabled'):
            _notify_group_chats(db, group_id, token, enabled, msg_text)
    except Exception:
        pass
    return jsonify({'ok': True, 'new_lesson_id': new_id})


@lessons_bp.route('/<int:lesson_id>/cancel', methods=['PATCH'])
def cancel_lesson(lesson_id: int):
    db = get_db()
    ddmm, subject_name, group_id = _lesson_notify_context(db, lesson_id)
    msg_text = f"Отменено занятие: {subject_name} {ddmm}".strip() if subject_name else f"Отменено занятие: {ddmm}".strip()
    if not ddmm:
        msg_text = f"Отменено занятие: {subject_name}".strip()
    db.cancel_lesson(lesson_id)
    try:
        token = db.get_setting('max_bot_token')
        enabled = db.get_setting('max_bot_enabled')
        if _is_bot_active(db, 'max_bot_token', 'max_bot_enabled'):
            _notify_group_chats(db, group_id, token, enabled, msg_text)
    except Exception:
        pass
    return jsonify({'ok': True})


@lessons_bp.route('/<int:lesson_id>', methods=['DELETE'])
def delete_lesson(lesson_id: int):
    get_db().delete_lesson(lesson_id)
    return jsonify({'ok': True})


@lessons_bp.route('/<int:lesson_id>/status', methods=['PATCH'])
@require_fields('status')
def update_lesson_status(lesson_id: int):
    get_db().set_lesson_status(lesson_id, request.json['status'])
    return jsonify({'ok': True})


@lessons_bp.route('/<int:lesson_id>/adjacent', methods=['GET'])
def adjacent_lessons(lesson_id: int):
    prev_id, next_id = get_db().get_adjacent_lessons(lesson_id)
    return jsonify({'prev_id': prev_id, 'next_id': next_id})


@lessons_bp.route('/<int:lesson_id>/attendance', methods=['GET'])
def get_attendance(lesson_id: int):
    db = get_db()
    lesson = db.get_lesson(lesson_id)
    return jsonify({
        'lesson': dict_row(lesson),
        'attendance': [dict(r) for r in db.get_attendance(lesson_id)],
        'students': [dict(r) for r in db.get_group_students(lesson_id)] if lesson else []
    })


@lessons_bp.route('/<int:lesson_id>/attendance', methods=['POST'])
def mark_attendance(lesson_id: int):
    data = request.json
    db = get_db()
    if isinstance(data, list):
        db.mark_attendance_bulk(lesson_id, data)
    else:
        db.mark_attendance(lesson_id, data['student_id'], data['grade'])

    # ---- Schedule debounced grade push via MAX bot ----
    try:
        pairs = []
        if isinstance(data, list):
            pairs = [(r.get('student_id'), r.get('grade')) for r in data]
        else:
            pairs = [(data['student_id'], data['grade'])]

        token = db.get_setting('max_bot_token')
        enabled = db.get_setting('max_bot_enabled')
        if not _is_bot_active(db, 'max_bot_token', 'max_bot_enabled'):
            # Bot not active — cancel any pending timers for these keys
            for sid, _grade in pairs:
                key = (lesson_id, sid)
                old = _pending.pop(key, None)
                if old is not None:
                    old.cancel()
                old2 = _pending_curator.pop(key, None)
                if old2 is not None:
                    old2.cancel()
            return jsonify({'ok': True})

        for sid, grade in pairs:
            key = (lesson_id, sid)
            # Cancel any existing timer for this key (debounce reset)
            old = _pending.pop(key, None)
            if old is not None:
                old.cancel()
            # If grade is falsy (deleted / empty), just skip — no schedule
            if not grade:
                continue
            t = threading.Timer(
                GRADE_PUSH_DELAY,
                _fire_grade_push,
                args=(token, lesson_id, sid),
            )
            t.daemon = True
            _pending[key] = t
            t.start()

        # ---- Curator push (group-wide) ----
        # Resolve group_id: try actual_subject_id first (the subject
        # actually taught), then subject_id, then any graded student's group.
        group_id = None
        try:
            les = db.get_lesson(lesson_id)
            if les is not None:
                for col in ('actual_subject_id', 'subject_id'):
                    sid_sub = row_get(les, col, None)
                    if sid_sub is not None and sid_sub != '':
                        try:
                            prow = db.conn.execute(
                                "SELECT group_id FROM subjects WHERE id=?",
                                (sid_sub,),
                            ).fetchone()
                            if prow:
                                group_id = prow['group_id']
                                break
                        except Exception:
                            pass
                # Fallback: pick group from any graded student
                if group_id is None:
                    for _sid, _g in pairs:
                        try:
                            st = db.get_student(_sid)
                            if st:
                                group_id = row_get(st, 'group_id', None)
                                if group_id is not None:
                                    break
                        except Exception:
                            pass
        except Exception as exc:
            print(f"[curator-push] group_id resolve error: {exc}", flush=True)

        cur_chat = None
        try:
            if group_id is not None:
                cur_chat = db.get_curator_chat(group_id)
        except Exception as exc:
            print(f"[curator-push] get_curator_chat error: {exc}", flush=True)
            cur_chat = None

        print(
            f"[curator-push] schedule: lesson={lesson_id} group={group_id} "
            f"cur_chat={cur_chat} pairs={len(pairs)}",
            flush=True,
        )

        if cur_chat is None:
            for sid, _grade in pairs:
                key = (lesson_id, sid)
                old = _pending_curator.pop(key, None)
                if old is not None:
                    old.cancel()
        else:
            for sid, grade in pairs:
                key = (lesson_id, sid)
                old = _pending_curator.pop(key, None)
                if old is not None:
                    old.cancel()
                if not grade:
                    continue
                t2 = threading.Timer(
                    CURATOR_PUSH_DELAY,
                    _fire_curator_push,
                    args=(token, lesson_id, sid, group_id),
                )
                t2.daemon = True
                _pending_curator[key] = t2
                t2.start()
    except Exception as exc:
        print(f"[curator-push] outer error: {exc}", flush=True)

    return jsonify({'ok': True})


def _read_settled_grade(db, lesson_id: int, student_id: int) -> str:
    try:
        rows = db.get_attendance(lesson_id)
        row = None
        for r in rows:
            if r['student_id'] == student_id:
                row = r
                break
        grade = row['grade'] if row and dict(row).get('grade') else ''
        return grade or ''
    except Exception:
        return ''


def _fire_grade_push(token: str, lesson_id: int, student_id: int) -> None:
    """Timer callback: re-read settled grade from DB and send notification.

    Timer reset on every tap; only the settled grade is re-read from DB
    and sent — so the student always gets the *latest* value.
    """
    key = (lesson_id, student_id)
    _pending.pop(key, None)
    try:
        from database import Database as _DB
        db = _DB()
        try:
            grade = _read_settled_grade(db, lesson_id, student_id)
            if not grade:
                return

            lesson = db.get_lesson(lesson_id)
            if not lesson:
                return

            raw_date = lesson['date'] or ''
            # DD.MM format from ISO date string
            date_str = f'{raw_date[8:10]}.{raw_date[5:7]}' if len(raw_date) >= 10 else ''
            subject = row_get(lesson, 'actual_subject_name', '')

            import maxbot as _maxbot
            _maxbot.notify_grade(token, student_id, grade, date_str, subject)
        except Exception:
            pass
        finally:
            try:
                db.close()
            except Exception:
                pass
    except Exception:
        pass


def _fire_curator_push(token: str, lesson_id: int, student_id: int, group_id: int) -> None:
    key = (lesson_id, student_id)
    _pending_curator.pop(key, None)
    try:
        from database import Database as _DB
        db = _DB()
        try:
            grade = _read_settled_grade(db, lesson_id, student_id)
            if not grade:
                print(f"[curator-push] skip: no grade for lesson={lesson_id} student={student_id}", flush=True)
                return

            # Resolve cur_chat: prefer the group_id passed from schedule,
            # fall back to re-lookup from lesson row.
            cur_chat = None
            try:
                cur_chat = db.get_curator_chat(group_id)
            except Exception as exc:
                print(f"[curator-push] get_curator_chat({group_id}) error: {exc}", flush=True)

            if not cur_chat:
                # Fallback: try to resolve group from lesson's subject
                try:
                    les = db.get_lesson(lesson_id)
                    if les is not None:
                        for col in ('actual_subject_id', 'subject_id'):
                            sid_sub = row_get(les, col, None)
                            if sid_sub is not None and sid_sub != '':
                                prow = db.conn.execute(
                                    "SELECT group_id FROM subjects WHERE id=?",
                                    (sid_sub,),
                                ).fetchone()
                                if prow and prow['group_id']:
                                    cur_chat = db.get_curator_chat(prow['group_id'])
                                    if cur_chat:
                                        group_id = prow['group_id']
                                        break
                except Exception as exc:
                    print(f"[curator-push] fallback group resolve error: {exc}", flush=True)

            if not cur_chat:
                print(
                    f"[curator-push] no cur_chat: lesson={lesson_id} student={student_id} "
                    f"group={group_id}",
                    flush=True,
                )
                return

            st = db.get_student(student_id)
            if not st:
                print(f"[curator-push] no student: id={student_id}", flush=True)
                return
            fio = f"{st['last_name']} {st['first_name'][0]}." if st['first_name'] else f"{st['last_name']}"
            lesson = db.get_lesson(lesson_id)
            if not lesson:
                print(f"[curator-push] no lesson: id={lesson_id}", flush=True)
                return
            raw_date = lesson['date'] or ''
            date_str = f'{raw_date[8:10]}.{raw_date[5:7]}' if len(raw_date) >= 10 else ''
            subject = row_get(lesson, 'actual_subject_name', '')
            if not subject:
                subject = row_get(lesson, 'planned_subject', '')
            text = f"{fio}: {subject} — {grade} ({date_str})"
            import maxbot as _maxbot
            _maxbot.send_message(token, int(cur_chat), text)
            print(
                f"[curator-push] sent: cur_chat={cur_chat} text={text!r}",
                flush=True,
            )
        except Exception as exc:
            print(f"[curator-push] inner error: {exc}", flush=True)
        finally:
            try:
                db.close()
            except Exception:
                pass
    except Exception as exc:
        print(f"[curator-push] outer error: {exc}", flush=True)


@lessons_bp.route('/date/<date_str>', methods=['GET'])
def lessons_by_date(date_str: str):
    return jsonify([dict(r) for r in get_db().list_lessons_by_date(date_str)])


app.register_blueprint(lessons_bp)


# ---- Reports ----
reports_bp = Blueprint('reports', __name__, url_prefix='/api/reports')


@reports_bp.route('/substitutions', methods=['GET'])
def substitutions():
    return jsonify([dict(r) for r in get_db().get_substitutions()])


@reports_bp.route('/average/<int:subject_id>', methods=['GET'])
def average_grades(subject_id: int):
    return jsonify([dict(r) for r in get_db().average_grades(subject_id)])


@reports_bp.route('/daily', methods=['GET'])
def daily_report():
    date_str = request.args.get('date', date.today().isoformat())
    return jsonify([dict(r) for r in get_db().daily_report(date_str)])


@reports_bp.route('/neglected/<int:group_id>', methods=['GET'])
def neglected_students(group_id: int):
    min_grades = optional_int(request.args.get('min_grades'), 3)
    days = optional_int(request.args.get('days'), 14)
    return jsonify([dict(r) for r in get_db().students_without_recent_grades(group_id, min_grades, days)])


app.register_blueprint(reports_bp)


# ---- Export ----
export_bp = Blueprint('export', __name__, url_prefix='/api/export')


def _missing_deps_response(e: Exception):
    return jsonify({'error': f'export unavailable: {e}. Rebuild APK with openpyxl.'}), 500


@export_bp.route('/grades/<int:subject_id>.<fmt>')
def download_grades(subject_id: int, fmt: str):
    if fmt != 'xlsx':
        return 'Only xlsx is enabled', 400
    try:
        data = export_grades_xlsx(subject_id, get_db())
        return send_file(io.BytesIO(data),
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True, download_name=f'grades_{subject_id}.xlsx')
    except RuntimeError as e:
        return _missing_deps_response(e)


@export_bp.route('/report/<date>.<fmt>')
def download_report(date: str, fmt: str):
    if fmt != 'xlsx':
        return 'Only xlsx is enabled', 400
    try:
        data = export_report_xlsx(date, get_db())
        return send_file(io.BytesIO(data),
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True, download_name=f'report_{date}.xlsx')
    except RuntimeError as e:
        return _missing_deps_response(e)


@export_bp.route('/lessons.ics')
def download_lessons_ics():
    return 'Only xlsx is enabled', 400


@export_bp.route('/schedule.ics')
def download_schedule_ics():
    return 'Only xlsx is enabled', 400


# ---- Telegram bot settings ----
settings_bp = Blueprint('settings', __name__, url_prefix='/api/settings')


@settings_bp.route('/bot', methods=['GET'])
def bot_settings():
    db = get_db()
    return jsonify({
        'has_token': bool(db.get_setting('bot_token')),
        'enabled': db.get_setting('bot_enabled') == '1',
    })


@settings_bp.route('/bot', methods=['POST'])
def save_bot_settings():
    data = request.json or {}
    db = get_db()
    if 'token' in data:
        token = (data['token'] or '').strip()
        db.set_setting('bot_token', token or None)
    if 'enabled' in data:
        v = data['enabled']
        db.set_setting('bot_enabled', '1' if v in (True, 1, '1', 'on', 'true') else '0')
    return jsonify({
        'ok': True,
        'has_token': bool(db.get_setting('bot_token')),
        'enabled': db.get_setting('bot_enabled') == '1',
    })


@settings_bp.route('/bot', methods=['DELETE'])
def delete_bot_settings():
    db = get_db()
    db.set_setting('bot_token', None)
    db.set_setting('bot_enabled', '0')
    return jsonify({'ok': True})


@settings_bp.route('/bot/check', methods=['GET'])
def check_bot():
    import tgbot
    token = get_db().get_setting('bot_token')
    if not token:
        return jsonify({'error': 'no bot token'}), 400
    try:
        info = tgbot.get_me(token) or {}
    except tgbot.BotError as e:
        msg = str(e)
        code = 401 if '401' in msg else 502
        return jsonify({'error': msg}), code
    return jsonify({'ok': True, 'username': info.get('username', '')})


app.register_blueprint(settings_bp)


# ---- MAX bot settings ----
maxbot_bp = Blueprint('maxbot_settings', __name__, url_prefix='/api/settings/maxbot')


@maxbot_bp.route('', methods=['GET'])
def maxbot_settings():
    db = get_db()
    code = db.get_setting('max_teacher_code')
    if not code:
        import uuid
        code = uuid.uuid4().hex[:8]
        db.set_setting('max_teacher_code', code)
    bound = bool(db.get_setting('max_teacher_chat'))
    return jsonify({
        'has_token': bool(db.get_setting('max_bot_token')),
        'enabled': db.get_setting('max_bot_enabled') == '1',
        'teacher_code': code,
        'teacher_bound': bound,
    })


@maxbot_bp.route('', methods=['POST'])
def save_maxbot_settings():
    data = request.json or {}
    db = get_db()
    if 'token' in data:
        token = (data['token'] or '').strip()
        db.set_setting('max_bot_token', token or None)
    if 'enabled' in data:
        v = data['enabled']
        db.set_setting('max_bot_enabled', '1' if v in (True, 1, '1', 'on', 'true') else '0')
    return jsonify({
        'ok': True,
        'has_token': bool(db.get_setting('max_bot_token')),
        'enabled': db.get_setting('max_bot_enabled') == '1',
    })


@maxbot_bp.route('', methods=['DELETE'])
def delete_maxbot_settings():
    db = get_db()
    db.set_setting('max_bot_token', None)
    db.set_setting('max_bot_enabled', '0')
    return jsonify({'ok': True})


@maxbot_bp.route('/check', methods=['GET'])
def check_maxbot():
    import maxbot
    token = get_db().get_setting('max_bot_token')
    if not token:
        return jsonify({'error': 'no bot token'}), 400
    try:
        info = maxbot.check(token) or {}
    except maxbot.MaxError as e:
        msg = str(e)
        code = 401 if '401' in msg else 502
        return jsonify({'error': msg}), code
    return jsonify({'ok': True})


@maxbot_bp.route('/teacher/unbind', methods=['POST'])
def teacher_unbind():
    db = get_db()
    db.set_setting('max_teacher_chat', None)
    return jsonify({'ok': True})


app.register_blueprint(maxbot_bp)


# ---- Telegram bot chat links ----
bot_bp = Blueprint('bot', __name__, url_prefix='/api/bot')


@bot_bp.route('/links', methods=['GET'])
def bot_links():
    return jsonify([dict(r) for r in get_db().list_bot_links()])


@bot_bp.route('/links/by-student/<int:student_id>', methods=['DELETE'])
def bot_unbind_student(student_id: int):
    get_db().unbind_student(student_id)
    return jsonify({'ok': True})


app.register_blueprint(bot_bp)


# ---- MAX bot chat links ----
maxbot_links_bp = Blueprint('maxbot_links', __name__, url_prefix='/api/maxbot')


@maxbot_links_bp.route('/links', methods=['GET'])
def maxbot_links():
    return jsonify([dict(r) for r in get_db().list_max_links()])


@maxbot_links_bp.route('/links/by-student/<int:student_id>', methods=['DELETE'])
def maxbot_unbind_student(student_id: int):
    get_db().unbind_max_student(student_id)
    return jsonify({'ok': True})


app.register_blueprint(maxbot_links_bp)


# ---- Save exports to device Downloads (нативный путь для WebView без шаринга) ----
XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def _android_context():
    """Контекст приложения без привязки к имени activity.

    org.kivy.android.PythonActivity есть не во всех бутстрапах (в webview
    его нет — ClassNotFoundException), поэтому сначала пробуем его,
    затем ActivityThread (фреймворк, всегда на месте).
    """
    from jnius import autoclass
    err1 = None
    try:
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        return PythonActivity.mActivity
    except Exception as e1:
        err1 = e1
    try:
        ActivityThread = autoclass('android.app.ActivityThread')
        app = ActivityThread.currentActivityThread().getApplication()
        if app is None:
            raise RuntimeError('application context is None')
        return app
    except Exception as e2:
        raise RuntimeError(f'no android context ({err1}; {e2})')


def _android_resolver():
    """ContentResolver через контекст приложения."""
    return _android_context().getContentResolver()


def _mediastore_delete_name(resolver, collection, filename: str) -> None:
    """Удалить старые записи с таким именем. Best-effort: любые ошибки молча."""
    try:
        cursor = resolver.query(collection, None, '_display_name=?', [filename], None)
        if cursor is None:
            return
        try:
            idx = cursor.getColumnIndex('_id')
            if idx < 0:
                return
            from jnius import autoclass as _ac
            ContentUris = _ac('android.content.ContentUris')
            while cursor.moveToNext():
                try:
                    resolver.delete(ContentUris.withAppendedId(collection, cursor.getLong(idx)), None, None)
                except Exception:
                    pass
        finally:
            cursor.close()
    except Exception:
        pass


def _save_to_downloads_full(data: bytes, filename: str, mimetype: str):
    """Сохранить в Загрузки. Возвращает (путь для показа, content-URI или None)."""
    try:
        from jnius import autoclass  # noqa — только на Android
    except ImportError:
        import os
        home = os.path.expanduser('~')
        os.makedirs(os.path.join(home, 'Downloads'), exist_ok=True)
        path = os.path.join(home, 'Downloads', filename)
        with open(path, 'wb') as f:
            f.write(data)
        return path, None
    # Вложенные Java-классы в pyjnius — только через '$', точка даёт
    # "has no attribute" (это и роняло экспорт на устройстве).
    BuildVersion = autoclass('android.os.Build$VERSION')
    if int(BuildVersion.SDK_INT) >= 29:
        try:
            Downloads = autoclass('android.provider.MediaStore$Downloads')
            collection = Downloads.getContentUri('external')
        except Exception:
            Files = autoclass('android.provider.MediaStore$Files')
            collection = Files.getContentUri('external')
        ContentValues = autoclass('android.content.ContentValues')
        resolver = _android_resolver()
        # Старый файл с таким именем мешает insert ("Failed to build unique file").
        _mediastore_delete_name(resolver, collection, filename)
        values = ContentValues()
        values.put('title', filename)
        values.put('_display_name', filename)
        values.put('mime_type', mimetype)
        values.put('relative_path', 'Download/')
        try:
            uri = resolver.insert(collection, values)
        except Exception:
            # Имя всё ещё занято — дописываем метку времени, уже не collide.
            import time as _time
            stem, dot, ext = filename.rpartition('.')
            filename = f"{stem}_{int(_time.time())}.{ext}" if dot else f"{filename}_{int(_time.time())}"
            values.put('title', filename)
            values.put('_display_name', filename)
            uri = resolver.insert(collection, values)
        out = resolver.openOutputStream(uri)
        try:
            out.write(data)
        finally:
            out.close()
        return 'Download/' + filename, uri.toString()
    path = '/sdcard/Download/' + filename
    try:
        with open(path, 'wb') as f:
            f.write(data)
        return path, None
    except OSError as e:
        raise RuntimeError(f'cannot write {path}: {e}')


def _save_to_downloads(data: bytes, filename: str, mimetype: str) -> str:
    """Совместимость: только путь (используют to-downloads и тесты)."""
    path, _ = _save_to_downloads_full(data, filename, mimetype)
    return path


def _share_file(uri_string: str, mimetype: str, label: str = 'vedomost') -> None:
    """Открыть шторку «Поделиться» (только Android)."""
    from jnius import autoclass, cast
    Intent = autoclass('android.content.Intent')
    Uri = autoclass('android.net.Uri')
    ctx = _android_context()
    uri = Uri.parse(uri_string)
    intent = Intent()
    intent.setAction(Intent.ACTION_SEND)
    intent.setType(mimetype)
    parcelable = cast('android.os.Parcelable', uri)
    intent.putExtra(Intent.EXTRA_STREAM, parcelable)
    intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    ctx.startActivity(intent)


@export_bp.route('/grades/<int:subject_id>/to-downloads', methods=['POST'])
def save_grades_to_downloads(subject_id: int):
    try:
        data = export_grades_xlsx(subject_id, get_db())
    except RuntimeError as e:
        return _missing_deps_response(e)
    try:
        where = _save_to_downloads(data, f'grades_{subject_id}.xlsx', XLSX_MIME)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify({'ok': True, 'path': where})


@export_bp.route('/report/<date>/to-downloads', methods=['POST'])
def save_report_to_downloads(date: str):
    try:
        data = export_report_xlsx(date, get_db())
    except RuntimeError as e:
        return _missing_deps_response(e)
    try:
        where = _save_to_downloads(data, f'report_{date}.xlsx', XLSX_MIME)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify({'ok': True, 'path': where})


def _save_and_share(data: bytes, filename: str):
    """Сохранить в Загрузки и открыть шторку. Файл остаётся, даже если шаринг не вышел."""
    try:
        where, uri = _save_to_downloads_full(data, filename, XLSX_MIME)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    if uri is None:
        return jsonify({'error': 'share available only on Android'}), 400
    try:
        _share_file(uri, XLSX_MIME, where.rsplit('/', 1)[-1])
    except Exception as e:
        return jsonify({'ok': True, 'path': where, 'shared': False, 'error': str(e)})
    return jsonify({'ok': True, 'path': where, 'shared': True})


@export_bp.route('/grades/<int:subject_id>/share', methods=['POST'])
def share_grades(subject_id: int):
    try:
        data = export_grades_xlsx(subject_id, get_db())
    except RuntimeError as e:
        return _missing_deps_response(e)
    return _save_and_share(data, f'grades_{subject_id}.xlsx')


@export_bp.route('/report/<date>/share', methods=['POST'])
def share_report(date: str):
    try:
        data = export_report_xlsx(date, get_db())
    except RuntimeError as e:
        return _missing_deps_response(e)
    return _save_and_share(data, f'report_{date}.xlsx')


app.register_blueprint(export_bp)


# ---- Backup / Restore ----
from database import DB_PATH as _DB_PATH


class BackupNotFound(Exception):
    """Raised when no backup file is found in Downloads."""


def _validate_sqlite_bytes(data: bytes) -> None:
    """Validate raw bytes look like a SQLite DB with required tables.

    Raises ValueError with a human message on invalid input.
    """
    if len(data) < 16:
        raise ValueError('file too small to be SQLite')
    if data[:16] != b'SQLite format 3\x00':
        raise ValueError('not a SQLite file')
    required = {'groups', 'students', 'subjects', 'lessons', 'grades'}
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    try:
        tmp.write(data)
        tmp.close()
        conn = sqlite3.connect(tmp.name)
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            found = {r[0] for r in rows}
            missing = required - found
            if missing:
                raise ValueError(f'missing tables: {", ".join(sorted(missing))}')
        finally:
            conn.close()
    finally:
        os.unlink(tmp.name)


def _restore_from_bytes(data: bytes) -> None:
    """Validate, auto-backup, checkpoint WAL, and atomically replace the DB.

    Raises ValueError with a human message on bad input.
    """
    _validate_sqlite_bytes(data)
    # Best-effort auto-backup of current DB
    try:
        with open(_DB_PATH, 'rb') as f:
            old_data = f.read()
        bak_name = f'teachhelper_backup_{_time.strftime("%Y%m%d_%H%M%S")}.db'
        _save_to_downloads_full(old_data, bak_name, 'application/x-sqlite3')
    except Exception:
        pass
    # Checkpoint WAL and close all connections
    try:
        db = Database()
        try:
            db.conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        finally:
            db.close()
    except Exception:
        pass
    # Atomic replace
    tmp_path = _DB_PATH + '.tmp_restore'
    with open(tmp_path, 'wb') as f:
        f.write(data)
    os.replace(tmp_path, _DB_PATH)
    for sidecar in (_DB_PATH + '-wal', _DB_PATH + '-shm'):
        try:
            os.unlink(sidecar)
        except OSError:
            pass


def _drain_pfd(pfd) -> bytes:
    try:
        fd = pfd.detachFd()
    except Exception:
        try:
            pfd.close()
        except Exception:
            pass
        raise
    chunks: list[bytes] = []
    try:
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        try:
            os.close(fd)
        except Exception:
            pass
    return b''.join(chunks)


def _is_android() -> bool:
    """True when running under pyjnius (Android/WebView runtime)."""
    try:
        from jnius import autoclass  # noqa: F401 — Android only
        return True
    except ImportError:
        return False


def _valid_backup_name(name) -> bool:
    """A name must be a plain basename of a teachhelper backup (no path, no ..)."""
    if not isinstance(name, str) or not name:
        return False
    if '/' in name or '\\' in name:
        return False
    if name.startswith('..') or name == '.':
        return False
    return _re.match(r'^teachhelper_.*\.db$', name) is not None


def _list_backup_files() -> list[dict]:
    """Enumerate every teachhelper_*.db backup in Downloads, newest first.

    Works on both platforms: desktop globs ~/Downloads; Android queries
    MediaStore Downloads and falls back to a direct filesystem scan of the
    public Download directory when MediaStore has not indexed the folder.
    Returns a list of {name, size, mtime} sorted by mtime descending.
    """
    entries: list[dict] = []
    if not _is_android():
        # Desktop: glob ~/Downloads
        try:
            home = os.path.expanduser('~')
            pattern = os.path.join(home, 'Downloads', 'teachhelper_*.db')
            for path in _glob.glob(pattern):
                try:
                    st = os.stat(path)
                except OSError:
                    continue
                entries.append({
                    'name': os.path.basename(path),
                    'size': st.st_size,
                    'mtime': st.st_mtime,
                })
        except Exception:
            pass
        entries.sort(key=lambda e: e['mtime'], reverse=True)
        return entries

    # Android: query MediaStore Downloads
    seen: set[str] = set()
    try:
        from jnius import autoclass  # noqa — Android only
        Downloads = autoclass('android.provider.MediaStore$Downloads')
        collection = Downloads.getContentUri('external')
        resolver = _android_resolver()
        cursor = resolver.query(
            collection,
            ['_id', '_display_name', 'date_added'],
            '_display_name LIKE ?',
            ['teachhelper_%.db'],
            'date_added DESC',
        )
        try:
            if cursor is not None:
                idx_name = cursor.getColumnIndex('_display_name')
                idx_added = cursor.getColumnIndex('date_added')
                idx_size = cursor.getColumnIndex('_size')
                while cursor.moveToNext():
                    try:
                        name = cursor.getString(idx_name)
                    except Exception:
                        continue
                    if not name:
                        continue
                    seen.add(name)
                    mtime = None
                    size = None
                    try:
                        mtime = cursor.getLong(idx_added)
                    except Exception:
                        pass
                    try:
                        size = cursor.getLong(idx_size)
                    except Exception:
                        pass
                    entries.append({'name': name, 'size': size, 'mtime': mtime})
        finally:
            if cursor is not None:
                cursor.close()
    except Exception:
        pass

    # Fallback: MediaStore didn't index the folder — read Download/ directly.
    try:
        from jnius import autoclass  # noqa — Android only
        env = autoclass('android.os.Environment')
        dl = env.getExternalStoragePublicDirectory(env.DIRECTORY_DOWNLOADS)
        dl_path = str(dl.getAbsolutePath())
        for path in _glob.glob(_glob.join(dl_path, 'teachhelper_*.db')):
            name = os.path.basename(path)
            if name in seen:
                continue
            try:
                st = os.stat(path)
            except OSError:
                continue
            entries.append({'name': name, 'size': st.st_size, 'mtime': st.st_mtime})
    except Exception:
        pass

    entries.sort(key=lambda e: e['mtime'] or 0, reverse=True)
    return entries


def _read_backup_bytes(name: str) -> bytes:
    """Read a backup's bytes by display name (same enumeration + open)."""
    if not _is_android():
        path = os.path.join(os.path.expanduser('~'), 'Downloads', name)
        if not os.path.isfile(path):
            raise BackupNotFound(f'no backup file: {name}')
        with open(path, 'rb') as f:
            return f.read()
    # Android: prefer MediaStore by exact name, then the direct filesystem path.
    try:
        from jnius import autoclass  # noqa — Android only
        Downloads = autoclass('android.provider.MediaStore$Downloads')
        collection = Downloads.getContentUri('external')
        resolver = _android_resolver()
        cursor = resolver.query(
            collection,
            ['_id', '_display_name'],
            '_display_name=?',
            [name],
            None,
        )
        try:
            if cursor is not None and cursor.moveToFirst():
                ContentUris = autoclass('android.content.ContentUris')
                uri = ContentUris.withAppendedId(collection, cursor.getLong(cursor.getColumnIndex('_id')))
                pfd = resolver.openFileDescriptor(uri, 'r')
                return _drain_pfd(pfd)
        finally:
            if cursor is not None:
                cursor.close()
    except Exception:
        pass
    try:
        from jnius import autoclass  # noqa — Android only
        env = autoclass('android.os.Environment')
        dl = env.getExternalStoragePublicDirectory(env.DIRECTORY_DOWNLOADS)
        dl_path = str(dl.getAbsolutePath())
        path = os.path.join(dl_path, name)
        if not os.path.isfile(path):
            raise BackupNotFound(f'no backup file: {name}')
        with open(path, 'rb') as f:
            return f.read()
    except BackupNotFound:
        raise
    except Exception as e:
        raise BackupNotFound(f'no backup file: {name}') from e


def _find_latest_backup_bytes() -> tuple[bytes, str]:
    """Find the most recent teachhelper_*.db in Downloads.

    On Android: queries MediaStore via ContentResolver (+ fs fallback).
    On desktop: globs ~/Downloads.
    Returns (bytes, display_name).
    Raises BackupNotFound if nothing found.
    """
    entries = _list_backup_files()
    if not entries:
        raise BackupNotFound('no backup files found in Downloads')
    data = _read_backup_bytes(entries[0]['name'])
    return data, entries[0]['name']


# ---- Native Android file picker (ACTION_OPEN_DOCUMENT) ----
# The picker result callback fires on the Android UI thread, OUTSIDE the Flask
# request stack. We hand bytes across threads through a module-level dict and a
# threading.Event, and the API handler waits on that event while the user picks.
_REQUEST_CODE = 4242
_RESULT_OK = -1  # android.app.Activity.RESULT_OK is -1
_file_pick = {'event': threading.Event(), 'bytes': None, 'name': None, 'code': -1}
_picker_bound = False


def _resolve_display_name(resolver, uri):
    """Best-effort display name for a content/documents URI (OpenableColumns)."""
    try:
        from jnius import autoclass  # noqa — Android only
        OpenableColumns = autoclass('android.provider.OpenableColumns')
        cursor = resolver.query(uri, [OpenableColumns.DISPLAY_NAME], None, None, None)
        try:
            if cursor is not None and cursor.moveToFirst():
                idx = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if idx >= 0:
                    name = cursor.getString(idx)
                    if name:
                        return name
        finally:
            if cursor is not None:
                cursor.close()
    except Exception:
        pass
    return None


def _on_pick_result(code, result_code, intent):
    """activity_bind(on_activity_result=...): runs on the Android UI thread."""
    try:
        if code != _REQUEST_CODE:
            return
        _file_pick['code'] = code
        if result_code != _RESULT_OK:
            _file_pick['event'].set()
            return
        uri = intent.getData() if intent is not None else None
        if uri is None:
            _file_pick['event'].set()
            return
        try:
            _file_pick['name'] = uri.getLastPathSegment() or None
        except Exception:
            _file_pick['name'] = None
        try:
            _file_pick['name'] = _resolve_display_name(_android_resolver(), uri) or _file_pick['name']
        except Exception:
            pass
        try:
            pfd = _android_resolver().openFileDescriptor(uri, 'r')
            _file_pick['bytes'] = _drain_pfd(pfd)
        except Exception:
            _file_pick['bytes'] = b''
        _file_pick['event'].set()
    except Exception:
        _file_pick['event'].set()


def _start_picker():
    """Launch ACTION_OPEN_DOCUMENT on Android (UI thread). Returns True if shown.

    On non-Android returns None immediately; the caller decides how to react.
    """
    if not _is_android():
        return None
    global _picker_bound
    from android.activity import bind as activity_bind
    from android.runnable import run_on_ui_thread
    from jnius import autoclass, cast

    Intent = autoclass('android.content.Intent')
    String = autoclass('java.lang.String')

    def _do_start():
        try:
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            mActivity = PythonActivity.mActivity
            intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
            intent.addCategory(Intent.CATEGORY_OPENABLE)
            intent.setType('*/*')
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            chooser = Intent.createChooser(
                intent, cast('java.lang.CharSequence', String('Выберите файл базы')))
            mActivity.startActivityForResult(chooser, _REQUEST_CODE)
        except Exception:
            # Launch failed — unblock the waiting handler.
            _file_pick['event'].set()

    if not _picker_bound:
        try:
            activity_bind(on_activity_result=_on_pick_result)
            _picker_bound = True
        except Exception:
            pass
    _file_pick['code'] = -1
    _file_pick['bytes'] = None
    _file_pick['name'] = None
    _file_pick['event'].clear()
    try:
        run_on_ui_thread(_do_start)()
    except Exception:
        _file_pick['event'].set()
    return True


backup_bp = Blueprint('backup', __name__, url_prefix='/api')


@backup_bp.route('/backup', methods=['POST'])
def backup_db():
    try:
        with open(_DB_PATH, 'rb') as f:
            data = f.read()
    except Exception as e:
        return jsonify({'error': f'read db failed: {e}'}), 500
    filename = f'teachhelper_{date.today().isoformat()}.db'
    try:
        path, _ = _save_to_downloads_full(data, filename, 'application/x-sqlite3')
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify({'ok': True, 'path': path})


@backup_bp.route('/restore', methods=['POST'])
def restore_db():
    uploaded = request.files.get('file')
    if uploaded is None:
        return jsonify({'error': 'no file'}), 400
    try:
        data = uploaded.read()
    except Exception as e:
        return jsonify({'error': f'read upload failed: {e}'}), 500
    try:
        _restore_from_bytes(data)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'restore failed: {e}'}), 500
    return jsonify({'ok': True})


@backup_bp.route('/restore/latest', methods=['POST'])
def restore_latest():
    try:
        data, name = _find_latest_backup_bytes()
    except BackupNotFound as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': f'find backup failed: {e}'}), 500
    try:
        _restore_from_bytes(data)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'restore failed: {e}'}), 500
    return jsonify({'ok': True, 'name': name})


@backup_bp.route('/backup/list', methods=['GET'])
def list_backups():
    """List backups in Downloads, newest first. Response {backups:[{name,size,mtime}]}."""
    return jsonify({'backups': _list_backup_files()})


@backup_bp.route('/restore/named', methods=['POST'])
def restore_named():
    """Restore a specific backup found in Downloads by display name."""
    body = request.get_json(silent=True) or {}
    name = body.get('name')
    if not _valid_backup_name(name):
        return jsonify({'error': 'invalid backup name'}), 400
    try:
        data = _read_backup_bytes(name)
    except BackupNotFound as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': f'read backup failed: {e}'}), 500
    try:
        _restore_from_bytes(data)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'restore failed: {e}'}), 500
    return jsonify({'ok': True, 'name': name})


@backup_bp.route('/restore/pick', methods=['POST'])
def restore_pick():
    """Restore a DB file the user picks via the native Android document picker.

    The Flask handler launches the picker, then waits for the result that the
    UI-thread callback delivers through the module-level coordinator.
    """
    if not _is_android():
        return jsonify({'error': 'Доступно только на Android'}), 400
    _file_pick['code'] = -1
    _file_pick['bytes'] = None
    _file_pick['name'] = None
    _file_pick['event'].clear()
    _start_picker()
    _file_pick['event'].wait(120)
    data = _file_pick['bytes']
    name = _file_pick['name']
    if not data:
        return jsonify({'error': 'Выбор файла отменён или файл не найден'}), 404
    try:
        _restore_from_bytes(data)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'restore failed: {e}'}), 500
    return jsonify({'ok': True, 'name': name})


app.register_blueprint(backup_bp)


# ---- In-app updater (GitHub Releases) ----
import urllib.request as _urllib_request
import urllib.error as _urllib_error

_GH_RELEASE_URL = 'https://api.github.com/repos/mifnail/tech/releases/latest'
_GH_COMMITS_URL = 'https://api.github.com/repos/mifnail/tech/commits?per_page=1'
_CACHE_TTL = 3600  # 1 hour

_upd_cache = None   # dict with release info
_upd_ts = 0.0       # time.monotonic() of last fetch


def _fetch_github_release():
    """Fetch latest release from GitHub, fallback to commits on 404."""
    import time as _time_mod
    global _upd_cache, _upd_ts
    now = _time_mod.monotonic()
    if _upd_cache is not None and (now - _upd_ts) < _CACHE_TTL:
        return _upd_cache

    try:
        req = _urllib_request.Request(
            _GH_RELEASE_URL,
            headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'teachhelper-updater'}
        )
        from botcore import _ctx as _ssl_ctx
        resp = _urllib_request.urlopen(req, timeout=10, context=_ssl_ctx())
        with resp:
            raw = resp.read()
            data = _json.loads(raw.decode('utf-8'))
    except _urllib_error.HTTPError as e:
        if e.code == 404:
            # No releases — fallback to latest commit
            try:
                req2 = _urllib_request.Request(
                    _GH_COMMITS_URL,
                    headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'teachhelper-updater'}
                )
                resp2 = _urllib_request.urlopen(req2, timeout=10, context=_ssl_ctx())
                with resp2:
                    commits = _json.loads(resp2.read().decode('utf-8'))
                    if commits:
                        sha = commits[0]['sha'][:7]
                        msg = commits[0]['commit']['message'].split('\n', 1)[0]
                        published = commits[0]['commit']['author']['date']
                        result = {
                            'version': f'0.dev.{sha}',
                            'url': f'https://github.com/mifnail/tech/archive/{commits[0]["sha"]}.zip',
                            'notes': msg,
                            'published_at': published,
                        }
                        _upd_cache = result
                        _upd_ts = _time_mod.monotonic()
                        return result
            except Exception:
                pass
            # No fallback data available
            raise
        raise
    except Exception:
        raise

    assets = data.get('assets', [])
    if assets:
        dl_url = assets[0].get('browser_download_url', '')
    else:
        dl_url = data.get('zipball_url', '')

    tag = data.get('tag_name', '')
    result = {
        'version': tag.lstrip('v') if tag else '',
        'url': dl_url,
        'notes': data.get('body', '') or '',
        'published_at': data.get('published_at', '') or '',
    }
    _upd_cache = result
    _upd_ts = _time_mod.monotonic()
    return result


def _parse_version(v: str) -> list[int]:
    """Parse '0.123' or 'v0.123' into [0, 123]."""
    v = v.strip().lstrip('v')
    parts = []
    for p in v.split('.'):
        try:
            parts.append(int(p))
        except ValueError:
            break
    return parts or [0]


update_bp = Blueprint('update', __name__, url_prefix='/api/update')


@update_bp.route('/latest', methods=['GET'])
def update_latest():
    try:
        info = _fetch_github_release()
        return jsonify(info)
    except _urllib_error.HTTPError as e:
        return jsonify({'error': f'GitHub API error: {e.code}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 502


@update_bp.route('/check', methods=['GET'])
def update_check():
    current = request.args.get('current', '0.0')
    try:
        latest = _fetch_github_release()
    except Exception:
        latest = {'version': '0.0', 'url': '', 'notes': '', 'published_at': ''}
    cur = _parse_version(current)
    lat = _parse_version(latest.get('version', '0.0'))
    return jsonify({
        'update_available': lat > cur,
        'latest': latest,
    })


@update_bp.route('/download', methods=['POST'])
def update_download():
    # Android only
    try:
        from jnius import autoclass  # noqa — Android only
    except ImportError:
        return jsonify({'error': 'download available only on Android'}), 400

    try:
        info = _fetch_github_release()
    except Exception as e:
        return jsonify({'error': f'cannot fetch release: {e}'}), 502

    dl_url = info.get('url', '')
    if not dl_url:
        return jsonify({'error': 'no download URL in release'}), 502

    try:
        from botcore import _ctx as _ssl_ctx
        req = _urllib_request.Request(dl_url, headers={'User-Agent': 'teachhelper-updater'})
        resp = _urllib_request.urlopen(req, timeout=60, context=_ssl_ctx())
        with resp:
            apk_bytes = resp.read()
    except Exception as e:
        return jsonify({'error': f'download failed: {e}'}), 502

    try:
        path, uri = _save_to_downloads_full(
            apk_bytes,
            'teachhelper-latest.apk',
            'application/vnd.android.package-archive',
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    return jsonify({'path': path, 'uri': uri})


@update_bp.route('/install', methods=['POST'])
def update_install():
    # Android only
    try:
        from jnius import autoclass, cast
    except ImportError:
        return jsonify({'error': 'install available only on Android'}), 400

    data = request.json or {}
    uri_str = data.get('uri', '')

    # If no URI provided, find latest APK via MediaStore
    if not uri_str:
        try:
            Downloads = autoclass('android.provider.MediaStore$Downloads')
            collection = Downloads.getContentUri('external')
            resolver = _android_resolver()
            cursor = resolver.query(
                collection,
                ['_id', '_display_name'],
                '_display_name=?',
                ['teachhelper-latest.apk'],
                None,
            )
            if cursor and cursor.moveToFirst():
                ContentUris = autoclass('android.content.ContentUris')
                idx_id = cursor.getColumnIndex('_id')
                uri = ContentUris.withAppendedId(collection, cursor.getLong(idx_id))
                uri_str = uri.toString()
                cursor.close()
        except Exception:
            pass

    if not uri_str:
        return jsonify({'error': 'no APK URI found'}), 404

    try:
        Uri = autoclass('android.net.Uri')
        Intent = autoclass('android.content.Intent')
        ctx = _android_context()
        uri = Uri.parse(uri_str)
        intent = Intent(Intent.ACTION_VIEW)
        intent.setDataAndType(
            uri,
            'application/vnd.android.package-archive',
        )
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        ctx.startActivity(intent)
    except Exception as e:
        return jsonify({'error': f'install intent failed: {e}'}), 500

    return jsonify({'ok': True})


app.register_blueprint(update_bp)
