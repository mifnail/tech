# buildozer.spec — сборка Android APK (webview bootstrap)
# Flask + p4a webview bootstrap → Android WebView → HTML/CSS/JS SPA.
# Kivy ПОЛНОСТЬЮ удалён.

[app]
title = Учёт занятий
package.name = teachhelper4
package.domain = com.teachhelper4

source.dir = .
source.include_exts = py,png,jpg,html,css,js,txt,db
version = 0.1

# webview bootstrap — встроенный Android WebView, Kivy не нужен
# NOTE: reportlab НЕ включаем: его рецепт тянет freetype с download.savannah.gnu.org,
# который лежит (502/timeout) и роняет сборку. PDF-экспорт на устройстве отдаёт
# понятную ошибку, рабочие форматы — XLSX (openpyxl, pure-python) и CSV.
# workflow повторяет сборку до 5 раз с backoff (см. build-apk.yml).
requirements = python3,flask,openpyxl

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

# Стабильная подпись: один ключ на все сборки -> обновления ставятся без конфликта.
# Ключ лежит в репо (личное приложение, уровень доверия как у shared debug key).
# ВАЖНО: уже установленный APK подписан другим (одноразовым debug-ключом CI),
# поэтому нужен ОДИН ручной снос/переустановка — дальше обновления сами.
android.release_keystore = release.keystore
android.release_keystore_password = teachhelper
android.release_key_password = teachhelper
android.release_keyalias = teachhelper
# APK, а не AAB: файл нужен для ручной установки на устройство (.aab сюда не грузится)
android.release_artifact = apk

# webview bootstrap + порт
p4a.bootstrap = webview
p4a.port = 5000
android.gradle_dependencies = androidx.webkit:webkit:1.8.0

[buildozer]
log_level = 2
warn_on_root = 1
