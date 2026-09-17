# iOS Phase 2 — иконки, версия сборки, гейт APK-апдейта на iOS

> Апрув владельца есть. Ограничения Phase 2: **не трогать** `build-apk.yml`/`buildozer.spec`, `code-and-design-review`, `node_modules`, `lessons.db` вообще, бэкенд `*.py` не трогать (всё решается фронтом/конфигами/CI). `tests/` можно дополнять. Не пушить.

## Задачи

1. **Иконки** — единый источник `icon-512.png` (28 KB, 512×512, уже в репо) плюс сгенерированная `icon-1024.png` (1024×1024, 109 KB, LANCZOS upscale) для iOS App Store / Briefcase. Briefcase берет `icon = "icon-1024.png"` из `pyproject.toml` и генерирует AppIcon набор (20,29,40,60,76,83.5,1024) автоматически если установлен Pillow.

2. **Версия сборки** — как на Android (`0.${github.run_number}`), но для iOS. На CI шаг `Set version from run number` пишет `0.${run_number}` в `VERSION` и патчит обе версии в `pyproject.toml` (`[project] version` и `[tool.briefcase] version`) через Python regex. Затем Briefcase и fallback `Info.plist` используют `CFBundleVersion`/`CFBundleShortVersionString = $VER`. Локально версия остаётся `0.261`.

3. **Гейт APK-апдейта на iOS** — `api.py` (`/api/update/*`) не трогаем. Гейтим только фронтом:
   - Новый `mobile-teacher-app-redesign/src/lib/platform.ts` — `isIOS()` (UA iPad/iPhone/iPod + iPadOS MacIntel+touch) и `isApkUpdaterAvailable() = !isIOS()`.
   - `src/lib/update.ts` — `checkUpdate` возвращает `null` на iOS, `downloadUpdate`/`installUpdate` бросают `APK not available on iOS` на iOS (и ре-экспорт `isIOS` для тестов).
   - `src/components/UpdateBanner.tsx` — хуки остаются безусловными, но `useEffect` ранний `return` на iOS и рендер `if (isIOS()) return null` + проверка `!info`.
   - `src/screens/Settings.tsx` — секция «Обновления» на iOS показывает карточку `На iOS обновления через TestFlight / App Store` вместо `UpdateBanner`+`Проверить обновления`.
   - `static/app.js` (legacy) — `function _isIOS()`, `if (_isIOS()) return` в `checkBanner`, с тостом в `download`/`install` на iOS.

## Файлы Phase 2

```
icon-1024.png                              # 1024×1024 LANCZOS из 512, для App Store
pyproject.toml                             # icon = "icon-1024.png" + sources + iOS ATS
src/lib/platform.ts                        # isIOS / isApkUpdaterAvailable
src/lib/update.ts                          # gate check/download/install
src/components/UpdateBanner.tsx            # gate render
src/screens/Settings.tsx                   # gate секции Обновления
static/app.js                              # _isIOS gate
mobile-teacher-app-redesign/dist/index.html # пересобран vite singlefile (396 KB, содержит TestFlight)
.github/workflows/build-ios.yml            # Phase 2: version+icons+gate валидация, IPA TeachHelper-${VER}-unsigned.ipa
docs/IOS_PHASE2.md                         # этот файл
tests/test_ios_phase2.py                   # иконки/версия/гейт
tests/test_ios_db_path.py                  # остаётся с Phase 1 (DB path)
```

## CI Phase 2: .github/workflows/build-ios.yml

- `on.push.paths` расширен: `icon-*.png`, `src/lib/platform.ts`, `src/lib/update.ts`, `UpdateBanner`, `Settings`, `static/app.js`, `VERSION`, `pyproject.toml`, `dist/**`.
- `Set version from run number` — `VER=0.${run_number}` → `VERSION` + `pyproject.toml` (обе секции) + `GITHUB_ENV VERSION`.
- `Validate icons` — `ls icon-512/1024`, `Pillow` проверяет 512 и 1024 square, `grep icon=` в pyproject.
- `Validate iOS gate in frontend` — `test -f platform.ts`, `grep isIOS`, `grep TestFlight` в Settings, `grep _isIOS` в static/app.js, `grep TestFlight/isIOS` в `dist/index.html`.
- `Install Briefcase & deps` — `pip install briefcase Pillow toga~=0.4.6`
- `Briefcase create/build iOS --no-input` → `xcodebuild CODE_SIGNING_ALLOWED=NO` → `Payload → TeachHelper-${VER}-unsigned.ipa` + `upload-artifact teachhelper-ios-unsigned-${VER}`.

## Локальная проверка

```powershell
# Иконки
python -c "from PIL import Image; print(Image.open('icon-512.png').size, Image.open('icon-1024.png').size)"
# Версия
cat VERSION; grep -E '^version' pyproject.toml
# Гейт фронтом
grep -n isIOS mobile-teacher-app-redesign/src/lib/platform.ts
grep -n isIOS mobile-teacher-app-redesign/src/components/UpdateBanner.tsx mobile-teacher-app-redesign/src/lib/update.ts static/app.js
grep -n TestFlight mobile-teacher-app-redesign/src/screens/Settings.tsx mobile-teacher-app-redesign/dist/index.html
# CI валидация
python -m pytest tests/test_ios_phase2.py -v
python -m pytest tests -q  # 492+?
# Dist пересобран
ls -lh mobile-teacher-app-redesign/dist/index.html
```

## Не тронуто

- `build-apk.yml`, `buildozer.spec` — `git diff --` пустой (проверь)
- `code-and-design-review/**`, `node_modules/**` — не трогали
- `lessons.db`, `*.db` — sacred, `.gitignore` `*.db`, тесты на `tmp_path`
- Бэкенд `*.py` (`api.py`, `database.py`, `botcore.py`…) — без diff (только `database.py` был в Phase 1, в Phase 2 — ноль `*.py`)
- Пуша нет — `python _push.py --dry-run` → `Nothing to push`
