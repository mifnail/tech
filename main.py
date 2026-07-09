"""
main.py — точка входа Kivy-приложения «Учёт занятий» (LessonTracker).

Экраны:
    * v0.2 — HomeScreen: перечень предметов; прогресс проведённых/оставшихся
      ЗАНЯТИЙ нарисован ПРОГРЕСС-БАРОМ на фоне ЗА НАЗВАНИЕМ предмета (canvas.before).
    * v0.3 — AddSubjectScreen: ввод нового предмета (название, план в занятиях,
      выбор группы из существующих ИЛИ ввод новой).
    * v0.3 — StudentsScreen: массовый ввод студентов группы (каждый с новой строки)
      + показ уже существующих (неповторяемость: существующий выбирается, не дублируется).

Принципы (см. AGENT.md):
    * Никаких matplotlib/numpy/pillow — только средства Kivy (canvas).
    * Весь доступ к БД — через database.py. Здесь SQL НЕТ.
    * Единица учёта — ЗАНЯТИЕ (не час): planned / held / remaining.

Запуск локально на ПК:
    python main.py
(предварительно один раз создать БД: python seed_db.py)
"""
from kivy.app import App
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.screenmanager import ScreenManager, Screen

from database import Database

DB_PATH = "lessons.db"

# Приятный размер окна на ПК (на Android игнорируется — там fullscreen).
Window.size = (420, 720)

NEW_GROUP_OPTION = "➕ Новая группа…"


def get_db() -> Database:
    """Единая точка получения подключения к БД. SQL — только внутри database.py."""
    db = Database(DB_PATH)
    db.init_schema()  # безопасно, если БД ещё пустая
    return db


# ---------------------------------------------------------------- главный экран
class SubjectRow(BoxLayout):
    """
    Одна строка списка предметов.

    Фон строки = прогресс-бар: слева направо закрашивается доля проведённых
    занятий (held / planned). Полоса рисуется в canvas.before, поэтому
    название предмета и цифры находятся ПОВЕРХ неё.
    """

    def __init__(self, subject: dict, **kwargs):
        super().__init__(orientation="vertical", size_hint_y=None, height=88,
                         padding=(16, 10), spacing=2, **kwargs)
        self.subject = subject

        planned = int(subject.get("planned", 0)) or 0
        held = int(subject.get("held", 0)) or 0
        self.progress = (held / planned) if planned > 0 else 0.0

        # --- Фон-прогрессбар (рисуется ДО содержимого) ---
        with self.canvas.before:
            Color(0.90, 0.90, 0.92, 1)                       # незаполненная часть
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
            Color(0.55, 0.80, 0.55, 1)                       # заполненная часть
            self._fill_rect = Rectangle(pos=self.pos, size=(0, self.height))

        self.bind(pos=self._redraw, size=self._redraw)

        # --- Содержимое поверх фона ---
        title = Label(
            text=f"[b]{subject['name']}[/b]  ({subject.get('group_name', '')})",
            markup=True, color=(0.1, 0.1, 0.1, 1),
            halign="left", valign="middle", size_hint_y=None, height=34,
        )
        title.bind(size=lambda inst, val: setattr(inst, "text_size", val))

        remaining = subject.get("remaining", max(0, planned - held))
        info = Label(
            text=f"Проведено: {held} / {planned}   •   Осталось: {remaining}   "
                 f"({int(round(self.progress * 100))}%)",
            color=(0.2, 0.2, 0.2, 1),
            halign="left", valign="middle", size_hint_y=None, height=26, font_size=13,
        )
        info.bind(size=lambda inst, val: setattr(inst, "text_size", val))

        self.add_widget(title)
        self.add_widget(info)

    def _redraw(self, *_):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        self._fill_rect.pos = self.pos
        self._fill_rect.size = (self.width * self.progress, self.height)


