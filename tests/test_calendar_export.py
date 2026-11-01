"""Экспорт в календарь (.ics).

Времени пар в базе нет — берём сетку PAIR_TIMES по номеру пары.
Чётность недель: week_type 1 — нечётная ISO-неделя, 2 — чётная.
"""
from datetime import date, datetime

import pytest

import api as _api_module
import calendar_export
from database import Database


@pytest.fixture
def db():
    with Database(':memory:') as database:
        yield database


@pytest.fixture
def client():
    _api_module.app.config['TESTING'] = True
    original = _api_module.get_db
    _db = Database(':memory:')
    _api_module.get_db = lambda: _db
    with _api_module.app.test_client() as c:
        yield c
    _db.close()
    _api_module.get_db = original


def _setup(db, subject='МДК 01.01'):
    gid = db.add_group('АДТ-31')
    sid = db.add_subject(subject, 30, gid)
    return gid, sid


def _dtstart(ics: str) -> str:
    for line in ics.splitlines():
        if line.startswith('DTSTART:'):
            return line.split(':', 1)[1]
    raise AssertionError('DTSTART не найден')


def _is_odd_iso_week(stamp: str) -> bool:
    d = datetime.strptime(stamp[:8], '%Y%m%d').date()
    return d.isocalendar()[1] % 2 == 1


class TestLessonsIcs:
    def test_only_held_lessons(self, db):
        _, sid = _setup(db)
        db.add_lesson(sid, '2026-09-14', status='held', lesson_number=1)
        db.add_lesson(sid, '2026-09-15', status='scheduled', lesson_number=1)
        db.add_lesson(sid, '2026-09-16', status='cancelled', lesson_number=1)

        ics = calendar_export.export_lessons_to_ics(db)

        assert ics.count('BEGIN:VEVENT') == 1
        assert ics.startswith('BEGIN:VCALENDAR')
        assert ics.rstrip().endswith('END:VCALENDAR')

    def test_event_uses_pair_time_grid(self, db):
        _, sid = _setup(db)
        db.add_lesson(sid, '2026-09-14', status='held', lesson_number=1)

        ics = calendar_export.export_lessons_to_ics(db)

        assert 'DTSTART:20260914T083000' in ics
        assert 'DTEND:20260914T100000' in ics

    def test_unknown_pair_falls_back(self, db):
        _, sid = _setup(db)
        db.add_lesson(sid, '2026-09-14', status='held', lesson_number=None)

        ics = calendar_export.export_lessons_to_ics(db)

        assert 'DTSTART:20260914T090000' in ics

    def test_has_dtstamp_and_calname(self, db):
        _, sid = _setup(db)
        db.add_lesson(sid, '2026-09-14', status='held', lesson_number=2)

        ics = calendar_export.export_lessons_to_ics(db)

        assert 'DTSTAMP:' in ics
        assert 'X-WR-CALNAME:' in ics
        assert 'UID:lesson-' in ics

    def test_escapes_commas_and_semicolons(self, db):
        _, sid = _setup(db, subject='МДК 01.01, часть 2; спец')

        ics = calendar_export.generate_ics([{
            'id': 1, 'date': '2026-09-14', 'lesson_number': 1,
            'actual_subject_name': 'МДК 01.01, часть 2; спец',
            'group_name': 'АДТ-31',
        }])

        summary = [l for l in ics.splitlines() if l.startswith('SUMMARY:')][0]
        assert '\\,' in summary
        assert '\\;' in summary


class TestScheduleIcs:
    def test_every_week(self, db):
        gid, sid = _setup(db)
        db.add_schedule_entry(1, 1, sid, 0)  # пн, 1 пара, каждую неделю

        ics = calendar_export.generate_schedule_ics(db)

        assert 'RRULE:FREQ=WEEKLY;BYDAY=MO' in ics
        assert 'DTSTART:' in ics

    def test_odd_week_anchor_is_odd(self, db):
        gid, sid = _setup(db)
        db.add_schedule_entry(3, 2, sid, 1)  # ср, нечётная

        ics = calendar_export.generate_schedule_ics(db)

        assert 'RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=WE' in ics
        assert _is_odd_iso_week(_dtstart(ics)) is True

    def test_even_week_anchor_is_even(self, db):
        gid, sid = _setup(db)
        db.add_schedule_entry(3, 2, sid, 2)  # ср, чётная

        ics = calendar_export.generate_schedule_ics(db)

        assert 'RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=WE' in ics
        assert _is_odd_iso_week(_dtstart(ics)) is False

    def test_pair_number_sets_time(self, db):
        gid, sid = _setup(db)
        db.add_schedule_entry(1, 3, sid, 0)

        ics = calendar_export.generate_schedule_ics(db)

        assert 'DTSTART:' in ics and 'T121000' in ics
        assert 'T134000' in ics

    def test_anchor_not_in_past(self, db):
        gid, sid = _setup(db)
        db.add_schedule_entry(1, 1, sid, 1)

        stamp = _dtstart(calendar_export.generate_schedule_ics(db))
        start = datetime.strptime(stamp[:8], '%Y%m%d').date()

        assert start >= date.today()


class TestEndpoints:
    def test_schedule_ics_download(self, client):
        db = _api_module.get_db()
        gid, sid = _setup(db)
        db.add_schedule_entry(1, 1, sid, 0)

        rv = client.get('/api/export/schedule.ics')

        assert rv.status_code == 200
        assert 'text/calendar' in rv.headers['Content-Type']
        assert b'BEGIN:VCALENDAR' in rv.data

    def test_lessons_ics_download(self, client):
        db = _api_module.get_db()
        gid, sid = _setup(db)
        db.add_lesson(sid, '2026-09-14', status='held', lesson_number=1)

        rv = client.get('/api/export/lessons.ics')

        assert rv.status_code == 200
        assert b'BEGIN:VEVENT' in rv.data
