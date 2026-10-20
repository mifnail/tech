#!/usr/bin/env python3
"""stand_seed.py — ПОЛНЫЙ сид фикстуры тестового стенда TeachHelper4.

Отдельный от seed_db.py сид, приближённый к реальной жизни учителя:
группы с русскими ФИО, предметы, расписание на будни с чередованием
недель, прошедшие занятия (проведённые с частичной посещаемостью и
отменённые), занятия на сегодня и на завтра.

Запуск СТОЯ:
    python stand_seed.py <path_to_db>

Скрипт создаёт/перезаписывает УКАЗАННУЮ базу через Database-класс из
database.py.  Никогда не трогает D:\\tech\\tech-redesign\\lessons.db —
если аргумент ведёт именно на неё, печатает отказ и выходит с кодом 2.

Детерминизм: random посажен на фиксированный seed; даты якорятся на
сегодняшнем дне (допустимо по ТЗ).
"""
from __future__ import annotations

import os
import random
import sys
from datetime import date, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from database import Database  # noqa: E402  (проектный класс, свой путь уже добавлен)

# Консоль Windows-раннера по умолчанию cp1252: русский текст в print падает
# с UnicodeEncodeError ещё до вывода результата, и сид «ломается» без причины.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:  # noqa: BLE001 — поток может быть заморожен/заменён
        pass

# --- детерминизм -----------------------------------------------------------
SEED = 20261013
PROTECTED_DB = os.path.normcase(os.path.realpath(os.path.join(BASE, 'lessons.db')))

# --- справочники -----------------------------------------------------------
SUBJECTS = [
    ('Информатика', 72),
    ('Компьютерные сети', 54),
    ('Базы данных', 68),
    ('Операционные системы', 60),
    ('Математика', 108),
]

GROUPS: list[tuple[str, list[tuple[str, str, str]]]] = [
    ('ПЗ-21', [
        ('Алексеев', 'Дмитрий', 'Сергеевич'),
        ('Баранова', 'Екатерина', 'Игоревна'),
        ('Волков', 'Артём', 'Павлович'),
        ('Гаврилова', 'Полина', 'Дмитриевна'),
        ('Дёмин', 'Никита', 'Александрович'),
        ('Ершова', 'Софья', 'Владимировна'),
        ('Жуков', 'Максим', 'Олегович'),
        ('Зайцева', 'Алина', 'Романовна'),
    ]),
    ('СЗ-11', [
        ('Игнатов', 'Кирилл', 'Юрьевич'),
        ('Ковалёва', 'Дарья', 'Максимовна'),
        ('Лаптев', 'Иван', 'Денисович'),
        ('Морозова', 'Вера', 'Андреевна'),
        ('Некрасов', 'Егор', 'Игоревич'),
        ('Овчинникова', 'Мария', 'Сергеевна'),
        ('Панфилов', 'Тимур', 'Русланович'),
    ]),
    ('ПЗ-22', [
        ('Романов', 'Алексей', 'Викторович'),
        ('Савельева', 'Ксения', 'Павловна'),
        ('Тарасов', 'Владислав', 'Михайлович'),
        ('Устинова', 'Елизавета', 'Олеговна'),
        ('Фёдоров', 'Глеб', 'Андреевич'),
        ('Хромова', 'Надежда', 'Ивановна'),
        ('Цыганов', 'Станислав', 'Юрьевич'),
        ('Черкасова', 'Юлия', 'Дмитриевна'),
        ('Шестаков', 'Роман', 'Алексеевич'),
    ]),
    ('СЗ-12', [
        ('Щукина', 'Татьяна', 'Михайловна'),
        ('Юрьев', 'Платон', 'Сергеевич'),
        ('Яковлева', 'Валерия', 'Егоровна'),
        ('Белозёров', 'Константин', 'Ильич'),
        ('Гордеева', 'Анастасия', 'Романовна'),
        ('Данилов', 'Артур', 'Валерьевич'),
    ]),
]

# (day_of_week 1..5, lesson_number 1..4, слот предмета в списке группы, week_type)
WEEK_TEMPLATE: list[tuple[int, int, int, int]] = [
    (1, 1, 0, 0), (1, 2, 1, 0),
    (2, 1, 2, 1), (2, 3, 3, 0),
    (3, 2, 0, 2), (3, 4, 1, 0),
    (4, 1, 2, 0), (4, 2, 3, 1),
    (5, 3, 0, 0), (5, 4, 1, 2),
]

# Веса оценок: 5/4/3/2/неуважительный пропуск
GRADE_POOL = ['5'] * 30 + ['4'] * 30 + ['3'] * 20 + ['2'] * 7 + ['absent'] * 13

PAST_DAYS = 14          # две полные недели занятий назад от сегодня
CANCELLED_RATE = 0.18   # доля отменённых занятий в прошлом
PRESENT_RATE = 0.82     # вероятность, что студент получил запись на занятии


def _week_type(day: date) -> int:
    """Чередование недель — та же формула, что у api.schedule_today()."""
    return 1 if day.isocalendar()[1] % 2 == 1 else 2


def _entries_for(day: date) -> list[tuple[int, int, int, int]]:
    """Слоты расписания на конкретную дату (учитывая чередование недель)."""
    weekday = day.isoweekday()
    if weekday <= 5:
        wt = _week_type(day)
        matched = [e for e in WEEK_TEMPLATE if e[0] == weekday and e[3] in (0, wt)]
        if matched:
            return matched
    # выходной / пустая неделя: берём понедельничные слоты (реалистично для
    # «переноса» занятия и просто чтобы сегодня/завтра всегда были пары)
    return [e for e in WEEK_TEMPLATE if e[0] == 1]


