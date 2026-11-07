"""Прикладной слой TeachHelper4: доменная логика и уведомления.

Слои проекта:
    database.py  — SQLite: схема, миграции, запросы (весь SQL здесь)
    services.py  — прикладная логика (этот файл)
    api.py       — HTTP: разбор запроса, валидация, ответ

Всё, что не про HTTP, живёт здесь: правила проведения занятия, разбор
ведомости, тексты уведомлений и отправка в MAX-бот. api.py превратился в
роуты и orchestration — он вызывает функции отсюда и собирает ответ.

Именование: функции без подчёркивания — публичный API слоя. В api.py
оставлены алиасы с прежними именами (`_curator_conduct_text` и т.п.),
чтобы тесты и внешние вызовы продолжали работать.

Журнал: logger из log_config, тот же файл flask.log рядом с базой.
"""
from __future__ import annotations

import threading
from typing import Any

from database import row_get
from log_config import get_logger

logger = get_logger('services')

# Реестры живых таймеров дебаунса: ключ (lesson_id, student_id) -> Timer.
# Живут здесь, потому что их чистят и читают функции отправки пушей.
_pending: dict[tuple[int, int], threading.Timer] = {}
_pending_curator: dict[tuple[int, int], threading.Timer] = {}


# ── Контекст занятия ───────────────────────────────────────────────────────

def lesson_group_id(db, lesson_id) -> int | None:
    """Группа занятия: из строки занятия, иначе по его предмету."""
    lesson = db.get_lesson(lesson_id)
    if not lesson:
        return None
    group_id = None
    try:
        if 'group_id' in lesson.keys():
            group_id = lesson['group_id']
    except Exception as exc:
        logger.debug("Не удалось прочитать group_id из занятия: %s", exc)
    if group_id is None:
        try:
            sid = row_get(lesson, 'subject_id', None)
            if sid is not None and str(sid) != '':
                r = db.conn.execute("SELECT group_id FROM subjects WHERE id=?", (sid,)).fetchone()
                if r:
                    group_id = r['group_id']
        except Exception as exc:
            logger.debug("Не удалось определить group_id по предмету: %s", exc)
    return group_id


def lesson_notify_context(db, lesson_id):
    """(дд.мм, название предмета, group_id) для уведомлений."""
    try:
        lesson = db.get_lesson(lesson_id)
        if not lesson:
            return ('', '', None)
        subject_name = row_get(lesson, 'actual_subject_name', '')
        if not subject_name:
            subject_name = row_get(lesson, 'planned_subject', '')
        date_iso = row_get(lesson, 'date', '')
        ddmm = f"{date_iso[8:10]}.{date_iso[5:7]}" if date_iso and len(date_iso) >= 10 else ''
        return (ddmm, subject_name or '', lesson_group_id(db, lesson_id))
    except Exception:
        return ('', '', None)


def mark_lesson_held(db, lesson_id: int) -> bool:
    """Проведение = lessons.status='held' на сервере.

    Без этого фронт ставил held только локально, а GET /lessons/<id>/attendance
    возвращал scheduled и «слетал признак проведено». Отменённые/не найденные
    уроки не трогаем.
    """
    try:
        lesson = db.get_lesson(lesson_id)
        if not lesson:
            return False
        if row_get(lesson, 'status', 'scheduled') == 'cancelled':
            return False
        if row_get(lesson, 'status', 'scheduled') != 'held':
            db.set_lesson_status(lesson_id, 'held')
        return True
    except Exception:
        return False


def hours_exhausted_notice(db, lesson_id: int) -> dict:
    """Пары по предмету вычитаны (held >= total_hours) → данные для тоста фронта.

    Пустой dict, если пары ещё остались — чтобы форма ответа не менялась.
    Текст используем «пары», а не «часы» (поле total_hours в БД не трогаем).
    """
    try:
        lesson = db.get_lesson(lesson_id)
        if not lesson:
            return {}
        subject_id = row_get(lesson, 'actual_subject_id', None) or row_get(lesson, 'subject_id', None)
        if subject_id is None:
            return {}
        summary = db.subject_summary(int(subject_id))
        if not summary:
            return {}
        total = int(row_get(summary, 'total_hours', 0) or 0)
        held = int(row_get(summary, 'held_lessons', 0) or 0)
        if total <= 0 or held < total:
            return {}
        name = row_get(summary, 'name', '') or row_get(summary, 'actual_subject_name', '')
        return {
            'hours_exhausted': True,
            'hours_message': f'Пары по предмету «{name}» вычитаны: {held} из {total}.',
            'held_lessons': held,
            'total_hours': total,
        }
    except Exception:
        return {}


