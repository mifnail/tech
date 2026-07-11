"""
api.py — REST-роуты для LessonTracker (Flask).
Все запросы к БД — через database.py.
"""
from datetime import date, datetime
import os

from flask import Flask, jsonify, request, render_template

from database import Database

DB_PATH = "lessons.db"
app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


def get_db() -> Database:
    db = Database(DB_PATH)
    db.init_schema()
    return db


# ----------------------------------------------------------- subjects
@app.route("/api/subjects", methods=["GET"])
def list_subjects():
    db = get_db()
    subjects = db.list_subjects()
    db.close()
    return jsonify(subjects)


@app.route("/api/subjects", methods=["POST"])
def add_subject():
    data = request.get_json()
    db = get_db()
    db.add_subject(data["name"], int(data["planned"]), data["group"])
    db.close()
    return jsonify({"ok": True})


@app.route("/api/subjects/<int:subject_id>/gradebook", methods=["GET"])
def subject_gradebook(subject_id):
    db = get_db()
    summary = db.subject_summary(subject_id)
    gradebook = db.subject_gradebook(subject_id)
    db.close()
    return jsonify({"summary": summary, "gradebook": gradebook})


# ----------------------------------------------------------- groups & students
@app.route("/api/groups", methods=["GET"])
def list_groups():
    db = get_db()
    groups = db.list_groups()
    db.close()
    return jsonify(groups)


@app.route("/api/students", methods=["GET"])
def list_students():
    group = request.args.get("group", "")
    db = get_db()
    students = db.list_students(group)
    db.close()
    return jsonify(students)


@app.route("/api/students/bulk", methods=["POST"])
def add_students_bulk():
    data = request.get_json()
    db = get_db()
    added = db.add_students_bulk(data["group"], data["names"])
    db.close()
    return jsonify({"added": added})


# ----------------------------------------------------------- schedule / lessons
@app.route("/api/schedule/today", methods=["GET"])
def today_schedule():
    db = get_db()
    lessons = db.list_schedule_for_date(date.today().isoformat())
    db.close()
    return jsonify(lessons)


@app.route("/api/lessons", methods=["POST"])
def add_lesson():
    data = request.get_json()
    db = get_db()
    db.add_lesson(int(data["subject_id"]), data["held_at"],
                  status=data.get("status", "scheduled"))
    db.close()
    return jsonify({"ok": True})


@app.route("/api/lessons/<int:lesson_id>", methods=["GET"])
def get_lesson(lesson_id):
    db = get_db()
    lesson = db.get_lesson(lesson_id)
    db.close()
    if lesson:
        return jsonify(lesson)
    return jsonify({"error": "not found"}), 404


@app.route("/api/lessons/<int:lesson_id>/status", methods=["PATCH"])
def set_lesson_status(lesson_id):
    data = request.get_json()
    db = get_db()
    db.set_lesson_status(lesson_id, data["status"])
    db.close()
    return jsonify({"ok": True})


@app.route("/api/lessons/<int:lesson_id>/subject", methods=["PATCH"])
def change_lesson_subject(lesson_id):
    data = request.get_json()
    db = get_db()
    db.change_lesson_subject(lesson_id, int(data["subject_id"]))
    db.close()
    return jsonify({"ok": True})


# ----------------------------------------------------------- attendance
@app.route("/api/lessons/<int:lesson_id>/attendance", methods=["GET"])
def get_attendance(lesson_id):
    db = get_db()
    attendance = db.get_attendance(lesson_id)
    db.close()
    return jsonify(attendance)


@app.route("/api/lessons/<int:lesson_id>/attendance", methods=["POST"])
def mark_attendance(lesson_id):
    data = request.get_json()
    db = get_db()
    db.mark_attendance(lesson_id, int(data["student_id"]),
                       present=data["present"], grade=data.get("grade"))
    db.close()
    return jsonify({"ok": True})


# ----------------------------------------------------------- export
@app.route("/api/export/ics", methods=["GET"])
def export_ics():
    from calendar_export import export_ics as do_export
    db = get_db()
    lessons = db.list_lessons_for_calendar()
    db.close()
    path = "schedule.ics"
    do_export(lessons, path)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return content, 200, {"Content-Type": "text/calendar; charset=utf-8"}
