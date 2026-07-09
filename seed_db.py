"""
seed_db.py — создаёт файл lessons.db и наполняет его ТЕСТОВЫМИ данными.

Запуск локально (на ПК, где есть обычный Python со встроенным sqlite3):
    python seed_db.py

После запуска в папке появится lessons.db — его можно закоммитить и запушить на GitHub.
Скрипт идемпотентный: повторный запуск не плодит дубликаты (данные уникальны по ключам),
но если хотите «чистую» БД — просто удалите lessons.db перед запуском.

Весь доступ к БД идёт через database.py (единственное место с SQL — см. AGENT.md).
"""
from datetime import date

from database import Database

DB_PATH = "lessons.db"

# --- Тестовые данные -------------------------------------------------------
# Группы -> студенты
GROUPS = {
    "ИС-11": [
        "Иванов Иван",
        "Петров Пётр",
        "Сидорова Анна",
        "Кузнецова Мария",
        "Смирнов Алексей",
    ],
    "ПО-21": [
        "Волков Дмитрий",
        "Морозова Елена",
        "Новиков Сергей",
        "Фёдорова Ольга",
    ],
}

# Предметы: (название, план в ЗАНЯТИЯХ, группа)
SUBJECTS = [
    ("Математика", 32, "ИС-11"),
    ("Программирование", 48, "ИС-11"),
    ("Базы данных", 24, "ПО-21"),
]

# Сколько занятий уже «проведено» по каждому предмету (для прогресс-бара на главном экране)
HELD = {
    "Математика": 12,
    "Программирование": 20,
    "Базы данных": 6,
}


def seed() -> None:
    db = Database(DB_PATH)
    db.init_schema()

    # Группы + студенты (массовый ввод списком)
    for group, students in GROUPS.items():
        db.add_students_bulk(group, students)

    # Предметы
    subject_ids = {}
    for name, planned, group in SUBJECTS:
        subject_ids[name] = db.add_subject(name, planned, group)

    # Проведённые занятия + отметки посещаемости/оценок
    for name, sid in subject_ids.items():
        group = next(g for (n, _, g) in SUBJECTS if n == name)
        students = db.list_students(group)
        for i in range(HELD.get(name, 0)):
            # Условная дата занятия: сентябрь, по одному в день
            held_at = f"2026-09-{(i % 28) + 1:02d}T10:00:00"
            lesson_id = db.add_lesson(sid, held_at)
            # Отмечаем присутствие: часть студентов с оценкой, часть — просто галочкой,
            # один — отсутствует (для наглядности ведомости).
            for j, st in enumerate(students):
                if j == 0 and i % 3 == 0:
                    db.mark_attendance(lesson_id, st["id"], present=False)  # отсутствовал
                elif j % 2 == 0:
                    grade = 3 + ((i + j) % 3)  # оценка 3..5
                    db.mark_attendance(lesson_id, st["id"], present=True, grade=grade)
                else:
                    db.mark_attendance(lesson_id, st["id"], present=True)  # только галочка

    # Пара занятий ПО РАСПИСАНИЮ НА СЕГОДНЯ (status='scheduled') — чтобы сразу было
    # что показать на экране «Расписание на сегодня» (в т.ч. два занятия по одному
    # предмету в один день и параллельное занятие по другому предмету).
    today = date.today().isoformat()
    db.add_lesson(subject_ids["Математика"], f"{today}T09:00:00", status="scheduled")
    db.add_lesson(subject_ids["Математика"], f"{today}T14:00:00", status="scheduled")
    db.add_lesson(subject_ids["Программирование"], f"{today}T09:00:00", status="scheduled")
    db.add_lesson(subject_ids["Базы данных"], f"{today}T11:00:00", status="scheduled")

    # Короткий отчёт в консоль
    print(f"БД создана: {DB_PATH}")
    print("Предметы (план / проведено / осталось, в занятиях):")
    for s in db.list_subjects():
        print(f"  - {s['name']} [{s['group_name']}]: "
              f"{s['planned']} / {s['held']} / {s['remaining']}")
    db.close()


def main() -> None:
    seed()


if __name__ == "__main__":
    main()