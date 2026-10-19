import BookArt from "./components/BookArt";
import ModalShell from "./components/ModalShell";
import { useEffect, useState } from "react";
import Icon, { type IconName } from "./components/Icon";
import {
  loadStore,
  TODAY,
  formatDate,
  subjects,
  type Group,
  type Lesson,
  type Store,
} from "./data";

type Page =
  "home" | "groups" | "subjects" | "schedule" | "reports" | "settings";
type Modal =
  | { type: "lesson"; lesson: Lesson }
  | { type: "newLesson" }
  | { type: "group"; group?: Group }
  | { type: "help" }
  | { type: "backup" }
  | null;
const nav: { id: Page; label: string; icon: IconName }[] = [
  { id: "home", label: "Обзор", icon: "home" },
  { id: "groups", label: "Группы", icon: "users" },
  { id: "subjects", label: "Предметы", icon: "book" },
  { id: "schedule", label: "Расписание", icon: "calendar" },
  { id: "reports", label: "Отчёты", icon: "chart" },
];

export default function App() {
  const [store, setStore] = useState<Store>(loadStore);
  const [page, setPage] = useState<Page>("home");
  const [modal, setModal] = useState<Modal>(null);
  const [selectedDay, setSelectedDay] = useState(TODAY);
  const [subjectFilter, setSubjectFilter] = useState("");
  const [weekOffset, setWeekOffset] = useState(0);
  const [search, setSearch] = useState("");
  const [selectedGroup, setSelectedGroup] = useState<number | null>(null);
  const [notifications, setNotifications] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [toast, setToast] = useState("");
  const [exporting, setExporting] = useState(false);
  const [semester, setSemester] = useState("1 семестр, 2026–2027");
  const [reportGroup, setReportGroup] = useState("all");
  const [reportMonth, setReportMonth] = useState("2026-09");
  const [studentQuery, setStudentQuery] = useState("");
  const [storageError, setStorageError] = useState(false);
  useEffect(() => {
    try {
      localStorage.setItem("teachhelper-v2", JSON.stringify(store));
      setStorageError(false);
    } catch {
      setStorageError(true);
    }
  }, [store]);
  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(""), 4000);
    return () => clearTimeout(id);
  }, [toast]);
  function go(next: Page) {
    setPage(next);
    setSearch("");
    setSubjectFilter("");
    setSelectedGroup(null);
    setMobileNav(false);
    setNotifications(false);
    window.scrollTo(0, 0);
  }
  const groupName = (id: number) =>
    store.groups.find((g) => g.id === id)?.name || "Группа";
  const dayLessons = store.lessons
    .filter(
      (l) =>
        l.date === selectedDay && (!subjectFilter || l.title === subjectFilter),
    )
    .sort((a, b) => a.time.localeCompare(b.time));
  const todayLessons = store.lessons.filter((l) => l.date === TODAY);
  const current = todayLessons.find((l) => l.status === "current");
  const done = todayLessons.filter((l) => l.status === "done").length;
  const reportLessons = store.lessons.filter(
    (l) =>
      l.date.slice(0, 7) === reportMonth &&
      (reportGroup === "all" || l.groupId === Number(reportGroup)),
  );
  const reportGrades = Object.keys(store.grades)
    .filter((key) => reportLessons.some((l) => key.startsWith(l.id + "-")))
    .map((key) => store.grades[key])
    .filter((g) => g !== "—");
  const numericGrades = reportGrades
    .filter((g) => ["2", "3", "4", "5"].indexOf(g) >= 0)
    .map(Number);
  const average = numericGrades.length
    ? (numericGrades.reduce((a, b) => a + b, 0) / numericGrades.length)
        .toFixed(1)
        .replace(".", ",")
    : "—";
  const attendance = reportGrades.length
    ? Math.round(
        (reportGrades.filter((g) => g !== "Н").length / reportGrades.length) *
          100,
      ) + "%"
    : "—";
  async function exportExcel() {
    setExporting(true);
    try {
      const { default: writeXlsxFile } =
        await import("write-excel-file/browser");
      const rows: any[][] = [
        [
          ...[
            "Дата",
            "Предмет",
            "Группа",
            "Студент",
            "Оценка / посещаемость",
          ].map((value) => ({
            value,
            fontWeight: "bold",
            backgroundColor: "#EAF2ED",
          })),
        ],
      ];
      reportLessons.forEach((l) => {
        store.students
          .filter((s) => s.groupId === l.groupId)
          .forEach((s) =>
            rows.push(
              [
                l.date,
                l.title,
                groupName(l.groupId),
                s.name,
                store.grades[`${l.id}-${s.id}`] || "—",
              ].map((value) => ({ type: String, value })),
            ),
          );
      });
      const blob = await writeXlsxFile(rows, {
        columns: [
          { width: 14 },
          { width: 34 },
          { width: 12 },
          { width: 28 },
          { width: 24 },
        ],
      }).toBlob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "teachhelper-" + reportMonth + ".xlsx";
      document.body.appendChild(anchor);
      anchor.click();
      setTimeout(() => {
        anchor.remove();
        URL.revokeObjectURL(url);
      }, 1000);
      setToast("Ведомость Excel подготовлена");
    } catch {
      setToast("Не удалось выгрузить файл. Попробуйте ещё раз.");
    } finally {
      setExporting(false);
    }
  }
  function backup() {
    const blob = new Blob([JSON.stringify(store, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "teachhelper-backup.json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    setToast("Резервная копия сохранена");
    setModal(null);
  }
  function openLesson(l: Lesson) {
    setStudentQuery("");
    setModal({ type: "lesson", lesson: l });
  }
  function changeLessonStatus(id: number, status: Lesson["status"]) {
    setStore((s) => ({
      ...s,
      lessons: s.lessons.map((l) => (l.id === id ? { ...l, status } : l)),
    }));
    setModal(null);
    setToast(
      status === "done"
        ? "Занятие завершено. Оценки сохранены"
        : "Занятие отменено",
    );
  }
  function cycleGrade(lessonId: number, studentId: number, direction: number) {
    const values = ["—", "0", "5", "4", "3", "2", "Н"];
    const key = `${lessonId}-${studentId}`;
    setStore((s) => {
      const old = values.indexOf(s.grades[key] || "—");
      return {
        ...s,
        grades: {
          ...s.grades,
          [key]: values[(old + direction + values.length) % values.length],
        },
      };
    });
  }
  const dateLabel = new Date(selectedDay + "T12:00:00").toLocaleDateString(
    "ru-RU",
    { weekday: "long", day: "numeric", month: "long" },
  );
  const weekDays = Array.from({ length: 7 }, (_, i) => {
    const d = new Date("2026-09-14T12:00:00");
    d.setDate(d.getDate() + weekOffset * 7 + i);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  });
  function weekStep(dir: number) {
    setWeekOffset((o) => o + dir);
    const d = new Date(selectedDay + "T12:00:00");
    d.setDate(d.getDate() + dir * 7);
    setSelectedDay(
      `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`,
    );
  }
  function groupCard(g: Group) {
    return (
      <button
        className="group-card"
        key={g.id}
        onClick={() => {
          setPage("groups");
          setSelectedGroup(g.id);
        }}
      >
        <div className="group-top">
          <span className={"group-icon " + g.color}>
            <Icon name="users" size={22} />
          </span>
          <span className="group-name">
            {g.name}
            <small>{g.course}</small>
          </span>
          <Icon name="right" size={17} />
        </div>
        <div className="group-meta">
          <span>
            <Icon name="users" size={15} />
            {store.students.filter((s) => s.groupId === g.id).length} студента
          </span>
          <span>
            <Icon name="book" size={15} />
            {g.subjects} предмета
          </span>
          <span className="group-course">
            {g.name.includes("3")
              ? 3
              : g.name.includes("1", 3) && g.name.indexOf("-1") >= 0
                ? 1
                : 2}{" "}
            курс
          </span>
        </div>
      </button>
    );
  }
  function scheduleList() {
    return (
      <div className="lesson-list">
        {dayLessons.length === 0 ? (
          <div className="empty-state">
            <Icon name="calendar" size={32} />
            <h3>День без занятий</h3>
            <p>Можно выдохнуть или добавить новое занятие.</p>
            <button
              className="button secondary"
              onClick={() => setModal({ type: "newLesson" })}
            >
              <Icon name="plus" size={17} />
              Добавить занятие
            </button>
          </div>
        ) : (
          dayLessons.map((l, i) => (
            <div
              key={l.id}
              className={
                "lesson-row " + (l.status === "current" ? "active-lesson" : "")
              }
            >
              <div className="lesson-time">
                <strong>{l.time}</strong>
                <span>{l.end}</span>
              </div>
              <div className={"lesson-line " + l.status} />
              <div className="lesson-info">
                <div className="lesson-name">{l.title}</div>
                <div className="lesson-meta">
                  <span className="group-label">{groupName(l.groupId)}</span>
                  <span>{l.type}</span>
                  <span className="room">Ауд. {l.room}</span>
                </div>
              </div>
              <div className="lesson-actions">
                {l.status === "done" ? (
                  <button className="status done" onClick={() => openLesson(l)}>
                    <Icon name="check" size={13} />
                    Проведено
                  </button>
                ) : l.status === "cancelled" ? (
                  <span className="status cancelled">Отменено</span>
                ) : l.status === "current" ? (
                  <button
                    className="button small primary"
                    onClick={() => openLesson(l)}
                  >
                    Продолжить
                    <Icon name="arrow" size={15} />
                  </button>
                ) : (
                  <button
                    className="button small subtle"
                    onClick={() => openLesson(l)}
                  >
                    Начать
                    <Icon name="arrow" size={15} />
                  </button>
                )}
                <span className="lesson-number">{i + 1} пара</span>
              </div>
            </div>
          ))
        )}
      </div>
    );
  }

  return (
    <div className="app-shell">
      {mobileNav && (
        <div className="sidebar-scrim" onClick={() => setMobileNav(false)} />
      )}
      <aside className={"sidebar " + (mobileNav ? "is-open" : "")}>
        <a
          href="#"
          className="brand"
          onClick={(e) => {
            e.preventDefault();
            go("home");
          }}
        >
          <span className="brand-mark">
            <Icon name="book" size={25} />
          </span>
          <span>
            TeachHelper<small>Журнал преподавателя</small>
          </span>
        </a>
        <div className="workspace">
          <span className="workspace-icon">Т</span>
          <div>
            Мой учебный кабинет<small>Личное пространство</small>
          </div>
          <span className="workspace-dot" />
        </div>
        <div className="nav-caption">РАБОЧЕЕ ПРОСТРАНСТВО</div>
        <nav className="main-nav" aria-label="Основная навигация">
          {nav.map((n) => (
            <button
              key={n.id}
              className={page === n.id ? "selected" : ""}
              onClick={() => go(n.id)}
            >
              <Icon name={n.icon} />
              <span>{n.label}</span>
              {n.id === "groups" && (
                <span className="nav-count">{store.groups.length}</span>
              )}
              {page === n.id && <span className="active-dot" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="local-note">
            <span className="local-note-icon">
              <Icon name="shield" size={19} />
            </span>
            <strong>Всё под рукой</strong>
            <p>
              Ваш журнал работает локально.
              <br />
              Данные остаются у вас.
            </p>
            <span>
              <i />
              Без лишней нагрузки
            </span>
          </div>
          <nav className="utility-nav">
            <button
              className={page === "settings" ? "selected" : ""}
              onClick={() => go("settings")}
            >
              <Icon name="settings" />
              Настройки
            </button>
            <button onClick={() => setModal({ type: "help" })}>
              <Icon name="help" />
              Помощь
            </button>
          </nav>
          <button className="profile" onClick={() => go("settings")}>
            <span className="avatar">АС</span>
            <span>
              {store.teacher}
              <small>Преподаватель</small>
            </span>
            <Icon name="chevron" size={15} />
          </button>
          <span className="version">TeachHelper · Локальная версия</span>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              onClick={() => setMobileNav(true)}
              aria-label="Открыть меню"
            >
              <Icon name="menu" />
            </button>
            <span className="breadcrumb-home">Рабочее пространство</span>
            <Icon name="right" size={14} />
            <strong>
              {nav.find((n) => n.id === page)?.label || "Настройки"}
            </strong>
          </div>
          <div className="topbar-right">
            <span className="semester-icon">
              <Icon name="calendar" size={17} />
            </span>
            <select
              className="semester-select"
              aria-label="Учебный семестр"
              value={semester}
              onChange={(e) => {
                setSemester(e.target.value);
                setToast("Учебный период: " + e.target.value);
              }}
            >
              <option>1 семестр, 2026–2027</option>
              <option>2 семестр, 2026–2027</option>
            </select>
            <span className="topbar-divider" />
            <div className="notification-wrap">
              <button
                className={
                  "icon-button notification-button " +
                  (notifications ? "pressed" : "")
                }
                aria-label="Уведомления"
                onClick={() => setNotifications(!notifications)}
              >
                <Icon name="bell" />
                {current && <i />}
              </button>
              {notifications && (
                <div className="notification-popover">
                  <h3>Уведомления</h3>
                  {current ? (
                    <button
                      onClick={() => {
                        openLesson(current);
                        setNotifications(false);
                      }}
                    >
                      <span className="notification-symbol">
                        <Icon name="clock" />
                      </span>
                      <span>
                        <strong>Занятие ещё не завершено</strong>
                        <small>
                          {current.title} · {groupName(current.groupId)}
                        </small>
                      </span>
                      <Icon name="right" size={15} />
                    </button>
                  ) : (
                    <p>Все занятия завершены. Новых уведомлений нет.</p>
                  )}
                  <div className="notification-foot">
                    Уведомления на этом устройстве
                  </div>
                </div>
              )}
            </div>
            <button
              className="avatar top-avatar"
              onClick={() => go("settings")}
              aria-label="Профиль преподавателя"
            >
              АС
            </button>
          </div>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                {page === "home" ? "ВАШ УЧЕБНЫЙ ДЕНЬ" : "РАБОЧЕЕ ПРОСТРАНСТВО"}
              </div>
              <h1>
                {page === "home"
                  ? `Хорошего дня, ${store.teacher.split(" ")[0]}!`
                  : page === "groups" && selectedGroup
                    ? groupName(selectedGroup)
                    : nav.find((n) => n.id === page)?.label || "Настройки"}
                {page === "home" && <span className="greeting-sun">☀</span>}
              </h1>
              <p>
                {page === "home" ? (
                  <>
                    Понедельник, 14 сентября{" "}
                    <span className="dot-separator">·</span>{" "}
                    <span>Нечётная неделя</span>
                  </>
                ) : page === "groups" ? (
                  "Студенты, успеваемость и всё важное о ваших группах"
                ) : page === "schedule" ? (
                  "Планируйте занятия и управляйте учебным днём"
                ) : page === "subjects" ? (
                  "Учебная нагрузка и прогресс по дисциплинам"
                ) : page === "reports" ? (
                  "Посещаемость и успеваемость в одном месте"
                ) : (
                  "Ваш профиль, данные и параметры журнала"
                )}
              </p>
            </div>
            {page === "groups" ? (
              <button
                className="button primary"
                onClick={() => setModal({ type: "group" })}
              >
                <Icon name="plus" size={18} />
                Добавить группу
              </button>
            ) : page === "reports" ? (
              <button
                className="button primary"
                onClick={exportExcel}
                disabled={exporting}
              >
                <Icon name="download" size={18} />
                {exporting ? "Подготовка…" : "Экспорт в Excel"}
              </button>
            ) : page !== "settings" && page !== "subjects" ? (
              <button
                className="button primary new-lesson"
                onClick={() => setModal({ type: "newLesson" })}
              >
                <Icon name="plus" size={19} />
                Начать занятие
              </button>
            ) : null}
          </div>

          {page === "home" && (
            <>
              <section className="welcome-banner">
                <div className="banner-content">
                  <div className="banner-kicker">
                    <span className="live-dot" />
                    {current
                      ? "СЕЙЧАС ПО РАСПИСАНИЮ"
                      : "ВАШ ДЕНЬ ПОД КОНТРОЛЕМ"}
                  </div>
                  <h2>{current ? current.title : "Всё идёт по плану"}</h2>
                  <p>
                    {current ? (
                      <>
                        <span>{groupName(current.groupId)}</span>
                        <i /> {current.time}–{current.end}
                        <i /> Аудитория {current.room}
                      </>
                    ) : (
                      "Проведённые занятия и оценки сохранены в журнале."
                    )}
                  </p>
                  <button
                    className="banner-link"
                    onClick={() =>
                      current ? openLesson(current) : go("schedule")
                    }
                  >
                    {current ? "Перейти к занятию" : "Открыть расписание"}
                    <Icon name="arrow" size={18} />
                  </button>
                </div>
                <BookArt />
                <div className="banner-note">
                  <Icon name="leaf" size={16} />
                  <span>
                    Меньше рутины.
                    <br />
                    Больше времени на главное.
                  </span>
                </div>
              </section>
              <section className="stats-grid" aria-label="Общая статистика">
                {[
                  {
                    icon: "calendar",
                    label: "Занятия сегодня",
                    value: String(todayLessons.length),
                    detail: (
                      <>
                        <span className="green-text">{done} проведено</span>
                        <span className="dot-separator">·</span>
                        {
                          todayLessons.filter(
                            (l) =>
                              l.status !== "done" && l.status !== "cancelled",
                          ).length
                        }{" "}
                        впереди
                      </>
                    ),
                    color: "green",
                    target: "schedule",
                  },
                  {
                    icon: "users",
                    label: "Учебные группы",
                    value: String(store.groups.length),
                    detail: `${store.students.length} студента в группах`,
                    color: "purple",
                    target: "groups",
                  },
                  {
                    icon: "book",
                    label: "Предметы",
                    value: String(subjects.length),
                    detail: "В этом семестре",
                    color: "orange",
                    target: "subjects",
                  },
                  {
                    icon: "chart",
                    label: "Посещаемость",
                    value: attendance,
                    detail: (
                      <>
                        <span className="green-text">
                          <Icon name="check" size={13} /> По журналу
                        </span>
                        <span className="stat-period">в сентябре</span>
                      </>
                    ),
                    color: "blue",
                    target: "reports",
                  },
                ].map((stat) => (
                  <button
                    key={stat.label}
                    className="stat-card"
                    onClick={() => go(stat.target as Page)}
                  >
                    <div className="stat-label">
                      {stat.label}
                      <span className={"stat-icon " + stat.color}>
                        <Icon name={stat.icon as IconName} size={19} />
                      </span>
                    </div>
                    <strong className="stat-value">{stat.value}</strong>
                    <div className="stat-detail">{stat.detail}</div>
                  </button>
                ))}
              </section>
            </>
          )}

          {page === "schedule" && subjectFilter && (
            <div className="subject-filter-note">
              <Icon name="book" size={17} />
              <span>Предмет: {subjectFilter}</span>
              <button
                className="text-button"
                onClick={() => setSubjectFilter("")}
              >
                Показать все
                <Icon name="close" size={15} />
              </button>
            </div>
          )}
          {(page === "home" || page === "schedule") && (
            <div className="dashboard-grid">
              <section className="panel schedule-panel">
                <div className="panel-heading">
                  <div>
                    <h2>
                      {page === "home"
                        ? "Расписание на сегодня"
                        : "Занятия на день"}
                      <span className="count-pill">{dayLessons.length}</span>
                    </h2>
                    <p className="capitalize">{dateLabel}</p>
                  </div>
                  <button
                    className="text-button"
                    onClick={() => {
                      if (page === "home") go("schedule");
                      else {
                        setSelectedDay(TODAY);
                        setWeekOffset(0);
                      }
                    }}
                  >
                    {page === "home" ? "Всё расписание" : "Сегодня"}
                    <Icon name="arrow" size={16} />
                  </button>
                </div>
                {scheduleList()}
                <div className="schedule-footer">
                  <Icon name="clock" size={15} />
                  {dayLessons.length ? (
                    <span>
                      {dayLessons.length} занятия{" "}
                      <span className="dot-separator">·</span>{" "}
                      {dayLessons.length * 2} академических часов
                    </span>
                  ) : (
                    <span>Свободный день</span>
                  )}
                  <span className="schedule-footer-right">
                    Время для новых знаний
                  </span>
                </div>
              </section>
              <div className="right-column">
                <section className="panel week-panel">
                  <div className="week-heading">
                    <h2>
                      {new Date(weekDays[0] + "T12:00:00")
                        .toLocaleDateString("ru-RU", {
                          month: "long",
                          year: "numeric",
                        })
                        .replace(" г.", "")}
                    </h2>
                    <div>
                      <button
                        className="icon-button"
                        aria-label="Предыдущая неделя"
                        onClick={() => weekStep(-1)}
                      >
                        <Icon name="left" size={16} />
                      </button>
                      <button
                        className="icon-button"
                        aria-label="Следующая неделя"
                        onClick={() => weekStep(1)}
                      >
                        <Icon name="right" size={16} />
                      </button>
                    </div>
                  </div>
                  <div className="week-days">
                    {weekDays.map((d, i) => (
                      <button
                        key={d}
                        className={
                          (d === selectedDay ? "selected " : "") +
                          (i > 4 ? "weekend" : "")
                        }
                        onClick={() => setSelectedDay(d)}
                      >
                        <span>
                          {["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"][i]}
                        </span>
                        <strong>{Number(d.slice(-2))}</strong>
                        <i
                          className={
                            store.lessons.some((l) => l.date === d)
                              ? "has-lessons"
                              : ""
                          }
                        />
                      </button>
                    ))}
                  </div>
                  <div className="week-footer">
                    <span className="tiny-dot" />
                    Нечётная неделя <span>3-я учебная неделя</span>
                  </div>
                </section>
                <section className="panel quick-panel">
                  <h2>Быстрые действия</h2>
                  <button onClick={() => go("reports")}>
                    <span className="quick-icon green">
                      <Icon name="file" size={18} />
                    </span>
                    <span>
                      Открыть ведомость<small>Оценки и посещаемость</small>
                    </span>
                    <Icon name="right" size={16} />
                  </button>
                  <button onClick={exportExcel} disabled={exporting}>
                    <span className="quick-icon blue">
                      <Icon name="download" size={18} />
                    </span>
                    <span>
                      {exporting ? "Готовим файл…" : "Экспорт в Excel"}
                      <small>Выгрузить данные журнала</small>
                    </span>
                    <Icon name="right" size={16} />
                  </button>
                  <button onClick={() => setModal({ type: "backup" })}>
                    <span className="quick-icon orange">
                      <Icon name="shield" size={18} />
                    </span>
                    <span>
                      Резервная копия<small>Сохранить самое важное</small>
                    </span>
                    <Icon name="right" size={16} />
                  </button>
                </section>
              </div>
            </div>
          )}

          {(page === "home" || (page === "groups" && !selectedGroup)) && (
            <section className="groups-section">
              <div className="section-heading">
                <h2>
                  {page === "home" ? "Мои группы" : "Учебные группы"}
                  <span className="count-pill">{store.groups.length}</span>
                </h2>
                {page === "home" ? (
                  <button className="text-button" onClick={() => go("groups")}>
                    Все группы
                    <Icon name="arrow" size={16} />
                  </button>
                ) : (
                  <label className="search-field">
                    <Icon name="search" size={17} />
                    <input
                      aria-label="Найти группу"
                      placeholder="Найти группу…"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                    />
                  </label>
                )}
              </div>
              <div className="group-grid">
                {store.groups
                  .filter(
                    (g) =>
                      g.name.toLowerCase().includes(search.toLowerCase()) ||
                      g.course.toLowerCase().includes(search.toLowerCase()),
                  )
                  .slice(0, page === "home" ? 3 : undefined)
                  .map(groupCard)}
              </div>
              {search &&
                !store.groups.some((g) =>
                  (g.name + g.course)
                    .toLowerCase()
                    .includes(search.toLowerCase()),
                ) && (
                  <div className="empty-state">
                    Группы не найдены. Попробуйте другой запрос.
                  </div>
                )}
            </section>
          )}

          {page === "groups" && selectedGroup && (
            <section className="panel detail-panel">
              <div className="panel-heading">
                <button
                  className="text-button"
                  onClick={() => setSelectedGroup(null)}
                >
                  <Icon name="left" size={16} />
                  Все группы
                </button>
                <button
                  className="button secondary small"
                  onClick={() =>
                    setModal({
                      type: "group",
                      group: store.groups.find((g) => g.id === selectedGroup),
                    })
                  }
                >
                  Изменить группу
                </button>
              </div>
              <div className="detail-toolbar">
                <h2>
                  Студенты{" "}
                  <span className="count-pill">
                    {
                      store.students.filter((s) => s.groupId === selectedGroup)
                        .length
                    }
                  </span>
                </h2>
                <label className="search-field">
                  <Icon name="search" size={17} />
                  <input
                    placeholder="Поиск по имени…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </label>
              </div>
              <form
                className="add-student"
                onSubmit={(e) => {
                  e.preventDefault();
                  const form = e.currentTarget;
                  const name = String(new FormData(form).get("name")).trim();
                  if (!name) return;
                  setStore((s) => ({
                    ...s,
                    students: [
                      ...s.students,
                      { id: Date.now(), name, groupId: selectedGroup },
                    ],
                  }));
                  form.reset();
                  setToast("Студент добавлен");
                }}
              >
                <input
                  name="name"
                  required
                  placeholder="Фамилия и имя нового студента"
                  aria-label="Фамилия и имя"
                />
                <button className="button secondary" type="submit">
                  <Icon name="plus" size={16} />
                  Добавить
                </button>
              </form>
              <div className="student-directory">
                {store.students
                  .filter(
                    (s) =>
                      s.groupId === selectedGroup &&
                      s.name.toLowerCase().includes(search.toLowerCase()),
                  )
                  .map((s, i) => (
                    <div key={s.id}>
                      <span className="student-index">{i + 1}</span>
                      <span className="student-avatar">
                        {s.name
                          .split(" ")
                          .map((n) => n[0])
                          .join("")}
                      </span>
                      <strong>{s.name}</strong>
                      <span className="directory-status">
                        <i />В группе
                      </span>
                    </div>
                  ))}
              </div>
              <div className="detail-toolbar">
                <h2>Занятия группы</h2>
              </div>
              <div className="group-lessons">
                {store.lessons
                  .filter((l) => l.groupId === selectedGroup)
                  .map((l) => (
                    <button key={l.id} onClick={() => openLesson(l)}>
                      <Icon name="book" />
                      <span>
                        <strong>{l.title}</strong>
                        <small>
                          {formatDate(l.date, true)} · {l.time}
                        </small>
                      </span>
                      <Icon name="right" size={17} />
                    </button>
                  ))}
                {!store.lessons.some((l) => l.groupId === selectedGroup) && (
                  <p className="muted">
                    Занятий пока нет. Создайте первое из расписания.
                  </p>
                )}
              </div>
            </section>
          )}

          {page === "subjects" && (
            <>
              <label className="search-field subject-search">
                <Icon name="search" size={18} />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Найти предмет…"
                  aria-label="Найти предмет"
                />
              </label>
              <div className="subject-grid">
                {subjects
                  .filter((s) =>
                    s.name.toLowerCase().includes(search.toLowerCase()),
                  )
                  .map((s) => (
                    <section className="panel subject-card" key={s.name}>
                      <span className={"group-icon " + s.color}>
                        <Icon name="book" size={23} />
                      </span>
                      <span className="subject-semester">
                        {semester.split(",")[0]}
                      </span>
                      <h2>{s.name}</h2>
                      <p>Учебный план · {s.hours} часов</p>
                      <div className="progress-label">
                        <span>Пройдено {s.done} ч.</span>
                        <strong>{Math.round((s.done / s.hours) * 100)}%</strong>
                      </div>
                      <div className="progress-track">
                        <span
                          style={{ width: (s.done / s.hours) * 100 + "%" }}
                        />
                      </div>
                      <button
                        className="text-button"
                        onClick={() => {
                          go("schedule");
                          setSelectedDay(TODAY);
                          setSubjectFilter(s.name);
                        }}
                      >
                        Занятия по предмету
                        <Icon name="arrow" size={16} />
                      </button>
                    </section>
                  ))}
              </div>
              {!subjects.some((s) =>
                s.name.toLowerCase().includes(search.toLowerCase()),
              ) && <div className="empty-state">Предметы не найдены</div>}
            </>
          )}

          {page === "reports" && (
            <>
              <div className="report-filters">
                <label>
                  Учебная группа
                  <select
                    value={reportGroup}
                    onChange={(e) => setReportGroup(e.target.value)}
                  >
                    <option value="all">Все группы</option>
                    {store.groups.map((g) => (
                      <option key={g.id} value={g.id}>
                        {g.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Период
                  <input
                    type="month"
                    value={reportMonth}
                    onChange={(e) => setReportMonth(e.target.value)}
                  />
                </label>
                <span>
                  <Icon name="shield" size={16} />
                  Данные вашего журнала
                </span>
              </div>
              <div className="report-stats">
                {[
                  {
                    name: "Проведено занятий",
                    value: reportLessons.filter((l) => l.status === "done")
                      .length,
                    icon: "calendar",
                  },
                  { name: "Средний балл", value: average, icon: "chart" },
                  { name: "Посещаемость", value: attendance, icon: "users" },
                ].map((s) => (
                  <div className="panel report-stat" key={s.name}>
                    <span className="quick-icon green">
                      <Icon name={s.icon as IconName} />
                    </span>
                    <div>
                      <p>{s.name}</p>
                      <strong>{s.value}</strong>
                    </div>
                  </div>
                ))}
              </div>
              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <h2>Ведомость занятий</h2>
                    <p>Нажмите на занятие, чтобы открыть оценки</p>
                  </div>
                  <Icon name="file" />
                </div>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Дата</th>
                        <th>Предмет</th>
                        <th>Группа</th>
                        <th>Статус</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {reportLessons.map((l) => (
                        <tr key={l.id}>
                          <td>{formatDate(l.date)}</td>
                          <td>
                            <button
                              className="table-link"
                              onClick={() => openLesson(l)}
                            >
                              {l.title}
                            </button>
                          </td>
                          <td>
                            <span className="group-label">
                              {groupName(l.groupId)}
                            </span>
                          </td>
                          <td>
                            <span className={"status " + l.status}>
                              {l.status === "done"
                                ? "Проведено"
                                : l.status === "current"
                                  ? "В процессе"
                                  : l.status === "cancelled"
                                    ? "Отменено"
                                    : "Запланировано"}
                            </span>
                          </td>
                          <td>
                            <button
                              className="icon-button"
                              aria-label={"Открыть " + l.title}
                              onClick={() => openLesson(l)}
                            >
                              <Icon name="right" size={17} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {!reportLessons.length && (
                    <div className="empty-state">
                      За выбранный период занятий нет
                    </div>
                  )}
                </div>
              </section>
            </>
          )}

          {page === "settings" && (
            <div className="settings-grid">
              <section className="panel settings-card">
                <h2>Профиль преподавателя</h2>
                <p className="muted">Как к вам обращаться в журнале</p>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const name = String(
                      new FormData(e.currentTarget).get("teacher"),
                    ).trim();
                    if (name) {
                      setStore((s) => ({ ...s, teacher: name }));
                      setToast("Профиль обновлён");
                    }
                  }}
                >
                  <label>
                    Имя и отчество
                    <input
                      name="teacher"
                      defaultValue={store.teacher}
                      required
                    />
                  </label>
                  <label>
                    Роль
                    <input value="Преподаватель" disabled />
                  </label>
                  <button className="button primary" type="submit">
                    Сохранить изменения
                  </button>
                </form>
              </section>
              <section className="panel settings-card">
                <h2>Данные и резервные копии</h2>
                <p className="muted">
                  Журнал хранится в браузере на этом устройстве. Сохраните копию
                  перед очисткой данных браузера.
                </p>
                <button className="button secondary" onClick={backup}>
                  <Icon name="download" size={17} />
                  Скачать резервную копию
                </button>
                <label className="restore-label">
                  Восстановить из файла
                  <input
                    type="file"
                    accept=".json"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      const reader = new FileReader();
                      reader.onload = () => {
                        try {
                          const data = JSON.parse(String(reader.result));
                          if (
                            !Array.isArray(data.groups) ||
                            !Array.isArray(data.lessons) ||
                            !Array.isArray(data.students) ||
                            !data.grades ||
                            typeof data.teacher !== "string" ||
                            !data.groups.every(
                              (g: Group) =>
                                typeof g.id === "number" &&
                                typeof g.name === "string",
                            ) ||
                            !data.lessons.every(
                              (l: Lesson) =>
                                typeof l.id === "number" &&
                                typeof l.date === "string" &&
                                typeof l.time === "string",
                            ) ||
                            !data.students.every(
                              (s: { name: string }) =>
                                typeof s.name === "string",
                            )
                          )
                            throw new Error();
                          if (
                            window.confirm(
                              "Заменить текущие данные данными из копии? Перед этим сохраните текущий журнал.",
                            )
                          ) {
                            setStore(data);
                            setToast("Журнал восстановлен из копии");
                          }
                        } catch {
                          setToast("Неверный формат резервной копии");
                        }
                      };
                      reader.readAsText(file);
                      e.target.value = "";
                    }}
                  />
                </label>
                <div className="settings-info">
                  <Icon name="shield" />
                  <span>
                    Это локальная веб-версия. Подключение к Flask, Telegram и
                    MAX требует сервера исходного проекта.
                  </span>
                </div>
              </section>
              <section className="panel settings-card">
                <h2>Лёгкий интерфейс</h2>
                <p className="muted">
                  Без видео, внешних шрифтов и тяжёлых визуальных эффектов.
                  Удобные кнопки и адаптивная вёрстка для смартфонов.
                </p>
                <div className="settings-info">
                  <Icon name="help" />
                  <span>
                    Для старых WebView автоматически подключается совместимая
                    сборка под Chromium 51+. Проверка на реальном Android 7 всё
                    ещё рекомендуется перед выпуском APK.
                  </span>
                </div>
              </section>
            </div>
          )}
          <footer className="main-footer">
            <span>
              <Icon name="shield" size={14} />
              {storageError
                ? "Не удалось сохранить: хранилище недоступно"
                : "Данные сохранены на этом устройстве"}
            </span>
            <span>Создано, чтобы преподавать было проще</span>
          </footer>
        </main>
      </div>

      {modal?.type === "newLesson" && (
        <ModalShell
          title="Начать занятие"
          subtitle="Выберите группу, предмет и дату"
          onClose={() => setModal(null)}
        >
          <form
            className="modal-form"
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              const lesson: Lesson = {
                id: Date.now(),
                title: String(f.get("subject")),
                groupId: Number(f.get("group")),
                date: String(f.get("date")),
                time: String(f.get("time")),
                end: String(f.get("end")),
                room: String(f.get("room")) || "—",
                status: "current",
                type: String(f.get("type")),
              };
              if (lesson.date > TODAY) {
                setToast("Начать можно занятие за сегодня или прошедшую дату");
                return;
              }
              if (lesson.end <= lesson.time) {
                setToast("Время окончания должно быть позже начала");
                return;
              }
              setStore((s) => ({ ...s, lessons: [...s.lessons, lesson] }));
              setSelectedDay(lesson.date);
              openLesson(lesson);
              setToast("Занятие создано");
            }}
          >
            <label>
              Учебная группа
              <select name="group" required>
                {store.groups.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name} — {g.course}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Предмет
              <select name="subject">
                {subjects.map((s) => (
                  <option key={s.name}>{s.name}</option>
                ))}
              </select>
            </label>
            <div className="form-row">
              <label>
                Дата занятия
                <input
                  type="date"
                  name="date"
                  defaultValue={selectedDay > TODAY ? TODAY : selectedDay}
                  max={TODAY}
                  required
                />
              </label>
              <label>
                Формат
                <select name="type">
                  <option>Практика</option>
                  <option>Лекция</option>
                  <option>Лабораторная</option>
                </select>
              </label>
            </div>
            <div className="form-row">
              <label>
                Начало
                <input type="time" name="time" defaultValue="10:10" required />
              </label>
              <label>
                Окончание
                <input type="time" name="end" defaultValue="11:40" required />
              </label>
              <label>
                Аудитория
                <input name="room" placeholder="208" />
              </label>
            </div>
            <div className="form-note">
              <Icon name="help" size={17} />
              Занятие сохранится в журнале выбранной группы.
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="button secondary"
                onClick={() => setModal(null)}
              >
                Отмена
              </button>
              <button type="submit" className="button primary">
                <Icon name="play" size={16} />
                Начать занятие
              </button>
            </div>
          </form>
        </ModalShell>
      )}
      {modal?.type === "group" && (
        <ModalShell
          title={modal.group ? "Изменить группу" : "Новая учебная группа"}
          subtitle="Объедините студентов в одном журнале"
          onClose={() => setModal(null)}
        >
          <form
            className="modal-form"
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              const name = String(f.get("name")).trim();
              if (!name) return;
              if (
                store.groups.some(
                  (g) =>
                    g.name.toLowerCase() === name.toLowerCase() &&
                    g.id !== modal.group?.id,
                )
              ) {
                setToast("Группа с таким названием уже существует");
                return;
              }
              const group = {
                id: modal.group?.id || Date.now(),
                name,
                course: String(f.get("course")).trim(),
                count: modal.group?.count || 0,
                subjects: modal.group?.subjects || 0,
                color: String(f.get("color")),
              };
              setStore((s) => ({
                ...s,
                groups: modal.group
                  ? s.groups.map((g) => (g.id === group.id ? group : g))
                  : [...s.groups, group],
              }));
              setModal(null);
              setToast(
                modal.group
                  ? "Группа обновлена"
                  : "Группа создана. Теперь можно добавить студентов",
              );
            }}
          >
            <label>
              Название группы
              <input
                name="name"
                placeholder="Например, ИС-23"
                defaultValue={modal.group?.name}
                required
                maxLength={24}
              />
            </label>
            <label>
              Направление
              <input
                name="course"
                placeholder="Информационные системы"
                defaultValue={modal.group?.course}
                required
              />
            </label>
            <label>
              Цвет группы
              <select name="color" defaultValue={modal.group?.color || "green"}>
                <option value="green">Шалфейный</option>
                <option value="purple">Лавандовый</option>
                <option value="orange">Персиковый</option>
                <option value="blue">Голубой</option>
              </select>
            </label>
            <div className="modal-footer">
              <button
                type="button"
                className="button secondary"
                onClick={() => setModal(null)}
              >
                Отмена
              </button>
              <button className="button primary" type="submit">
                {modal.group ? "Сохранить" : "Создать группу"}
              </button>
            </div>
          </form>
        </ModalShell>
      )}
      {modal?.type === "lesson" &&
        (() => {
          const l =
            store.lessons.find((l) => l.id === modal.lesson.id) || modal.lesson;
          const students = store.students.filter(
            (s) => s.groupId === l.groupId,
          );
          const marked = students.filter(
            (s) =>
              store.grades[`${l.id}-${s.id}`] &&
              store.grades[`${l.id}-${s.id}`] !== "—",
          ).length;
          return (
            <ModalShell
              wide
              title={l.title}
              subtitle={`${groupName(l.groupId)} · ${formatDate(l.date, true)} · ${l.time}–${l.end} · Ауд. ${l.room}`}
              onClose={() => setModal(null)}
            >
              <div className="journal-toolbar">
                <label className="search-field">
                  <Icon name="search" size={17} />
                  <input
                    placeholder="Найти студента…"
                    value={studentQuery}
                    onChange={(e) => setStudentQuery(e.target.value)}
                  />
                </label>
                <button
                  className="button secondary small"
                  onClick={() => {
                    setStore((s) => {
                      const grades = { ...s.grades };
                      students.forEach((st) => {
                        if (
                          !grades[`${l.id}-${st.id}`] ||
                          grades[`${l.id}-${st.id}`] === "—"
                        )
                          grades[`${l.id}-${st.id}`] = "0";
                      });
                      return { ...s, grades };
                    });
                    setToast("Неотмеченные студенты отмечены присутствующими");
                  }}
                >
                  <Icon name="check" size={16} />
                  Все присутствуют
                </button>
              </div>
              <div className="journal-hint">
                <span>Слева — назад, справа — вперёд по оценкам</span>
                <span>0 — присутствует · Н — отсутствует</span>
              </div>
              <div className="journal-students">
                {students
                  .filter((s) =>
                    s.name.toLowerCase().includes(studentQuery.toLowerCase()),
                  )
                  .map((s, i) => {
                    const grade = store.grades[`${l.id}-${s.id}`] || "—";
                    return (
                      <div className="journal-student" key={s.id}>
                        <button
                          className="student-cycle"
                          aria-label={"Предыдущая оценка: " + s.name}
                          onClick={() => cycleGrade(l.id, s.id, -1)}
                        >
                          <span>{i + 1}</span>
                          <strong>{s.name}</strong>
                        </button>
                        <button
                          className={
                            "grade grade-" + (grade === "Н" ? "absent" : grade)
                          }
                          aria-label={`Оценка ${grade}, ${s.name}. Следующая оценка`}
                          onClick={() => cycleGrade(l.id, s.id, 1)}
                        >
                          {grade === "0" ? (
                            <Icon name="check" size={19} />
                          ) : (
                            grade
                          )}
                        </button>
                      </div>
                    );
                  })}
              </div>
              {!students.length && (
                <div className="empty-state">
                  В группе пока нет студентов. Добавьте их в разделе «Группы».
                </div>
              )}
              <div className="journal-summary">
                <Icon name="shield" size={16} />
                <span>
                  Отмечено {marked} из {students.length} ·{" "}
                  {storageError ? "Ошибка сохранения" : "Изменения сохранены"}
                </span>
              </div>
              <div className="modal-footer">
                <button
                  className="button danger-quiet"
                  onClick={() => {
                    if (
                      window.confirm(
                        `Отменить занятие? Выставлено отметок: ${marked}. Отметки будут сохранены в локальном журнале.`,
                      )
                    )
                      changeLessonStatus(l.id, "cancelled");
                  }}
                >
                  Отменить занятие
                </button>
                <button
                  className="button primary"
                  onClick={() => changeLessonStatus(l.id, "done")}
                >
                  <Icon name="check" size={17} />
                  {l.status === "done" ? "Готово" : "Завершить занятие"}
                </button>
              </div>
            </ModalShell>
          );
        })()}
      {modal?.type === "backup" && (
        <ModalShell
          title="Резервная копия"
          subtitle="Пусть важное всегда будет в сохранности"
          onClose={() => setModal(null)}
        >
          <div className="backup-body">
            <span className="backup-icon">
              <Icon name="shield" size={32} />
            </span>
            <h3>Весь журнал — в одном файле</h3>
            <p>
              Копия содержит группы, студентов, занятия и оценки. Сохраните файл
              в надёжном месте, чтобы восстановить данные в настройках.
            </p>
            <div className="backup-summary">
              <span>{store.groups.length} групп</span>
              <span>{store.students.length} студента</span>
              <span>{store.lessons.length} занятий</span>
            </div>
            <button className="button primary" onClick={backup}>
              <Icon name="download" size={18} />
              Скачать копию (.json)
            </button>
            <small>Копия этой веб-версии не заменяет lessons.db</small>
          </div>
        </ModalShell>
      )}
      {modal?.type === "help" && (
        <ModalShell
          title="Преподавать проще с TeachHelper"
          subtitle="Коротко о работе с журналом"
          onClose={() => setModal(null)}
        >
          <div className="help-content">
            {[
              {
                icon: "calendar",
                title: "Начните занятие",
                text: "Выберите занятие в расписании или нажмите «Начать занятие», чтобы создать новое.",
              },
              {
                icon: "check",
                title: "Отметьте студентов",
                text: "Нажимайте на оценку справа, чтобы двигаться вперёд: — → 0 → 5 → 4 → 3 → 2 → Н. Нажатие на имя возвращает предыдущую оценку.",
              },
              {
                icon: "download",
                title: "Сохраните результат",
                text: "Оценки сохраняются автоматически. Экспортируйте ведомость в Excel или создайте резервную копию всего журнала.",
              },
            ].map((item) => (
              <div key={item.title}>
                <span className="quick-icon green">
                  <Icon name={item.icon as IconName} />
                </span>
                <div>
                  <h3>{item.title}</h3>
                  <p>{item.text}</p>
                </div>
              </div>
            ))}
            <div className="form-note">
              <Icon name="help" />
              Демонстрационные данные можно редактировать. Они хранятся только в
              этом браузере.
            </div>
          </div>
          <div className="modal-footer">
            <button className="button primary" onClick={() => setModal(null)}>
              Всё понятно
            </button>
          </div>
        </ModalShell>
      )}
      {toast && (
        <div className="toast" role="status">
          <span className="toast-icon">
            <Icon name="check" size={17} />
          </span>
          {toast}
          <button aria-label="Закрыть уведомление" onClick={() => setToast("")}>
            <Icon name="close" size={15} />
          </button>
        </div>
      )}
    </div>
  );
}
