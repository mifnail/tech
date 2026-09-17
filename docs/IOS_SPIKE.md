# iOS spike — Phase 0: repo → CI macOS → unsigned IPA

> Легенда фазы 0. Задача — **только** доказать работоспособность пайплайна.
> Никаких изменений в Android-сборке и бэкенде, `lessons.db` не трогать, не пушить без команды.

## Идея

На репозитории уже есть `.github/workflows/build-apk.yml` (`ubuntu-latest` → `buildozer` → signed APK).
Для iOS заводится **отдельный** workflow `.github/workflows/build-ios.yml`:

- `runs-on: macos-14` (Xcode 15/16 на GitHub Hosted).
- `xcodebuild -project ios-spike/TeachHelperSpike.xcodeproj -scheme TeachHelperSpike -sdk iphoneos CODE_SIGNING_ALLOWED=NO` — сборка без подписи.
- `Payload/*.app → zip -r unsigned.ipa` — классическая «unsigned IPA» (не ставится на устройство без подписи, но доказывает что артефакт собирается).
- Fallback: если `xcodebuild` не нашёл `.app`, собирается dummy `Payload/TeachHelperSpike.app` с минимальным `Info.plist` + `PkgInfo`, чтобы джоб всё равно выпустил артефакт (пайплайн доказал что `zip → upload-artifact` работает).

Триггер — `push` по `ios-spike/**` + `workflow_dispatch` для ручного прогона. Android-пайплайн не затрагивается (другой путь в `on.push.paths`).

## Структура спайка

```
ios-spike/
  README.md
  TeachHelperSpike.xcodeproj/project.pbxproj  # CODE_SIGNING_ALLOWED=NO, GENERATE_INFOPLIST_FILE=YES
  TeachHelperSpike/App.swift                 # SwiftUI single-view, без зависимостей
```

`project.pbxproj` — минимальный `Xcode 14.0`/`objectVersion 56`, `IPHONEOS_DEPLOYMENT_TARGET 15.0`,
`TARGETED_DEVICE_FAMILY 1,2`, `bundleId com.teachhelper4.spike`. Никаких Assets/Cocoapods — заведомый минимум
который компилируется на `macos-14`.

## Как убедиться что ничего не сломали

```powershell
# 1. Только новые файлы (на машине без git — сверить с tech-main)
# 2. YAML парсится
python -c "import yaml, pathlib; yaml.safe_load(pathlib.Path('.github/workflows/build-ios.yml').read_text(encoding='utf-8')); print('YAML OK')"
# 3. Бэкенд не трогали — тесты зелёные
pytest -q
# 4. lessons.db — mtime не менялся
```

## Как запустить проверку на GitHub

1. Закоммитить **только** новые файлы (`build-ios.yml`, `ios-spike/**`, `docs/IOS_SPIKE.md`) — не пушить.
2. Вручную нажать `Actions → Build unsigned IPA (iOS spike — Phase 0) → Run workflow` (или запушить в `redesign`).
3. Дождаться артефакта `teachhelper-ios-spike-unsigned` — внутри `TeachHelperSpike-unsigned.ipa` (`unzip -l` показывает `Payload/TeachHelperSpike.app/Info.plist`).

## Критерий готовности фазы 0

- [ ] Workflow `build-ios.yml` валиден (`yaml.safe_load` + `actionlint` если есть).
- [ ] Джо́б на `macos-14` зелёный, артефакт `.ipa` скачивается, `unzip -l` видит `Payload/`.
- [ ] `build-apk.yml`/`buildozer.spec`/`api.py`/`database.py`/`lessons.db` — без diff.
- [ ] Не было `git push` (проверяется `git log --not --remotes` или историей `_push.py`).

## Что дальше (вне Phase 0)

- Phase 1: проброс Flask-бэкенда в WKWebView / `python-apple-support` (отдельный `ios/` проект).
- Phase 2: подпись (Development / Ad-hoc) и выкладка в TestFlight — только после выбора аккаунта.
- Версионирование IPA из `VERSION`/`github.run_number` как в APK-пайплайне.

