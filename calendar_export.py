"""Экспорт в iCalendar (.ics): плановое расписание и проведённые занятия.

Времени пар в базе нет — хранится только номер пары (schedule.lesson_number).
Поэтому время берётся из типовой сетки PAIR_TIMES: если в колледже звонки
другие, правится одной константой здесь.

Чётность недель: schedule.week_type 0 — каждую неделю, 1 — нечётная,
2 — чётная (как в UI: weekTypeOf в lib/date.ts). Нечётная = нечётный номер
ISO-недели. Для повторяющегося события важно правильно поставить DTSTART:
RRULE с INTERVAL=2 сохраняет ту чётность, с которой начал.
"""

from __future__ import annotations

from datetime import datetime, timedelta, date as date_type, timezone
from typing import Optional

from database import Database

# Типовая сетка звонков. Ключ — номер пары.
PAIR_TIMES = {
    1: ('08:30', '10:00'),
    2: ('10:10', '11:40'),
    3: ('12:10', '13:40'),
    4: ('13:50', '15:20'),
    5: ('15:30', '17:00'),
    6: ('17:10', '18:40'),
}
DEFAULT_PAIR_TIME = ('09:00', '10:30')

WEEKDAYS = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']

CAL_NAME_LESSONS = 'Учёт занятий — проведённые'
CAL_NAME_SCHEDULE = 'Учёт занятий — расписание'


def _escape(text: str) -> str:
    """Экранирование текста по RFC 5545: \\ ; , и переводы строк."""
    out = str(text or '')
    out = out.replace('\\', '\\\\')
    out = out.replace(';', '\\;').replace(',', '\\,')
    out = out.replace('\r\n', '\\n').replace('\n', '\\n').replace('\r', '\\n')
    return out


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def _pair_time(number) -> tuple[str, str]:
    try:
        return PAIR_TIMES.get(int(number), DEFAULT_PAIR_TIME)
    except (TypeError, ValueError):
        return DEFAULT_PAIR_TIME


def _event_dt(date_str: str, number) -> tuple[str, str, datetime] | None:
    try:
        day = datetime.strptime(str(date_str)[:10], '%Y-%m-%d')
    except (ValueError, TypeError):
        return None
    start_h, end_h = _pair_time(number)
    start = day.replace(hour=int(start_h[:2]), minute=int(start_h[3:]))
    end = day.replace(hour=int(end_h[:2]), minute=int(end_h[3:]))
    return (
        start.strftime('%Y%m%dT%H%M%S'),
        end.strftime('%Y%m%dT%H%M%S'),
        start,
    )


def _calendar(lines: list[str], name: str) -> str:
    body = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Uchet zanyatiy//RU',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        f'X-WR-CALNAME:{_escape(name)}',
        *_flatten(lines),
        'END:VCALENDAR',
    ]
    return '\r\n'.join(body) + '\r\n'


def _flatten(lines) -> list[str]:
    out: list[str] = []
    for item in lines:
        if isinstance(item, list):
            out.extend(_flatten(item))
        else:
            out.append(item)
    return out


def _lesson_events(lessons: list[dict]) -> list[list[str]]:
    events: list[list[str]] = []
    stamp = _stamp()
    for lesson in lessons:
        when = _event_dt(lesson.get('date', ''), lesson.get('lesson_number'))
        if when is None:
            continue
        start, end, _ = when
        subject = lesson.get('actual_subject_name') or lesson.get('subject_name') or 'Занятие'
        group = lesson.get('group_name') or ''
        summary = f'{subject} ({group})' if group else subject
        number = lesson.get('lesson_number')
        desc = f'Пара {number}' if number else 'Занятие'
        events.append([
            'BEGIN:VEVENT',
            f"UID:lesson-{lesson.get('id', 0)}@uchet",
            f'DTSTAMP:{stamp}',
            f'DTSTART:{start}',
            f'DTEND:{end}',
            f'SUMMARY:{_escape(summary)}',
            f'DESCRIPTION:{_escape(desc)}',
            'END:VEVENT',
        ])
    return events


