"""Проведённым занятие делает ведомость, а не прошедшая дата.

Баг №1: фронт создаёт пару со статусом 'scheduled' («её ещё можно отменить»),
а ввод оценок через /attendance статус не поднимал — только явный
«Провести» (/conduct). В итоге занятия с заполненной ведомостью висели
в журнале как запланированные.

Баг №2 (обратная сторона): нормализация закрывала ВСЁ прошедшее, включая
пары без единой отметки. Преподаватель открывал пропущенную пару, ничего
не заполнял, выходил — и в списке появлялась зелёная галочка «проведено».
Теперь прошедшая дата сама по себе ничего не значит.
"""
import time

import pytest

import api as _api_module
from database import Database


def _today() -> str:
    return time.strftime('%Y-%m-%d')


def _shift(days: int) -> str:
    return time.strftime('%Y-%m-%d', time.localtime(time.time() + days * 86400))


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


class TestPastLessonsBecomeHeld:
    def test_past_without_attendance_stays_scheduled(self, tmp_path):
        """Открыл пропущенную пару, ничего не отметил, вышел — не «проведено».

        Раньше здесь срабатывало `date < today` и занятие получало held
        без единой отметки — в списке появлялась зелёная галочка.
        """
        path = str(tmp_path / 'journal.db')
        with Database(path) as first:
            gid = first.add_group('АДТ-31')
            sid = first.add_subject('МДК', 30, gid)
            past = first.add_lesson(sid, _shift(-3), status='scheduled')

        with Database(path) as again:
            assert again.get_lesson(past)['status'] == 'scheduled'

    def test_past_with_attendance_becomes_held(self, tmp_path):
        """Ведомость заполнена — пара состоялась, даже без нажатия «Провести»."""
        path = str(tmp_path / 'journal.db')
        with Database(path) as first:
            gid = first.add_group('АДТ-31')
            sid = first.add_subject('МДК', 30, gid)
            student = first.add_student(gid, 'Иванов', 'Иван')
            past = first.add_lesson(sid, _shift(-3), status='scheduled')
            first.mark_attendance(past, student, '4')

        with Database(path) as again:
            assert again.get_lesson(past)['status'] == 'held'

    def test_today_and_future_stay_scheduled(self, tmp_path):
        path = str(tmp_path / 'journal.db')
        with Database(path) as first:
            gid = first.add_group('АДТ-31')
            sid = first.add_subject('МДК', 30, gid)
            today = first.add_lesson(sid, _today(), status='scheduled')
            future = first.add_lesson(sid, _shift(3), status='scheduled')

        with Database(path) as again:
            assert again.get_lesson(today)['status'] == 'scheduled'
            assert again.get_lesson(future)['status'] == 'scheduled'

    def test_today_with_attendance_becomes_held(self, tmp_path):
        """Сегодняшняя пара с заполненной ведомостью — уже проведена."""
        path = str(tmp_path / 'journal.db')
        with Database(path) as first:
            gid = first.add_group('АДТ-31')
            sid = first.add_subject('МДК', 30, gid)
            student = first.add_student(gid, 'Иванов', 'Иван')
            today = first.add_lesson(sid, _today(), status='scheduled')
            first.mark_attendance(today, student, '4')

        with Database(path) as again:
            assert again.get_lesson(today)['status'] == 'held'

    def test_cancelled_and_held_untouched(self, tmp_path):
        path = str(tmp_path / 'journal.db')
        with Database(path) as first:
            gid = first.add_group('АДТ-31')
            sid = first.add_subject('МДК', 30, gid)
            cancelled = first.add_lesson(sid, _shift(-5), status='cancelled')
            held = first.add_lesson(sid, _shift(-4), status='held')

        with Database(path) as again:
            assert again.get_lesson(cancelled)['status'] == 'cancelled'
            assert again.get_lesson(held)['status'] == 'held'

    def test_idempotent(self, tmp_path):
        """Повторные открытия не меняют статус ни туда, ни обратно."""
        path = str(tmp_path / 'journal.db')
        with Database(path) as first:
            gid = first.add_group('АДТ-31')
            sid = first.add_subject('МДК', 30, gid)
            student = first.add_student(gid, 'Иванов', 'Иван')
            filled = first.add_lesson(sid, _shift(-2), status='scheduled')
            first.mark_attendance(filled, student, '5')
            empty = first.add_lesson(sid, _shift(-1), status='scheduled')

        with Database(path):
            pass
        with Database(path) as again:
            assert again.get_lesson(filled)['status'] == 'held'
            assert again.get_lesson(empty)['status'] == 'scheduled'


class TestAttendanceMarksHeld:
    def _setup(self, client, lesson_date):
        gid = client.post('/api/groups', json={'name': 'АДТ-31'}).json['id']
        sid = client.post('/api/subjects', json={
            'name': 'МДК', 'total_hours': 32, 'group_id': gid}).json['id']
        db = _api_module.get_db()
        student = db.add_student(gid, 'Иванов', 'Иван')
        lid = db.add_lesson(sid, lesson_date, status='scheduled')
        return lid, student

    def test_attendance_sets_held(self, client):
        lid, student = self._setup(client, _shift(-1))
        rv = client.post(f'/api/lessons/{lid}/attendance',
                         json=[{'student_id': student, 'grade': '4'}])
        assert rv.status_code == 200
        assert _api_module.get_db().get_lesson(lid)['status'] == 'held'

    def test_attendance_keeps_cancelled(self, client):
        """Отменённое занятие оценки не принимает — статус остаётся cancelled."""
        lid, student = self._setup(client, _shift(-1))
        _api_module.get_db().set_lesson_status(lid, 'cancelled')
        rv = client.post(f'/api/lessons/{lid}/attendance',
                         json=[{'student_id': student, 'grade': '4'}])
        assert rv.status_code == 400
        assert _api_module.get_db().get_lesson(lid)['status'] == 'cancelled'

    def test_attendance_on_future_does_not_set_held(self, client):
        lid, student = self._setup(client, _shift(2))
        rv = client.post(f'/api/lessons/{lid}/attendance',
                         json=[{'student_id': student, 'grade': '4'}])
        assert rv.status_code == 200
        assert _api_module.get_db().get_lesson(lid)['status'] == 'scheduled'
