"""Export schedule to iCalendar (.ics) format."""
from datetime import datetime, timedelta
from database import Database

def export_ics(db_path=None):
    db = Database(db_path)
    lessons = db.conn.execute("""
        SELECT l.date, COALESCE(fs.name, ps.name) AS subject_name, g.name AS group_name
        FROM lessons l
        JOIN subjects ps ON l.subject_id = ps.id
        LEFT JOIN subjects fs ON l.actual_subject_id = fs.id
        JOIN groups g ON ps.group_id = g.id
        ORDER BY l.date
    """).fetchall()
    db.close()

    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//TeachHelper4//RU',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
    ]

    for l in lessons:
        d = datetime.strptime(l['date'], '%Y-%m-%d')
        dt_start = d.strftime('%Y%m%dT090000')
        dt_end = d.strftime('%Y%m%dT103000')
        uid = f'lesson-{l["date"]}-{l["subject_name"]}@teachhelper4'
        summary = f'{l["subject_name"]} ({l["group_name"]})'

        lines.extend([
            'BEGIN:VEVENT',
            f'UID:{uid}',
            f'DTSTART:{dt_start}',
            f'DTEND:{dt_end}',
            f'SUMMARY:{summary}',
            'END:VEVENT',
        ])

    lines.append('END:VCALENDAR')
    return '\r\n'.join(lines) + '\r\n'

if __name__ == '__main__':
    print(export_ics())
