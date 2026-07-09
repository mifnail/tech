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
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.screenmanager import ScreenManager, Screen

from database import Database

DB_PATH = "lessons.db"

# Приятный размер окна на ПК (на Android игнорируется — там fullscreen).
Window.size = (420, 720)

NEW_GROUP_OPTION = "➕ Новая группа…"

# Период напоминания — раз в час (в секундах). Вынесено в константу для наглядности.
REMINDER_PERIOD_SEC = 60 * 60


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
        super().__init__(orientation="vertical", size_hint_y=None, height=88,
                         padding=(16, 10), spacing=2, **kwargs)
        self.subject = subject
        self._on_press_row = on_press_row

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

    def on_release(self):
        # Клик по строке предмета → передаём выбранный предмет наверх.
        if self._on_press_row:
            self._on_press_row(self.subject)

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
                container.add_widget(SubjectRow(subj, on_press_row=self._open_lesson))
            scroll.add_widget(container)
            root.add_widget(scroll)

        self.add_widget(root)

    def _open_lesson(self, subject: dict):
        """Открыть экран проведения занятия для выбранного предмета."""
        lesson_screen = self.manager.get_screen("lesson")
        lesson_screen.subject = subject
        self.manager.current = "lesson"


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
        super().__init__(size_hint_y=None, height=44, markup=True,
                         halign="left", valign="middle", **kwargs)
        self.student = student
        self._cycle_idx = initial_idx  # начальное состояние из БД (по умолч. 'absent')
        self._on_change = on_change    # колбэк авто-сохранения при каждом нажатии
        self.bind(size=lambda inst, val: setattr(inst, "text_size", val))

        with self.canvas.before:
            self._bg_color = Color(0.93, 0.93, 0.94, 1)
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
            rgb = (0.93, 0.93, 0.94)
            self.color = (0.45, 0.45, 0.45, 1)
        elif st == "present":
            self.text = f"  {name}   ✓ присутствует"
            rgb = (0.80, 0.92, 0.80)
            self.color = (0.1, 0.3, 0.1, 1)
        else:  # оценка — цвет фона зависит от балла (по требованию владельца)
            self.text = f"  {name}   ✓  оценка: [b]{st}[/b]"
            # 5 — красный, 4 — синий, 3 — серый, 2 — чёрный.
            grade_bg = {
                5: (0.85, 0.20, 0.20),   # красный
                4: (0.20, 0.35, 0.80),   # синий
                3: (0.55, 0.55, 0.55),   # серый
                2: (0.10, 0.10, 0.10),   # чёрный
            }
            rgb = grade_bg.get(st, (0.55, 0.55, 0.55))
            # На тёмном фоне (синий/чёрный/красный) — белый текст; на сером — тёмный.
            self.color = (0.15, 0.15, 0.15, 1) if st == 3 else (1, 1, 1, 1)
        self._bg_color.rgb = rgb

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

    subject = None  # dict выбранного предмета (задаётся перед входом)

    def on_pre_enter(self, *_):
        self.clear_widgets()
        self._rows = []
        subj = self.subject or {}
        root = BoxLayout(orientation="vertical", padding=16, spacing=10)

        root.add_widget(Label(
            text=f"[b]{subj.get('name', '')}[/b]  ({subj.get('group_name', '')})",
            markup=True, font_size=18, color=(0.1, 0.1, 0.1, 1),
            size_hint_y=None, height=36,
        ))
        root.add_widget(Label(
            text="Занятие проведено?", font_size=16,
            color=(0.2, 0.2, 0.2, 1), size_hint_y=None, height=30,
        ))

        # Кнопки «да/нет»
        yn = BoxLayout(orientation="horizontal", size_hint_y=None, height=48, spacing=8)
        no_btn = Button(text="Нет")
        no_btn.bind(on_release=lambda *_: setattr(self.manager, "current", "home"))
        yes_btn = Button(text="Да, отметить", background_color=(0.4, 0.7, 0.4, 1))
        yes_btn.bind(on_release=self._show_attendance)
        yn.add_widget(no_btn)
        yn.add_widget(yes_btn)
        root.add_widget(yn)

        # Контейнер, куда после «Да» подставим список студентов.
        self._body = BoxLayout(orientation="vertical", spacing=8)
        root.add_widget(self._body)

        self.add_widget(root)

    def _show_attendance(self, *_):
        """
        Показать список студентов группы для отметки нажатием на ФИО.

        Ключевая логика (по требованию — «каждое нажатие синхронизируется с БД»):
          1) занятие на СЕГОДНЯ для этого предмета берётся через get_or_create_lesson
             (один вход = одно занятие в день, повторный вход НЕ плодит дубли и не
             завышает счётчик проведённых);
          2) уже сохранённые отметки/оценки подтягиваются из БД и проставляются в строки;
          3) каждый тап по ФИО тут же пишется в БД (см. _persist_row) — поэтому
             повторное «Да, отметить» перечитывает актуальные данные и ничего не теряет.
        """
        self._body.clear_widgets()
        self._rows = []

        db = get_db()
        # 1) занятие за сегодня (get-or-create) — фиксируем факт проведения.
        self._lesson_id = db.get_or_create_lesson(
            self.subject["id"], date.today().isoformat(), datetime.now().isoformat()
        )
        students = db.list_students(self.subject.get("group_name", ""))
        # 2) сохранённые ранее отметки этого занятия.
        saved = db.get_attendance(self._lesson_id)
        db.close()

        if not students:
            self._body.add_widget(Label(
                text="В группе нет студентов.\nДобавьте их через «+ Предмет».",
                halign="center", valign="middle", color=(0.5, 0.5, 0.5, 1),
            ))
            return

        self._body.add_widget(Label(
            text="Нажимайте на ФИО: отсутствует → ✓ → оценка 5→4→3→2 → отсутствует\n"
                 "Отметки сохраняются автоматически.",
            font_size=12, color=(0.4, 0.4, 0.4, 1), size_hint_y=None, height=36,
        ))

        scroll = ScrollView()
        box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=4, padding=(0, 4))
        box.bind(minimum_height=box.setter("height"))
        for st in students:
            initial_idx = cycle_idx_from_saved(saved.get(st["id"]))
            row = StudentAttendanceRow(st, initial_idx=initial_idx, on_change=self._persist_row)
            self._rows.append(row)
            box.add_widget(row)
        scroll.add_widget(box)
        self._body.add_widget(scroll)

        # Кнопка «Готово»: дозаписывает неотмеченных как отсутствующих и уходит на главный.
        save = Button(text="Готово", size_hint_y=None, height=48,
                      background_color=(0.4, 0.7, 0.4, 1))
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
        self.manager.current = "home"


# ------------------------------------------------------------------------- app
class LessonTrackerApp(App):
    title = "Учёт занятий"

    def build(self):
        Window.clearcolor = (0.97, 0.97, 0.98, 1)
        self.sm = ScreenManager()
        self.sm.add_widget(HomeScreen(name="home"))
        self.sm.add_widget(AddSubjectScreen(name="add_subject"))
        self.sm.add_widget(StudentsScreen(name="students"))
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
            self.sm.current = "home"

        go.bind(on_release=_go)
        btns.add_widget(later)
        btns.add_widget(go)
        content.add_widget(btns)
        popup.open()


def main():
    LessonTrackerApp().run()


if __name__ == "__main__":
    main()