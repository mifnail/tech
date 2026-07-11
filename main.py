"""
main.py — точка входа Kivy-приложения «Учёт занятий» (LessonTracker).

Экраны:
    * v0.2 — HomeScreen: перечень предметов; прогресс проведённых/оставшихся
      ЗАНЯТИЙ нарисован ПРОГРЕСС-БАРОМ на фоне ЗА НАЗВАНИЕМ предмета (canvas.before).
      Строка предмета КЛИКАБЕЛЬНА → открывает проведение занятия (v0.4).
    * v0.3 — AddSubjectScreen: ввод нового предмета (название, план в занятиях,
      выбор группы из существующих ИЛИ ввод новой).
    * v0.3 — StudentsScreen: массовый ввод студентов группы (каждый с новой строки)
      + показ уже существующих (неповторяемость: существующий выбирается, не дублируется).
    * v0.4 — LessonScreen: «Занятие проведено?» → отметка присутствующих НАЖАТИЕМ на
      ФИО (тап циклически: отсутствует → присутствует ✓ → оценка 5→4→3→2 → отсутствует).
      Неотмеченные сохраняются как отсутствующие.
    * v0.4 — напоминание раз в час (Kivy Clock) с вопросом «Заполнить занятие?».

Принципы (см. AGENT.md):
    * Никаких matplotlib/numpy/pillow — только средства Kivy (canvas).
    * Весь доступ к БД — через database.py. Здесь SQL НЕТ.
    * Единица учёта — ЗАНЯТИЕ (не час): planned / held / remaining.

Внимание (см. docs/MIGRATION / ROADMAP): напоминание через Clock работает, пока
приложение живо/в фоне. Гарантированные срабатывания после закрытия приложения —
это Android AlarmManager/WorkManager через pyjnius (задача миграции, не v0.4).

Запуск локально на ПК:
    python main.py
(предварительно один раз создать БД: python seed_db.py)
"""
from datetime import date, datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp, sp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.uix.screenmanager import ScreenManager, Screen

from database import Database

DB_PATH = "lessons.db"

# Приятный размер окна на ПК (на Android игнорируется — там fullscreen).
Window.size = (420, 720)

NEW_GROUP_OPTION = "➕ Новая группа…"

# Период напоминания — раз в час (в секундах). Вынесено в константу для наглядности.
REMINDER_PERIOD_SEC = 60 * 60


# --------------------------------------------------------------------- theme
# Единая цветовая тема приложения. Все экраны используют эти цвета.
class Theme:
    BG          = (0.97, 0.97, 0.98, 1)  # фон приложения
    CARD        = (1, 1, 1, 1)           # карточка/строка
    CARD_BORDER = (0.88, 0.88, 0.90, 1)  # граница карточки
    CARD_SHADOW = (0.87, 0.87, 0.89, 1)  # тень карточки (подложка)

    TEXT        = (0.12, 0.12, 0.12, 1)
    TEXT_MUTED  = (0.45, 0.45, 0.45, 1)
    TEXT_BRIGHT = (1, 1, 1, 1)

    PRIMARY     = (0.30, 0.55, 0.82, 1)  # основной акцент (синий)
    SUCCESS     = (0.30, 0.70, 0.35, 1)  # успех / проведено (зелёный)
    DANGER      = (0.75, 0.25, 0.25, 1)  # отмена / ошибка (красный)
    WARNING     = (0.85, 0.65, 0.20, 1)  # предупреждение (жёлтый)

    PROGRESS_BG    = (0.90, 0.90, 0.92, 1)
    PROGRESS_FILL  = (0.45, 0.75, 0.50, 1)
    PROGRESS_FILL_OVER = (0.90, 0.55, 0.35, 1)  # при > 100%

    # Цвета оценок: 5=отлично(зелёный) .. 2=плохо(красный)
    GRADE_COLORS = {5: (0.20, 0.60, 0.25), 4: (0.30, 0.55, 0.85),
                    3: (0.85, 0.65, 0.20), 2: (0.80, 0.25, 0.25)}

    # Фоны строк отметки посещаемости
    ATT_DEFAULT_BG = (0.93, 0.93, 0.94, 1)
    ATT_PRESENT_BG = (0.75, 0.90, 0.75, 1)  # or (0.80, 0.92, 0.80, 1) original
    ATT_GRADE_BG   = {5: (0.20, 0.60, 0.25), 4: (0.20, 0.40, 0.75),
                      3: (0.50, 0.50, 0.50), 2: (0.10, 0.10, 0.10)}

    LESSON_STATUS = {
        "scheduled": ("по расписанию", PRIMARY),
        "held":      ("проведено ✓", SUCCESS),
        "cancelled": ("отменено ✕", DANGER),
    }


def make_button(text: str, color=None, width=None, callback=None):
    """Создаёт кнопку в едином стиле приложения."""
    btn = Button(
        text=text,
        background_color=color or Theme.PRIMARY,
        background_normal="",
        color=Theme.TEXT_BRIGHT,
        bold=True,
        size_hint_x=width,
    )
    with btn.canvas.before:
        Color(*Theme.CARD_SHADOW)
        btn._shadow_rect = Rectangle(pos=(btn.x, btn.y - 2), size=(btn.width, btn.height))
    def _update(inst, _val):
        inst._shadow_rect.pos = (inst.x, inst.y - 2)
        inst._shadow_rect.size = inst.size
    btn.bind(pos=_update, size=_update)
    if callback:
        btn.bind(on_release=callback)
    return btn


def card_bg(widget):
    """Добавляет фон-карточку (с подложкой-тенью) виджету."""
    with widget.canvas.before:
        Color(*Theme.CARD_SHADOW)
        _shadow = Rectangle(pos=(widget.x, widget.y - 2), size=widget.size)
        Color(*Theme.CARD)
        _card = Rectangle(pos=widget.pos, size=widget.size)
    widget._card_shadow = _shadow
    widget._card_rect = _card
    widget.bind(pos=_card_update, size=_card_update)


def _card_update(inst, _val):
    inst._card_shadow.pos = (inst.x, inst.y - 2)
    inst._card_shadow.size = inst.size
    inst._card_rect.pos = inst.pos
    inst._card_rect.size = inst.size


