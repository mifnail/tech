"""Экспорт занятий в iCalendar (.ics) формат."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from database import Database


def generate_ics(lessons: list[dict]) -> str:
    """Генерирует .ics-строку из списка занятий."""
    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//TeachHelper4//RU',
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
        lines.extend([
            'BEGIN:VEVENT',
            f'DTSTART:{start}',
            f'DTEND:{end}',
            f'SUMMARY:{subject}',
            'END:VEVENT',
        ])
    lines.append('END:VCALENDAR')
    return '\r\n'.join(lines) + '\r\n'


def export_lessons_to_ics(db: Optional[Database] = None) -> str:
    """Экспортирует все уроки из БД в .ics."""
    if db is None:
        db = Database()
    lessons = db.conn.execute("""
        SELECT l.date, COALESCE(fs.name, ps.name) AS actual_subject_name
        FROM lessons l
        JOIN subjects ps ON l.subject_id = ps.id
        LEFT JOIN subjects fs ON l.actual_subject_id = fs.id
        WHERE l.status != 'free'
        ORDER BY l.date
    """).fetchall()
    return generate_ics([dict(r) for r in lessons])


def export_to_file(filepath: str = 'lessons.ics', db: Optional[Database] = None) -> str:
    """Сохраняет .ics файл."""
    content = export_lessons_to_ics(db)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    return filepath