# ── Ведомость ──────────────────────────────────────────────────────────────

def student_fio(row) -> str:
    """«Фамилия И.» — как в остальных пушах куратору и студенту."""
    last = row_get(row, 'last_name', '') or ''
    first = row_get(row, 'first_name', '') or ''
    return f"{last} {first[0]}." if first else last


# MAX не поддерживает цвет текста: в HTML-разметке разрешены только b/i/u/s/
# code/pre/mark/blockquote/a/h1, в markdown — *курсив*, **жирный**, ++подчёркнутый++,
# ^^красная подсветка^^. Поэтому состояние показываем цветными кружками —
# они читаются в любом клиенте и не зависят от версии приложения.
MARK_GRADED = '🟢'   # оценка выставлена
MARK_NOGRADE = '⚪'  # был на паре, но без оценки
MARK_ABSENT = '🔴'   # отсутствовал


def lesson_header(db, lesson_id: int):
    """(дата, предмет, номер пары) для шапки уведомлений. None — урока нет."""
    lesson = db.get_lesson(lesson_id)
    if not lesson:
        return None
    raw_date = row_get(lesson, 'date', '') or ''
    date_str = f'{raw_date[8:10]}.{raw_date[5:7]}' if len(raw_date) >= 10 else ''
    subject = (row_get(lesson, 'actual_subject_name', '')
               or row_get(lesson, 'planned_subject', '') or '')
    ln = row_get(lesson, 'lesson_number', None)
    return date_str, subject, ('' if ln is None else str(ln))


def lesson_marks(db, lesson_id: int):
    """Разбор ведомости: (присутствующие [(строка студента, оценка)], отсутствующие).

    Присутствие — строка в grades ('0' = был без оценки, '2'–'5' = оценка).
    Нет строки или 'absent' — студент отсутствовал.
    """
    marks: dict[int, str] = {}
    for r in db.get_attendance(lesson_id):
        try:
            marks[int(r['student_id'])] = str(r['grade'] or '')
        except Exception:
            continue
    present: list[tuple[Any, str]] = []
    absent: list[Any] = []
    for st in db.get_group_students(lesson_id):
        grade = marks.get(int(st['id']), '')
        if grade in ('', 'absent'):
            absent.append(st)
        else:
            present.append((st, grade))
    return present, absent


# ── Тексты уведомлений ────────────────────────────────────────────────────

def curator_conduct_text(db, lesson_id: int) -> str:
    """Сводка куратору о проведённой паре: кто был и кого не было.

    Строится по ВСЕМУ составу группы, а не по изменённым оценкам: куратору
    нужны и присутствовавшие без оценок, и отсутствующие. Поэтому сообщение
    уходит и тогда, когда ни одной оценки не поставили — только отметили
    посещаемость.

    Формат:
        Дата: 22.10
        Предмет: МДК_0202_УправлениеПроектами
        Номер пары: 3
        Присутствовали:
        🟢 Гаус Э. — 5
        ⚪ Черников А.
        Отсутствовали:
        🔴 Энгель К.

    Пустая строка — урок/группа не разрешаются.
    """
    header = lesson_header(db, lesson_id)
    if header is None:
        return ''
    date_str, subject, lesson_number_str = header
    present, absent = lesson_marks(db, lesson_id)

    lines = [
        f'Дата: {date_str}',
        f'Предмет: {subject}',
        f'Номер пары: {lesson_number_str}',
        'Присутствовали:',
    ]
    if present:
        for st, grade in present:
            # '0' — присутствовал без оценки; куратору понятнее прочерк.
            if grade == '0':
                lines.append(f'{MARK_NOGRADE} {student_fio(st)}')
            else:
                lines.append(f'{MARK_GRADED} {student_fio(st)} — {grade}')
    else:
        lines.append('нет')
    lines.append('Отсутствовали:')
    if absent:
        lines.extend(f'{MARK_ABSENT} {student_fio(st)}' for st in absent)
    else:
        lines.append('нет')
    return '\n'.join(lines)