def get_db() -> Database:
    """Единая точка получения подключения к БД. SQL — только внутри database.py."""
    db = Database(DB_PATH)
    db.init_schema()  # безопасно, если БД ещё пустая
    return db


# ---------------------------------------------------------------- главный экран
class SubjectRow(ButtonBehavior, BoxLayout):
    """
    Одна строка списка предметов (КЛИКАБЕЛЬНА — открывает проведение занятия).

    Фон строки = прогресс-бар: слева направо закрашивается доля проведённых
    занятий (held / planned). Полоса рисуется в canvas.before, поэтому
    название предмета и цифры находятся ПОВЕРХ неё.
    """

    def __init__(self, subject: dict, on_press_row, **kwargs):
        super().__init__(orientation="vertical", size_hint_y=None, height=96,
                         padding=(16, 12), spacing=4, **kwargs)
        self.subject = subject
        self._on_press_row = on_press_row

        planned = int(subject.get("planned", 0)) or 0
        held = int(subject.get("held", 0)) or 0
        self.progress = (held / planned) if planned > 0 else 0.0

        # --- Фон-карточка + прогресс-бар (всё в canvas.before) ---
        with self.canvas.before:
            Color(*Theme.CARD_SHADOW)
            self._shadow = Rectangle(pos=(self.x, self.y - 2), size=self.size)
            Color(*Theme.PROGRESS_BG)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
            fill_color = Theme.PROGRESS_FILL_OVER if self.progress > 1.0 else Theme.PROGRESS_FILL
            Color(*fill_color)
            self._fill_rect = Rectangle(pos=self.pos, size=(0, self.height))

        self.bind(pos=self._redraw, size=self._redraw)

        # --- Содержимое поверх фона ---
        title = Label(
            text=f"[b]{subject['name']}[/b]  ({subject.get('group_name', '')})",
            markup=True, color=Theme.TEXT,
            halign="left", valign="middle", size_hint_y=None, height=36,
        )
        title.bind(size=lambda inst, val: setattr(inst, "text_size", val))

        remaining = subject.get("remaining", max(0, planned - held))
        info = Label(
            text=f"Проведено: {held} / {planned}   •   Осталось: {remaining}   "
                 f"({int(round(self.progress * 100))}%)",
            color=Theme.TEXT_MUTED,
            halign="left", valign="middle", size_hint_y=None, height=26, font_size=13,
        )
        info.bind(size=lambda inst, val: setattr(inst, "text_size", val))

        self.add_widget(title)
        self.add_widget(info)

    def on_release(self):
        if self._on_press_row:
            self._on_press_row(self.subject)

    def _redraw(self, *_):
        self._shadow.pos = (self.x, self.y - 2)
        self._shadow.size = self.size
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        self._fill_rect.pos = self.pos
        self._fill_rect.size = (self.width * self.progress, self.height)


