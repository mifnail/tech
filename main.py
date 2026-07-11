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

    MainApp().run()


# ---- CLI -----------------------------------------------------------
if __name__ == "__main__":
    if "--android" in sys.argv:
        serve_android()
    elif "--prod" in sys.argv:
        _start_flask()
    else:
        serve_dev()
