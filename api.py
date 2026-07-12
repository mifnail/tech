from __future__ import annotations
import functools
from datetime import date
from typing import Any
import os

from flask import Flask, Blueprint, request, jsonify, send_from_directory

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
    gid = get_db().add_group(request.json['name'])
    return jsonify({'id': gid}), 201


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
    sid = get_db().add_subject(data['name'], data['total_hours'], data['group_id'])
    return jsonify({'id': sid}), 201


@subjects_bp.route('/<int:subject_id>/gradebook')
def subject_gradebook(subject_id: int):
    db = get_db()
    return jsonify({
        'summary': dict_row(db.subject_summary(subject_id)),
        'grades': [dict(r) for r in db.subject_gradebook(subject_id)]
    })


@subjects_bp.route('/<int:subject_id>/substitution-list', methods=['GET'])
def substitution_list(subject_id: int):
    db = get_db()
    subj = db.conn.execute("SELECT * FROM subjects WHERE id = ?", (subject_id,)).fetchone()
    if not subj:
        return jsonify([])
    db.get_free_subject_id(subj['group_id'])
    return jsonify([dict(r) for r in db.list_subjects(subj['group_id'], include_free=True)])


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


@schedule_bp.route('/today', methods=['GET'])
def schedule_today():
    today = date.today()
    day = today.isoweekday()
    db = get_db()
    return jsonify({
        'date': today.isoformat(),
        'day_of_week': day,
        'schedule': [dict(r) for r in db.get_schedule_for_day(day)],
        'lessons': [dict(r) for r in db.list_lessons_by_date(today.isoformat())]
    })


app.register_blueprint(schedule_bp)


# ---- Lessons ----
lessons_bp = Blueprint('lessons', __name__, url_prefix='/api/lessons')


@lessons_bp.route('', methods=['POST'])
@require_fields('subject_id')
def create_lesson():
    data = request.json
    lid = get_db().add_lesson(
        data['subject_id'],
        data.get('date', date.today().isoformat()),
        data.get('actual_subject_id'),
        data.get('status', 'held'))
    return jsonify({'id': lid}), 201


@lessons_bp.route('/<int:lesson_id>', methods=['GET'])
def get_lesson(lesson_id: int):
    lesson = get_db().get_lesson(lesson_id)
    if not lesson:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(lesson))


@lessons_bp.route('/<int:lesson_id>/substitute', methods=['PATCH'])
@require_fields('new_subject_id')
def substitute_lesson(lesson_id: int):
    get_db().substitute_lesson(lesson_id, request.json['new_subject_id'])
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
