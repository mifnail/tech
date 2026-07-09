"""Тесты выгрузки ведомости в Excel/PDF (headless, без Kivy/sqlite)."""
from report_export import build_xlsx, build_pdf, _overall_avg

SUBJECT = {"name": "Математика", "group_name": "ИС-11",
           "planned": 32, "held": 12, "remaining": 20}
GRADEBOOK = [
    {"name": "Алексеев А.", "avg_grade": 4.5, "grades_count": 2,
     "present_count": 5, "absent_count": 1},
    {"name": "Борисов Б.", "avg_grade": None, "grades_count": 0,
     "present_count": 3, "absent_count": 3},
    {"name": "Власов В.", "avg_grade": 3.0, "grades_count": 1,
     "present_count": 2, "absent_count": 0},
]


def test_overall_avg_ignores_none():
    # (4.5 + 3.0) / 2 = 3.75; студент без оценок не учитывается.
    assert _overall_avg(GRADEBOOK) == 3.75


def test_overall_avg_empty():
    assert _overall_avg([{"name": "X", "avg_grade": None}]) is None


def test_build_xlsx_is_valid_zip():
    data = build_xlsx(SUBJECT, GRADEBOOK)
    # .xlsx — это zip-контейнер (сигнатура 'PK').
    assert data[:2] == b"PK"
    assert len(data) > 500


def test_build_pdf_is_valid_pdf():
    data = build_pdf(SUBJECT, GRADEBOOK)
    assert data[:4] == b"%PDF"
    assert len(data) > 500