def student_conduct_messages(
    db, lesson_id: int, header, was_held: bool, changed_ids: set[int],
) -> list[tuple[int, str]]:
    """Сообщения студентам о проведённой паре: (chat_id, текст).

    Шапка как у куратора, дальше только собственная строка студента —
    чужие фамилии и оценки в личку не уходят.

    Однократность: при первом проведении сообщение получает каждый, у кого
    есть привязка MAX (оценка / без оценки / отсутствие). При повторном —
    только те, у кого оценка изменилась: иначе «отсутствие» приходило бы
    второй раз при каждом перепроведении.
    """
    date_str, subject, lesson_number_str = header
    present, absent = lesson_marks(db, lesson_id)
    out: list[tuple[int, str]] = []

    def add(st, mark_line: str) -> None:
        try:
            chat_id = db.get_max_student_chat(int(st['id']))
        except Exception:
            return
        if chat_id is None:
            return
        out.append((int(chat_id), '\n'.join([
            f'Дата: {date_str}',
            f'Предмет: {subject}',
            f'Номер пары: {lesson_number_str}',
            mark_line,
        ])))

    for st, grade in present:
        if grade == '0':
            if not was_held:
                add(st, f'{MARK_NOGRADE} Без оценки')
        elif not was_held or int(st['id']) in changed_ids:
            add(st, f'{MARK_GRADED} Оценка: {grade}')
    if not was_held:
        for st in absent:
            add(st, f'{MARK_ABSENT} Отсутствие')
    return out


# ── Проведение занятия ─────────────────────────────────────────────────────

def norm_grade(value) -> str:
    """Привести оценку к каноничному виду.

    '' и 'absent' — одно и то же состояние (студента не было): без
    нормализации «отметил присутствие → отменил» выглядело бы как
    изменение, и повторное «Провести» рассылало бы уведомления заново.
    """
    if value is None:
        return ''
    text = str(value)
    return '' if text in ('', 'absent') else text


def changed_grades(records, old_map) -> tuple[list[tuple[int, str]], bool]:
    """Что изменилось по сравнению с прежним состоянием.

    Возвращает (changed, state_changed):
      changed — список (student_id, оценка) для тех, кому писать;
      state_changed — изменилось ли вообще хоть что-нибудь, включая
                     появление или снятие отсутствия.
    """
    changed: list[tuple[int, str]] = []
    state_changed = False

    for r in records:
        sid = r['student_id']
        new_grade = norm_grade(r['grade'])
        old_grade = norm_grade(old_map.get(sid, ''))
        if new_grade == old_grade:
            continue
        state_changed = True
        if not new_grade:
            continue
        # '0' — присутствовал без оценки. Студенту про такое писать нечего:
        # «Новая оценка: … — 0» читается как ноль баллов.
        if new_grade == '0':
            continue
        try:
            sid_int = int(sid)
        except Exception:
            continue
        changed.append((sid_int, new_grade))

    return changed, state_changed


def prepare_conduct_notifications(db, lesson_id: int, was_held: bool,
                                   changed: list[tuple[int, str]]):
    """Что и кому отправляем после «Провести».

    Возвращает (student_msgs, cur_chat, curator_text). Считается в контексте
    запроса: в фоновом потоке БД уже не та.
    """
    student_msgs: list[tuple[int, str]] = []
    header = lesson_header(db, lesson_id)
    if header is not None:
        try:
            student_msgs = student_conduct_messages(
                db, lesson_id, header, was_held, {sid for sid, _ in changed})
        except Exception as exc:  # noqa: BLE001 — рассылка не должна ронять проведение
            logger.warning('[conduct] student messages build error: %s', exc)

    cur_chat = None
    group_id = lesson_group_id(db, lesson_id)
    if group_id is not None:
        try:
            cur_chat = db.get_curator_chat(group_id)
        except Exception:
            cur_chat = None

    curator_text = ''
    try:
        if cur_chat is not None:
            curator_text = curator_conduct_text(db, lesson_id)
    except Exception as exc:
        logger.warning("[curator-push] build error: %s", exc)

    return student_msgs, cur_chat, curator_text


