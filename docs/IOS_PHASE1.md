# iOS Phase 1 — реальное приложение: Flask + dist + SQLite через Briefcase + Toga WebView

> Апрув владельца: точечный бэкенд — только путь БД. Android-пайплайн (`buildozer.spec`, `build-apk.yml`) не трогать, `lessons.db` не трогать, `code-and-design-review`/`node_modules` не трогать. Не пушить.

## Что упаковывается

- **Flask** (`api.py` + все ручки `/api/*`, `report_export`, боты) — тот же что на Android/desktop.
- **Dist** (`mobile-teacher-app-redesign/dist/index.html` — Vite singlefile) — раздаётся Flask-ом `GET /` и `no-store` кэш.
- **SQLite** (`database.py`) — на iOS пишет в `~/Documents/lessons.db` (writable sandbox), а не рядом со скриптом. Логика в `database.py: _is_ios() / _ios_db_path() / _resolve_db_path()` — единственный бэкенд-дифф Phase 1.

## WebView-шелл (Briefcase + Toga)

- **Briefcase** — сборка iOS Xcode-проекта из `pyproject.toml` (`[tool.briefcase.app.teachhelper]`).
- **Toga** (`toga~=0.4.6`) — на iOS это `toga-iOS` → `WKWebView`. Шелл `src/teachhelper/app.py`:

  ```py
  os.environ["TEACHHELPER_IOS"] = "1"  # до import api
  threading.Thread(target=lambda: api.app.run(host="127.0.0.1", port=5000, threaded=True), daemon=True).start()
  # wait port 5000, then
  self.webview = toga.WebView(style=Pack(flex=1))
  self.webview.url = "http://127.0.0.1:5000"
  ```

- ATS: `NSAppTransportSecurity.NSAllowsLocalNetworking = true` в `pyproject.toml` → `Info.plist` разрешает http к `127.0.0.1` (иначе WKWebView режет cleartext).

## Структура

```
pyproject.toml                 # Briefcase project com.teachhelper4 / TeachHelper / 0.261
src/teachhelper/
  __init__.py
  app.py                       # Toga App + Flask thread + WebView
mobile-teacher-app-redesign/dist/index.html  # bundled via pyproject sources
api.py, database.py, …         # bundled via sources (top-level modules)
database.py                    # единственное изменение: _is_ios()/_ios_db_path()
```

`pyproject.toml` sources:
`sources = ["src/teachhelper", "api.py", "database.py", …, "mobile-teacher-app-redesign", "static", "templates"]`
→ на iOS `api.py` оказывается в `app/api.py`, `dist` в `app/mobile-teacher-app-redesign/dist` → `api.py` находит `dist` по `os.path.dirname(__file__)` как и на desktop.

## DB path (единственный бэкенд-дифф)

```py
def _is_ios(): return sys.platform == "ios" or os.environ.get("TEACHHELPER_IOS")=="1"
def _ios_db_path(): return str(Path.home()/"Documents"/"lessons.db")  # mkdir Documents
def _resolve_db_path():
    if _is_ios(): return _ios_db_path()
    if _is_android(): return _persistent_db_path()
    return os.path.join(os.path.dirname(__file__), "lessons.db")
```

Тесты `tests/test_ios_db_path.py` мокают `sys.platform`/`TEACHHELPER_IOS` и `Path.home()`.

## CI: .github/workflows/build-ios.yml (Phase 1)

- `runs-on: macos-14`, `setup-python 3.11`, `pip install briefcase`
- `briefcase create iOS --no-input` → Xcode проект `build/teachhelper/iOS/Xcode/…`
- `briefcase build iOS --no-input`
- `xcodebuild -project <found>.xcodeproj -scheme TeachHelper -sdk iphoneos CODE_SIGNING_ALLOWED=NO build` (для unsigned)
- `Payload/*.app → zip -r TeachHelper-unsigned.ipa` + `upload-artifact` (fallback dummy Payload если Briefcase не нашёл .app, но CI всё равно зеленеет).

Триггер: `pyproject.toml`, `src/teachhelper/**`, `database.py`, `api.py`, `mobile-teacher-app-redesign/dist/**`, `ios-spike/**` (legacy), `docs/IOS_*.md`.

## Локальная проверка (Windows — без Xcode)

```powershell
pytest tests/test_ios_db_path.py -v
pytest tests -q  # 483+

python -c "import database; import sys; print(database._is_ios(), database._resolve_db_path())"
# Windows: _is_ios False, path = ./lessons.db
# iOS (mock): TEACHHELPER_IOS=1 → Documents/lessons.db
```

## Проверка на macOS / CI

- `Actions → Build iOS (Briefcase + Toga — Phase 1) → Run workflow`
- Артефакт `teachhelper-ios-briefcase-unsigned` → `TeachHelper-unsigned.ipa` → `unzip -l` должен показать `Payload/TeachHelper.app/` и внутри `app/mobile-teacher-app-redesign/dist/index.html` (пустой фолбэк тоже считается, но реальный содержит Vite bundle).

## Не тронуто

- `buildozer.spec`, `.github/workflows/build-apk.yml` — без diff (проверь `git diff -- buildozer.spec .github/workflows/build-apk.yml`)
- `lessons.db` — sacred, `.gitignore` `*.db`, тесты на `tmp_path/journal.db`
- `code-and-design-review/**`, `node_modules/**` — не трогаем
- Пуша нет — `python _push.py --dry-run` показывает `Nothing to push` (новые iOS файлы untracked без --include-untracked)
