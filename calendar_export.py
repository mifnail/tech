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
"""
from datetime import datetime, timedelta, timezone

# Длительность одного занятия для события календаря (в минутах).
LESSON_DURATION_MIN = 90

# Часовой пояс по умолчанию (Европа/Москва, UTC+3). Меняется под регион пользователя.
DEFAULT_TZ = timezone(timedelta(hours=3))


def _parse_dt(value: str) -> datetime:
    """
    Разбирает ISO-строку из БД в datetime с часовым поясом DEFAULT_TZ.
    Поддерживает как 'YYYY-MM-DDTHH:MM:SS', так и 'YYYY-MM-DD' (тогда время 00:00).
    """
    value = (value or "").strip()
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        dt = datetime.fromisoformat(value[:10])
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=DEFAULT_TZ)
    return dt


def _fmt_ics_dt(dt: datetime) -> str:
    """Формат даты-времени для .ics в UTC (суффикс Z)."""
    utc = dt.astimezone(timezone.utc)
    return utc.strftime("%Y%m%dT%H%M%SZ")


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
    tz_offset = int(DEFAULT_TZ.utcoffset(None).total_seconds() / 60)
    tz_hours = tz_offset // 60
    tz_mins = abs(tz_offset) % 60
    tz_id = f"UTC{tz_hours:+03d}:{tz_mins:02d}" if tz_mins else f"UTC{tz_hours:+03d}"
    offset_str = f"{tz_hours:+03d}{tz_mins:02d}"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//LessonTracker//RU",
        "CALSCALE:GREGORIAN",
        f"X-WR-TIMEZONE:{tz_id}",
        "BEGIN:VTIMEZONE",
        f"TZID:{tz_id}",
        "BEGIN:STANDARD",
        f"TZOFFSETFROM:{offset_str}",
        f"TZOFFSETTO:{offset_str}",
        "END:STANDARD",
        "END:VTIMEZONE",
    ]
    stamp = _fmt_ics_dt(datetime.now(tz=DEFAULT_TZ))
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