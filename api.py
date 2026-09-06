from __future__ import annotations
import functools
import io
from datetime import date
from typing import Any
import os

import sqlite3

from flask import Flask, Blueprint, request, jsonify, send_from_directory, send_file

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


# ---- SPA shell ----
@app.route('/')
def index():
    return send_from_directory('templates', 'index.html')


@app.route('/static/<path:path>')
def serve_static(path: str):
    return send_from_directory('static', path)


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
    return jsonify({
        'date': today.isoformat(),
        'formatted_date': today.strftime('%d.%m.%Y'),
        'day_of_week': day,
        'schedule': [dict(r) for r in db.get_schedule_for_day(day, week_type)],
        'lessons': [dict(r) for r in db.list_lessons_by_date(today.isoformat())]
    })


app.register_blueprint(schedule_bp)


# ---- Lessons ----
lessons_bp = Blueprint('lessons', __name__, url_prefix='/api/lessons')


@lessons_bp.route('', methods=['POST'])
@require_fields('subject_id')
def create_lesson():
    data = request.json
    db = get_db()
    lesson_date = data.get('date', date.today().isoformat())
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
        from datetime import datetime
        try:
            dt = datetime.strptime(lesson_dict['date'], '%Y-%m-%d')
            lesson_dict['formatted_date'] = dt.strftime('%d.%m.%Y')
        except ValueError:
            lesson_dict['formatted_date'] = lesson_dict['date']
    return jsonify(lesson_dict)


@lessons_bp.route('/<int:lesson_id>/substitute', methods=['PATCH'])
@require_fields('new_subject_id')
def substitute_lesson(lesson_id: int):
    new_id = get_db().substitute_lesson(lesson_id, request.json['new_subject_id'])
    return jsonify({'ok': True, 'new_lesson_id': new_id})


@lessons_bp.route('/<int:lesson_id>/cancel', methods=['PATCH'])
def cancel_lesson(lesson_id: int):
    get_db().cancel_lesson(lesson_id)
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
    return jsonify({'ok': True})


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
from report_export import export_grades_xlsx, export_report_xlsx

export_bp = Blueprint('export', __name__, url_prefix='/api/export')


def _missing_deps_response(e: Exception):
    return jsonify({'error': f'export unavailable: {e}. Rebuild APK with openpyxl+reportlab or use CSV.'}), 500


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


SHARE_MODES = ('cast', 'clip', 'both')


def _count_handlers(mimetype: str) -> int:
    """Сколько приложений готовы принять ACTION_SEND с таким MIME."""
    from jnius import autoclass
    Intent = autoclass('android.content.Intent')
    ctx = _android_context()
    probe = Intent()
    probe.setAction(Intent.ACTION_SEND)
    probe.setType(mimetype)
    pm = ctx.getPackageManager()
    return int(pm.queryIntentActivities(probe, 0).size())


def _share_file(uri_string: str, mimetype: str, label: str = 'vedomost',
                mode: str = 'cast') -> None:
    """Открыть шторку «Поделиться» (только Android).

    mode: 'cast' — proven: cast(Uri→Parcelable) + putExtra(EXTRA_STREAM);
    'clip' — только ClipData; 'both' — cast + ClipData.

    Источник паттерна: androidstorage4kivy/sharesheet.py (MIT).
    """
    if mode not in SHARE_MODES:
        raise ValueError(f'bad share mode: {mode}')
    from jnius import autoclass, cast
    Intent = autoclass('android.content.Intent')
    Uri = autoclass('android.net.Uri')
    ctx = _android_context()
    uri = Uri.parse(uri_string)
    intent = Intent()
    intent.setAction(Intent.ACTION_SEND)
    intent.setType(mimetype)
    if mode in ('cast', 'both'):
        parcelable = cast('android.os.Parcelable', uri)
        intent.putExtra(Intent.EXTRA_STREAM, parcelable)
    if mode in ('clip', 'both'):
        ClipData = autoclass('android.content.ClipData')
        clip = ClipData.newUri(ctx.getContentResolver(), label, uri)
        intent.setClipData(clip)
    intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    chooser = Intent.createChooser(intent, 'Поделиться ведомостью')
    chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    ctx.startActivity(chooser)


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


def _save_and_share(data: bytes, filename: str, mode: str = 'clip'):
    """Сохранить в Загрузки и открыть шторку. Файл остаётся, даже если шаринг не вышел."""
    if mode not in SHARE_MODES:
        return jsonify({'error': f'bad share mode: {mode}'}), 400
    try:
        where, uri = _save_to_downloads_full(data, filename, XLSX_MIME)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    if uri is None:
        return jsonify({'error': 'share available only on Android'}), 400
    try:
        _share_file(uri, XLSX_MIME, where.rsplit('/', 1)[-1], mode)
    except Exception as e:
        return jsonify({'ok': True, 'path': where, 'shared': False, 'error': str(e)})
    return jsonify({'ok': True, 'path': where, 'shared': True})


