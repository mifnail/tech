"""
TeachHelper iOS — Briefcase + Toga WebView shell over Flask.

Real app: Flask (api.py) + bundled dist (mobile-teacher-app-redesign/dist) + SQLite (database.py)
with iOS-writable DB path via TEACHHELPER_IOS / sys.platform == "ios".

Toga WebView loads http://127.0.0.1:5000 which serves the SPA.
"""
from __future__ import annotations

import os
import sys
import threading
import time
import socket
from pathlib import Path

# Mark as iOS before importing Flask/database so _is_ios() picks Documents path.
# On device sys.platform == "ios" already; on simulator/hosted runner it may be "darwin",
# so force via env for the Briefcase bundle.
if sys.platform == "ios" or os.environ.get("BRIEFCASE_APP_NAME"):
    os.environ.setdefault("TEACHHELPER_IOS", "1")

# iOS sandbox Documents must exist before Database() first import.
try:
    docs = Path.home() / "Documents"
    docs.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

import toga
from toga.style import Pack
from toga.style.pack import COLUMN


FLASK_HOST = "127.0.0.1"
FLASK_PORT = 5000
FLASK_URL = f"http://{FLASK_HOST}:{FLASK_PORT}/"


def _is_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _run_flask():
    """Run Flask in background thread. No reloader, no debug on device."""
    # Import here so env flag above is already set.
    try:
        from api import app as flask_app

        # Ensure Flask's dist lookup works even when bundle layout differs:
        # api.py expects mobile-teacher-app-redesign/dist next to itself.
        # If not found, try alternative locations (src layout).
        import api as api_mod

        dist_candidates = []
        try:
            base = Path(api_mod.__file__).parent
            dist_candidates.append(base / "mobile-teacher-app-redesign" / "dist" / "index.html")
            # src layout fallback: api at app/api.py, dist at app/mobile-teacher-app-redesign/dist
            # already covered; also try app/teachhelper/dist symlink
            dist_candidates.append(Path(__file__).parent / "dist" / "index.html")
            dist_candidates.append(Path(__file__).parent.parent / "mobile-teacher-app-redesign" / "dist" / "index.html")
        except Exception:
            pass
        # Log which candidate exists (visible in Xcode console)
        try:
            for c in dist_candidates:
                if c.exists():
                    print(f"[teachhelper] dist found: {c}", flush=True)
                    break
            else:
                print(f"[teachhelper] dist not found among {dist_candidates}, will rely on Flask fallback", flush=True)
        except Exception:
            pass

        print(f"[teachhelper] starting Flask on {FLASK_URL}", flush=True)
        # threaded=True required for Toga WebView concurrent requests
        flask_app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, threaded=True, use_reloader=False)
    except Exception as e:
        print(f"[teachhelper] Flask failed: {e}", flush=True)
        import traceback

        traceback.print_exc()


class TeachHelper(toga.App):
    def startup(self):
        self.main_window = toga.MainWindow(title=self.formal_name)

        # Start Flask daemon thread before showing WebView
        t = threading.Thread(target=_run_flask, daemon=True, name="flask")
        t.start()

        # Wait up to ~8s for Flask to bind
        for i in range(16):
            if _is_port_open(FLASK_HOST, FLASK_PORT):
                print(f"[teachhelper] Flask ready after {i*0.5:.1f}s", flush=True)
                break
            time.sleep(0.5)
        else:
            print("[teachhelper] Flask not ready after 8s, WebView will show loading", flush=True)

        # Toga WebView — WKWebView on iOS, WebView2/Cocoa elsewhere
        try:
            self.webview = toga.WebView(style=Pack(flex=1))
            # iOS needs ATS exception for http://127.0.0.1 (set via Info.plist NSAllowsLocalNetworking)
            self.webview.url = FLASK_URL
            print(f"[teachhelper] WebView url set to {FLASK_URL}", flush=True)
        except Exception as e:
            print(f"[teachhelper] WebView init failed: {e}", flush=True)
            # Fallback label if WebView unavailable (e.g. missing backend)
            self.webview = toga.Label(f"WebView unavailable: {e}\nFlask at {FLASK_URL}", style=Pack(padding=20, flex=1))

        box = toga.Box(style=Pack(direction=COLUMN, flex=1))
        box.add(self.webview)
        self.main_window.content = box
        self.main_window.show()


def main():
    # Briefcase entry point: returns Toga app instance
    return TeachHelper()
