"""Парсер schedule.txt — импорт расписания из текстового файла."""

from __future__ import annotations

import re
from typing import Optional

from database import Database


def parse_schedule(filepath: str) -> list[dict]:
    """Читает schedule.txt, возвращает список записей расписания."""
    entries: list[dict] = []
    pattern = re.compile(r'^\s*(\d+);(\d+);(\d+);(\d+)')
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            m = pattern.match(line)
            if m:
                entries.append({
                    'day_of_week': int(m.group(1)),
                    'lesson_number': int(m.group(2)),
                    'subject_id': int(m.group(3)),
                    'week_type': int(m.group(4)),
                })
    return entries


def import_schedule(filepath: str, db: Optional[Database] = None) -> int:
    """Импортирует расписание из файла в БД."""
    if db is None:
        db = Database()
    entries = parse_schedule(filepath)
    for entry in entries:
        db.add_schedule_entry(**entry)
    return len(entries)