class HomeScreen(Screen):
    """Главный экран: заголовок, кнопка «+ Предмет» и прокручиваемый список предметов."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = BoxLayout(orientation="vertical",
                         padding=(dp(12), dp(6), dp(12), dp(6)),
                         spacing=dp(6))

        header = BoxLayout(orientation="horizontal", size_hint_y=None,
                           height=dp(52), spacing=dp(10))
        title = Label(text="[b]Мои предметы[/b]", markup=True,
                      font_size=sp(20), color=Theme.TEXT,
                      halign="left", valign="middle", size_hint_x=0.55)
        title.bind(size=lambda i, v: setattr(i, "text_size", v))
        header.add_widget(title)
        add_btn = Button(text="+ Предмет", font_size=sp(15), bold=True,
                         background_color=Theme.PRIMARY, background_normal="",
                         color=Theme.TEXT_BRIGHT, size_hint_x=0.45,
                         size_hint_y=1)
        add_btn.bind(on_release=lambda *_: self._go("add_subject"))
        header.add_widget(add_btn)
        root.add_widget(header)

        nav = BoxLayout(orientation="horizontal", size_hint_y=None,
                        height=dp(46), spacing=dp(10))
        today_btn = Button(text="Расписание", font_size=sp(15), bold=True,
                           background_color=Theme.PRIMARY, background_normal="",
                           color=Theme.TEXT_BRIGHT, size_hint_x=0.5,
                           size_hint_y=1)
        today_btn.bind(on_release=lambda *_: self._go("today"))
        grades_btn = Button(text="Ведомость", font_size=sp(15), bold=True,
                            background_color=Theme.SUCCESS, background_normal="",
                            color=Theme.TEXT_BRIGHT, size_hint_x=0.5,
                            size_hint_y=1)
        grades_btn.bind(on_release=lambda *_: self._go("gradebook"))
        nav.add_widget(today_btn)
        nav.add_widget(grades_btn)
        root.add_widget(nav)

        self.content = BoxLayout(orientation="vertical")
        root.add_widget(self.content)

        self.add_widget(root)

    def _go(self, screen: str):
        if self.manager:
            self.manager.current = screen

    def on_pre_enter(self, *_):
        self.content.clear_widgets()

        db = get_db()
        subjects = db.list_subjects()
        db.close()

        if not subjects:
            self.content.add_widget(Widget(size_hint_y=1))
            lbl1 = Label(text="Предметов пока нет.",
                         halign="center", valign="middle", color=Theme.TEXT_MUTED,
                         font_size=sp(16), size_hint_y=None, height=dp(30))
            lbl1.bind(size=lambda i, v: setattr(i, "text_size", v))
            self.content.add_widget(lbl1)
            lbl2 = Label(text="Нажмите «+ Предмет», чтобы добавить.",
                         halign="center", valign="middle", color=Theme.TEXT_MUTED,
                         font_size=sp(13), size_hint_y=None, height=dp(24))
            lbl2.bind(size=lambda i, v: setattr(i, "text_size", v))
            self.content.add_widget(lbl2)
            self.content.add_widget(Widget(size_hint_y=1))
        else:
            scroll = ScrollView()
            container = BoxLayout(orientation="vertical", size_hint_y=None,
                                  spacing=dp(6))
            container.bind(minimum_height=container.setter("height"))
            for subj in subjects:
                container.add_widget(SubjectRow(subj, on_press_row=self._open_lesson))
            scroll.add_widget(container)
            self.content.add_widget(scroll)

    def _open_lesson(self, subject: dict):
        self._go("today")


# ------------------------------------------------------------- ввод предмета
class AddSubjectScreen(Screen):
    """Ввод нового предмета: название, план в занятиях, выбор/создание группы."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = BoxLayout(orientation="vertical",
                         padding=(dp(12), dp(6), dp(12), dp(6)),
                         spacing=dp(8))

        root.add_widget(Label(text="[b]Новый предмет[/b]", markup=True, font_size=sp(20),
                              color=Theme.TEXT, size_hint_y=None, height=dp(44)))

        root.add_widget(Label(text="Название предмета:", size_hint_y=None, height=dp(22),
                              halign="left", color=Theme.TEXT, font_size=sp(14)))
        self.name_input = TextInput(multiline=False, size_hint_y=None, height=dp(40),
                                    font_size=sp(15), padding=(dp(8), dp(8), dp(8), dp(8)))
        root.add_widget(self.name_input)

        root.add_widget(Label(text="План (в занятиях):", size_hint_y=None, height=dp(22),
                              halign="left", color=Theme.TEXT, font_size=sp(14)))
        self.planned_input = TextInput(multiline=False, input_filter="int",
                                       size_hint_y=None, height=dp(40), text="0",
                                       font_size=sp(15), padding=(dp(8), dp(8), dp(8), dp(8)))
        root.add_widget(self.planned_input)

        root.add_widget(Label(text="Группа:", size_hint_y=None, height=dp(22),
                              halign="left", color=Theme.TEXT, font_size=sp(14)))
        self.group_spinner = Spinner(
            text=NEW_GROUP_OPTION,
            values=[NEW_GROUP_OPTION],
            size_hint_y=None, height=dp(40), font_size=sp(14),
        )
        self.group_spinner.bind(text=self._on_group_change)
        root.add_widget(self.group_spinner)

        self.new_group_input = TextInput(
            multiline=False, size_hint_y=None, height=dp(40),
            hint_text="Название новой группы", font_size=sp(14),
            padding=(dp(8), dp(8), dp(8), dp(8)),
        )
        self.new_group_input.opacity = 0
        self.new_group_input.disabled = True
        root.add_widget(self.new_group_input)

        self.status = Label(text="", size_hint_y=None, height=dp(24),
                            color=Theme.DANGER, font_size=sp(13))
        root.add_widget(self.status)

        root.add_widget(Widget(size_hint_y=1))

        buttons = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(48),
                            spacing=dp(8))
        back = Button(text="Назад", font_size=sp(14), bold=True,
                      background_color=Theme.TEXT_MUTED, background_normal="",
                      color=Theme.TEXT_BRIGHT, size_hint_x=0.5, size_hint_y=1)
        back.bind(on_release=lambda *_: self._go("home"))
        save = Button(text="Сохранить", font_size=sp(14), bold=True,
                      background_color=Theme.SUCCESS, background_normal="",
                      color=Theme.TEXT_BRIGHT, size_hint_x=0.5, size_hint_y=1)
        save.bind(on_release=self._save)
        buttons.add_widget(back)
        buttons.add_widget(save)
        root.add_widget(buttons)

        self.add_widget(root)

    def _go(self, screen: str):
        if self.manager:
            self.manager.current = screen

    def on_pre_enter(self, *_):
        db = get_db()
        groups = [g["name"] for g in db.list_groups()]
        db.close()
        self.group_spinner.values = groups + [NEW_GROUP_OPTION]
        if groups:
            self.group_spinner.text = groups[0]
        else:
            self.group_spinner.text = NEW_GROUP_OPTION
            self._show_new_group(True)

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
        self._go("students")


# ------------------------------------------------------------- ввод студентов
class StudentsScreen(Screen):
    """Массовый ввод студентов группы + список уже существующих (неповторяемость)."""

    target_group = ""  # какую группу редактируем (задаётся перед входом)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = BoxLayout(orientation="vertical",
                         padding=(dp(12), dp(6), dp(12), dp(6)),
                         spacing=dp(8))

        self._header_label = Label(
            text="", markup=True,
            font_size=sp(18), color=Theme.TEXT, size_hint_y=None, height=dp(40),
        )
        root.add_widget(self._header_label)

        root.add_widget(Label(
            text="Уже в группе:", size_hint_y=None, height=dp(22),
            halign="left", color=Theme.TEXT, font_size=sp(14),
        ))
        self._exist_scroll = ScrollView(size_hint_y=0.35)
        self._exist_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(2))
        self._exist_box.bind(minimum_height=self._exist_box.setter("height"))
        self._exist_scroll.add_widget(self._exist_box)
        root.add_widget(self._exist_scroll)

        root.add_widget(Label(
            text="Добавить студентов (каждый с новой строки):",
            size_hint_y=None, height=dp(22), halign="left", color=Theme.TEXT,
            font_size=sp(14),
        ))
        self.bulk_input = TextInput(multiline=True, hint_text="Иванов Иван\nПетров Пётр\n…",
                                    font_size=sp(14), padding=(dp(8), dp(8), dp(8), dp(8)))
        root.add_widget(self.bulk_input)

        self.status = Label(text="", size_hint_y=None, height=dp(24),
                            color=Theme.SUCCESS, font_size=sp(13))
        root.add_widget(self.status)

        buttons = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(48),
                            spacing=dp(10))
        home = Button(text="На главный", font_size=sp(15), bold=True,
                      background_color=Theme.TEXT_MUTED, background_normal="",
                      color=Theme.TEXT_BRIGHT, size_hint_x=0.5, size_hint_y=1)
        home.bind(on_release=lambda *_: self._go("home"))
        add = Button(text="Добавить", font_size=sp(15), bold=True,
                     background_color=Theme.SUCCESS, background_normal="",
                     color=Theme.TEXT_BRIGHT, size_hint_x=0.5, size_hint_y=1)
        add.bind(on_release=self._add_bulk)
        buttons.add_widget(home)
        buttons.add_widget(add)
        root.add_widget(buttons)

        self.add_widget(root)

    def _go(self, screen: str):
        if self.manager:
            self.manager.current = screen

    def on_pre_enter(self, *_):
        self._header_label.text = f"[b]Студенты группы {self.target_group}[/b]"

        db = get_db()
        existing = [s["name"] for s in db.list_students(self.target_group)]
        db.close()

        self._exist_box.clear_widgets()
        if existing:
            for nm in existing:
                lbl = Label(text=nm, size_hint_y=None, height=dp(26), halign="left",
                            valign="middle", color=Theme.TEXT, font_size=sp(14))
                lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
                self._exist_box.add_widget(lbl)
        else:
            self._exist_box.add_widget(Label(text="— пока никого —", size_hint_y=None,
                                              height=dp(26), color=Theme.TEXT_MUTED))
        self.bulk_input.text = ""
        self.status.text = ""

    def _add_bulk(self, *_):
        lines = self.bulk_input.text.split("\n")
        db = get_db()
        added = db.add_students_bulk(self.target_group, lines)  # дубликаты игнорируются
        db.close()
        self.status.text = f"Добавлено новых: {added} (дубликаты пропущены)."
        self.bulk_input.text = ""
        # Обновить список существующих
        self.on_pre_enter()


