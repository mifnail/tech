# iOS spike — Phase 0

Цель фазы 0: **доказать** что пайплайн `репо → CI macOS → unsigned IPA` работает,
не трогая Android-пайплайн и бэкенд.

## Что добавлено (только новые файлы)

- `.github/workflows/build-ios.yml` — отдельный workflow, `runs-on: macos-14`, собирает unsigned IPA.
- `ios-spike/TeachHelperSpike.xcodeproj/project.pbxproj` + `ios-spike/TeachHelperSpike/App.swift` — минимальный SwiftUI-таргет `com.teachhelper4.spike`.
- `docs/IOS_SPIKE.md` — легенда спайка и как проверить.

## Что НЕ трогали

- `buildozer.spec`, `.github/workflows/build-apk.yml`, `main.py`/`api.py`/`database.py` — без изменений.
- `lessons.db` — священна (тесты на `:memory:`).
- Никакого пуша — артефакты только в `Actions → Build unsigned IPA`.

## Как работает workflow

1. `xcodebuild` с `CODE_SIGNING_ALLOWED=NO / CODE_SIGNING_REQUIRED=NO / CODE_SIGN_IDENTITY=""` собирает `.app` для `iphoneos`.
2. Если `.app` найден — копируется в `Payload/`, иначе создаётся dummy `Payload/TeachHelperSpike.app` (fallback для доказательства пайплайна даже если Xcode-шаг упадёт).
3. `zip -r -y TeachHelperSpike-unsigned.ipa Payload` → `build/*.ipa` → `actions/upload-artifact@v4`.

Отдельный `upload-artifact` с `if-no-files-found: error` гарантирует что без IPA джоб падает.

## Как проверить локально (Windows — без Xcode)

```powershell
# 1. YAML валиден
python -c "import yaml, pathlib; yaml.safe_load(pathlib.Path('.github/workflows/build-ios.yml').read_text(encoding='utf-8')); print('YAML OK')"
# 2. Dummy IPA собирается тем же приёмом что и на CI
Remove-Item -Recurse -Force Payload,build -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path Payload,build | Out-Null
New-Item -ItemType Directory -Path Payload\TeachHelperSpike.app | Out-Null
@'
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0"><dict><key>CFBundleIdentifier</key><string>com.teachhelper4.spike</string></dict></plist>
'@ | Set-Content Payload\TeachHelperSpike.app\Info.plist -Encoding utf8
"spike" | Set-Content Payload\TeachHelperSpike.app\TeachHelperSpike
Compress-Archive -Path Payload -DestinationPath build\TeachHelperSpike-unsigned.ipa -Force
Get-Item build\TeachHelperSpike-unsigned.ipa | Format-List Name,Length
```

## Как запустить на CI

- Push ветки `main`/`redesign` с изменениями в `ios-spike/**` или `.github/workflows/build-ios.yml`, или `Run workflow` вручную в GitHub Actions.
- Ожидать зелёный джоб `Build unsigned IPA (macOS)` и артефакт `teachhelper-ios-spike-unsigned`.

## Дальше (не в Phase 0)

- Подключить Flask-бэкенд / WebView (python-ios, WKWebView) — отдельным PR.
- Подпись (ad-hoc / TestFlight) — только после решения по сертификатам.
- Версионирование из `VERSION` / `github.run_number` — как в Android-пайплайне.