def _mark_partial(db: Database, rng: random.Random, student_ids: list[int], lesson_id: int) -> int:
    """Посещаемость, размазанная по студентам: у кого-то оценка, у кого-то
    пропуск без записи, у кого-то «absent»."""
    records = []
    for sid in student_ids:
        if rng.random() < PRESENT_RATE:
            records.append({'student_id': sid, 'grade': rng.choice(GRADE_POOL)})
    db.mark_attendance_bulk(lesson_id, records)
    return len(records)


def seed(db_path: str) -> dict[str, int]:
    """Заполнить базу. Возвращает словарь счётчиков для отчёта."""
    rng = random.Random(SEED)
    stats = {
        'groups': 0, 'students': 0, 'subjects': 0, 'schedule': 0,
        'lessons': 0, 'held': 0, 'scheduled': 0, 'cancelled': 0, 'grades': 0,
    }

    with Database(db_path) as db:
        # --- группы и студенты ---
        groups = []
        for name, roster in GROUPS:
            gid = db.add_group(name)
            db.add_students_bulk(gid, [
                {'last_name': last, 'first_name': first, 'middle_name': middle}
                for (last, first, middle) in roster
            ])
            stats['groups'] += 1
            stats['students'] += len(roster)
            groups.append({'id': gid, 'subjects': []})

        # --- предметы (5 разных названий, у каждой группы свой набор) ---
        for index, group in enumerate(groups):
            for slot in range(4):
                subject_name, hours = SUBJECTS[(index + slot) % len(SUBJECTS)]
                group['subjects'].append(db.add_subject(subject_name, hours, group['id']))
                stats['subjects'] += 1

        # --- расписание: будни, пары 1-4, чередование 0/1/2 ---
        for group in groups:
            for day, number, slot, week_type in WEEK_TEMPLATE:
                db.add_schedule_entry(day, number, group['subjects'][slot], week_type)
                stats['schedule'] += 1

        students_by_group = {
            group['id']: [row['id'] for row in db.list_students(group['id'])]
            for group in groups
        }

        today = date.today()

        # --- прошедшие две недели занятий: часть held, часть cancelled ---
        for offset in range(PAST_DAYS, 0, -1):
            day = today - timedelta(days=offset)
            if day.isoweekday() > 5:
                continue
            for group in groups:
                for number_slot in _entries_for(day):
                    day_of_week, lesson_number, subject_slot, _week = number_slot
                    if day_of_week != day.isoweekday():
                        continue
                    status = 'cancelled' if rng.random() < CANCELLED_RATE else 'held'
                    lesson_id = db.add_lesson(
                        group['subjects'][subject_slot],
                        day.isoformat(),
                        status=status,
                        lesson_number=lesson_number)
                    stats['lessons'] += 1
                    stats[status] += 1
                    if status == 'held':
                        stats['grades'] += _mark_partial(
                            db, rng, students_by_group[group['id']], lesson_id)

        # --- на сегодня: одно held (с посещаемостью) и одно scheduled ---
        today_slots = _entries_for(today)
        first_group, second_group = groups[0], groups[1]
        day_a, number_a, slot_a, _ = today_slots[0]
        lesson_id = db.add_lesson(
            first_group['subjects'][slot_a], today.isoformat(),
            status='held', lesson_number=number_a)
        stats['lessons'] += 1
        stats['held'] += 1
        stats['grades'] += _mark_partial(db, rng, students_by_group[first_group['id']], lesson_id)

        day_b, number_b, slot_b, _ = today_slots[min(1, len(today_slots) - 1)]
        db.add_lesson(
            second_group['subjects'][slot_b], today.isoformat(),
            status='scheduled', lesson_number=number_b)
        stats['lessons'] += 1
        stats['scheduled'] += 1

        # --- на завтра и послезавтра: scheduled ---
        for offset, group in ((1, groups[2]), (2, groups[3])):
            day = today + timedelta(days=offset)
            day_c, number_c, slot_c, _ = _entries_for(day)[0]
            db.add_lesson(
                group['subjects'][slot_c], day.isoformat(),
                status='scheduled', lesson_number=number_c)
            stats['lessons'] += 1
            stats['scheduled'] += 1

    return stats


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print('Использование: python stand_seed.py <path_to_db>', file=sys.stderr)
        return 2

    target = os.path.realpath(os.path.abspath(argv[1]))
    if os.path.normcase(target) == PROTECTED_DB:
        print('ОТКАЗ: рабочая база проекта lessons.db не будет перезаписана. '
              'Укажите другой путь (например %TEMP%\\stand_test.db).', file=sys.stderr)
        return 2

    # Перезапись: снимаем старый файл и его WAL/Journal-спутники.
    for suffix in ('', '-wal', '-shm', '-journal'):
        stale = target + suffix
        if os.path.exists(stale):
            os.remove(stale)

    parent = os.path.dirname(target)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)

    stats = seed(target)

    print(f'Сид готов: {target}')
    print(f"  Групп: {stats['groups']}, студентов: {stats['students']}, "
          f"предметов: {stats['subjects']}, записей расписания: {stats['schedule']}")
    print(f"  Занятий: {stats['lessons']} (held {stats['held']}, "
          f"cancelled {stats['cancelled']}, scheduled {stats['scheduled']})")
    print(f"  Отмечено посещаемости/оценок: {stats['grades']}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
