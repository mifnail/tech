"""
schedule_file.py — чтение файла-расписания преподавателя и генерация занятий.

Файл расписания заполняет САМ преподаватель (обычный текстовый файл, разделитель ';').
Здесь НЕТ доступа к БД и НЕТ Kivy — только чистый разбор текста и вычисление дат
занятий, поэтому модуль тестируется headless и переносится при миграции.

ФОРМАТ ФАЙЛА (см. docs/SCHEDULE.md):

    # строки-комментарии начинаются с '#'
    # Мета-строка: дата начала семестра и чётность ПЕРВОЙ недели (Ч или Н)
    СЕМЕСТР=2026-09-01; ПЕРВАЯ_НЕДЕЛЯ=Н

    # День; Пара(1..4); Предмет; Группа; Признак Ч/Н
    Понедельник; 1; Математика; ИС-11; ЧН
    Понедельник; 3; Программирование; ПО-21; Ч
    Среда;       2; Базы данных;   ИС-11; Н

СМЫСЛ Ч/Н:
    * 'ЧН' — предмет идёт КАЖДУЮ неделю в этот день/пару;
    * 'Ч'  — только по ЧЁТНЫМ неделям (через неделю);
    * 'Н'  — только по НЕЧЁТНЫМ неделям (через неделю).
    Чётность недели отсчитывается от даты СЕМЕСТР и признака ПЕРВАЯ_НЕДЕЛЯ.

ВРЕМЯ ПАР (только для экспорта в календарь; в расписании времени нет — только пара):
    пара длится PAIR_DURATION_MIN минут, пара 1 начинается в FIRST_PAIR_START,
    пары идут подряд: N-я начинается в FIRST_PAIR_START + (N-1)*PAIR_DURATION_MIN.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Optional

# --- Тайминги пар (для вычисления времени события календаря) ----------------
PAIR_DURATION_MIN = 105          # 1 час 45 минут
FIRST_PAIR_START = time(9, 0)    # первая пара — 09:00
MAX_PAIR = 8                     # разумный предел номера пары

# --- Дни недели (понимаем полные названия и сокращения) ---------------------
_WEEKDAYS = {
    "понедельник": 0, "пн": 0,
    "вторник": 1, "вт": 1,
    "среда": 2, "ср": 2,
    "четверг": 3, "чт": 3,
    "пятница": 4, "пт": 4,
    "суббота": 5, "сб": 5,
    "воскресенье": 6, "вс": 6,
}

_PARITIES = {"Ч", "Н", "ЧН"}


class ScheduleError(Exception):
    """Ошибка разбора файла расписания (с человекочитаемым сообщением)."""


def pair_start_time(pair: int) -> time:
    """Время начала пары N (1-based). Пары идут подряд от FIRST_PAIR_START."""
    base = datetime.combine(date(2000, 1, 1), FIRST_PAIR_START)
    start = base + timedelta(minutes=(pair - 1) * PAIR_DURATION_MIN)
    return start.time()


def _normalize_parity(raw: str) -> str:
    """Приводит признак Ч/Н к канону 'Ч'|'Н'|'ЧН'. 'НЧ' == 'ЧН'."""
    p = (raw or "").strip().upper().replace(" ", "")
    if p == "НЧ":
        p = "ЧН"
    if p not in _PARITIES:
        raise ScheduleError(f"Недопустимый признак Ч/Н: '{raw}' (ожидается Ч, Н или ЧН)")
    return p


def parse_schedule(text: str) -> dict:
    """
    Разбирает текст файла расписания. Возвращает
        {
          "semester_start": date,
          "first_week_parity": 'Ч'|'Н',
          "entries": [ {day_idx, day_name, pair, subject, group, parity}, ... ],
        }
    Бросает ScheduleError с понятным сообщением при ошибке.
    """
    semester_start: Optional[date] = None
    first_week_parity: Optional[str] = None
    entries: list[dict] = []

    for lineno, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        # Мета-строка (содержит СЕМЕСТР=...)
        if "СЕМЕСТР" in line.upper():
            for part in line.split(";"):
                if "=" not in part:
                    continue
                key, _, value = part.partition("=")
                key = key.strip().upper()
                value = value.strip()
                if key == "СЕМЕСТР":
                    try:
                        semester_start = datetime.strptime(value, "%Y-%m-%d").date()
                    except ValueError:
                        raise ScheduleError(
                            f"Строка {lineno}: дата СЕМЕСТР должна быть в формате ГГГГ-ММ-ДД, "
                            f"получено '{value}'"
                        )
                elif key in ("ПЕРВАЯ_НЕДЕЛЯ", "ПЕРВАЯНЕДЕЛЯ"):
                    fp = value.strip().upper()
                    if fp not in ("Ч", "Н"):
                        raise ScheduleError(
                            f"Строка {lineno}: ПЕРВАЯ_НЕДЕЛЯ должна быть Ч или Н, получено '{value}'"
                        )
                    first_week_parity = fp
            continue

        # Строка занятия: День; Пара; Предмет; Группа; Ч/Н
        cols = [c.strip() for c in line.split(";")]
        if len(cols) < 5:
            raise ScheduleError(
                f"Строка {lineno}: ожидается 5 полей через ';' "
                f"(День; Пара; Предмет; Группа; Ч/Н), а получено {len(cols)}: '{line}'"
            )
        day_raw, pair_raw, subject, group, parity_raw = cols[:5]

        day_key = day_raw.strip().lower()
        if day_key not in _WEEKDAYS:
            raise ScheduleError(f"Строка {lineno}: неизвестный день недели '{day_raw}'")
        try:
            pair = int(pair_raw)
        except ValueError:
            raise ScheduleError(f"Строка {lineno}: номер пары должен быть числом, получено '{pair_raw}'")
        if not (1 <= pair <= MAX_PAIR):
            raise ScheduleError(f"Строка {lineno}: номер пары вне диапазона 1..{MAX_PAIR}: {pair}")
        if not subject:
            raise ScheduleError(f"Строка {lineno}: не указан предмет")
        if not group:
            raise ScheduleError(f"Строка {lineno}: не указана группа")

        entries.append({
            "day_idx": _WEEKDAYS[day_key],
            "day_name": day_raw.strip(),
            "pair": pair,
            "subject": subject,
            "group": group,
            "parity": _normalize_parity(parity_raw),
        })

    if semester_start is None:
        raise ScheduleError("Не найдена мета-строка с 'СЕМЕСТР=ГГГГ-ММ-ДД'")
    if first_week_parity is None:
        raise ScheduleError("Не указана 'ПЕРВАЯ_НЕДЕЛЯ=Ч' или '=Н'")
    if not entries:
        raise ScheduleError("В файле нет ни одной строки занятия")

    return {
        "semester_start": semester_start,
        "first_week_parity": first_week_parity,
        "entries": entries,
    }


def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def week_parity(target: date, semester_start: date, first_week_parity: str) -> str:
    """
    Возвращает чётность недели ('Ч'|'Н'), в которую попадает дата target.
    Неделя, содержащая semester_start, имеет чётность first_week_parity, дальше
    чередуется.
    """
    delta_weeks = (_monday_of(target) - _monday_of(semester_start)).days // 7
    other = "Н" if first_week_parity == "Ч" else "Ч"
    return first_week_parity if delta_weeks % 2 == 0 else other


def generate_occurrences(parsed: dict, subject_plans: dict, max_weeks: int = 200) -> list[dict]:
    """
    Генерирует занятия по расписанию.

    parsed          — результат parse_schedule().
    subject_plans   — dict {(subject, group): plan_in_lessons} (план из карточки предмета).
                      Для каждого предмета генерируется РОВНО plan+1 занятий.
    Возвращает список occurrences:
        {subject, group, pair, held_at (ISO 'YYYY-MM-DDTHH:MM:SS')}
    в хронологическом порядке.
    """
    semester_start = parsed["semester_start"]
    first_week_parity = parsed["first_week_parity"]
    entries = parsed["entries"]

    # Группируем слоты по (предмет, группа).
    slots_by_subject: dict[tuple, list[dict]] = {}
    for e in entries:
        slots_by_subject.setdefault((e["subject"], e["group"]), []).append(e)

    occurrences: list[dict] = []
    start_monday = _monday_of(semester_start)

    for key, slots in slots_by_subject.items():
        subject, group = key
        # Сколько занятий нужно сгенерировать: план из карточки + 1.
        target_count = subject_plans.get(key)
        if target_count is None:
            # Предмет из расписания не заведён в карточках — пропускаем (сообщит вызывающий).
            continue
        target_count = int(target_count) + 1

        produced = 0
        week = 0
        while produced < target_count and week < max_weeks:
            monday = start_monday + timedelta(weeks=week)
            parity = week_parity(monday, semester_start, first_week_parity)
            # Слоты этой недели: 'ЧН' всегда, иначе — по совпадению чётности.
            week_slots = [s for s in slots if s["parity"] == "ЧН" or s["parity"] == parity]
            # По порядку (день недели, номер пары).
            for s in sorted(week_slots, key=lambda x: (x["day_idx"], x["pair"])):
                occ_date = monday + timedelta(days=s["day_idx"])
                if occ_date < semester_start:
                    continue  # до начала семестра не генерируем
                held_at = datetime.combine(occ_date, pair_start_time(s["pair"]))
                occurrences.append({
                    "subject": subject,
                    "group": group,
                    "pair": s["pair"],
                    "held_at": held_at.strftime("%Y-%m-%dT%H:%M:%S"),
                })
                produced += 1
                if produced >= target_count:
                    break
            week += 1

    occurrences.sort(key=lambda o: o["held_at"])
    return occurrences