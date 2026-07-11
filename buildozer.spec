# buildozer.spec — конфигурация сборки Android debug-APK.
# Kivy используется ТОЛЬКО как bootstrap (нужен для sdl2-активити).
# UI полностью на HTML/CSS/JS через Android WebView в jnius.

[app]
title = Учёт занятий
package.name = lessontracker
package.domain = org.lessontracker

source.dir = .
source.include_exts = py,png,jpg,html,css,js
version = 0.3

# Kivy — только для bootstrap (sdl2 Activity). Весь UI — WebView + Flask.
requirements = python3,kivy==2.3.1,flask==3.1.3,waitress==3.0.2,pyjnius

orientation = portrait
fullscreen = 0

# Android
android.api = 34
android.minapi = 24
android.archs = arm64-v8a
android.allow_backup = 1
android.accept_sdk_license = True
android.ndk = 25c

[buildozer]
log_level = 2
warn_on_root = 1
