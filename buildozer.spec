# buildozer.spec — сборка Android APK (webview bootstrap)
# Flask + p4a webview bootstrap → Android WebView → HTML/CSS/JS SPA.
# Kivy ПОЛНОСТЬЮ удалён.

[app]
title = Учёт занятий
package.name = teachhelper4
package.domain = com.teachhelper4

source.dir = .
source.include_exts = py,png,jpg,html,css,js,txt
version = 0.1

# webview bootstrap — встроенный Android WebView, Kivy не нужен
requirements = python3,flask

orientation = portrait
fullscreen = 0

osx.python_version = 3
osx.kivy_version = 2.2.0
presplash.filename =
icon.filename =

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
android.gradle_dependencies = androidx.webkit:webkit:1.8.0

[buildozer]
log_level = 2
warn_on_root = 1