# ------------------------------------------------- проведение занятия (v0.4)
# Порядок циклической смены статуса по нажатию на ФИО студента.
# 'absent'  — отсутствует (по умолчанию, если по ФИО не нажимали)
# 'present' — присутствует, только «галочка», без оценки
#  5,4,3,2  — присутствует + оценка
ATTENDANCE_CYCLE = ["absent", "present", 5, 4, 3, 2]


def cycle_idx_from_saved(saved: dict | None) -> int:
    """
    Преобразует сохранённую в БД отметку студента в индекс ATTENDANCE_CYCLE,
    чтобы при повторном открытии занятия строка сразу отражала сохранённое состояние.
      нет записи / present=False → 'absent'
      present=True, grade=None   → 'present' (галочка)
      present=True, grade=N      → соответствующая оценка
    """
    if not saved or not saved.get("present"):
        return 0
    grade = saved.get("grade")
    if grade is None:
        return 1
    try:
        return ATTENDANCE_CYCLE.index(int(grade))
    except (ValueError, TypeError):
        return 1


class StudentAttendanceRow(ButtonBehavior, Label):
    """
    Строка студента на занятии. Нажатие ЦИКЛИЧЕСКИ меняет статус
    (см. ATTENDANCE_CYCLE). Текст и цвет фона отражают текущий статус.
    """

    def __init__(self, student: dict, initial_idx: int = 0, on_change=None, **kwargs):
        super().__init__(size_hint_y=None, height=48, markup=True,
                         halign="left", valign="middle", **kwargs)
        self.student = student
        self._cycle_idx = initial_idx
        self._on_change = on_change
        self.bind(size=lambda inst, val: setattr(inst, "text_size", val))

        with self.canvas.before:
            self._bg_color = Color(*Theme.ATT_DEFAULT_BG)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._redraw, size=self._redraw)

        self._render()

    @property
    def att_state(self):
        # ВНИМАНИЕ: нельзя называть это свойство `state` — оно конфликтует с
        # ButtonBehavior.state (Kivy при нажатии делает self.state = 'down').
        return ATTENDANCE_CYCLE[self._cycle_idx]

    def on_release(self):
        # Каждое нажатие — следующий статус по кругу...
        self._cycle_idx = (self._cycle_idx + 1) % len(ATTENDANCE_CYCLE)
        self._render()
        # ...и сразу синхронизируем с БД (auto-save), чтобы ничего не терялось.
        if self._on_change:
            self._on_change(self)

    def _render(self):
        st = self.att_state
        name = self.student["name"]
        if st == "absent":
            self.text = f"  {name}   —   отсутствует"
            self._bg_color.rgba = Theme.ATT_DEFAULT_BG
            self.color = Theme.TEXT_MUTED
        elif st == "present":
            self.text = f"  {name}   ✓ присутствует"
            self._bg_color.rgba = Theme.ATT_PRESENT_BG
            self.color = Theme.SUCCESS
        else:
            self.text = f"  {name}   ✓  оценка: [b]{st}[/b]"
            self._bg_color.rgba = Theme.ATT_GRADE_BG.get(st, (0.50, 0.50, 0.50))
            self.color = Theme.TEXT if st == 3 else Theme.TEXT_BRIGHT

    def _redraw(self, *_):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size