def generate_ics(lessons: list[dict]) -> str:
    """Собрать .ics из списка занятий (проведённых)."""
    return _calendar(_lesson_events(lessons), CAL_NAME_LESSONS)


def export_lessons_to_ics(db: Optional[Database] = None) -> str:
    """Все проведённые занятия в .ics."""
    own = db is None
    if own:
        db = Database()
    try:
        rows = db.conn.execute("""
            SELECT l.id, l.date, l.lesson_number,
                COALESCE(fs.name, ps.name) AS actual_subject_name,
                g.name AS group_name
            FROM lessons l
            JOIN subjects ps ON l.subject_id = ps.id
            LEFT JOIN subjects fs ON l.actual_subject_id = fs.id
            JOIN groups g ON ps.group_id = g.id
            WHERE l.status = 'held'
            ORDER BY l.date, COALESCE(l.lesson_number, 999)
        """).fetchall()
        return generate_ics([dict(r) for r in rows])
    finally:
        if own:
            db.close()


def _anchor_date(today: date_type, dow: int, week_type: int) -> date_type:
    """Ближайшая (сегодня или позже) дата нужного дня недели и чётности.

    dow: 0 — понедельник. week_type 0 — любая неделя, 1 — нечётная ISO,
    2 — чётная ISO.
    """
    monday = today - timedelta(days=today.weekday())
    if not week_type:
        anchor = monday + timedelta(days=dow)
        while anchor < today:
            anchor += timedelta(days=7)
        return anchor

    want_odd = week_type == 1
    for week in range(3):
        m = monday + timedelta(weeks=week)
        if (m.isocalendar()[1] % 2 == 1) == want_odd:
            anchor = m + timedelta(days=dow)
            if anchor >= today:
                return anchor
            return anchor + timedelta(days=14)
    return monday + timedelta(days=dow)


def generate_schedule_ics(db: Optional[Database] = None) -> str:
    """Плановое расписание как повторяющиеся события."""
    own = db is None
    if own:
        db = Database()
    try:
        entries = [dict(e) for e in db.list_schedule()]
    finally:
        if own:
            db.close()

    today = date_type.today()
    stamp = _stamp()
    events: list[list[str]] = []
    for e in entries:
        dow = int(e.get('day_of_week') or 1) - 1
        if not 0 <= dow <= 6:
            continue
        week_type = int(e.get('week_type') or 0)
        anchor = _anchor_date(today, dow, week_type)
        start_h, end_h = _pair_time(e.get('lesson_number'))
        start = datetime.combine(anchor, datetime.min.time()).replace(
            hour=int(start_h[:2]), minute=int(start_h[3:]))
        end = datetime.combine(anchor, datetime.min.time()).replace(
            hour=int(end_h[:2]), minute=int(end_h[3:]))

        byday = WEEKDAYS[dow]
        if week_type:
            rrule = f'FREQ=WEEKLY;INTERVAL=2;BYDAY={byday}'
        else:
            rrule = f'FREQ=WEEKLY;BYDAY={byday}'

        summary = f"{e.get('subject_name') or 'Занятие'} ({e.get('group_name') or ''})"
        events.append([
            'BEGIN:VEVENT',
            f"UID:schedule-{e.get('id', 0)}@uchet",
            f'DTSTAMP:{stamp}',
            f'DTSTART:{start.strftime("%Y%m%dT%H%M%S")}',
            f'DTEND:{end.strftime("%Y%m%dT%H%M%S")}',
            f'SUMMARY:{_escape(summary)}',
            f'DESCRIPTION:{_escape("Пара " + str(e.get("lesson_number") or ""))}',
            f'RRULE:{rrule}',
            'END:VEVENT',
        ])

    return _calendar(events, CAL_NAME_SCHEDULE)


def export_to_file(filepath: str = 'lessons.ics', db: Optional[Database] = None) -> str:
    """Сохранить .ics проведённых занятий в файл."""
    content = export_lessons_to_ics(db)
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        f.write(content)
    return filepath


def export_schedule_to_file(filepath: str = 'schedule.ics', db: Optional[Database] = None) -> str:
    """Сохранить .ics расписания в файл."""
    content = generate_schedule_ics(db)
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        f.write(content)
    return filepath
