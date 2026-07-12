"""Export reports to Excel and PDF."""
from database import Database
from datetime import date as dt_date

def export_excel(subject_id, filepath, db_path=None):
    from openpyxl import Workbook
    db = Database(db_path)
    grades = db.subject_gradebook(subject_id)
    summary = db.subject_summary(subject_id)
    students = db.list_students(summary['group_id'] if summary else None)
    db.close()

    wb = Workbook()
    ws = wb.active
    ws.title = 'Ведомость'

    if summary:
        ws['A1'] = f'Предмет: {summary["name"]}'
        ws['A2'] = f'Группа: {summary["group_name"]}'
        ws['A3'] = f'Проведено: {summary["held_lessons"]} / {summary["total_hours"]}'

    ws['A5'] = 'Студент'
    ws['B5'] = 'Оценка'
    ws['C5'] = 'Дата'

    row = 6
    for g in grades:
        ws[f'A{row}'] = f'{g["last_name"]} {g["first_name"]}'
        ws[f'B{row}'] = g['grade']
        ws[f'C{row}'] = g['date']
        row += 1

    wb.save(filepath)
    return filepath


def export_pdf(subject_id, filepath, db_path=None):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os

    font_path = 'C:\\Windows\\Fonts\\arial.ttf'
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont('Arial', font_path))
        font_name = 'Arial'
    else:
        font_name = 'Helvetica'

    db = Database(db_path)
    grades = db.subject_gradebook(subject_id)
    summary = db.subject_summary(subject_id)
    db.close()

    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4

    c.setFont(font_name, 16)
    c.drawString(50, height - 40, f'Ведомость: {summary["name"] if summary else ""}')
    c.setFont(font_name, 12)
    c.drawString(50, height - 60, f'Группа: {summary["group_name"] if summary else ""}')

    y = height - 90
    c.setFont(font_name, 10)
    for g in grades:
        c.drawString(50, y, f'{g["last_name"]} {g["first_name"]}')
        c.drawString(250, y, str(g['grade']))
        c.drawString(300, y, str(g['date'] or ''))
        y -= 15
        if y < 40:
            c.showPage()
            y = height - 40

    c.save()
    return filepath
