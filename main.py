"""main.py — Учет занятий
Desktop:  python main.py
Prod:     python main.py --prod
Android:  p4a webview bootstrap
"""
import sys
import os
from api import app
from log_config import configure_logging, get_logger

logger = get_logger('main')


def _maybe_start_bot(debug: bool) -> None:
    """Telegram polling в фоне, если задан токен и бот включён.

    Без тяжёлых импортов на верхнем уровне: всё лениво и в try/except,
    сервер никогда не падает из-за бота. При debug-релоадере стартуем
    только в дочернем процессе (WERKZEUG_RUN_MAIN).
    """
    if os.environ.get('TEACHHELPER_NO_BOT') == '1':
        return
    if debug and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        return
    try:
        from database import Database
        db = Database()
        try:
            token = db.get_setting('bot_token')
            enabled = db.get_setting('bot_enabled')
        finally:
            db.close()
    except Exception as e:
        logger.warning('Telegram-бот не запущен (нет настроек): %s', e)
        return
    if not token or enabled != '1':
        return
    try:
        import tgbot
        tgbot.start_polling(token)
        logger.info('Telegram-бот запущен')
    except Exception as e:
        logger.warning('Telegram-бот не запущен: %s', e)


def _maybe_start_maxbot(debug: bool) -> None:
    """MAX polling в фоне, если задан токен и бот включён."""
    if os.environ.get('TEACHHELPER_NO_BOT') == '1':
        return
    if debug and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        return
    try:
        from database import Database
        db = Database()
        try:
            token = db.get_setting('max_bot_token')
            enabled = db.get_setting('max_bot_enabled')
        finally:
            db.close()
    except Exception as e:
        logger.warning('MAX-бот не запущен (нет настроек): %s', e)
        return
    if not token or enabled != '1':
        return
    try:
        import maxbot
        maxbot.start_polling(token)
        maxbot.start_reminders(token)
        logger.info('MAX-бот запущен')
    except Exception as e:
        logger.warning('MAX-бот не запущен: %s', e)


if __name__ == '__main__':
    prod = '--prod' in sys.argv or os.environ.get('MODE') == 'prod'
    debug = not prod and 'ANDROID_ARGUMENT' not in os.environ
    # This single-user journal has no network authentication boundary.
    # Production disables debug; it must not expose grades/tokens to the LAN.
    host = '127.0.0.1'
    port = int(os.environ.get('PORT', 5000))

    if not prod and 'ANDROID_ARGUMENT' not in os.environ:
        import threading
        def open_browser():
            import time, webbrowser
            time.sleep(1.5)
            webbrowser.open(f'http://127.0.0.1:{port}')
        threading.Thread(target=open_browser, daemon=True).start()

    # Журнал — рядом с базой: на десктопе в папке проекта, на Android
    # в PRIVATE storage приложения. Никуда наружу не отправляется.
    from database import DB_PATH
    configure_logging(DB_PATH)
    logger.info('Запуск TeachHelper4 (prod=%s, port=%s)', prod, port)

    _maybe_start_bot(debug)
    _maybe_start_maxbot(debug)

    app.run(host=host, port=port, debug=debug, threaded=True)
