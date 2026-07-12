"""Глобальный обработчик исключений — логирование в файл."""

from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime
from typing import Optional

LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')


def _ensure_log_dir() -> str:
    os.makedirs(LOG_DIR, exist_ok=True)
    return LOG_DIR


def log_exception(exc: Optional[BaseException] = None) -> str:
    """Записывает traceback в лог-файл, возвращает путь к логу."""
    _ensure_log_dir()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = os.path.join(LOG_DIR, f'crash_{timestamp}.log')
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f'Time: {datetime.now().isoformat()}\n')
        if exc:
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=f)
        else:
            traceback.print_exc(file=f)
    return filename


def install_global_handler() -> None:
    """Устанавливает глобальный обработчик необработанных исключений."""
    def handler(exc_type, exc_value, exc_tb):
        log_exception(exc_value)
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = handler
