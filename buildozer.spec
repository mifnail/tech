[app]
title = Учёт занятий
package.name = teachhelper4
package.domain = com.teachhelper4
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,html,js,css,txt
version = 0.1
requirements = python3,flask
orientation = portrait
osx.python_version = 3
osx.kivy_version = 2.2.0
presplash.filename =
icon.filename =
android.api = 34
android.minapi = 24
android.ndk = 25c
p4a.bootstrap = webview
android.gradle_dependencies = androidx.webkit:webkit:1.8.0
android.add_src =
android.permissions = INTERNET
android.archs = arm64-v8a
android.wakelock = True
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
