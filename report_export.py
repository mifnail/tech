"""
report_export.py — выгрузка ВЕДОМОСТИ УСПЕВАЕМОСТИ в Excel (.xlsx) и PDF.

Модуль НЕ обращается к БД и НЕ использует Kivy — на вход подаётся уже готовая
ведомость (список словарей из database.Database.subject_gradebook) плюс мета-данные
предмета. Благодаря этому логика легко тестируется headless и переносится при
миграции.

Зависимости:
    * openpyxl — чисто-Python, кириллица без проблем (основной, надёжный формат).
    * reportlab — для PDF. У встроенных шрифтов reportlab (Helvetica) НЕТ кириллицы,
      поэтому мы пытаемся зарегистрировать системный TTF (DejaVuSans/Arial). Если не
      нашли — PDF всё равно сформируется, но кириллица может отображаться неверно;
      в этом случае используйте Excel. См. docs/REPORTS.md.

Обе функции принимают:
    subject:   dict с ключами name, group_name, planned, held, remaining
    gradebook: list[dict] с ключами name, avg_grade, grades_count,
               present_count, absent_count
и ВОЗВРАЩАЮТ bytes готового файла (запись на диск — обязанность вызывающего кода,
чтобы модуль оставался чистым и тестируемым).
"""
from __future__ import annotations

import io
from typing import Optional


# ------------------------------------------------------------------- заголовки
COLUMNS = [
    ("ФИО", "name"),
    ("Средний балл", "avg_grade"),
    ("Кол-во оценок", "grades_count"),
    ("Присутствовал", "present_count"),
    ("Отсутствовал", "absent_count"),
]


def _avg_text(value: Optional[float]) -> str:
    return f"{value:.2f}" if value is not None else "—"


def _overall_avg(gradebook: list[dict]) -> Optional[float]:
    vals = [d["avg_grade"] for d in gradebook if d.get("avg_grade") is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


# ------------------------------------------------------------------- Excel
def build_xlsx(subject: dict, gradebook: list[dict]) -> bytes:
    """Формирует .xlsx с ведомостью и возвращает его как bytes."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "Ведомость"

    bold = Font(bold=True)
    center = Alignment(horizontal="center", vertical="center")
    head_fill = PatternFill("solid", fgColor="DDDDDD")

    # Шапка с мета-данными предмета.
    ws["A1"] = f"Ведомость успеваемости — {subject.get('name', '')}"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = (
        f"Группа: {subject.get('group_name', '')}    "
        f"Занятия — план: {subject.get('planned', 0)}, "
        f"проведено: {subject.get('held', 0)}, "
        f"осталось: {subject.get('remaining', 0)}"
    )
    overall = _overall_avg(gradebook)
    ws["A3"] = f"Средний балл по предмету: {_avg_text(overall)}"

    header_row = 5
    for col_idx, (title, _key) in enumerate(COLUMNS, start=1):
        c = ws.cell(row=header_row, column=col_idx, value=title)
        c.font = bold
        c.alignment = center
        c.fill = head_fill

    for i, d in enumerate(gradebook):
        r = header_row + 1 + i
        ws.cell(row=r, column=1, value=d.get("name", ""))
        ws.cell(row=r, column=2, value=(d["avg_grade"] if d.get("avg_grade") is not None else "—"))
        ws.cell(row=r, column=3, value=d.get("grades_count", 0))
        ws.cell(row=r, column=4, value=d.get("present_count", 0))
        ws.cell(row=r, column=5, value=d.get("absent_count", 0))

    # Ширины колонок для читабельности.
    widths = [28, 14, 14, 14, 14]
    for idx, w in enumerate(widths, start=1):
        ws.column_dimensions[chr(64 + idx)].width = w

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ------------------------------------------------------------------- PDF
def _register_cyrillic_font() -> str:
    """
    Пытается зарегистрировать TTF-шрифт с кириллицей и вернуть его имя.
    Если ни один системный шрифт не найден — возвращает 'Helvetica'
    (кириллица может отображаться неверно — тогда лучше Excel).
    """
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os

    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",       # Linux (CI)
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",                          # Windows
        "C:\\Windows\\Fonts\\segoeui.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",           # macOS
    ]
    for path in candidates:
        try:
            if os.path.exists(path):
                pdfmetrics.registerFont(TTFont("AppCyr", path))
                return "AppCyr"
        except Exception:
            continue
    return "Helvetica"


def build_pdf(subject: dict, gradebook: list[dict]) -> bytes:
    """Формирует PDF с ведомостью и возвращает его как bytes."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    font_name = _register_cyrillic_font()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("t", parent=styles["Title"], fontName=font_name)
    normal = ParagraphStyle("n", parent=styles["Normal"], fontName=font_name)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=15 * mm, bottomMargin=15 * mm)
    flow = []
    flow.append(Paragraph(f"Ведомость успеваемости — {subject.get('name', '')}", title_style))
    flow.append(Paragraph(
        f"Группа: {subject.get('group_name', '')} &nbsp;&nbsp; "
        f"Занятия — план: {subject.get('planned', 0)}, "
        f"проведено: {subject.get('held', 0)}, осталось: {subject.get('remaining', 0)}",
        normal))
    overall = _overall_avg(gradebook)
    flow.append(Paragraph(f"Средний балл по предмету: {_avg_text(overall)}", normal))
    flow.append(Spacer(1, 8 * mm))

    data = [[c[0] for c in COLUMNS]]
    for d in gradebook:
        data.append([
            d.get("name", ""),
            _avg_text(d.get("avg_grade")),
            str(d.get("grades_count", 0)),
            str(d.get("present_count", 0)),
            str(d.get("absent_count", 0)),
        ])
    table = Table(data, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDDDDD")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    flow.append(table)
    doc.build(flow)
    return buf.getvalue()