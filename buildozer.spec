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
requirements = python3,kivy==2.3.0

orientation = portrait
fullscreen = 0

# Android
android.api = 34
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = 1
android.accept_sdk_license = True

# Ветка python-for-android (пинована для воспроизводимости)
p4a.branch = develop

[buildozer]
log_level = 2
warn_on_root = 1