class LessonScreen(Screen):
    """
    Проведение занятия по выбранному предмету:
      1) вопрос «Занятие проведено?» (да/нет);
      2) при «да» — отметка присутствующих нажатием на ФИО;
      3) сохранение: неотмеченные записываются как отсутствующие.
    """

    # id КОНКРЕТНОГО занятия (задаётся перед входом на экране расписания).
    # Вопрос «Занятие проведено?» теперь задаётся на TodayScheduleScreen; сюда
    # попадаем уже для проведённого занятия, поэтому при входе статус → 'held'.
    lesson_id = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = BoxLayout(orientation="vertical",
                         padding=(dp(12), dp(6), dp(12), dp(6)),
                         spacing=dp(6))
        self._header = Label(
            text="", markup=True, font_size=sp(18), color=Theme.TEXT,
            size_hint_y=None, height=dp(40),
        )
        root.add_widget(self._header)
        self._body = BoxLayout(orientation="vertical", spacing=dp(8))
        root.add_widget(self._body)
        self.add_widget(root)

    def on_pre_enter(self, *_):
        self._show_attendance()

    def _show_attendance(self, *_):
        self._body.clear_widgets()
        self._rows = []

        db = get_db()
        self._lesson_id = self.lesson_id
        lesson = db.get_lesson(self._lesson_id) if self._lesson_id else None
        if not lesson:
            db.close()
            self._body.add_widget(Label(
                text="Занятие не найдено.", halign="center", valign="middle",
                color=Theme.DANGER,
            ))
            return
        db.set_lesson_status(self._lesson_id, "held")
        self._header.text = f"[b]{lesson['subject_name']}[/b]  ({lesson['group_name']})"
        students = db.list_students(lesson["group_name"])
        saved = db.get_attendance(self._lesson_id)
        db.close()

        if not students:
            self._body.add_widget(Label(
                text="В группе нет студентов.\nДобавьте их через «+ Предмет».",
                halign="center", valign="middle", color=Theme.TEXT_MUTED,
            ))
            return

        self._body.add_widget(Label(
            text="Нажимайте на ФИО: отсутствует → ✓ → оценка 5→4→3→2 → отсутствует\n"
                 "Отметки сохраняются автоматически.",
            font_size=sp(12), color=Theme.TEXT_MUTED, size_hint_y=None, height=dp(36),
        ))

        scroll = ScrollView()
        box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4),
                        padding=[0, dp(4)])
        box.bind(minimum_height=box.setter("height"))
        for st in students:
            initial_idx = cycle_idx_from_saved(saved.get(st["id"]))
            row = StudentAttendanceRow(st, initial_idx=initial_idx, on_change=self._persist_row)
            self._rows.append(row)
            box.add_widget(row)
        scroll.add_widget(box)
        self._body.add_widget(scroll)

        save = Button(text="Готово", font_size=sp(15), bold=True,
                      background_color=Theme.SUCCESS, background_normal="",
                      color=Theme.TEXT_BRIGHT, size_hint_y=None, height=dp(48))
        save.bind(on_release=self._finish_lesson)
        self._body.add_widget(save)

    def _persist_row(self, row) -> None:
        """Немедленно сохранить отметку одного студента (auto-save при каждом тапе)."""
        db = get_db()
        self._write_row(db, row)
        db.close()

    def _write_row(self, db, row) -> None:
        """Записать текущее состояние строки в БД (UPSERT по lesson_id+student_id)."""
        st = row.att_state
        sid = row.student["id"]
        if st == "absent":
            db.mark_attendance(self._lesson_id, sid, present=False, grade=None)
        elif st == "present":
            db.mark_attendance(self._lesson_id, sid, present=True, grade=None)
        else:  # оценка
            db.mark_attendance(self._lesson_id, sid, present=True, grade=int(st))

    def _finish_lesson(self, *_):
        """
        Завершить отметку занятия: неотмеченные (нетронутые) явно фиксируются как
        отсутствующие, затем возврат на главный (прогресс-бар обновится).
        Само занятие уже создано при входе, отметки — уже сохранены по мере нажатий.
        """
        db = get_db()
        for row in self._rows:
            self._write_row(db, row)
        db.close()

        Popup(title="Готово",
              content=Label(text="Занятие и отметки сохранены."),
              size_hint=(0.8, 0.3)).open()
        # Возврат на экран расписания сегодняшнего дня (откуда мы и пришли).
        self._go("today")


# --------------------------------------------------- расписание на сегодня
# Статусы занятия и их отображение на экране расписания.
LESSON_STATUS_LABEL = {
    "scheduled": ("по расписанию", Theme.PRIMARY),
    "held":      ("проведено ✓", Theme.SUCCESS),
    "cancelled": ("отменено ✕", Theme.DANGER),
}


