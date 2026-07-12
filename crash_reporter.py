import sys
import traceback
import logging

logging.basicConfig(level=logging.ERROR, filename='crash.log',
                    format='%(asctime)s %(levelname)s: %(message)s')

def install_crash_handler(webhook_url=None, telegram_token=None, chat_id=None):
    def handler(exctype, value, tb):
        details = ''.join(traceback.format_exception(exctype, value, tb))
        logging.error(details)
        if webhook_url:
            try:
                import urllib.request
                import json
                urllib.request.urlopen(webhook_url, json.dumps({'text': details}).encode(), timeout=5)
            except Exception:
                pass
        if telegram_token and chat_id:
            try:
                import urllib.request
                url = f'https://api.telegram.org/bot{telegram_token}/sendMessage'
                data = f'chat_id={chat_id}&text={urllib.parse.quote(details[:3000])}'
                urllib.request.urlopen(url, data.encode(), timeout=5)
            except Exception:
                pass
    sys.excepthook = handler
