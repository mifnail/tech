"""
crash_reporter.py — ловит unhandled exceptions и отправляет.
Поддерживаемые транспорты:
  - telegram: POST в Telegram Bot API
  - webhook:  POST на любой URL
  - sentry:   sentry-sdk (нужен pip install sentry-sdk)
  - file:     запись в /sdcard/lessontracker_crash.log (Android)
"""
import os
import sys
import traceback
from datetime import datetime


class CrashReporter:
    def __init__(self, transport: str, **kwargs):
        self.transport = transport
        self.params = kwargs
        self._orig_excepthook = sys.excepthook
        sys.excepthook = self._handler

    def _build_payload(self, exc_type, exc_value, tb) -> str:
        lines = [
            f"=== CRASH {datetime.now().isoformat()} ===",
            f"Device: {os.uname().nodename if hasattr(os, 'uname') else 'android'}",
            "".join(traceback.format_exception(exc_type, exc_value, tb)),
            "=" * 40,
        ]
        return "\n".join(lines)

    def _send(self, text: str):
        try:
            if self.transport == "telegram":
                self._send_telegram(text)
            elif self.transport == "webhook":
                self._send_webhook(text)
            elif self.transport == "sentry":
                self._send_sentry(text)
            else:  # file — fallback по умолчанию
                self._write_file(text)
        except Exception:
            self._write_file(text)

    def _send_telegram(self, text: str):
        import urllib.request
        token = self.params["bot_token"]
        chat_id = self.params["chat_id"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = f"chat_id={chat_id}&text={urllib.parse.quote(text[:3500])}"
        urllib.request.urlopen(url, data.encode(), timeout=10)

    def _send_webhook(self, text: str):
        import urllib.request
        req = urllib.request.Request(
            self.params["url"],
            data=text.encode("utf-8"),
            headers={"Content-Type": "text/plain"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)

    def _send_sentry(self, text: str):
        import sentry_sdk
        sentry_sdk.capture_message(text)

    def _write_file(self, text: str):
        path = self.params.get("path", "/sdcard/lessontracker_crash.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n")

    def _handler(self, exc_type, exc_value, tb):
        text = self._build_payload(exc_type, exc_value, tb)
        self._send(text)
        if self._orig_excepthook:
            self._orig_excepthook(exc_type, exc_value, tb)
