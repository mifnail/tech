"""Экспорт отчётов в Excel (.xlsx) и CSV."""

from __future__ import annotations

import csv
import os
from typing import Optional

from database import Database


def export_grades_csv(subject_id: int, filepath: Optional[str] = None, db: Optional[Database] = None) -> str:
    """Экспортирует ведомость по предмету в CSV (таблица студенты × занятия)."""
    if db is None:
        db = Database()
    if filepath is None:
        filepath = os.path.join(os.path.dirname(__file__), f'grades_{subject_id}.csv')
    students, lessons, grades = db.subject_gradebook(subject_id)
    summary = db.subject_summary(subject_id)
    subj_name = dict(summary)['name'] if summary else f'Subject #{subject_id}'

    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow([subj_name])
        header = ['Студент'] + [str(i + 1) for i in range(len(lessons))]
        writer.writerow(header)
        for s in students:
            row = [f"{s['last_name']} {s['first_name']}"]
            for l in lessons:
                row.append(grades.get(str(s['id']), {}).get(str(l['id']), ''))
            writer.writerow(row)
    return filepath


def export_report_csv(date: str, filepath: Optional[str] = None, db: Optional[Database] = None) -> str:
    """Экспортирует дневной отчёт в CSV."""
    if db is None:
        db = Database()
    if filepath is None:
        filepath = os.path.join(os.path.dirname(__file__), f'report_{date}.csv')
    rows = db.daily_report(date)

    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow([f'Отчёт за {date}'])
        writer.writerow(['Предмет', 'Группа', 'Статус', 'Оценок', 'Пропусков'])
        for r in rows:
            rd = dict(r)
            writer.writerow([
                rd.get('subject_name', ''),
                rd.get('group_name', ''),
                rd.get('status', ''),
                rd.get('grades_count', 0),
                rd.get('absent_count', 0),
            ])
    return filepath