def send_conduct_notifications(token: str, student_msgs, cur_chat,
                                curator_text: str, notice: dict) -> None:
    """Фоновая отправка после «Провести»: студентам и куратору.

    Студенту — только своя строка. Куратору — сводка (уходит и тогда, когда
    оценки не ставили, только отметили посещаемость) и, если вычитаны все
    пары, отдельное сообщение об исчерпании часов.
    """
    try:
        import maxbot as _maxbot
        for chat_id, text in student_msgs:
            try:
                _maxbot.send_message(token, chat_id, text)
            except Exception as exc:
                logger.warning("Уведомление студенту не отправлено (chat=%s): %s", chat_id, exc, exc_info=True)
        try:
            if cur_chat is not None and curator_text:
                _maxbot.send_message(token, int(cur_chat), curator_text)
        except Exception as exc:
            logger.warning("Уведомление куратору не отправлено: %s", exc, exc_info=True)
        try:
            if cur_chat is not None and notice.get('hours_exhausted'):
                _maxbot.send_message(token, int(cur_chat), notice['hours_message'])
        except Exception as exc:
            logger.warning("Уведомление об исчерпании часов не отправлено: %s", exc, exc_info=True)
    except Exception as exc:
        logger.warning("Ошибка отправки уведомлений при проведении: %s", exc, exc_info=True)


# ── Настройки ботов ────────────────────────────────────────────────────────

def is_bot_active(db, token_key='max_bot_token', enabled_key='max_bot_enabled'):
    """Token truthy and enabled=='1'."""
    try:
        return bool(db.get_setting(token_key)) and db.get_setting(enabled_key) == '1'
    except Exception:
        return False


def notify_group_chats(db, group_id, token, enabled, msg_text):
    """Best-effort daemon thread with 0.6s gaps; lazy imports inside."""
    try:
        if group_id is None:
            return
        if not token or enabled != '1':
            return
        chat_ids = []
        try:
            for st in db.list_students(group_id):
                try:
                    cid = db.get_max_student_chat(st['id'])
                    if cid is not None:
                        chat_ids.append(cid)
                except Exception:
                    continue
        except Exception:
            return
        if not chat_ids:
            return

        def _run():
            try:
                import time as _time
                import maxbot as _maxbot
                for cid in chat_ids:
                    try:
                        _maxbot.send_message(token, cid, msg_text)
                    except Exception as exc:
                        logger.warning("Уведомление в чат %s не отправлено: %s", cid, exc, exc_info=True)
                    _time.sleep(0.6)
            except Exception as exc:
                logger.warning("Не удалось отправить уведомления группе: %s", exc, exc_info=True)

        threading.Thread(target=_run, daemon=True).start()
    except Exception as exc:
        logger.warning("Не удалось запустить отправку уведомлений: %s", exc, exc_info=True)


# ── Пуши оценок (таймеры дебаунса) ────────────────────────────────────────

def read_settled_grade(db, lesson_id: int, student_id: int) -> str:
    """Оценка, устоявшаяся после последнего тапа."""
    try:
        rows = db.get_attendance(lesson_id)
        row = None
        for r in rows:
            if r['student_id'] == student_id:
                row = r
                break
        grade = row['grade'] if row and dict(row).get('grade') else ''
        return grade or ''
    except Exception:
        return ''


