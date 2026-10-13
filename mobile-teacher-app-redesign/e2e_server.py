#!/usr/bin/env python3
"""E2E-сервер стенда TeachHelper4: React dist + живой Flask.

Делает три вещи:
  1) Выделяет disposable HOME/USERPROFILE (tempfile) — lessons.db проекта не трогается
     НИКОГДА; TEACHHELPER_NO_BOT=1 (паттерн tests/conftest.py), боты и релоадер не поднимаем.
  2) Сидирует временную БД: сначала `python stand_seed.py <tmp db>` (параллельная лань),
     иначе свой сид (database.seed_default) + E2E-фикстура: группа/предмет/студенты
     и ПРОВЕДЁННОЕ занятие на 14 дней назад (чип «Проведено» в Расписании).
     Если tmp-БД не создалась — exit 2.
  3) Поднимает Flask из main.py на 127.0.0.1:5111.

Playwright (playwright.config.ts) зовёт этот файл через webServer.command и ждёт baseURL.
Если внешний раннер (stand.py/stand_seed.py) уже поднял сервер — reuseExistingServer: true,
Playwright просто подхватывает живой http://127.0.0.1:5111 и этот скрипт не стартует.
"""
from __future__ import annotations

import atexit
import datetime as _dt
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))  # .../mobile-teacher-app-redesign
ROOT = os.path.dirname(HERE)  # .../tech-redesign
PORT = 5111
FIXTURE_OFFSET_DAYS = 14  # фикстура: ровно 14 дней назад («неделя −2», прошлое)


def log(msg: str) -> None:
    print(f"[e2e_server] {msg}", flush=True)


def _db_fingerprint(path: str):
    """(mtime, size) lessons.db или None, если файла нет — tripwire сида."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_mtime, st.st_size)


def prepare_env() -> str:
    """Временный HOME/USERPROFILE + отключение ботов. Возвращает путь к tmp-БД."""
    home = tempfile.mkdtemp(prefix="th-e2e-home-")
    # утечка в %TEMP%: убираем tmp-каталог при любом выходе процесса
    atexit.register(shutil.rmtree, home, ignore_errors=True)
    os.makedirs(os.path.join(home, "Downloads"), exist_ok=True)
    os.environ["HOME"] = home
    os.environ["USERPROFILE"] = home
    os.environ["TEACHHELPER_NO_BOT"] = "1"
    os.environ["MODE"] = "prod"
    os.environ["PORT"] = str(PORT)
    for var in ("ANDROID_PRIVATE", "ANDROID_ARGUMENT", "TEACHHELPER_IOS"):
        os.environ.pop(var, None)
    return os.path.join(home, "lessons.db")


def patch_db_path(db_path: str) -> None:
    """database.DB_PATH патчим ДО импорта api/main (там `from database import DB_PATH`)."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    import database  # noqa: E402

    database.DB_PATH = db_path


def seed_with_stand(db_path: str) -> bool:
    """Сид через stand_seed.py параллельной лани, если он есть и принимает путь."""
    script = os.path.join(ROOT, "stand_seed.py")
    if not os.path.exists(script):
        log("stand_seed.py ещё не создан параллельной ланью — сидируем сами")
        return False
    try:
        with open(script, encoding="utf-8") as fh:
            src = fh.read()
    except OSError as exc:
        log(f"stand_seed.py не читается ({exc}) — сидируем сами")
        return False
    if "sys.argv" not in src:
        # Без argv скрипт пишет в lessons.db проекта — это запрещено, пропускаем.
        log("stand_seed.py не принимает путь (нет sys.argv) — пропускаем, чтобы не тронуть lessons.db")
        return False
    try:
        proc = subprocess.run(
            [sys.executable, script, db_path],
            cwd=ROOT,
            env=dict(os.environ),
            capture_output=True,
            text=True,
            timeout=180,
        )
    except Exception as exc:  # noqa: BLE001 — деградируем на свой сид
        log(f"stand_seed.py не запустился ({exc}) — сидируем сами")
        return False
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        log(f"stand_seed.py rc={proc.returncode} ({'; '.join(tail)}) — сидируем сами")
        return False
    return os.path.exists(db_path)


