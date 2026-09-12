/* Экран «Сегодня»: приветствие, занятия дня, быстрые метрики. */

import { useMemo, useState } from "react";
import { CalendarOff, ChevronRight, Play, CircleAlert, CircleCheck, Ban } from "lucide-react";
import { useDB, useVersion, store, lessonAvg } from "../lib/store";
import { formatLong, todayISO, weekParity, addDaysISO, formatDotShort, weekdayShort } from "../lib/date";
import { isDebtor, avgOf, formatAvg } from "../lib/grades";
import { navigate } from "../lib/router";
import { BigHeader, Screen } from "../components/shell";
import { Btn, Card, Chip, EmptyState, SectionTitle } from "../components/ui";
import { NewLessonSheet } from "../components/NewLessonSheet";
import type { Lesson } from "../lib/types";

function LessonCard({ lesson }: { lesson: Lesson }) {
  const subject = store.subject(lesson.subjectId);
  const group = store.group(lesson.groupId);
  const recs = store.gradesOfLesson(lesson.id);
  const avg = lessonAvg(recs);
  const graded = recs.filter((r) => r.present && r.value !== null).length;

  return (
    <Card
      className="p-3.5 mb-2 flex items-center gap-3"
      onClick={() => navigate("/lesson/" + lesson.id)}
    >
      {lesson.lessonNumber > 0 && (
        <>
          <div className="w-[52px] shrink-0 text-center">
            <div className="text-[15px] font-extrabold tabular-nums leading-none">
              №{lesson.lessonNumber}
            </div>
            <div className="mt-1 text-[10px] font-bold uppercase tracking-wide text-faint">
              пара
            </div>
          </div>
          <div className="w-px self-stretch bg-line" />
        </>
      )}
      <div className="min-w-0 flex-1">
        <div className="text-[14.5px] font-bold truncate">{subject?.name}</div>
        <div className="text-[12px] text-muted truncate">
          {group?.name}
          {lesson.status === "held" && graded > 0 && (
            <> · ср. {formatAvg(avg)} из {graded}</>
          )}
        </div>
      </div>
      {lesson.status === "held" && <Chip tone="success"><CircleCheck size={11} />Проведено</Chip>}
      {lesson.status === "scheduled" && <Chip tone="warn"><CircleAlert size={11} />Назначено</Chip>}
      {lesson.status === "cancelled" && <Chip tone="danger"><Ban size={11} />Отменено</Chip>}
      <ChevronRight size={16} className="text-faint shrink-0" />
    </Card>
  );
}

export default function TodayScreen() {
  const db = useDB();
  const ver = useVersion();
  const today = todayISO();
  const [sheetOpen, setSheetOpen] = useState(false);

  const lessons = store.lessonsOn(today);
  const parity = weekParity(today);

  const stats = useMemo(() => {
    const weekAgo = addDaysISO(today, -7);
    const weekLessonIds = new Set(
      db.lessons.filter((l) => l.date >= weekAgo && l.date <= today && l.status === "held").map((l) => l.id),
    );
    const weekGrades = db.grades
      .filter((g) => weekLessonIds.has(g.lessonId) && g.present)
      .map((g) => g.value);
    const debtors = db.students.filter((s) =>
      isDebtor(db.grades.filter((g) => g.studentId === s.id && g.present).map((g) => g.value)),
    ).length;
    return {
      students: db.students.length,
      avg: avgOf(weekGrades),
      debtors,
      groups: db.groups.length,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [db, ver]);

  const name = db.settings.teacherName.trim() || "Преподаватель";
  const yesterdayISO = addDaysISO(today, -1);
  const yesterdayLessons = store.lessonsOn(yesterdayISO).filter((l) => l.status === "held");

  return (
    <Screen className="pb-28">
      <BigHeader
        kicker={`${formatLong(today)} · ${parity === 1 ? "чётная" : "нечётная"} неделя`}
        title={`Здравствуйте,\n${name}`}
      />

      <Btn
        size="lg"
        icon={Play}
        className="w-full mb-1 tracking-[0.01em]"
        onClick={() => setSheetOpen(true)}
      >
        Начать занятие
      </Btn>

      <SectionTitle className="mt-5">
        Занятия сегодня · {lessons.length}
      </SectionTitle>

      {lessons.length === 0 && (
        <Card>
          <EmptyState
            icon={CalendarOff}
            title="Сегодня пар нет"
            hint="Начните занятие вручную или проверьте расписание на неделю."
          />
        </Card>
      )}
      {lessons.map((l) => (
        <LessonCard key={l.id} lesson={l} />
      ))}

      {yesterdayLessons.length > 0 && (
        <>
          <SectionTitle>{weekdayShort(yesterdayISO)}, {formatDotShort(yesterdayISO)} — проведённые</SectionTitle>
          {yesterdayLessons.slice(0, 3).map((l) => (
            <LessonCard key={l.id} lesson={l} />
          ))}
        </>
      )}

      <SectionTitle>Сводка</SectionTitle>
      <Card className="grid grid-cols-3 divide-x divide-line">
        {[
          { label: "Студентов", value: String(stats.students), sub: `${stats.groups} гр.` },
          { label: "Ср. балл недели", value: formatAvg(stats.avg), sub: "домашняя сводка" },
          { label: "Должники", value: String(stats.debtors), sub: "ср. ниже 3.5", tone: stats.debtors > 0 ? "text-g2" : "" },
        ].map((s) => (
          <div key={s.label} className="px-3 py-3.5 text-center">
            <div className={`text-[22px] font-extrabold tabular-nums leading-none ${s.tone ?? ""}`}>
              {s.value}
            </div>
            <div className="mt-1.5 text-[10px] font-bold uppercase tracking-[0.07em] text-muted">
              {s.label}
            </div>
            <div className="text-[10px] text-faint">{s.sub}</div>
          </div>
        ))}
      </Card>

      <NewLessonSheet
        open={sheetOpen}
        onClose={() => setSheetOpen(false)}
        onCreated={(lesson) => navigate("/lesson/" + lesson.id)}
      />
    </Screen>
  );
}
