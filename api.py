from __future__ import annotations
import functools
import io
from datetime import date, datetime
from typing import Any
import os

import sqlite3

from flask import Flask, Blueprint, request, jsonify, send_from_directory, send_file, Response

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
from report_export import export_grades_pdf, export_grades_xlsx, export_report_pdf, export_report_xlsx
from calendar_export import generate_schedule_ics, export_lessons_to_ics

export_bp = Blueprint('export', __name__, url_prefix='/api/export')


def _build_grades_csv_bytes(db, subject_id: int) -> bytes:
    """Ведомость предмета в CSV (UTF-8+BOM). Общее для скачивания и публикации."""
    import csv as _csv
    students, lessons, grades = db.subject_gradebook(subject_id)
    buf = io.StringIO()
    buf.write('\ufeff')
    w = _csv.writer(buf)
    w.writerow(['Студент'] + [f"{l.get('date','')} №{l.get('lesson_number') or ''} (#{l['id']})" for l in lessons])
    for s in students:
        row = [f"{s['last_name']} {s['first_name']}"]
        for l in lessons:
            row.append(grades.get(str(s['id']), {}).get(str(l['id']), ''))
        w.writerow(row)
    return buf.getvalue().encode('utf-8')


def _missing_deps_response(e: Exception):
    return jsonify({'error': f'export unavailable: {e}. Rebuild APK with openpyxl+reportlab or use CSV.'}), 500


@export_bp.route('/grades/<int:subject_id>.<fmt>')
def download_grades(subject_id: int, fmt: str):
    try:
        if fmt == 'pdf':
            data = export_grades_pdf(subject_id)
            return send_file(io.BytesIO(data), mimetype='application/pdf',
                             as_attachment=True, download_name=f'grades_{subject_id}.pdf')
        elif fmt == 'xlsx':
            data = export_grades_xlsx(subject_id)
            return send_file(io.BytesIO(data),
                             mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                             as_attachment=True, download_name=f'grades_{subject_id}.xlsx')
        elif fmt == 'csv':
            raw = _build_grades_csv_bytes(get_db(), subject_id)
            return send_file(io.BytesIO(raw), mimetype='text/csv',
                             as_attachment=True, download_name=f'grades_{subject_id}.csv')
    except RuntimeError as e:
        return _missing_deps_response(e)
    return 'Unsupported format', 400


@export_bp.route('/report/<date>.<fmt>')
def download_report(date: str, fmt: str):
    try:
        if fmt == 'pdf':
            data = export_report_pdf(date)
            return send_file(io.BytesIO(data), mimetype='application/pdf',
                             as_attachment=True, download_name=f'report_{date}.pdf')
        elif fmt == 'xlsx':
            data = export_report_xlsx(date)
            return send_file(io.BytesIO(data),
                             mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                             as_attachment=True, download_name=f'report_{date}.xlsx')
        elif fmt == 'csv':
            import csv as _csv
            rows = get_db().daily_report(date)
            buf = io.StringIO()
            buf.write('\ufeff')
            w = _csv.writer(buf)
            w.writerow([f'Отчёт за {date}'])
            w.writerow(['Занятие #', 'Предмет', 'Группа', 'Статус', 'Оценок', 'Пропусков'])
            for r in rows:
                rd = dict(r)
                w.writerow([rd.get('id',''), rd.get('subject_name',''), rd.get('group_name',''),
                            rd.get('status',''), rd.get('grades_count',0), rd.get('absent_count',0)])
            raw = buf.getvalue().encode('utf-8')
            return send_file(io.BytesIO(raw), mimetype='text/csv',
                             as_attachment=True, download_name=f'report_{date}.csv')
    except RuntimeError as e:
        return _missing_deps_response(e)
    return 'Unsupported format', 400


@export_bp.route('/lessons.ics')
def download_lessons_ics():
    return Response(export_lessons_to_ics(), mimetype='text/calendar',
                    headers={'Content-Disposition': 'attachment; filename=lessons.ics'})


@export_bp.route('/schedule.ics')
def download_schedule_ics():
    return Response(generate_schedule_ics(), mimetype='text/calendar',
                    headers={'Content-Disposition': 'attachment; filename=schedule.ics'})


app.register_blueprint(export_bp)


# ---- Publish to Yandex Disk ----
from yandex_publish import (
    upload_and_publish, check_token as yandex_check_token,
    YandexError, YandexAuthError, YandexNetworkError,
)

