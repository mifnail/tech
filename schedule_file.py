"""Parse schedule.txt and generate lessons in DB.

Format (semicolon-delimited):
    День_недели;Номер_пары;ID_Предмета;Признак_недели
Example:
    1;1;1;0   # Пн, пара 1, предмет ID=1, каждую неделю
    1;2;2;1   # Пн, пара 2, предмет ID=2, числитель
"""
from datetime import date, timedelta
from database import Database

WEEKDAY_NAMES = {1:'Пн',2:'Вт',3:'Ср',4:'Чт',5:'Пт',6:'Сб'}

def parse_schedule_file(filepath):
    entries = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split(';')
            if len(parts) >= 3:
                entries.append({
                    'day_of_week': int(parts[0]),
                    'lesson_number': int(parts[1]),
                    'subject_id': int(parts[2]),
                    'week_type': int(parts[3]) if len(parts) > 3 and parts[3] else 0,
                })
    return entries

def generate_lessons(schedule_entries, semester_start, semester_end, db_path=None):
    db = Database(db_path)
    created = 0
    d = semester_start
    while d <= semester_end:
        if d.isoweekday() >= 7:
            d += timedelta(days=1)
            continue
        week_num = (d - semester_start).days // 7 + 1
        is_odd = week_num % 2 == 1
        weekday = d.isoweekday()
        for entry in schedule_entries:
            if entry['day_of_week'] != weekday:
                continue
            if entry['week_type'] == 1 and not is_odd:
                continue
            if entry['week_type'] == 2 and is_odd:
                continue
            db.add_lesson(entry['subject_id'], d.isoformat(), entry['subject_id'])
            created += 1
        d += timedelta(days=1)
    db.close()
    return created

if __name__ == '__main__':
    import sys
    filepath = sys.argv[1] if len(sys.argv) > 1 else 'schedule.txt'
    start = date(2026, 9, 1)
    end = date(2026, 12, 31)
    entries = parse_schedule_file(filepath)
    count = generate_lessons(entries, start, end)
    print(f'Generated {count} lessons from {len(entries)} schedule entries')
