from flask import Flask, request, jsonify, send_from_directory
from datetime import date
import os

app = Flask(__name__, static_folder='static', template_folder='templates')

from database import Database

def get_db():
    return Database()

# --- SPA shell ---
@app.route('/')
def index():
    return send_from_directory('templates', 'index.html')

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

# --- Groups ---
@app.route('/api/groups', methods=['GET'])
def list_groups():
    db = get_db()
    groups = db.list_groups()
    return jsonify([dict(g) for g in groups])

@app.route('/api/groups', methods=['POST'])
def create_group():
    data = request.json
    db = get_db()
    gid = db.add_group(data['name'])
    return jsonify({'id': gid}), 201

# --- Students ---
@app.route('/api/students', methods=['GET'])
def list_students():
    group_id = request.args.get('group_id', type=int)
    db = get_db()
    students = db.list_students(group_id)
    return jsonify([dict(s) for s in students])

@app.route('/api/students/bulk', methods=['POST'])
def add_students_bulk():
    data = request.json
    db = get_db()
    count = db.add_students_bulk(data['group_id'], data['students'])
    return jsonify({'added': count}), 201

# --- Subjects ---
@app.route('/api/subjects', methods=['GET'])
def list_subjects():
    group_id = request.args.get('group_id', type=int)
    include_free = request.args.get('include_free', type=int, default=0)
    db = get_db()
    subjects = db.list_subjects(group_id, include_free=bool(include_free))
    return jsonify([dict(s) for s in subjects])

@app.route('/api/subjects', methods=['POST'])
def create_subject():
    data = request.json
    db = get_db()
    sid = db.add_subject(data['name'], data['total_hours'], data['group_id'])
    return jsonify({'id': sid}), 201

@app.route('/api/subjects/<int:subject_id>/gradebook')
def subject_gradebook(subject_id):
    db = get_db()
    rows = db.subject_gradebook(subject_id)
    summary = db.subject_summary(subject_id)
    return jsonify({
        'summary': dict(summary) if summary else None,
        'grades': [dict(r) for r in rows]
    })

@app.route('/api/subjects/<int:subject_id>/substitution-list', methods=['GET'])
def substitution_list(subject_id):
    db = get_db()
    subj = db.conn.execute("SELECT * FROM subjects WHERE id = ?", (subject_id,)).fetchone()
    if not subj:
        return jsonify([])
    group_subjects = db.list_subjects(subj['group_id'], include_free=True)
    return jsonify([dict(s) for s in group_subjects])

# --- Schedule ---
@app.route('/api/schedule', methods=['GET'])
def get_schedule():
    db = get_db()
    entries = db.list_schedule()
    return jsonify([dict(e) for e in entries])

@app.route('/api/schedule', methods=['POST'])
def add_schedule_entry():
    data = request.json
    db = get_db()
    eid = db.add_schedule_entry(
        data['day_of_week'], data['lesson_number'],
        data['subject_id'], data.get('week_type', 0))
    return jsonify({'id': eid}), 201

@app.route('/api/schedule/<int:entry_id>', methods=['DELETE'])
def delete_schedule_entry(entry_id):
    db = get_db()
    db.delete_schedule_entry(entry_id)
    return jsonify({'ok': True})

@app.route('/api/schedule/today', methods=['GET'])
def schedule_today():
    today = date.today()
    day = today.isoweekday()
    db = get_db()
    entries = db.get_schedule_for_day(day)
    lessons = db.list_lessons_by_date(today.isoformat())
    return jsonify({
        'date': today.isoformat(),
        'day_of_week': day,
        'schedule': [dict(e) for e in entries],
        'lessons': [dict(l) for l in lessons]
    })

# --- Lessons ---
@app.route('/api/lessons', methods=['POST'])
def create_lesson():
    data = request.json
    db = get_db()
    lid = db.add_lesson(
        data['subject_id'],
        data.get('date', date.today().isoformat()),
        data.get('actual_subject_id'),
        data.get('status', 'held'))
    return jsonify({'id': lid}), 201

@app.route('/api/lessons/<int:lesson_id>', methods=['GET'])
def get_lesson(lesson_id):
    db = get_db()
    lesson = db.get_lesson(lesson_id)
    if not lesson:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(lesson))

@app.route('/api/lessons/<int:lesson_id>/substitute', methods=['PATCH'])
def substitute_lesson(lesson_id):
    data = request.json
    db = get_db()
    db.substitute_lesson(lesson_id, data['new_subject_id'])
    return jsonify({'ok': True})

@app.route('/api/lessons/<int:lesson_id>/status', methods=['PATCH'])
def update_lesson_status(lesson_id):
    data = request.json
    db = get_db()
    db.set_lesson_status(lesson_id, data['status'])
    return jsonify({'ok': True})

@app.route('/api/subjects/<int:subject_id>/lessons', methods=['GET'])
def subject_lessons(subject_id):
    db = get_db()
    lessons = db.list_lessons_for_subject(subject_id)
    return jsonify([dict(l) for l in lessons])

@app.route('/api/lessons/<int:lesson_id>/adjacent', methods=['GET'])
def adjacent_lessons(lesson_id):
    db = get_db()
    prev_id, next_id = db.get_adjacent_lessons(lesson_id)
    return jsonify({'prev_id': prev_id, 'next_id': next_id})

@app.route('/api/lessons/<int:lesson_id>/attendance', methods=['GET'])
def get_attendance(lesson_id):
    db = get_db()
    records = db.get_attendance(lesson_id)
    lesson = db.get_lesson(lesson_id)
    students = db.get_group_students(lesson_id) if lesson else []
    return jsonify({
        'lesson': dict(lesson) if lesson else None,
        'attendance': [dict(r) for r in records],
        'students': [dict(s) for s in students]
    })

@app.route('/api/lessons/<int:lesson_id>/attendance', methods=['POST'])
def mark_attendance(lesson_id):
    data = request.json
    db = get_db()
    if isinstance(data, list):
        db.mark_attendance_bulk(lesson_id, data)
    else:
        db.mark_attendance(lesson_id, data['student_id'], data['grade'])
    return jsonify({'ok': True})

@app.route('/api/lessons/date/<date_str>', methods=['GET'])
def lessons_by_date(date_str):
    db = get_db()
    lessons = db.list_lessons_by_date(date_str)
    return jsonify([dict(l) for l in lessons])

# --- Reports ---
@app.route('/api/reports/substitutions', methods=['GET'])
def substitutions():
    db = get_db()
    rows = db.get_substitutions()
    return jsonify([dict(r) for r in rows])

@app.route('/api/reports/average/<int:subject_id>', methods=['GET'])
def average_grades(subject_id):
    db = get_db()
    rows = db.average_grades(subject_id)
    return jsonify([dict(r) for r in rows])

@app.route('/api/reports/daily', methods=['GET'])
def daily_report():
    date_str = request.args.get('date', date.today().isoformat())
    db = get_db()
    rows = db.daily_report(date_str)
    return jsonify(rows)

@app.route('/api/reports/neglected/<int:group_id>', methods=['GET'])
def neglected_students(group_id):
    min_grades = request.args.get('min_grades', 3, type=int)
    days = request.args.get('days', 14, type=int)
    db = get_db()
    rows = db.students_without_recent_grades(group_id, min_grades, days)
    return jsonify([dict(r) for r in rows])

# --- Student grades ---
@app.route('/api/students/<int:student_id>/grades', methods=['GET'])
def student_grades(student_id):
    subject_id = request.args.get('subject_id', type=int)
    db = get_db()
    rows = db.student_grades(student_id, subject_id)
    return jsonify([dict(r) for r in rows])
