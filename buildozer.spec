# buildozer.spec — сборка Android APK (webview bootstrap)
# Flask + p4a webview bootstrap → Android WebView → HTML/CSS/JS SPA.
# Kivy ПОЛНОСТЬЮ удалён.

[app]
title = Учёт занятий
package.name = lessontracker
package.domain = org.lessontracker

source.dir = .
source.include_exts = py,png,jpg,html,css,js
version = 0.4

# webview bootstrap — встроенный Android WebView, Kivy не нужен
requirements = python3,flask

orientation = portrait
fullscreen = 0

android.permissions = INTERNET
android.api = 34
android.minapi = 24
android.archs = arm64-v8a
android.allow_backup = 1
android.accept_sdk_license = True
android.ndk = 25c

# webview bootstrap + порт
p4a.bootstrap = webview
p4a.port = 5000

[buildozer]
log_level = 2
warn_on_root = 1