def fire_grade_push(token: str, lesson_id: int, student_id: int) -> None:
    """Timer callback: re-read settled grade from DB and send notification.

    Timer reset on every tap; only the settled grade is re-read from DB
    and sent — so the student always gets the *latest* value.
    """
    key = (lesson_id, student_id)
    _pending.pop(key, None)
    try:
        from database import Database as _DB
        db = _DB()
        try:
            grade = read_settled_grade(db, lesson_id, student_id)
            if not grade:
                return

            lesson = db.get_lesson(lesson_id)
            if not lesson:
                return

            raw_date = lesson['date'] or ''
            # DD.MM format from ISO date string
            date_str = f'{raw_date[8:10]}.{raw_date[5:7]}' if len(raw_date) >= 10 else ''
            subject = row_get(lesson, 'actual_subject_name', '')

            import maxbot as _maxbot
            _maxbot.notify_grade(token, student_id, grade, date_str, subject)
        except Exception as exc:
            logger.warning("Пуш оценки не отправлен: %s", exc, exc_info=True)
        finally:
            try:
                db.close()
            except Exception as exc:
                logger.debug("Не удалось закрыть соединение с БД: %s", exc)
    except Exception as exc:
        logger.warning("Ошибка пуша оценки: %s", exc, exc_info=True)


def fire_curator_push(token: str, lesson_id: int, student_id: int, group_id: int) -> None:
    """Timer callback: отправить куратору группы оценку студента."""
    key = (lesson_id, student_id)
    _pending_curator.pop(key, None)
    try:
        from database import Database as _DB
        db = _DB()
        try:
            grade = read_settled_grade(db, lesson_id, student_id)
            if not grade:
                logger.debug("[curator-push] skip: no grade for lesson=%s student=%s",
                             lesson_id, student_id)
                return

            # Resolve cur_chat: prefer the group_id passed from schedule,
            # fall back to re-lookup from lesson row.
            cur_chat = None
            try:
                cur_chat = db.get_curator_chat(group_id)
            except Exception as exc:
                logger.warning("[curator-push] get_curator_chat(%s) error: %s", group_id, exc)

            if not cur_chat:
                # Fallback: try to resolve group from lesson's subject
                try:
                    les = db.get_lesson(lesson_id)
                    if les is not None:
                        for col in ('actual_subject_id', 'subject_id'):
                            sid_sub = row_get(les, col, None)
                            if sid_sub is not None and sid_sub != '':
                                prow = db.conn.execute(
                                    "SELECT group_id FROM subjects WHERE id=?",
                                    (sid_sub,),
                                ).fetchone()
                                if prow and prow['group_id']:
                                    cur_chat = db.get_curator_chat(prow['group_id'])
                                    if cur_chat:
                                        group_id = prow['group_id']
                                        break
                except Exception as exc:
                    logger.warning("[curator-push] fallback group resolve error: %s", exc)

            if not cur_chat:
                logger.info(
                    "[curator-push] no cur_chat: lesson=%s student=%s group=%s",
                    lesson_id, student_id, group_id,
                )
                return

            st = db.get_student(student_id)
            if not st:
                logger.warning("[curator-push] no student: id=%s", student_id)
                return
            fio = f"{st['last_name']} {st['first_name'][0]}." if st['first_name'] else f"{st['last_name']}"
            lesson = db.get_lesson(lesson_id)
            if not lesson:
                logger.warning("[curator-push] no lesson: id=%s", lesson_id)
                return
            raw_date = lesson['date'] or ''
            date_str = f'{raw_date[8:10]}.{raw_date[5:7]}' if len(raw_date) >= 10 else ''
            subject = row_get(lesson, 'actual_subject_name', '')
            if not subject:
                subject = row_get(lesson, 'planned_subject', '')
            text = f"{fio}: {subject} — {grade} ({date_str})"
            import maxbot as _maxbot
            _maxbot.send_message(token, int(cur_chat), text)
            logger.info("[curator-push] sent: cur_chat=%s text=%r", cur_chat, text)
        except Exception as exc:
            logger.warning("[curator-push] inner error: %s", exc)
        finally:
            try:
                db.close()
            except Exception as exc:
                logger.debug("Не удалось закрыть соединение с БД: %s", exc)
    except Exception as exc:
        logger.warning("[curator-push] outer error: %s", exc)
