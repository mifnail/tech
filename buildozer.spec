# buildozer.spec — конфигурация сборки Android debug-APK.
# Flask + WebView (pywebview) → SPA на HTML/CSS/JS.
# Версии инструментов пинуются в CI (см. .github/workflows/build-apk.yml).

[app]
title = Учёт занятий
package.name = lessontracker
package.domain = org.lessontracker

source.dir = .
source.include_exts = py,png,jpg,html,css,js
version = 0.2

# pywebview + Flask (Kivy полностью удалён)
requirements = python3,flask==3.1.3,waitress==3.0.2,pywebview

orientation = portrait
fullscreen = 0

# Android
android.api = 34
android.minapi = 24
android.archs = arm64-v8a
android.allow_backup = 1
android.accept_sdk_license = True
android.ndk = 25c

# Flask использует werkzeug — не указывать отдельно, входит в flask

[buildozer]
log_level = 2
warn_on_root = 1
