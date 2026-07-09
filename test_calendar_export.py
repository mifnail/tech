"""
Тесты генерации .ics (без БД и Kivy — чистая логика). Гоняются в CI.
Запуск: pytest -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from calendar_export import build_ics  # noqa: E402


def _sample():
    return [
        {"id": 1, "held_at": "2026-09-01T09:00:00",
         "subject_name": "Математика", "group_name": "ИС-11"},
        {"id": 2, "held_at": "2026-09-01T14:00:00",
         "subject_name": "Базы, данных", "group_name": "ПО-21"},
    ]


def test_ics_structure():
    ics = build_ics(_sample())
    assert ics.startswith("BEGIN:VCALENDAR")
    assert "END:VCALENDAR" in ics
    assert ics.count("BEGIN:VEVENT") == 2
    assert ics.count("END:VEVENT") == 2
    assert "VERSION:2.0" in ics


def test_ics_dtstart_and_duration():
    ics = build_ics(_sample())
    # Начало первого занятия — 09:00, конец через 90 минут — 10:30.
    assert "DTSTART:20260901T090000" in ics
    assert "DTEND:20260901T103000" in ics


def test_ics_escaping_comma():
    ics = build_ics(_sample())
    # Запятая в названии предмета должна быть экранирована.
    assert "SUMMARY:Базы\\, данных" in ics


def test_ics_empty_list():
    ics = build_ics([])
    assert "BEGIN:VCALENDAR" in ics
    assert "BEGIN:VEVENT" not in ics