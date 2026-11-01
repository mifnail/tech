"""Утренний дайджест преподавателю: пары на сегодня + незаполненные.

Незаполненные пары — те, что в прошлом и не «проведено»/«отменено».
Раньше о них знал только экран «Сегодня»; в боте напоминания не было.
"""
import time

import pytest

import maxbot
from database import Database


def _shift(days: int) -> str:
    return time.strftime('%Y-%m-%d', time.localtime(time.time() + days * 86400))


@pytest.fixture
def db():
    with Database(':memory:') as database:
        yield database


def _setup(db):
    gid = db.add_group('АДТ-31')
    sid = db.add_subject('МДК 01.01', 30, gid)
    st = db.add_student(gid, 'Иванов', 'Иван')
    return gid, sid, st


class TestPendingBlock:
    def test_empty_when_nothing_pending(self, db):
        _, sid, _ = _setup(db)
        db.add_lesson(sid, _shift(-1), status='held')

        assert maxbot._pending_digest_block(db, _shift(0)) == ''

    def test_lists_pending_pair(self, db):
        _, sid, _ = _setup(db)
        db.add_lesson(sid, _shift(-2), status='scheduled', lesson_number=3)

        block = maxbot._pending_digest_block(db, _shift(0))

        assert block.startswith('Незаполненная пара:')
        assert 'пара 3' in block
        assert 'АДТ-31' in block
        assert 'МДК 01.01' in block

    def test_counts_and_truncates(self, db):
        _, sid, _ = _setup(db)
        for i in range(5):
            db.add_lesson(sid, _shift(-1 - i), status='scheduled', lesson_number=i + 1)

        block = maxbot._pending_digest_block(db, _shift(0))

        assert 'Незаполненные пары: 5' in block
        assert '…и ещё 2' in block
        assert block.count('• ') == 3

    def test_today_is_not_pending_yet(self, db):
        _, sid, _ = _setup(db)
        db.add_lesson(sid, _shift(0), status='scheduled')

        assert maxbot._pending_digest_block(db, _shift(0)) == ''

    def test_cancelled_not_listed(self, db):
        _, sid, _ = _setup(db)
        db.add_lesson(sid, _shift(-1), status='cancelled')

        assert maxbot._pending_digest_block(db, _shift(0)) == ''


class TestTeacherTargets:
    def test_no_lessons_today_still_reports_pending(self, db):
        _, sid, _ = _setup(db)
        db.add_lesson(sid, _shift(-3), status='scheduled', lesson_number=2)

        text = maxbot.teacher_targets(db, _shift(0))

        assert text.startswith('Сегодня занятий нет.')
        assert 'Незаполненная пара:' in text

    def test_held_today_with_pending(self, db):
        _, sid, st = _setup(db)
        lid = db.add_lesson(sid, _shift(0), status='held')
        db.mark_attendance(lid, st, '5')
        db.add_lesson(sid, _shift(-2), status='scheduled')

        text = maxbot.teacher_targets(db, _shift(0))

        assert 'Дайджест' in text
        assert '1 оценок' in text
        assert 'Незаполненная пара:' in text

    def test_no_pending_means_no_extra_block(self, db):
        _, sid, _ = _setup(db)
        db.add_lesson(sid, _shift(0), status='held')

        text = maxbot.teacher_targets(db, _shift(0))

        assert 'Незаполнен' not in text
