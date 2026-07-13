"""Экспорт в iCalendar (.ics) формат: проведённые занятия и плановое расписание."""

from __future__ import annotations

from datetime import datetime, timedelta, date as date_type
from typing import Optional

from database import Database


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime('%Y%m%dT%H%M%S')


def _fmt_date(d: date_type) -> str:
    return d.strftime('%Y%m%d')


WEEKDAYS = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']


def generate_ics(lessons: list[dict]) -> str:
    """Генерирует .ics-строку из списка занятий (проведённые)."""
    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//TeachHelper4//RU',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
    ]
    for lesson in lessons:
        date_str = lesson.get('date', '2000-01-01')
        subject = lesson.get('actual_subject_name', 'Занятие')
        try:
            dt = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            dt = datetime.now()
        start = dt.strftime('%Y%m%dT090000')
        end = (dt + timedelta(hours=1, minutes=30)).strftime('%Y%m%dT103000')
        uid = f"lesson-{lesson.get('id', '0')}@{dt.strftime('%Y%m%d')}"
        lines.extend([
            'BEGIN:VEVENT',
            f'UID:{uid}',
            f'DTSTART:{start}',
            f'DTEND:{end}',
            f'SUMMARY:{subject}',
            'END:VEVENT',
        ])
    lines.append('END:VCALENDAR')
    return '\r\n'.join(lines) + '\r\n'


def export_lessons_to_ics(db: Optional[Database] = None) -> str:
    """Экспортирует все проведённые уроки в .ics."""
    if db is None:
        db = Database()
    lessons = db.conn.execute("""
        SELECT l.id, l.date, COALESCE(fs.name, ps.name) AS actual_subject_name
        FROM lessons l
        JOIN subjects ps ON l.subject_id = ps.id
        LEFT JOIN subjects fs ON l.actual_subject_id = fs.id
        WHERE l.status NOT IN ('cancelled', 'replaced')
        ORDER BY l.date
    """).fetchall()
    return generate_ics([dict(r) for r in lessons])


def generate_schedule_ics(db: Optional[Database] = None) -> str:
    """Генерирует .ics с плановым расписанием (повторяющиеся события).

    Каждая запись расписания → еженедельное событие (RRULE:FREQ=WEEKLY).
    week_type=1 → нечётная неделя, week_type=2 → чётная.
    """
    if db is None:
        db = Database()
    entries = db.list_schedule()
    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//TeachHelper4//RU',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
    ]
    today = date_type.today()
    # Start from the most recent Monday
    monday = today - timedelta(days=today.weekday())

    for e in entries:
        dow = e['day_of_week'] - 1  # 0=Monday
        rrule = 'FREQ=WEEKLY'
        if e['week_type'] == 1:
            rrule += ';INTERVAL=2'
        elif e['week_type'] == 2:
            rrule += ';INTERVAL=2'

        # DTSTART on the next occurrence of this weekday
        days_ahead = (dow - today.weekday()) % 7
        first_occurrence = today + timedelta(days=days_ahead)
        dtstart = datetime.combine(first_occurrence, datetime.min.time().replace(hour=9))
        dtend = dtstart + timedelta(hours=1, minutes=30)
        uid = f"schedule-{e['id']}@plan"

        byday = WEEKDAYS[dow]
        if e['week_type'] == 0:
            rrule = f'FREQ=WEEKLY;BYDAY={byday}'
        elif e['week_type'] == 1:
            rrule = f'FREQ=WEEKLY;INTERVAL=2;BYDAY={byday}'
        else:
            rrule = f'FREQ=WEEKLY;INTERVAL=2;BYDAY={byday}'

        lines.extend([
            'BEGIN:VEVENT',
            f'UID:{uid}',
            f'DTSTART:{_fmt_dt(dtstart)}',
            f'DTEND:{_fmt_dt(dtend)}',
            f'SUMMARY:{e["subject_name"]} ({e["group_name"]})',
            f'RRULE:{rrule}',
            f'DESCRIPTION:Занятие {e["lesson_number"]}',
            'END:VEVENT',
        ])

    lines.append('END:VCALENDAR')
    return '\r\n'.join(lines) + '\r\n'


def export_to_file(filepath: str = 'lessons.ics', db: Optional[Database] = None) -> str:
    """Сохраняет .ics файл проведённых занятий."""
    content = export_lessons_to_ics(db)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    return filepath


def export_schedule_to_file(filepath: str = 'schedule.ics', db: Optional[Database] = None) -> str:
    """Сохраняет .ics файл планового расписания."""
    content = generate_schedule_ics(db)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    return filepath
