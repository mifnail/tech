"""
main.py — точка входа LessonTracker (Flask + WebView).
Локально:    python main.py
На Android:  python main.py --android
"""
import argparse
import os
import sys
import threading
import webbrowser

from api import app


def serve_dev():
    threading.Thread(target=_open_browser, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=True)


def serve_prod():
    from waitress import serve
    port = int(os.environ.get("PORT", 5000))
    serve(app, host="0.0.0.0", port=port)


def serve_android():
    """Запуск Flask + pywebview в одном процессе."""
    import time

    def _start_flask():
        from waitress import serve
        serve(app, host="127.0.0.1", port=5000)

    t = threading.Thread(target=_start_flask, daemon=True)
    t.start()
    time.sleep(1.5)
    import webview
    webview.create_window("Учёт занятий", "http://127.0.0.1:5000")
    webview.start()


def _open_browser():
    import time
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    mode = "--android" if "--android" in sys.argv else os.environ.get("MODE", "dev")
    if mode == "android":
        serve_android()
    elif mode == "prod":
        serve_prod()
    else:
        serve_dev()