class HomeScreen(Screen):
    """Главный экран: заголовок, кнопка «+ Предмет» и прокручиваемый список предметов."""

    def on_pre_enter(self, *_):
        """Перестраиваем список при каждом входе (данные могли измениться)."""
        self.clear_widgets()
        root = BoxLayout(orientation="vertical")

        # Шапка с кнопкой добавления предмета
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=52,
                           padding=(12, 6), spacing=8)
        header.add_widget(Label(text="[b]Мои предметы[/b]", markup=True, font_size=20,
                                color=(0.1, 0.1, 0.1, 1), halign="left", valign="middle"))
        add_btn = Button(text="+ Предмет", size_hint_x=None, width=120)
        add_btn.bind(on_release=lambda *_: setattr(self.manager, "current", "add_subject"))
        header.add_widget(add_btn)
        root.add_widget(header)

        db = get_db()
        subjects = db.list_subjects()
        db.close()

        if not subjects:
            root.add_widget(Label(
                text="Предметов пока нет.\nНажмите «+ Предмет», чтобы добавить.",
                halign="center", valign="middle", color=(0.4, 0.4, 0.4, 1),
            ))
        else:
            scroll = ScrollView()
            container = BoxLayout(orientation="vertical", size_hint_y=None,
                                  spacing=8, padding=(8, 8))
            container.bind(minimum_height=container.setter("height"))
            for subj in subjects:
                container.add_widget(SubjectRow(subj))
            scroll.add_widget(container)
            root.add_widget(scroll)

        self.add_widget(root)


# ------------------------------------------------------------- ввод предмета
class AddSubjectScreen(Screen):
    """Ввод нового предмета: название, план в занятиях, выбор/создание группы."""

    def on_pre_enter(self, *_):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical", padding=16, spacing=10)
        root.add_widget(Label(text="[b]Новый предмет[/b]", markup=True, font_size=20,
                              color=(0.1, 0.1, 0.1, 1), size_hint_y=None, height=40))

        # Название предмета
        root.add_widget(Label(text="Название предмета:", size_hint_y=None, height=22,
                              halign="left", color=(0.2, 0.2, 0.2, 1)))
        self.name_input = TextInput(multiline=False, size_hint_y=None, height=40)
        root.add_widget(self.name_input)

        # План в занятиях
        root.add_widget(Label(text="План (в занятиях):", size_hint_y=None, height=22,
                              halign="left", color=(0.2, 0.2, 0.2, 1)))
        self.planned_input = TextInput(multiline=False, input_filter="int",
                                       size_hint_y=None, height=40, text="0")
        root.add_widget(self.planned_input)

        # Группа: выбор существующей ИЛИ новая
        root.add_widget(Label(text="Группа:", size_hint_y=None, height=22,
                              halign="left", color=(0.2, 0.2, 0.2, 1)))
        db = get_db()
        groups = [g["name"] for g in db.list_groups()]
        db.close()
        self.group_spinner = Spinner(
            text=groups[0] if groups else NEW_GROUP_OPTION,
            values=groups + [NEW_GROUP_OPTION],
            size_hint_y=None, height=40,
        )
        self.group_spinner.bind(text=self._on_group_change)
        root.add_widget(self.group_spinner)

        # Поле для новой группы (показывается только при выборе «Новая группа…»)
        self.new_group_input = TextInput(
            multiline=False, size_hint_y=None, height=40,
            hint_text="Название новой группы",
        )
        self.new_group_input.opacity = 0
        self.new_group_input.disabled = True
        if not groups:
            self._show_new_group(True)
        root.add_widget(self.new_group_input)

        # Статус/ошибки
        self.status = Label(text="", size_hint_y=None, height=24,
                            color=(0.7, 0.2, 0.2, 1))
        root.add_widget(self.status)

        root.add_widget(BoxLayout())  # распорка

        # Кнопки
        buttons = BoxLayout(orientation="horizontal", size_hint_y=None, height=48, spacing=8)
        back = Button(text="Назад")
        back.bind(on_release=lambda *_: setattr(self.manager, "current", "home"))
        save = Button(text="Сохранить", background_color=(0.4, 0.7, 0.4, 1))
        save.bind(on_release=self._save)
        buttons.add_widget(back)
        buttons.add_widget(save)
        root.add_widget(buttons)

        self.add_widget(root)

    def _on_group_change(self, _spinner, value):
        self._show_new_group(value == NEW_GROUP_OPTION)

    def _show_new_group(self, show: bool):
        self.new_group_input.opacity = 1 if show else 0
        self.new_group_input.disabled = not show

    def _resolve_group_name(self) -> str:
        if self.group_spinner.text == NEW_GROUP_OPTION:
            return self.new_group_input.text.strip()
        return self.group_spinner.text.strip()

    def _save(self, *_):
        name = self.name_input.text.strip()
        group = self._resolve_group_name()
        try:
            planned = int(self.planned_input.text or "0")
        except ValueError:
            planned = 0

        if not name:
            self.status.text = "Укажите название предмета."
            return
        if not group:
            self.status.text = "Укажите или выберите группу."
            return

        db = get_db()
        db.add_subject(name, planned, group)     # add_subject сам создаёт группу при нужде
        db.close()

        # После создания предмета — сразу перейти к вводу студентов этой группы.
        students_screen = self.manager.get_screen("students")
        students_screen.target_group = group
        self.manager.current = "students"