def seed_own(db_path: str) -> None:
    import database

    db = database.Database(db_path)
    try:
        db.seed_default()
    finally:
        db.close()


def ensure_fixture(db_path: str) -> None:
    """Группа/предмет/студенты + проведённое занятие на прошедшей дате (идемпотентно)."""
    import database

    target = (_dt.date.today() - _dt.timedelta(days=FIXTURE_OFFSET_DAYS)).isoformat()
    db = database.Database(db_path)
    try:
        conn = db.conn
        row = conn.execute("SELECT id FROM groups WHERE name = 'ИС-11'").fetchone()
        if row is None:
            row = conn.execute("SELECT id FROM groups ORDER BY id LIMIT 1").fetchone()
        gid = row["id"] if row else db.add_group("ИС-11")

        cnt = conn.execute(
            "SELECT COUNT(*) AS c FROM students WHERE group_id = ?", (gid,)
        ).fetchone()["c"]
        if not cnt:
            db.add_students_bulk(gid, [
                {"last_name": "Иванов", "first_name": "Иван", "middle_name": "Иванович"},
                {"last_name": "Петров", "first_name": "Пётр", "middle_name": "Петрович"},
                {"last_name": "Сидорова", "first_name": "Мария", "middle_name": "Сергеевна"},
            ])

        row = conn.execute(
            "SELECT id FROM subjects WHERE name = 'Математика' AND group_id = ?", (gid,)
        ).fetchone()
        sid = row["id"] if row else db.add_subject("Математика", 100, gid)

        row = conn.execute(
            "SELECT id FROM lessons WHERE date = ? AND actual_subject_id = ?", (target, sid)
        ).fetchone()
        if row:
            lid = row["id"]
        else:
            lid = db.add_lesson(sid, target, actual_subject_id=sid, status="held", lesson_number=1)

        # Оценки: ведомость «живая», тап по ячейке меняет оценку (5 → 4) и делает занятие грязным.
        students = conn.execute(
            "SELECT id FROM students WHERE group_id = ?", (gid,)
        ).fetchall()
        for st in students:
            conn.execute(
                "INSERT OR IGNORE INTO grades (lesson_id, student_id, grade) VALUES (?, ?, '5')",
                (lid, st["id"]),
            )
        conn.commit()
        log(f"fixture: lesson id={lid} date={target} group id={gid} subject id={sid}")
    finally:
        db.close()


def serve() -> int:
    spec = importlib.util.spec_from_file_location("th_e2e_main", os.path.join(ROOT, "main.py"))
    if spec is None or spec.loader is None:
        log(f"main.py не найден: {os.path.join(ROOT, 'main.py')}")
        return 2
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # `from api import app`; __main__-блок не выполняется

    log(f"ready http://127.0.0.1:{PORT} db={os.environ.get('HOME')}")
    module.app.run(
        host="127.0.0.1",
        port=PORT,
        debug=False,
        threaded=True,
        use_reloader=False,
    )
    return 0


def main() -> int:
    db_path = prepare_env()
    patch_db_path(db_path)

    project_db = os.path.join(ROOT, "lessons.db")
    before = _db_fingerprint(project_db)

    if not seed_with_stand(db_path):
        seed_own(db_path)

    if not os.path.exists(db_path):
        log("tmp-БД не создалась — выход с кодом 2")
        return 2

    ensure_fixture(db_path)

    after = _db_fingerprint(project_db)
    if before != after:
        log(f"ОШИБКА: {project_db} изменился во время сида (mtime/size {before} → {after}) — это баг стенда!")
        return 3

    return serve()


if __name__ == "__main__":
    sys.exit(main())