class TodayScheduleScreen(Screen):
    """
    ОТДЕЛЬНЫЙ от сводного главного экран: список занятий ЗА СЕГОДНЯ по всем предметам
    (данные из БД — list_schedule_for_date). По одному предмету в день может быть
    НЕСКОЛЬКО занятий (в т.ч. параллельных).

    Логика тапа по занятию по расписанию:
      «Проведено?» → Да  → отметка присутствия/оценок (LessonScreen по этому lesson_id);
                   → Нет → «Заменить на другое?» (выбор другого предмета) / «Отменить»
                            (занятие помечается cancelled — в учёт проведённых НЕ идёт).
    Плюс кнопки: «➕ ДОБАВИТЬ ЗАНЯТИЕ» (внеочередное на сегодня) и выгрузка расписания
    в .ics (Google/Яндекс).
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = BoxLayout(orientation="vertical",
                         padding=(dp(12), dp(6), dp(12), dp(6)),
                         spacing=dp(6))

        header = BoxLayout(orientation="horizontal", size_hint_y=None,
                           height=dp(52), spacing=dp(10))
        back = Button(text="← Назад", font_size=sp(15), bold=True,
                      background_color=Theme.TEXT_MUTED, background_normal="",
                      color=Theme.TEXT_BRIGHT, size_hint_x=0.3, size_hint_y=1)
        back.bind(on_release=lambda *_: self._go("home"))
        header.add_widget(back)
        hdr_label = Label(text="[b]Сегодня[/b]", markup=True, font_size=sp(20),
                          color=Theme.TEXT, size_hint_x=0.7)
        header.add_widget(hdr_label)
        root.add_widget(header)
        root.add_widget(Label(
            text=date.today().strftime("%d.%m.%Y"), size_hint_y=None, height=dp(22),
            color=Theme.TEXT_MUTED, font_size=sp(14),
        ))

        self.content = BoxLayout(orientation="vertical")
        root.add_widget(self.content)

        actions = BoxLayout(orientation="horizontal", size_hint_y=None,
                            height=dp(52), spacing=dp(10))
        add_les = Button(text="+ ДОБАВИТЬ", font_size=sp(15), bold=True,
                         background_color=Theme.SUCCESS, background_normal="",
                         color=Theme.TEXT_BRIGHT, size_hint_x=0.6, size_hint_y=1)
        add_les.bind(on_release=self._add_lesson_dialog)
        export = Button(text="ICS", font_size=sp(15), bold=True,
                        background_color=Theme.PRIMARY, background_normal="",
                        color=Theme.TEXT_BRIGHT, size_hint_x=0.4, size_hint_y=1)
        export.bind(on_release=self._export_calendar)
        actions.add_widget(add_les)
        actions.add_widget(export)
        root.add_widget(actions)

        self.add_widget(root)

    def _go(self, screen: str):
        if self.manager:
            self.manager.current = screen

    def on_pre_enter(self, *_):
        self.content.clear_widgets()

        db = get_db()
        lessons = db.list_schedule_for_date(date.today().isoformat())
        db.close()

        scroll = ScrollView()
        box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8))
        box.bind(minimum_height=box.setter("height"))
        if not lessons:
            box.add_widget(Label(
                text="На сегодня занятий нет.\nНажмите «ДОБАВИТЬ ЗАНЯТИЕ».",
                halign="center", valign="middle", color=Theme.TEXT_MUTED,
                size_hint_y=None, height=100, font_size=15,
            ))
        else:
            for les in lessons:
                box.add_widget(self._lesson_row(les))
        scroll.add_widget(box)
        self.content.add_widget(scroll)

    def _lesson_row(self, les: dict):
        """
        Одна строка занятия: слева — время/предмет(группа)/статус/счётчик отметок,
        справа — кнопка «Открыть» (тап открывает диалог «Проведено?»).
        """
        status_text, status_color = LESSON_STATUS_LABEL.get(
            les["status"], (les["status"], (0.3, 0.3, 0.3, 1))
        )
        held_at = les.get("held_at", "")
        time_str = held_at.split("T", 1)[1][:5] if "T" in held_at else ""

        wrap = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(72),
                         spacing=dp(8))
        card_bg(wrap)

        inner = BoxLayout(orientation="vertical", padding=(dp(10), dp(6), dp(10), dp(6)),
                          spacing=dp(2))
        title = Label(
            text=f"[b]{time_str}  {les['subject_name']}[/b]  ({les['group_name']})",
            markup=True, color=Theme.TEXT, halign="left", valign="middle",
            size_hint_y=None, height=28,
        )
        title.bind(size=lambda i, v: setattr(i, "text_size", v))
        sub = Label(
            text=f"{status_text}   •   отмечено: {les['present_count']}, "
                 f"с оценкой: {les['graded_count']}",
            color=status_color, halign="left", valign="middle",
            size_hint_y=None, height=22, font_size=12,
        )
        sub.bind(size=lambda i, v: setattr(i, "text_size", v))
        inner.add_widget(title)
        inner.add_widget(sub)

        open_btn = Button(text="Открыть", font_size=sp(13), bold=True,
                          background_color=Theme.PRIMARY, background_normal="",
                          color=Theme.TEXT_BRIGHT, size_hint_x=0.28, size_hint_y=0.7)
        open_btn.bind(on_release=lambda *_: self._on_lesson_tap(les))

        wrap.add_widget(inner)
        wrap.add_widget(open_btn)
        return wrap

    def _on_lesson_tap(self, les: dict):
        """Тап по занятию: «Проведено?» да/нет (см. описание класса)."""
        content = BoxLayout(orientation="vertical", spacing=10, padding=10)
        content.add_widget(Label(
            text=f"{les['subject_name']} ({les['group_name']})\nЗанятие проведено?"
        ))
        btns = BoxLayout(size_hint_y=None, height=44, spacing=8)
        popup = Popup(title="Занятие", content=content, size_hint=(0.85, 0.4))

        yes = Button(text="Да", background_color=(0.4, 0.7, 0.4, 1))
        yes.bind(on_release=lambda *_: (popup.dismiss(), self._open_marking(les)))
        no = Button(text="Нет")
        no.bind(on_release=lambda *_: (popup.dismiss(), self._not_held_dialog(les)))
        btns.add_widget(no)
        btns.add_widget(yes)
        content.add_widget(btns)
        popup.open()

    def _open_marking(self, les: dict):
        lesson_screen = self.manager.get_screen("lesson")
        lesson_screen.lesson_id = les["id"]
        self._go("lesson")

    def _not_held_dialog(self, les: dict):
        """«Нет» → Заменить на другой предмет / Отменить занятие."""
        content = BoxLayout(orientation="vertical", spacing=10, padding=10)
        content.add_widget(Label(text="Занятие не проведено.\nЧто сделать?"))
        btns = BoxLayout(size_hint_y=None, height=44, spacing=8)
        popup = Popup(title="Не проведено", content=content, size_hint=(0.85, 0.42))

        replace = Button(text="Заменить на другое")
        replace.bind(on_release=lambda *_: (popup.dismiss(), self._replace_dialog(les)))
        cancel = Button(text="Отменить", background_color=(0.8, 0.4, 0.4, 1))
        cancel.bind(on_release=lambda *_: (popup.dismiss(), self._cancel_lesson(les)))
        btns.add_widget(replace)
        btns.add_widget(cancel)
        content.add_widget(btns)
        popup.open()

    def _cancel_lesson(self, les: dict):
        """Пометить занятие отменённым (в учёт проведённых НЕ идёт; запись остаётся)."""
        db = get_db()
        db.set_lesson_status(les["id"], "cancelled")
        db.close()
        self.on_pre_enter()

    def _replace_dialog(self, les: dict):
        """Выбор другого предмета для этого занятия (замена)."""
        db = get_db()
        subjects = db.list_subjects()
        db.close()
        names = [f"{s['name']} ({s['group_name']})" for s in subjects]
        id_by_label = {f"{s['name']} ({s['group_name']})": s["id"] for s in subjects}

        content = BoxLayout(orientation="vertical", spacing=10, padding=10)
        content.add_widget(Label(text="Заменить занятие на предмет:",
                                 size_hint_y=None, height=24))
        spinner = Spinner(text=names[0] if names else "нет предметов",
                          values=names, size_hint_y=None, height=44)
        content.add_widget(spinner)
        btns = BoxLayout(size_hint_y=None, height=44, spacing=8)
        popup = Popup(title="Замена", content=content, size_hint=(0.9, 0.45))
        ok = Button(text="Заменить", background_color=(0.4, 0.7, 0.4, 1))

        def _do(*_):
            if spinner.text in id_by_label:
                db2 = get_db()
                db2.change_lesson_subject(les["id"], id_by_label[spinner.text])
                db2.close()
            popup.dismiss()
            self.on_pre_enter()

        ok.bind(on_release=_do)
        close = Button(text="Отмена")
        close.bind(on_release=popup.dismiss)
        btns.add_widget(close)
        btns.add_widget(ok)
        content.add_widget(btns)
        popup.open()

    def _add_lesson_dialog(self, *_):
        """➕ Внеочередное занятие на сегодня: выбор предмета + время начала."""
        db = get_db()
        subjects = db.list_subjects()
        db.close()
        names = [f"{s['name']} ({s['group_name']})" for s in subjects]
        id_by_label = {f"{s['name']} ({s['group_name']})": s["id"] for s in subjects}

        content = BoxLayout(orientation="vertical", spacing=10, padding=10)
        content.add_widget(Label(text="Предмет:", size_hint_y=None, height=22))
        spinner = Spinner(text=names[0] if names else "нет предметов",
                          values=names, size_hint_y=None, height=44)
        content.add_widget(spinner)
        content.add_widget(Label(text="Время начала (ЧЧ:ММ):",
                                 size_hint_y=None, height=22))
        time_input = TextInput(text=datetime.now().strftime("%H:%M"),
                               multiline=False, size_hint_y=None, height=40)
        content.add_widget(time_input)
        btns = BoxLayout(size_hint_y=None, height=44, spacing=8)
        popup = Popup(title="Новое занятие", content=content, size_hint=(0.9, 0.5))
        ok = Button(text="Добавить", background_color=(0.4, 0.7, 0.4, 1))

        def _do(*_):
            if spinner.text in id_by_label:
                hhmm = time_input.text.strip() or datetime.now().strftime("%H:%M")
                held_at = f"{date.today().isoformat()}T{hhmm}:00"
                db2 = get_db()
                # Внеочередное занятие создаём сразу как проведённое (status='held'):
                # оно фактически проводится и подлежит учёту.
                db2.add_lesson(id_by_label[spinner.text], held_at, status="held")
                db2.close()
            popup.dismiss()
            self.on_pre_enter()

        ok.bind(on_release=_do)
        close = Button(text="Отмена")
        close.bind(on_release=popup.dismiss)
        btns.add_widget(close)
        btns.add_widget(ok)
        content.add_widget(btns)
        popup.open()

    def _export_calendar(self, *_):
        """Выгрузить занятия из БД в .ics (Google/Яндекс)."""
        from calendar_export import export_ics

        db = get_db()
        lessons = db.list_lessons_for_calendar()
        db.close()
        path = "schedule.ics"
        export_ics(lessons, path)
        Popup(title="Экспорт в календарь",
              content=Label(text=f"Расписание выгружено в файл:\n{path}\n\n"
                                 f"Импортируйте его в Google/Яндекс Календарь."),
              size_hint=(0.9, 0.4)).open()


# ------------------------------------------------------- ведомость (v0.5)
class GradeBarChart(BoxLayout):
    """
    Простая СТОЛБЧАТАЯ диаграмма среднего балла по студентам средствами Kivy `canvas`
    (без matplotlib). Высота столбца пропорциональна среднему баллу по шкале 2..5.
    Рисуется в canvas.after поверх виджета; подписи (ФИО/балл) — отдельными Label.
    """

    def __init__(self, data: list[dict], **kwargs):
        super().__init__(orientation="vertical", size_hint_y=None, height=240, **kwargs)
        # data — только студенты, у которых есть средний балл (avg_grade не None).
        self._data = [d for d in data if d.get("avg_grade") is not None]
        with self.canvas.before:
            Color(*Theme.CARD)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size
        self.canvas.after.clear()
        # Удаляем прежние подписи (пересоздаём при каждом перерисовывании).
        self.clear_widgets()
        if not self._data:
            self.add_widget(Label(text="Нет выставленных оценок для диаграммы.",
                                  color=Theme.TEXT_MUTED))
            return

        n = len(self._data)
        pad = 10
        gap = 8
        base_y = self.y + 34            # место снизу под подписи ФИО
        top_pad = 24                    # место сверху под цифру балла
        avail_w = self.width - 2 * pad
        avail_h = self.height - 34 - top_pad
        bar_w = max(8.0, (avail_w - gap * (n - 1)) / n)

        # Шкала: 2..5 → 0..1 (минимальная оценка 2 = «дно» столбца).
        def norm(v):
            return max(0.0, min(1.0, (v - 2.0) / 3.0))

        grade_color = Theme.GRADE_COLORS
        with self.canvas.after:
            for i, d in enumerate(self._data):
                avg = float(d["avg_grade"])
                x = self.x + pad + i * (bar_w + gap)
                h = avail_h * norm(avg)
                r, g, b = grade_color.get(int(round(avg)), (0.4, 0.4, 0.4))
                Color(r, g, b, 1)
                Rectangle(pos=(x, base_y), size=(bar_w, h))
                # Подпись балла над столбцом.
                lbl = Label(text=f"{avg:.2f}", font_size=11, color=Theme.TEXT,
                            size_hint=(None, None), size=(bar_w + gap, 20),
                            halign="center", valign="middle")
                lbl.pos = (x - gap / 2, base_y + h + 2)
                self.add_widget(lbl)
                # Короткая подпись ФИО под столбцом (фамилия).
                short = d["name"].split()[0] if d["name"] else ""
                name_lbl = Label(text=short, font_size=10, color=Theme.TEXT_MUTED,
                                 size_hint=(None, None), size=(bar_w + gap, 30),
                                 halign="center", valign="top")
                name_lbl.text_size = (bar_w + gap, 30)
                name_lbl.pos = (x - gap / 2, self.y)
                self.add_widget(name_lbl)


class GradebookScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = BoxLayout(orientation="vertical",
                         padding=(dp(12), dp(6), dp(12), dp(6)),
                         spacing=dp(6))

        header = BoxLayout(orientation="horizontal", size_hint_y=None,
                           height=dp(52), spacing=dp(10))
        back = Button(text="← Назад", font_size=sp(15), bold=True,
                      background_color=Theme.TEXT_MUTED, background_normal="",
                      color=Theme.TEXT_BRIGHT, size_hint_x=0.3, size_hint_y=1)
        back.bind(on_release=lambda *_: self._go("home"))
        header.add_widget(back)
        header.add_widget(Label(text="[b]Ведомость[/b]", markup=True, font_size=sp(20),
                                color=Theme.TEXT, size_hint_x=0.7))
        root.add_widget(header)

        self._spinner = Spinner(text="", values=[], size_hint_y=None, height=dp(44))
        self._spinner.bind(text=lambda *_: self._render_subject())
        root.add_widget(self._spinner)

        self._content = BoxLayout(orientation="vertical")
        root.add_widget(self._content)

        self.add_widget(root)

    def _go(self, screen: str):
        if self.manager:
            self.manager.current = screen

    def on_pre_enter(self, *_):
        db = get_db()
        subjects = db.list_subjects()
        db.close()
        self._subjects = subjects
        self._label_to_id = {
            f"{s['name']} ({s['group_name']})": s["id"] for s in subjects
        }

        if not subjects:
            self._content.clear_widgets()
            self._content.add_widget(Label(
                text="Предметов пока нет.\nДобавьте предмет и проведите занятия.",
                halign="center", valign="middle", color=Theme.TEXT_MUTED,
            ))
            return

        labels = list(self._label_to_id.keys())
        self._spinner.values = labels
        if self._spinner.text not in labels:
            self._spinner.text = labels[0]
        self._render_subject()

    def _render_subject(self, *_):
        self._content.clear_widgets()
        subject_id = self._label_to_id.get(self._spinner.text)
        if subject_id is None:
            return

        db = get_db()
        summary = db.subject_summary(subject_id)
        gradebook = db.subject_gradebook(subject_id)
        db.close()

        # --- Сводка по занятиям (план/проведено/осталось) ---
        if summary:
            self._content.add_widget(Label(
                text=f"Занятия: план [b]{summary['planned']}[/b]  •  "
                     f"проведено [b]{summary['held']}[/b]  •  "
                     f"осталось [b]{summary['remaining']}[/b]",
                markup=True, size_hint_y=None, height=30, color=Theme.TEXT,
            ))

        # --- Средний балл по предмету в целом ---
        all_avgs = [d["avg_grade"] for d in gradebook if d["avg_grade"] is not None]
        overall = round(sum(all_avgs) / len(all_avgs), 2) if all_avgs else None
        self._content.add_widget(Label(
            text=(f"Средний балл по предмету: [b]{overall}[/b]" if overall is not None
                  else "Средний балл по предмету: —"),
            markup=True, size_hint_y=None, height=26, color=Theme.TEXT,
        ))

        # --- Диаграмма (Kivy canvas) ---
        self._content.add_widget(Label(text="[b]Средний балл по студентам[/b]",
                                       markup=True, size_hint_y=None, height=24,
                                       color=Theme.TEXT))
        self._content.add_widget(GradeBarChart(gradebook))

        # --- Пофамильная таблица ---
        self._content.add_widget(Label(text="[b]Пофамильно[/b]", markup=True,
                                       size_hint_y=None, height=24,
                                       color=Theme.TEXT))
        # Заголовок таблицы.
        head = BoxLayout(orientation="horizontal", size_hint_y=None, height=26,
                         padding=(6, 0))
        for text, w in (("ФИО", 0.5), ("Ср. балл", 0.2),
                        ("Оценок", 0.15), ("Прис./Отс.", 0.15)):
            head.add_widget(Label(text=f"[b]{text}[/b]", markup=True, size_hint_x=w,
                                  color=Theme.TEXT_MUTED, font_size=12))
        self._content.add_widget(head)

        scroll = ScrollView()
        box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=1)
        box.bind(minimum_height=box.setter("height"))
        for d in gradebook:
            box.add_widget(self._student_row(d))
        scroll.add_widget(box)
        self._content.add_widget(scroll)

    def _student_row(self, d: dict):
        row = BoxLayout(orientation="horizontal", size_hint_y=None, height=32,
                        padding=(6, 0))
        avg_text = f"{d['avg_grade']:.2f}" if d["avg_grade"] is not None else "—"
        cells = (
            (d["name"], 0.5, "left"),
            (avg_text, 0.2, "center"),
            (str(d["grades_count"]), 0.15, "center"),
            (f"{d['present_count']}/{d['absent_count']}", 0.15, "center"),
        )
        for text, w, align in cells:
            lbl = Label(text=text, size_hint_x=w, color=Theme.TEXT,
                        halign=align, valign="middle", font_size=13)
            lbl.bind(size=lambda i, v: setattr(i, "text_size", v))
            row.add_widget(lbl)
        return row


# ------------------------------------------------------------------------- app
class LessonTrackerApp(App):
    title = "Учёт занятий"

    def build(self):
        Window.clearcolor = Theme.BG
        self.sm = ScreenManager()
        self.sm.add_widget(HomeScreen(name="home"))
        self.sm.add_widget(AddSubjectScreen(name="add_subject"))
        self.sm.add_widget(StudentsScreen(name="students"))
        self.sm.add_widget(TodayScheduleScreen(name="today"))
        self.sm.add_widget(GradebookScreen(name="gradebook"))
        self.sm.add_widget(LessonScreen(name="lesson"))

        # Напоминание раз в час, пока приложение живо/в фоне (см. примечание в шапке файла).
        Clock.schedule_interval(self._hourly_reminder, REMINDER_PERIOD_SEC)
        return self.sm

    def _hourly_reminder(self, *_):
        """Раз в час спрашивает, не нужно ли заполнить проведённое занятие."""
        content = BoxLayout(orientation="vertical", spacing=10, padding=10)
        content.add_widget(Label(text="Пора отметить занятие?\nЗаполните проведённое занятие."))
        btns = BoxLayout(size_hint_y=None, height=44, spacing=8)
        popup = Popup(title="Напоминание", content=content, size_hint=(0.85, 0.4))
        later = Button(text="Позже")
        later.bind(on_release=popup.dismiss)
        go = Button(text="К предметам", background_color=(0.4, 0.7, 0.4, 1))

        def _go(*_):
            popup.dismiss()
            self.sm.current = "today"

        go.bind(on_release=_go)
        btns.add_widget(later)
        btns.add_widget(go)
        content.add_widget(btns)
        popup.open()


def main():
    LessonTrackerApp().run()


if __name__ == "__main__":
    main()