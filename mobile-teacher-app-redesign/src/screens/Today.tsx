/* Экран «Сегодня»: занятия дня, быстрые метрики. */

import { useMemo, useState } from "react";
import { CalendarOff, ChevronRight, Play } from "lucide-react";
import { useDB, useVersion, store, lessonAvg } from "../lib/store";
import { formatLong, todayISO, weekParity, addDaysISO } from "../lib/date";
import { isDebtor, avgOf, formatAvg } from "../lib/grades";
import { navigate } from "../lib/router";
import { BigHeader, PairNumber, Screen, StatusDot, groupInk, dayRows } from "../components/shell";
import type { DayRow } from "../components/shell";
import { Btn, Card, Chip, EmptyState, SectionTitle, Sheet } from "../components/ui";
import { NewLessonSheet } from "../components/NewLessonSheet";
import { PendingLessonsCard } from "../components/PendingLessonsCard";
import type { LessonStatus, Student } from "../lib/types";

/** Запись списка должников: студент + его средний балл (2–5). */
interface DebtorRow {
  student: Student;
  avg: number | null;
}

/** Русская форма числа: «пара / пары / пар» по правилам склонения. */
function pairWord(n: number): string {
  const a = n % 10;
  const b = n % 100;
  if (a === 1 && b !== 11) return "пара";
  if (a >= 2 && a <= 4 && (b < 12 || b > 14)) return "пары";
  return "пар";
}

function LessonCard({
  row, onStartPlan,
}: {
  row: DayRow;
  /** Тап по строке шаблона: открыть «Начать занятие» с уже выбранной парой. */
  onStartPlan: (pair: { groupId: number; subjectId: number }) => void;
}) {
  const src = row.kind === "lesson" ? row.lesson : row.item;
  const lesson = row.kind === "lesson" ? row.lesson : null;
  const plan = row.kind === "plan";
  const group = store.group(src.groupId);
  const subject = store.subject(src.subjectId);
  const recs = lesson ? store.gradesOfLesson(lesson.id) : [];
  const avg = lessonAvg(recs);
  const graded = recs.filter((r) => r.present && r.value !== null).length;
  const status: LessonStatus = lesson ? lesson.status : "scheduled";

  return (
    <Card
      className="relative p-3.5 mb-2 flex items-center gap-3"
      onClick={() =>
        lesson
          ? navigate("/lesson/" + lesson.id)
          : onStartPlan({ groupId: src.groupId, subjectId: src.subjectId })
      }
    >
      <PairNumber
        n={src.lessonNumber}
        code={group ? group.name : "—"}
        codeColor={group ? groupInk(group.name) : undefined}
        className="w-[48px]"
      />
      <div className="w-px self-stretch bg-line" />
      <div className="min-w-0 flex-1">
        <div className="text-[14.5px] font-bold leading-snug line-clamp-2 min-h-[2.6em]">{subject?.name}</div>
        <div className="mt-1 flex items-center gap-1.5 min-w-0">
          {/* Группа — под номером пары; здесь только время и средний балл. */}
          <span className="min-w-0 truncate text-[12px] text-muted">
            {[
              plan && src.time ? `${src.time}${src.room ? " · " + src.room : ""}` : "",
              lesson && lesson.status === "held" && graded > 0
                ? `ср. ${formatAvg(avg)} из ${graded}`
                : "",
            ].filter(Boolean).join(" · ")}
          </span>
          {plan && <Chip tone="neutral">по расписанию</Chip>}
        </div>
      </div>
      <StatusDot status={status} />
      <ChevronRight size={16} className="text-faint shrink-0" />
    </Card>
  );
}

