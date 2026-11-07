"""Единая настройка логирования для бэкенда TeachHelper4.

Зачем этот модуль: до него в Flask-бэкенде не было ни одной строки
`logging`. Ошибки в продакшене были невидимы, а места с
`except Exception: pass` глушили их молча — потеря уведомления ученику
или несохранённый бэкап выглядели как «ничего не произошло».

Куда пишем:
- `flask.log` рядом с базой данных. На десктопе — папка проекта,
  на Android — PRIVATE storage приложения (пользователю недоступно);
- консоль (stderr) — для запуска из терминала и для CI.

Куда НЕ пишем: никуда в сеть. Журнал содержит фамилии и оценки, поэтому
он остаётся на устройстве и не покидает его. Файл закрыт `.gitignore`
(`*.log`), а `tests/test_buildozer_spec.py` следит, чтобы в APK логи
не попали.

Модуль намеренно ничего не знает про Flask: его можно вызвать из
`main.py`, из бота или из теста.
"""
from __future__ import annotations

import logging
import logging.handlers
import re
from pathlib import Path

LOGGER_NAME = 'teachhelper'
LOG_FILENAME = 'flask.log'
LOG_MAX_BYTES = 512 * 1024
LOG_BACKUPS = 1
LOG_FORMAT = '%(asctime)s %(levelname)-7s %(name)s: %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# Куда положен файл журнала — заполняется в configure_logging().
_log_file: Path | None = None
_configured = False


def log_path(db_path) -> Path:
    """Путь журнала рядом с базой — там же, где приватные данные."""
    return Path(db_path).expanduser().resolve().parent / LOG_FILENAME


def get_logger(name: str | None = None) -> logging.Logger:
    """Логгер проекта.

    До вызова `configure_logging()` пишет в пустоту: приложение не должно
    сыпать трассировки в stderr, если журнал не настроен (тесты, импорт).
    """
    base = logging.getLogger(LOGGER_NAME)
    if not any(isinstance(h, logging.NullHandler) for h in base.handlers):
        base.addHandler(logging.NullHandler())
    return base.getChild(name) if name else base


def configure_logging(db_path, *, level: int = logging.INFO,
                      stream: bool = True) -> logging.Logger:
    """Подключить файловый и консольный обработчики.

    Идемпотентно: повторный вызов ничего не меняет, чтобы не плодить
    дубли записей при перезапуске потоков.
    """
    global _configured, _log_file
    logger = logging.getLogger(LOGGER_NAME)
    if _configured:
        return logger

    logger.setLevel(level)
    # propagate=True: записи доходят до корневого логгера, поэтому их видно
    # и в pytest (caplog), и в любом внешнем обработчике.
    logger.propagate = True

    formatter = logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)

    path = log_path(db_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUPS, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        _log_file = path
    except OSError:
        # Места для журнала нет (read-only FS, нет прав) — работаем без файла,
        # в консоль пишем всё равно.
        _log_file = None

    if stream:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    _configured = True
    return logger


def current_log_path() -> Path | None:
    """Путь активного журнала или None, если файла нет."""
    return _log_file


# Технические ошибки ботов пишутся в общий flask.log, а события для
# пользователя — в bot.log. Экран настроек показывает оба потока.
BOT_LOGGERS = ('teachhelper.botcore', 'teachhelper.maxbot', 'teachhelper.tgbot')


def read_bot_errors_tail(limit: int = 30) -> list[str]:
    """Последние WARNING/ERROR от модулей ботов из flask.log.

    Многострочные traceback-записи сохраняем целиком: без стека по строке
    «ошибка обработана» невозможно понять, что именно сломалось.
    """
    if _log_file is None:
        return []
    try:
        with open(_log_file, encoding='utf-8', errors='replace') as f:
            rows = [row.rstrip('\n') for row in f.readlines()]
    except OSError:
        return []

    records: list[list[str]] = []
    current: list[str] | None = None
    for row in rows:
        # Начало записи: "2026-11-07 14:43:38 WARNING teachhelper.maxbot: ..."
        if re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ', row):
            if current:
                records.append(current)
            current = [row] if any(n in row for n in BOT_LOGGERS) and (
                ' WARNING ' in row or ' ERROR ' in row) else None
        elif current is not None:
            current.append(row)
    if current:
        records.append(current)

    return [line for record in records[-limit:] for line in record]


def read_log_tail(limit: int = 60) -> list[str]:
    """Последние строки журнала (свежие в конце).

    Нет файла — пустой список: экран настроек покажет «Журнал пуст».
    """
    if _log_file is None:
        return []
    try:
        with open(_log_file, encoding='utf-8', errors='replace') as f:
            rows = f.readlines()
    except OSError:
        return []
    return [row.rstrip('\n') for row in rows[-limit:]]
