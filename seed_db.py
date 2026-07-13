"""Generate default database with seed data."""
import os
from database import Database

DB_PATH = os.path.join(os.path.dirname(__file__), 'lessons.db')

if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

db = Database(DB_PATH)
db.seed_default()

total = db.conn.execute("SELECT COUNT(*) AS c FROM students").fetchone()['c']
subjs = db.conn.execute("SELECT COUNT(*) AS c FROM subjects WHERE name != 'СВОБОДНО'").fetchone()['c']
schedule_entries = db.conn.execute("SELECT COUNT(*) AS c FROM schedule").fetchone()['c']

print(f"Default database created: {DB_PATH}")
print(f"  Groups: 3, Students: {total}, Subjects: {subjs}, Schedule entries: {schedule_entries}")
print("  No lessons, no grades.")
db.close()
