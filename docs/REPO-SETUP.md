# REPO-SETUP — упаковка репозитория для людей

Пошагово: открой → вставь → сохрани. Всё делается в веб-интерфейсе GitHub, код не трогаем.

## 1. About (главная страница репо → шестерёнка «Edit repository details»)

- **Description** (вставить):
  ```
  Электронный журнал преподавателя: группы, занятия, оценки, посещаемость, экспорт ведомостей. Работает офлайн на Android и в браузере.
  ```
- **Website** (вставить):
  ```
  https://github.com/mifnail/tech/releases/latest
  ```
  Появится ссылка «Latest release» — оттуда скачивают APK.

## 2. Topics (там же, поле Topics — вписать 14 штук через запятую)

```
python, flask, sqlite, rest-api, vanilla-js, react, typescript, android, buildozer, teacher-tools, education, gradebook, telegram-bot, offline-first
```

Логика: стек (`python flask sqlite rest-api react typescript buildozer`), платформа (`android offline-first`), назначение (`education teacher-tools gradebook`), интеграции (`telegram-bot`). `vanilla-js` — пока жив `static/app.js`; удалите вместе с legacy-фронтом.

## 3. Pages — НЕ включаем

Бейдж приватности ведёт прямой ссылкой на `docs/PRIVACY.md`, Pages не нужен.

## 4. Скриншоты (ждёт фото с телефона)

Снять PNG на телефоне и положить в `docs/screenshots/` с именами:

| Файл | Экран |
|---|---|
| `today.png` | Главная |
| `lesson.png` | Занятие с оценками |
| `statement.png` | Ведомость |
| `schedule.png` | Расписание (по желанию) |

`README.md` уже ссылается на первые три — как только файлы лягут, таблица «Как выглядит» оживёт сама.

## 5. Релизы (автомат, руками ничего не делать)

Каждый пуш в `main` → workflow «Build debug APK» → GitHub Release `v0.N` + подписанный APK + `latest`-ссылка. Версия приложения (`VERSION`, подпись в Настройках) проставляется из номера сборки автоматически.
