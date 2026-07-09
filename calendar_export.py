"""
calendar_export.py — выгрузка занятий из БД в формат iCalendar (.ics).

Файл .ics — это универсальный формат, который импортируют и Google Календарь, и
Яндекс Календарь (и Outlook/Apple). Мы формируем по одному событию (VEVENT) на
занятие. Данные берём из database.Database.list_lessons_for_calendar()
(все занятия, КРОМЕ отменённых).

Здесь НЕТ доступа к БД и НЕТ Kivy — только чистое преобразование списка занятий в
текст .ics, поэтому модуль легко тестируется headless и переносится при миграции.

Формат held_at в БД: ISO-строка 'YYYY-MM-DDTHH:MM:SS' (время локальное).
Длительность одного занятия по умолчанию — LESSON_DURATION_MIN минут.
Одна «пара» = 1 час 45 минут (105 мин), пары считаются начиная с 09:00
(см. schedule_file.py).
"""
from datetime import datetime, timedelta

# Длительность одного занятия («пары») для события календаря — 1 ч 45 мин.
LESSON_DURATION_MIN = 105


def _parse_dt(value: str) -> datetime:
    """
    Разбирает ISO-строку из БД в datetime.
    Поддерживает как 'YYYY-MM-DDTHH:MM:SS', так и 'YYYY-MM-DD' (тогда время 00:00).
    """
    value = (value or "").strip()
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        # На случай нестандартной строки — берём только дату.
        return datetime.fromisoformat(value[:10])


def _fmt_ics_dt(dt: datetime) -> str:
    """Формат даты-времени для .ics в «плавающем» локальном времени: YYYYMMDDTHHMMSS."""
    return dt.strftime("%Y%m%dT%H%M%S")


def _escape(text: str) -> str:
    """Экранирование спецсимволов в текстовых полях .ics (запятая, ; и перевод строки)."""
    return (
        (text or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def build_ics(lessons: list[dict]) -> str:
    """
    Строит текст .ics (VCALENDAR со списком VEVENT) из списка занятий.

    Каждый элемент lessons — словарь с ключами:
        id, held_at, subject_name, group_name (status игнорируется — отменённые
        должны быть отфильтрованы на уровне БД).

    Возвращает строку с CRLF-переводами строк (как требует спецификация iCalendar).
    """
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//LessonTracker//RU",
        "CALSCALE:GREGORIAN",
    ]
    stamp = _fmt_ics_dt(datetime.now())
    for les in lessons:
        start = _parse_dt(les.get("held_at", ""))
        end = start + timedelta(minutes=LESSON_DURATION_MIN)
        uid = f"lesson-{les.get('id', '')}@lessontracker"
        summary = _escape(les.get("subject_name", "Занятие"))
        group = _escape(les.get("group_name", ""))
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{_fmt_ics_dt(start)}",
            f"DTEND:{_fmt_ics_dt(end)}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:Группа {group}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    # Спецификация iCalendar требует CRLF между строками.
    return "\r\n".join(lines) + "\r\n"


def export_ics(lessons: list[dict], path: str) -> str:
    """
    Формирует .ics из списка занятий и записывает его в файл `path`.
    Возвращает путь к записанному файлу.
    """
    content = build_ics(lessons)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path