# ------------------------------------------------------------- ввод студентов
class StudentsScreen(Screen):
    """Массовый ввод студентов группы + список уже существующих (неповторяемость)."""

    target_group = ""  # какую группу редактируем (задаётся перед входом)

    def on_pre_enter(self, *_):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical", padding=16, spacing=10)

        root.add_widget(Label(
            text=f"[b]Студенты группы {self.target_group}[/b]", markup=True,
            font_size=18, color=(0.1, 0.1, 0.1, 1), size_hint_y=None, height=40,
        ))

        # Уже существующие студенты (их не нужно вводить повторно)
        db = get_db()
        existing = [s["name"] for s in db.list_students(self.target_group)]
        db.close()

        root.add_widget(Label(
            text=f"Уже в группе ({len(existing)}):", size_hint_y=None, height=22,
            halign="left", color=(0.2, 0.2, 0.2, 1),
        ))
        exist_scroll = ScrollView(size_hint_y=0.35)
        exist_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=2)
        exist_box.bind(minimum_height=exist_box.setter("height"))
        if existing:
            for nm in existing:
                lbl = Label(text=nm, size_hint_y=None, height=26, halign="left",
                            valign="middle", color=(0.15, 0.15, 0.15, 1))
                lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
                exist_box.add_widget(lbl)
        else:
            exist_box.add_widget(Label(text="— пока никого —", size_hint_y=None,
                                       height=26, color=(0.5, 0.5, 0.5, 1)))
        exist_scroll.add_widget(exist_box)
        root.add_widget(exist_scroll)

        # Массовый ввод: каждый студент с новой строки
        root.add_widget(Label(
            text="Добавить студентов (каждый с новой строки):",
            size_hint_y=None, height=22, halign="left", color=(0.2, 0.2, 0.2, 1),
        ))
        self.bulk_input = TextInput(multiline=True, hint_text="Иванов Иван\nПетров Пётр\n…")
        root.add_widget(self.bulk_input)

        self.status = Label(text="", size_hint_y=None, height=24,
                            color=(0.2, 0.5, 0.2, 1))
        root.add_widget(self.status)

        buttons = BoxLayout(orientation="horizontal", size_hint_y=None, height=48, spacing=8)
        home = Button(text="На главный")
        home.bind(on_release=lambda *_: setattr(self.manager, "current", "home"))
        add = Button(text="Добавить", background_color=(0.4, 0.7, 0.4, 1))
        add.bind(on_release=self._add_bulk)
        buttons.add_widget(home)
        buttons.add_widget(add)
        root.add_widget(buttons)

        self.add_widget(root)

    def _add_bulk(self, *_):
        lines = self.bulk_input.text.split("\n")
        db = get_db()
        added = db.add_students_bulk(self.target_group, lines)  # дубликаты игнорируются
        db.close()
        self.status.text = f"Добавлено новых: {added} (дубликаты пропущены)."
        self.bulk_input.text = ""
        # Обновить список существующих
        self.on_pre_enter()


# ------------------------------------------------------------------------- app
class LessonTrackerApp(App):
    title = "Учёт занятий"

    def build(self):
        Window.clearcolor = (0.97, 0.97, 0.98, 1)
        sm = ScreenManager()
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(AddSubjectScreen(name="add_subject"))
        sm.add_widget(StudentsScreen(name="students"))
        return sm


def main():
    LessonTrackerApp().run()


if __name__ == "__main__":
    main()