"""main.py — TeachHelper4 (LessonTracker)
Desktop:  python main.py
Prod:     python main.py --prod
Android:  p4a webview bootstrap
"""
import sys
import os
from api import app

if __name__ == '__main__':
    prod = '--prod' in sys.argv or os.environ.get('MODE') == 'prod'
    debug = not prod and 'ANDROID_ARGUMENT' not in os.environ
    host = '0.0.0.0' if prod else '127.0.0.1'
    port = int(os.environ.get('PORT', 5000))

    if not prod and 'ANDROID_ARGUMENT' not in os.environ:
        import threading
        def open_browser():
            import time, webbrowser
            time.sleep(1.5)
            webbrowser.open(f'http://127.0.0.1:{port}')
        threading.Thread(target=open_browser, daemon=True).start()

    _maybe_start_bot(debug)

    app.run(host=host, port=port, debug=debug)


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
        print('bot not started (db):', e)
        return
    if not token or enabled != '1':
        return
    try:
        import tgbot
        tgbot.start_polling(token)
        print('telegram bot polling started')
    except Exception as e:
        print('bot not started:', e)