publish_bp = Blueprint('publish', __name__, url_prefix='/api/publish')


def _publish_file_for_subject(db, subject_id: int):
    """(ext, bytes): XLSX если есть openpyxl, иначе CSV."""
    try:
        return 'xlsx', export_grades_xlsx(subject_id, db)
    except RuntimeError:
        return 'csv', _build_grades_csv_bytes(db, subject_id)


@publish_bp.route('/<int:subject_id>', methods=['POST'])
def publish_subject(subject_id: int):
    db = get_db()
    if not db.subject_summary(subject_id):
        return jsonify({'error': 'subject not found'}), 404
    token = db.get_setting('yandex_token')
    if not token:
        return jsonify({'error': 'no yandex token. Add it in Settings.'}), 400
    folder = (db.get_setting('yandex_folder') or '/TeachHelper').rstrip('/') or '/TeachHelper'
    ext, data = _publish_file_for_subject(db, subject_id)
    remote = f"{folder}/vedomost-{subject_id}.{ext}"
    try:
        url = upload_and_publish(token, remote, data)
    except YandexAuthError as e:
        return jsonify({'error': str(e)}), 401
    except YandexNetworkError as e:
        db.set_setting(f'publish_pending_{subject_id}', '1')
        return jsonify({'error': str(e)}), 502
    except YandexError as e:
        return jsonify({'error': str(e)}), 500
    db.set_setting(f'publish_url_{subject_id}', url)
    db.set_setting(f'publish_time_{subject_id}', datetime.now().isoformat(timespec='minutes'))
    db.set_setting(f'publish_pending_{subject_id}', None)
    return jsonify({'ok': True, 'url': url})


@publish_bp.route('/<int:subject_id>/touch', methods=['POST'])
def touch_publish(subject_id: int):
    """Пометить ведомость как требующую публикации (после проставления оценки)."""
    get_db().set_setting(f'publish_pending_{subject_id}', '1')
    return jsonify({'ok': True})


@publish_bp.route('/<int:subject_id>/status', methods=['GET'])
def publish_status(subject_id: int):
    db = get_db()
    return jsonify({
        'url': db.get_setting(f'publish_url_{subject_id}'),
        'time': db.get_setting(f'publish_time_{subject_id}'),
        'pending': db.get_setting(f'publish_pending_{subject_id}') == '1',
        'has_token': bool(db.get_setting('yandex_token')),
    })


app.register_blueprint(publish_bp)


# ---- Yandex settings ----
settings_bp = Blueprint('settings', __name__, url_prefix='/api/settings')


@settings_bp.route('/yandex', methods=['GET'])
def yandex_settings():
    db = get_db()
    return jsonify({
        'has_token': bool(db.get_setting('yandex_token')),
        'folder': db.get_setting('yandex_folder') or '/TeachHelper',
    })


@settings_bp.route('/yandex', methods=['POST'])
def save_yandex_settings():
    data = request.json or {}
    db = get_db()
    if 'token' in data:
        token = (data['token'] or '').strip()
        db.set_setting('yandex_token', token or None)
    if 'folder' in data:
        folder = (data['folder'] or '').strip() or '/TeachHelper'
        if not folder.startswith('/'):
            folder = '/' + folder
        db.set_setting('yandex_folder', folder)
    return jsonify({
        'ok': True,
        'has_token': bool(db.get_setting('yandex_token')),
        'folder': db.get_setting('yandex_folder') or '/TeachHelper',
    })


@settings_bp.route('/yandex', methods=['DELETE'])
def delete_yandex_token():
    get_db().set_setting('yandex_token', None)
    return jsonify({'ok': True})


@settings_bp.route('/yandex/check', methods=['GET'])
def check_yandex():
    token = get_db().get_setting('yandex_token')
    if not token:
        return jsonify({'error': 'no yandex token'}), 400
    try:
        info = yandex_check_token(token)
    except YandexAuthError as e:
        return jsonify({'error': str(e)}), 401
    except YandexNetworkError as e:
        return jsonify({'error': str(e)}), 502
    except YandexError as e:
        return jsonify({'error': str(e)}), 500
    return jsonify({'ok': True, 'info': {k: info.get(k) for k in ('total_space', 'used_space') if k in info}})


app.register_blueprint(settings_bp)
