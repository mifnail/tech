#!/usr/bin/env python3
"""
seed_db.py — Пересоздать базу данных с тестовыми данными.

⚠️  ВНИМАНИЕ: Этот скрипт УНИЧТОЖАЕТ текущую lessons.db и создаёт новую
    с тестовыми данными. Запускать ТОЛЬКО если реальной базы нет
    или она не нужна.

    Если нужна чистая тестовая БД без риска — используй: python -m pytest
"""
import os
import sys
from database import Database

DB_PATH = os.path.join(os.path.dirname(__file__), 'lessons.db')

if os.path.exists(DB_PATH):
    print(f"⚠️  ВНИМАНИЕ: Существует база данных: {DB_PATH}")
    resp = input("Удалить и пересоздать? (yes/NO): ").strip().lower()
    if resp != 'yes':
        print("Отмена. База данных не изменена.")
        sys.exit(0)
    os.remove(DB_PATH)
    print("Удалена.")

db = Database(DB_PATH)
db.seed_default()

total = db.conn.execute("SELECT COUNT(*) AS c FROM students").fetchone()['c']
subjs = db.conn.execute("SELECT COUNT(*) AS c FROM subjects").fetchone()['c']
schedule_entries = db.conn.execute("SELECT COUNT(*) AS c FROM schedule").fetchone()['c']

print(f"База данных создана: {DB_PATH}")
print(f"  Группы: 1, Студентов: {total}, Предметов: {subjs}, Записей расписания: {schedule_entries}")
print("  Занятий: 0, Оценок: 0.")
db.close()
