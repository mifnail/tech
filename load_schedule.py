"""
load_schedule.py — читает schedule.txt, генерирует занятия и добавляет в БД.

Запуск:
    python load_schedule.py              # добавить новые занятия
    python load_schedule.py --dry-run    # только показать, что будет добавлено
    python load_schedule.py --clear      # удалить ВСЕ занятия перед добавлением
"""
import sys
from datetime import date

from database import Database
from schedule_file import parse_schedule, generate_occurrences


def main():
    dry_run = "--dry-run" in sys.argv
    clear_first = "--clear" in sys.argv
    schedule_path = "schedule.txt"

    # Читаем расписание
    with open(schedule_path, encoding="utf-8") as f:
        parsed = parse_schedule(f.read())

    # Планы из БД
    db = Database("lessons.db")
    db.init_schema()

    subjects = db.list_subjects()
    plans = {}
    name_to_id = {}
    for s in subjects:
        plans[(s["name"], s["group_name"])] = s["planned"]
        name_to_id[(s["name"], s["group_name"])] = s["id"]

    # Генерируем занятия
    occurrences = generate_occurrences(parsed, plans)
    print(f"Сгенерировано занятий: {len(occurrences)}")

    if not occurrences:
        print("Нет занятий для добавления.")
        db.close()
        return

    # Фильтр: пропускаем уже проведённые (сравнение по дате и предмету)
    existing_lessons = db._conn.execute(
        "SELECT subject_id, held_at FROM lessons"
    ).fetchall()
    existing_set = {(r[0], r[1]) for r in existing_lessons}

    new_occ = []
    skipped = 0
    for o in occurrences:
        sid = name_to_id.get((o["subject"], o["group"]))
        if sid is None:
            skipped += 1
            continue
        if (sid, o["held_at"]) in existing_set:
            skipped += 1
            continue
        new_occ.append((sid, o["held_at"]))

    print(f"  новых: {len(new_occ)}, пропущено (уже есть): {skipped}")

    if dry_run:
        print("\n--- DRY RUN — ничего не добавлено ---")
        for sid, held_at in new_occ[:10]:
            print(f"  {held_at}  subj_id={sid}")
        if len(new_occ) > 10:
            print(f"  ... и ещё {len(new_occ) - 10}")
        db.close()
        return

    if clear_first:
        db._conn.execute("DELETE FROM lessons")
        db._conn.commit()
        # После удаления — все сгенерированные считаются новыми
        new_occ = [(name_to_id[(o["subject"], o["group"])], o["held_at"])
                   for o in occurrences
                   if name_to_id.get((o["subject"], o["group"]))]
        print(f"  (после очистки: {len(new_occ)} занятий)")

    # Вставляем (без отметок посещаемости — они проставляются на занятии)
    for sid, held_at in new_occ:
        db.add_lesson(sid, held_at, status="scheduled")

    print(f"\nДобавлено занятий: {len(new_occ)}")
    db.close()


if __name__ == "__main__":
    main()
