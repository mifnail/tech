"""
main.py — LessonTracker.
Desktop:  python main.py
Prod:     python main.py --prod
Android:  Kivy bootstrap → WebView c Flask SPA
"""
import os
import sys
import threading

from api import app

# ---- crash reporter config -----------------------------------------
# Раскомментируйте нужный вариант и заполните свои параметры.
# Вариант A: Telegram (бот + chat_id)
#   import telebot; from crash_reporter import CrashReporter
#   reporter = CrashReporter("telegram", bot_token="...", chat_id="...")
#
# Вариант B: любой HTTP-эндпоинт
#   reporter = CrashReporter("webhook", url="https://your-server.com/crash")
#
# Вариант C: Sentry
#   pip install sentry-sdk
#   reporter = CrashReporter("sentry")
#
# Вариант D: файл на телефоне (по умолчанию, ничего делать не надо)
reporter = None  # заменить на CrashReporter(...) когда понадобится


def _start_flask():
    port = int(os.environ.get("PORT", 5000))
    if os.environ.get("MODE") == "prod" or "--prod" in sys.argv:
        from waitress import serve
        serve(app, host="0.0.0.0", port=port)
    else:
        app.run(host="0.0.0.0", port=port, debug=True)


# ---- entry points -------------------------------------------------
def serve_dev():
    import webbrowser
    def _open():
        import time; time.sleep(1.5)
        webbrowser.open("http://127.0.0.1:5000")
    threading.Thread(target=_open, daemon=True).start()
    _start_flask()


def serve_android():
    """Запуск через Kivy bootstrap → замена на Android WebView."""
    from kivy.app import App
    from kivy.uix.label import Label
    from kivy.clock import Clock

    threading.Thread(target=_start_flask, daemon=True).start()

    class MainApp(App):
        def build(self):
            Clock.schedule_once(self._show_webview, 2.5)
            return Label(text="Загрузка…")

        def _show_webview(self, dt):
            try:
                from jnius import autoclass
                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                WebView = autoclass("android.webkit.WebView")
                WebViewClient = autoclass("android.webkit.WebViewClient")
                LayoutParams = autoclass("android.view.ViewGroup$LayoutParams")

                activity = PythonActivity.mActivity
                wv = WebView(activity)
                wv.getSettings().setJavaScriptEnabled(True)
                wv.getSettings().setDomStorageEnabled(True)
                wv.setWebViewClient(WebViewClient())
                wv.loadUrl("http://127.0.0.1:5000")
                activity.setContentView(wv, LayoutParams(
                    LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT))
            except Exception:
                import webbrowser
                webbrowser.open("http://127.0.0.1:5000")

    try:
        MainApp().run()
    except Exception:
        import traceback
        _dump_crash(traceback.format_exc())
        raise


def _dump_crash(text: str):
    """Файловый fallback — пишет в /sdcard если доступно, иначе в CWD."""
    paths = ["/sdcard/lessontracker_crash.log",
             os.path.join(os.path.dirname(__file__), "crash.log")]
    for p in paths:
        try:
            with open(p, "a", encoding="utf-8") as f:
                f.write(f"=== {datetime.now().isoformat()} ===\n{text}\n")
            return
        except OSError:
            continue


# ---- CLI -----------------------------------------------------------
if __name__ == "__main__":
    if "--android" in sys.argv:
        serve_android()
    elif "--prod" in sys.argv:
        _start_flask()
    else:
        serve_dev()
