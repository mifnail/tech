# buildozer.spec — конфигурация сборки Android debug-APK.
# Версии инструментов пинуются в CI (см. .github/workflows/build-apk.yml).
# ВАЖНО: никаких matplotlib/numpy/pillow — только чистый Kivy (см. AGENT.md §2).

[app]
title = Учёт занятий
package.name = lessontracker
package.domain = org.lessontracker

source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.1

# Только лёгкие зависимости. sqlite3 встроен в Python на Android — отдельно НЕ указываем.
# openpyxl — чисто-Python (для выгрузки ведомости в Excel), безопасен для APK.
# reportlab (PDF) НЕ включаем в APK: тяжёлый, грузится лениво и используется в
# основном на ПК (см. docs/REPORTS.md). Синхронизация с календарём — только через
# выгрузку .ics (calendar_export.py), внешних зависимостей не требует.
requirements = python3,kivy==2.3.0,openpyxl

orientation = portrait
fullscreen = 0

# Android
android.api = 34
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = 1

[buildozer]
log_level = 2
warn_on_root = 1