export default function TodayScreen() {
  const db = useDB();
  const ver = useVersion();
  const today = todayISO();
  const [sheetOpen, setSheetOpen] = useState(false);
  const [debtorsOpen, setDebtorsOpen] = useState(false);
  /** Пара, выбранная тапом по строке шаблона (для листа «Начать занятие»). */
  const [planPair, setPlanPair] = useState<{ groupId: number; subjectId: number } | null>(null);

  // Занятия дня + слоты шаблона расписания, которых ещё нет в журнале.
  const rows = dayRows(db, today);
  const parity = weekParity(today);

  const stats = useMemo(() => {
    const weekAgo = addDaysISO(today, -7);
    const weekLessonIds = new Set(
      db.lessons.filter((l) => l.date >= weekAgo && l.date <= today && l.status === "held").map((l) => l.id),
    );
    const weekGrades = db.grades
      .filter((g) => weekLessonIds.has(g.lessonId) && g.present)
      .map((g) => g.value);
    const debtorRows: DebtorRow[] = [];
    for (const s of db.students) {
      const vals = db.grades.filter((g) => g.studentId === s.id && g.present).map((g) => g.value);
      if (isDebtor(vals)) debtorRows.push({ student: s, avg: avgOf(vals) });
    }
    return {
      students: db.students.length,
      avg: avgOf(weekGrades),
      debtors: debtorRows.length,
      debtorRows,
      groups: db.groups.length,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [db, ver]);

  /** Сводка по предметам: проведённые/выделенные пары + прогресс-бар. */
  const subjectRows = useMemo(() => {
    const held = new Map<number, number>();
    for (const l of db.lessons) {
      if (l.status === "held") held.set(l.subjectId, (held.get(l.subjectId) ?? 0) + 1);
    }
    return db.subjects.map((s) => {
      const lessonHeld = held.get(s.id) ?? 0;
      const apiHeld = s.heldLessons ?? 0;
      // Проведённые: локальный счётчик занятий (консистентен с API held_lessons);
      // если уроки ещё не загружены — фолбэк на heldLessons из API.
      const h = lessonHeld > 0 ? lessonHeld : apiHeld;
      const total = s.totalHours ?? 0;
      const group = db.groups.find((g) => g.subjectIds.includes(s.id));
      return {
        subject: s,
        held: h,
        total,
        progress: total > 0 ? Math.round((h / total) * 100) : 0,
        groupId: group?.id ?? 0,
        groupName: group?.name ?? "—",
      };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [db, ver]);

  return (
    <Screen className="pb-28">
      <BigHeader
        kicker={`${formatLong(today)} · ${parity === 1 ? "чётная" : "нечётная"} неделя`}
        title="Сегодня"
      />

      {/* Прошедшие пары без «проведено»/«отменено» — напоминание со ссылками. */}
      <PendingLessonsCard />

      <Btn
        size="lg"
        icon={Play}
        className="w-full mb-1 tracking-[0.01em]"
        onClick={() => {
          setPlanPair(null);
          setSheetOpen(true);
        }}
      >
        Начать занятие
      </Btn>

      <SectionTitle className="mt-5">
        Занятия сегодня · {rows.length}
      </SectionTitle>

      {rows.length === 0 && (
        <Card>
          <EmptyState
            icon={CalendarOff}
            title="Сегодня пар нет"
            hint="Начните занятие вручную или проверьте расписание на неделю."
          />
        </Card>
      )}
      {rows.map((row) => (
        <LessonCard
          key={row.key}
          row={row}
          onStartPlan={(pair) => {
            setPlanPair(pair);
            setSheetOpen(true);
          }}
        />
      ))}

      <SectionTitle>Сводка</SectionTitle>
      <Card className="grid grid-cols-3 divide-x divide-line">
        {[
          { label: "Студентов", value: String(stats.students), sub: `${stats.groups} гр.` },
          { label: "Ср. балл недели", value: formatAvg(stats.avg), sub: "домашняя сводка" },
          {
            label: "Должники", value: String(stats.debtors), sub: "ср. ниже 3",
            tone: stats.debtors > 0 ? "text-g2" : "",
            tap: true,
          },
        ].map((s) => (
          <div
            key={s.label}
            className={`px-3 py-3.5 text-center${s.tap ? " cursor-pointer active:bg-surface2" : ""}`}
            onClick={s.tap ? () => setDebtorsOpen(true) : undefined}
          >
            <div className={`text-[22px] font-extrabold tabular-nums leading-none ${s.tone ?? ""}`}>
              {s.value}
            </div>
            <div className="mt-1.5 text-[10px] font-bold uppercase tracking-[0.07em] text-muted inline-flex items-center gap-0.5">
              {s.label}
              {s.tap && <ChevronRight size={10} className="text-faint" />}
            </div>
            <div className="text-[10px] text-faint">{s.sub}</div>
          </div>
        ))}
      </Card>

      <SectionTitle>По предметам</SectionTitle>
      <Card className="divide-y divide-line overflow-hidden">
        {subjectRows.length === 0 ? (
          <div className="py-6 text-center text-[13px] text-muted">Нет предметов</div>
        ) : (
          subjectRows.map((r) => (
            <div
              key={r.subject.id}
              className="px-3.5 py-3 cursor-pointer active:bg-surface2"
              onClick={() => navigate(`/statement/${r.groupId}/${r.subject.id}`)}
            >
              <div className="flex items-center gap-2.5">
                <div className="min-w-0 flex-1">
                  <div className="text-[14px] font-semibold truncate">{r.subject.name}</div>
                </div>
                <Chip tone="neutral">{r.groupName}</Chip>
                <span className="text-[13px] font-bold tabular-nums shrink-0">
                  {r.total > 0 ? `${r.held} / ${r.total} ${pairWord(r.total)}` : "—"}
                </span>
                <ChevronRight size={14} className="text-faint shrink-0" />
              </div>
              <div className="mt-2.5 flex items-center gap-2.5">
                <div className="flex-1 h-2.5 rounded-full bg-line overflow-hidden">
                  <div className="h-full rounded-full bg-accent" style={{ width: `${r.progress}%` }} />
                </div>
                <span className="w-9 shrink-0 text-right text-[12px] font-bold tabular-nums text-muted">
                  {r.total > 0 ? `${r.progress}%` : "—"}
                </span>
              </div>
              {r.total === 0 && (
                <div className="mt-1 text-[11px] text-faint">выделенных пар нет</div>
              )}
            </div>
          ))
        )}
      </Card>

      <Sheet
        open={debtorsOpen}
        onClose={() => setDebtorsOpen(false)}
        title={`Должники · ${stats.debtors}`}
      >
        {stats.debtorRows.length === 0 ? (
          <div className="py-8 text-center text-[14px] text-muted">Нет должников</div>
        ) : (
          <Card className="divide-y divide-line overflow-hidden">
            {stats.debtorRows.map(({ student, avg }) => {
              const group = store.group(student.groupId);
              return (
                <div
                  key={student.id}
                  className="flex items-center gap-2.5 px-3 py-2.5 cursor-pointer active:bg-surface2"
                  onClick={() => {
                    setDebtorsOpen(false);
                    navigate("/group/" + student.groupId);
                  }}
                >
                  <div className="min-w-0 flex-1">
                    <div className="text-[14px] font-semibold truncate text-g2">{student.name}</div>
                    <div className="text-[11px] text-faint">{group?.name ?? "—"}</div>
                  </div>
                  {avg !== null && (
                    <span className="text-[13px] font-bold tabular-nums text-g2">{formatAvg(avg)}</span>
                  )}
                  <ChevronRight size={14} className="text-faint shrink-0" />
                </div>
              );
            })}
          </Card>
        )}
      </Sheet>

      <NewLessonSheet
        open={sheetOpen}
        onClose={() => setSheetOpen(false)}
        initialPair={planPair ?? undefined}
        onCreated={(lesson) => navigate("/lesson/" + lesson.id)}
      />
    </Screen>
  );
}
