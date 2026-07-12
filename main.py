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

    app.run(host=host, port=port, debug=debug)
