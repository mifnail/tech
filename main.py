"""
main.py — LessonTracker.
Desktop:  python main.py          (debug + auto-open browser)
Prod:     python main.py --prod   (waitress, если установлен)
Android:  p4a webview bootstrap   (Flask, WebView сам грузит SPA)
"""
import os
import sys

from api import app


def _run_flask(host: str, port: int, debug: bool = False):
    app.run(host=host, port=port, debug=debug, use_reloader=False)


def _run_dev(host: str, port: int):
    import webbrowser
    import threading

    def _open():
        import time; time.sleep(1.5)
        webbrowser.open(f"http://{host}:{port}")

    threading.Thread(target=_open, daemon=True).start()
    _run_flask(host, port, debug=True)


def _run_prod(host: str, port: int):
    try:
        from waitress import serve
        serve(app, host=host, port=port)
    except ImportError:
        _run_flask(host, port)


if __name__ == "__main__":
    host = "127.0.0.1"
    port = int(os.environ.get("PORT", 5000))
    is_android = "ANDROID_ARGUMENT" in os.environ

    if is_android:
        _run_flask(host, port)
    elif "--prod" in sys.argv or os.environ.get("MODE") == "prod":
        _run_prod(host, port)
    else:
        _run_dev(host, port)
