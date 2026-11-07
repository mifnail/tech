"""Тесты прикладного слоя (services.py).

Проверяем чистые правила, которые раньше были размазаны по api.py:
нормализацию оценок, расчёт изменений и то, что логика живёт в
services.py, а api.py только вызывает её.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

import api as api_module
import database
import services


# ── Нормализация оценок ────────────────────────────────────────────────────

@pytest.mark.parametrize('raw, expected', [
    (None, ''),
    ('', ''),
    ('absent', ''),
    ('0', '0'),
    ('2', '2'),
    ('5', '5'),
    (5, '5'),
])
def test_norm_grade(raw, expected):
    """'' и 'absent' — одно и то же состояние: студента не было."""
    assert services.norm_grade(raw) == expected


# ── Расчёт изменений ──────────────────────────────────────────────────────

def test_changed_grades_detects_new_grade():
    changed, state_changed = services.changed_grades(
        [{'student_id': 1, 'grade': '5'}], {1: ''})
    assert changed == [(1, '5')]
    assert state_changed is True


def test_changed_grades_ignores_same_grade():
    changed, state_changed = services.changed_grades(
        [{'student_id': 1, 'grade': '5'}], {1: '5'})
    assert changed == []
    assert state_changed is False


def test_changed_grades_absence_is_not_a_grade():
    """Отсутствие вместо оценки: состояние изменилось, но оценки нет."""
    changed, state_changed = services.changed_grades(
        [{'student_id': 1, 'grade': 'absent'}], {1: '5'})
    assert changed == []
    assert state_changed is True


def test_changed_grades_absent_and_empty_are_same_state():
    """«Отметил присутствие → отменил» не должно считаться изменением.

    '' и 'absent' нормализуются в одно состояние, поэтому переход между
    ними молчит: повторное «Провести» не рассылает уведомления заново.
    """
    changed, state_changed = services.changed_grades(
        [{'student_id': 1, 'grade': 'absent'}], {1: ''})
    assert changed == []
    assert state_changed is False

    changed, state_changed = services.changed_grades(
        [{'student_id': 1, 'grade': ''}], {1: 'absent'})
    assert changed == []
    assert state_changed is False


def test_changed_grades_skips_zero_for_students():
    """'0' — был без оценки; студенту про такое писать нечего."""
    changed, state_changed = services.changed_grades(
        [{'student_id': 1, 'grade': '0'}], {1: ''})
    assert changed == []
    assert state_changed is True


# ── Правила проведения ────────────────────────────────────────────────────

def _make_lesson(tmp_path, total_hours=2):
    db = database.Database(str(tmp_path / 'journal.db'))
    group_id = db.add_group('Группа-1')
    subject_id = db.add_subject('Предмет', total_hours, group_id)
    student_id = db.add_student(group_id, 'Иванов', 'Иван', 'И')
    lesson_id = db.add_lesson(subject_id, date='2026-11-07', status='scheduled')
    return db, group_id, subject_id, student_id, lesson_id


def test_mark_lesson_held_sets_status(tmp_path):
    db, _, _, _, lesson_id = _make_lesson(tmp_path)
    try:
        assert services.mark_lesson_held(db, lesson_id) is True
        assert db.get_lesson(lesson_id)['status'] == 'held'
    finally:
        db.close()


def test_mark_lesson_held_skips_cancelled(tmp_path):
    db, _, _, _, lesson_id = _make_lesson(tmp_path)
    try:
        db.set_lesson_status(lesson_id, 'cancelled')
        assert services.mark_lesson_held(db, lesson_id) is False
        assert db.get_lesson(lesson_id)['status'] == 'cancelled'
    finally:
        db.close()


def test_hours_exhausted_notice(tmp_path):
    db, _, subject_id, _, lesson_id = _make_lesson(tmp_path, total_hours=1)
    try:
        assert services.hours_exhausted_notice(db, lesson_id) == {}
        services.mark_lesson_held(db, lesson_id)
        notice = services.hours_exhausted_notice(db, lesson_id)
        assert notice['hours_exhausted'] is True
        assert notice['total_hours'] == 1
        assert 'Пары по предмету' in notice['hours_message']
    finally:
        db.close()


def test_is_bot_active(tmp_path):
    db, _, _, _, _ = _make_lesson(tmp_path)
    try:
        assert services.is_bot_active(db) is False
        db.set_setting('max_bot_token', '123')
        assert services.is_bot_active(db) is False
        db.set_setting('max_bot_enabled', '1')
        assert services.is_bot_active(db) is True
    finally:
        db.close()


def test_lesson_marks_splits_present_and_absent(tmp_path):
    db, group_id, subject_id, student_id, lesson_id = _make_lesson(tmp_path)
    try:
        db.mark_attendance_bulk(lesson_id, [{'student_id': student_id, 'grade': '4'}])
        present, absent = services.lesson_marks(db, lesson_id)
        assert len(present) == 1
        assert absent == []
    finally:
        db.close()


# ── Архитектурные стражи ──────────────────────────────────────────────────

MOVE_TO_SERVICES = [
    '_lesson_notify_context',
    '_is_bot_active',
    '_notify_group_chats',
    '_mark_lesson_held',
    '_hours_exhausted_notice',
    '_student_fio',
    '_lesson_header',
    '_lesson_marks',
    '_curator_conduct_text',
    '_student_conduct_messages',
    '_read_settled_grade',
    '_fire_grade_push',
    '_fire_curator_push',
]


def test_api_does_not_duplicate_service_logic():
    """Реализация живёт в services.py — в api.py её второй раз нет."""
    tree = ast.parse(Path(api_module.__file__).read_text(encoding='utf-8'))
    defined = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    overlap = defined & set(MOVE_TO_SERVICES)
    assert overlap == set(), f'логика продублирована в api.py: {sorted(overlap)}'


def test_api_aliases_point_to_services():
    """Алиасы api.py — те же объекты, что и в services.py."""
    assert api_module._curator_conduct_text is services.curator_conduct_text
    assert api_module._lesson_header is services.lesson_header
    assert api_module._student_conduct_messages is services.student_conduct_messages
    assert api_module._fire_grade_push is services.fire_grade_push
    assert api_module._fire_curator_push is services.fire_curator_push
    assert api_module._mark_lesson_held is services.mark_lesson_held


def test_services_does_not_import_api():
    """Слой не зависит от HTTP: services.py не знает про api."""
    source = Path(services.__file__).read_text(encoding='utf-8')
    assert 'import api' not in source
    assert 'from api' not in source


def test_row_helpers_live_with_database():
    """row_get/dict_row работают со строками SQLite — им место в database.py."""
    assert database.row_get({'a': 1}, 'a') == 1
    assert database.row_get(None, 'a', default='x') == 'x'
    assert database.dict_row({'a': 1}) == {'a': 1}
    assert api_module.row_get is database.row_get
