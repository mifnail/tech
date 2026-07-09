"""
Тесты разбора файла-расписания и генерации занятий (без БД и Kivy — чистая логика).
Запуск: pytest -q
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from schedule_file import (  # noqa: E402
    ScheduleError,
    generate_occurrences,
    pair_start_time,
    parse_schedule,
    week_parity,
)

SAMPLE = """
# коммент
СЕМЕСТР=2026-09-07; ПЕРВАЯ_НЕДЕЛЯ=Н
Понедельник; 1; Математика; ИС-11; ЧН
Понедельник; 3; Программирование; ПО-21; Ч
Среда; 2; Математика; ИС-11; Н
"""


def test_pair_times():
    # Пара длится 1:45; отсчёт с 09:00, пары подряд.
    assert pair_start_time(1).strftime("%H:%M") == "09:00"
    assert pair_start_time(2).strftime("%H:%M") == "10:45"
    assert pair_start_time(3).strftime("%H:%M") == "12:30"
    assert pair_start_time(4).strftime("%H:%M") == "14:15"


def test_parse_ok():
    parsed = parse_schedule(SAMPLE)
    assert parsed["semester_start"] == date(2026, 9, 7)
    assert parsed["first_week_parity"] == "Н"
    assert len(parsed["entries"]) == 3


def test_parse_parity_normalization():
    parsed = parse_schedule(
        "СЕМЕСТР=2026-09-07; ПЕРВАЯ_НЕДЕЛЯ=Ч\nПн; 1; X; Г; нч"
    )
    assert parsed["entries"][0]["parity"] == "ЧН"


def test_parse_missing_meta():
    with pytest.raises(ScheduleError):
        parse_schedule("Понедельник; 1; Математика; ИС-11; ЧН")


def test_parse_bad_pair():
    with pytest.raises(ScheduleError):
        parse_schedule("СЕМЕСТР=2026-09-07; ПЕРВАЯ_НЕДЕЛЯ=Н\nПн; x; A; Г; ЧН")


def test_parse_too_few_fields():
    with pytest.raises(ScheduleError):
        parse_schedule("СЕМЕСТР=2026-09-07; ПЕРВАЯ_НЕДЕЛЯ=Н\nПн; 1; A; ЧН")


def test_week_parity_alternates():
    ss = date(2026, 9, 7)  # понедельник
    assert week_parity(date(2026, 9, 7), ss, "Н") == "Н"
    assert week_parity(date(2026, 9, 14), ss, "Н") == "Ч"
    assert week_parity(date(2026, 9, 21), ss, "Н") == "Н"
    # день в середине той же недели даёт ту же чётность
    assert week_parity(date(2026, 9, 9), ss, "Н") == "Н"


def test_generate_plan_plus_one():
    parsed = parse_schedule(SAMPLE)
    plans = {("Математика", "ИС-11"): 3, ("Программирование", "ПО-21"): 2}
    occ = generate_occurrences(parsed, plans)
    math = [o for o in occ if o["subject"] == "Математика"]
    prog = [o for o in occ if o["subject"] == "Программирование"]
    assert len(math) == 4   # план 3 + 1
    assert len(prog) == 3   # план 2 + 1


def test_generate_parity_dates():
    parsed = parse_schedule(SAMPLE)
    plans = {("Программирование", "ПО-21"): 2}
    occ = generate_occurrences(parsed, plans)
    # 'Ч' → первая чётная неделя начинается 14.09, пара 3 → 12:30.
    assert occ[0]["held_at"] == "2026-09-14T12:30:00"
    # Через 2 недели — 28.09.
    assert occ[1]["held_at"] == "2026-09-28T12:30:00"


def test_generate_skips_unknown_subject():
    parsed = parse_schedule(SAMPLE)
    # Планы не заданы вовсе — генератор просто ничего не выдаёт (пропуск на уровне БД).
    occ = generate_occurrences(parsed, {})
    assert occ == []


def test_generate_chronological_order():
    parsed = parse_schedule(SAMPLE)
    plans = {("Математика", "ИС-11"): 3, ("Программирование", "ПО-21"): 2}
    occ = generate_occurrences(parsed, plans)
    times = [o["held_at"] for o in occ]
    assert times == sorted(times)