@export_bp.route('/grades/<int:subject_id>/share', methods=['POST'])
def share_grades(subject_id: int):
    try:
        data = export_grades_xlsx(subject_id, get_db())
    except RuntimeError as e:
        return _missing_deps_response(e)
    return _save_and_share(data, f'grades_{subject_id}.xlsx',
                           request.args.get('mode', 'clip'))


@export_bp.route('/report/<date>/share', methods=['POST'])
def share_report(date: str):
    try:
        data = export_report_xlsx(date, get_db())
    except RuntimeError as e:
        return _missing_deps_response(e)
    return _save_and_share(data, f'report_{date}.xlsx',
                           request.args.get('mode', 'clip'))


@export_bp.route('/diag', methods=['POST'])
def diag_share():
    """Стенд: проверить каждый шаг шаринга по очереди, без запуска шторки."""
    steps = []

    def step(name, fn):
        try:
            info = fn()
            steps.append({'name': name, 'ok': True, 'info': str(info or '')[:120]})
            return True
        except Exception as e:
            steps.append({'name': name, 'ok': False, 'error': str(e)[:300]})
            return False

    try:
        from jnius import autoclass
        steps.append({'name': 'jnius import', 'ok': True, 'info': ''})
    except Exception as e:
        steps.append({'name': 'jnius import', 'ok': False, 'error': str(e)[:300]})
        return jsonify({'ok': False, 'steps': steps})

    box = {}

    def do_ctx():
        box['ctx'] = _android_context()
        return 'context ok'

    def do_sdk():
        BuildVersion = autoclass('android.os.Build$VERSION')
        box['sdk'] = int(BuildVersion.SDK_INT)
        return f"SDK {box['sdk']}"

    def do_collection():
        try:
            Downloads = autoclass('android.provider.MediaStore$Downloads')
            box['collection'] = Downloads.getContentUri('external')
        except Exception:
            Files = autoclass('android.provider.MediaStore$Files')
            box['collection'] = Files.getContentUri('external')
        return 'collection ok'

    def do_insert_write():
        ContentValues = autoclass('android.content.ContentValues')
        resolver = box['ctx'].getContentResolver()
        box['resolver'] = resolver
        values = ContentValues()
        values.put('title', 'diag_test.txt')
        values.put('_display_name', 'diag_test.txt')
        values.put('mime_type', 'text/plain')
        values.put('relative_path', 'Download/')
        uri = resolver.insert(box['collection'], values)
        out = resolver.openOutputStream(uri)
        try:
            out.write(b'diag')
        finally:
            out.close()
        box['uri'] = uri.toString()
        return box['uri']

    def do_clip():
        ClipData = autoclass('android.content.ClipData')
        Uri = autoclass('android.net.Uri')
        ClipData.newUri(box['ctx'].getContentResolver(), 'diag', Uri.parse(box['uri']))
        return 'clip ok'

    def do_extra():
        Intent = autoclass('android.content.Intent')
        Uri = autoclass('android.net.Uri')
        t = Intent()
        t.setAction(Intent.ACTION_SEND)
        t.setType('text/plain')
        t.putExtra(Intent.EXTRA_STREAM, Uri.parse(box['uri']))
        return 'putExtra ok'

    def do_cast():
        from jnius import cast
        Uri = autoclass('android.net.Uri')
        uri = Uri.parse(box['uri'])
        parcelable = cast('android.os.Parcelable', uri)
        return f'cast ok: {parcelable}'

    def do_handlers():
        nx = _count_handlers(XLSX_MIME)
        nw = _count_handlers('*/*')
        return f'xlsx:{nx} */*:{nw}'

    def do_launch():
        from jnius import autoclass, cast
        Intent = autoclass('android.content.Intent')
        Uri = autoclass('android.net.Uri')
        ClipData = autoclass('android.content.ClipData')
        ctx = box['ctx']
        uri = Uri.parse(box['uri'])
        parcelable = cast('android.os.Parcelable', uri)
        intent = Intent()
        intent.setAction(Intent.ACTION_SEND)
        intent.setType(XLSX_MIME)
        intent.putExtra(Intent.EXTRA_STREAM, parcelable)
        clip = ClipData.newUri(ctx.getContentResolver(), 'diag_test.txt', uri)
        intent.setClipData(clip)
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        chooser = Intent.createChooser(intent, 'Диагностика: шторка')
        chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        ctx.startActivity(chooser)
        return 'sheet fired'

    if (step('context', do_ctx) and step('sdk', do_sdk)
            and step('collection', do_collection)
            and step('insert+write', do_insert_write)
            and step('cast', do_cast)):
        step('handlers', do_handlers)
        step('cleanup', do_cleanup)
        if request.args.get('launch') == '1':
            step('launch', do_launch)
    return jsonify({'ok': all(s['ok'] for s in steps), 'steps': steps})


app.register_blueprint(export_bp)
