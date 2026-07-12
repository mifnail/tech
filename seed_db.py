"""Fill database with test data."""
from database import Database
from datetime import date, timedelta

db = Database()

# Groups
g1 = db.add_group('ИС-11')
g2 = db.add_group('ПО-21')

# Students
students_is11 = [
    ('Иванов', 'Иван', 'Иванович'),
    ('Петров', 'Петр', 'Петрович'),
    ('Сидоров', 'Сидор', 'Сидорович'),
    ('Кузнецов', 'Алексей', 'Андреевич'),
    ('Смирнова', 'Ольга', 'Сергеевна'),
]
students_po21 = [
    ('Зайцев', 'Михаил', 'Дмитриевич'),
    ('Волкова', 'Анна', 'Викторовна'),
    ('Козлов', 'Дмитрий', 'Алексеевич'),
    ('Морозов', 'Артем', 'Игоревич'),
]
for s in students_is11:
    db.add_student(g1, *s)
for s in students_po21:
    db.add_student(g2, *s)

# Subjects
s1 = db.add_subject('Математика', 32, g1)
s2 = db.add_subject('Программирование', 48, g1)
s3 = db.add_subject('Базы данных', 24, g1)
s4 = db.add_subject('Математика', 32, g2)
s5 = db.add_subject('Физика', 24, g2)

# Schedule: Пн-Пт
schedule_data = [
    (1, 1, s1, 0), (1, 2, s2, 0),
    (2, 1, s3, 0), (2, 2, s1, 1),
    (3, 1, s2, 0), (3, 2, s3, 2),
    (4, 1, s4, 0), (4, 2, s5, 0),
    (5, 1, s5, 1),
]
for day, num, subj, week in schedule_data:
    db.add_schedule_entry(day, num, subj, week)

# Past lessons with grades
today = date.today()
students_is11_ids = [r['id'] for r in db.list_students(g1)]
students_po21_ids = [r['id'] for r in db.list_students(g2)]

for i in range(5):
    d = (today - timedelta(days=7 - i)).isoformat()
    lid1 = db.add_lesson(s1, d, s1)
    lid2 = db.add_lesson(s2, d, s2)
    lid3 = db.add_lesson(s3, d, s3)
    for sid in students_is11_ids:
        import random
        grades = ['5', '5', '4', '4', '3', '3', '2', 'absent']
        db.mark_attendance(lid1, sid, random.choice(grades))
        db.mark_attendance(lid2, sid, random.choice(grades))
    db.mark_attendance(lid3, students_is11_ids[0], '5')
    db.mark_attendance(lid3, students_is11_ids[1], '4')
    db.mark_attendance(lid3, students_is11_ids[2], '3')
    db.mark_attendance(lid3, students_is11_ids[3], 'absent')
    db.mark_attendance(lid3, students_is11_ids[4], '5')

# Substitution example
lid5 = db.add_lesson(s4, (today - timedelta(days=2)).isoformat(), s5)
for sid in students_po21_ids:
    db.mark_attendance(lid5, sid, '4')

# Today's lessons
today_lid = db.add_lesson(s1, today.isoformat(), s1)
for sid in students_is11_ids:
    db.mark_attendance(today_lid, sid, '4')

print("Seed data created successfully!")
print(f"Groups: {len([g1,g2])}, Students: {len(students_is11)+len(students_po21)}, Subjects: 5, Lessons: with grades")
db.close()
