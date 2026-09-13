/* Экран проведения занятия — основной рабочий сценарий преподавателя.
   2-колоночный компактный список: правая половина строки — оценка вперёд
   (— → 0 → 5 → 4 → 3 → 2), левая — назад. Точка слева — отсутствие.
   Шапка и подвал компактные (≤10% высоты экрана каждая). */

import { useEffect, useMemo, useState } from "react";
import {
  Ban, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight,
  CircleCheck, MoreVertical, RotateCcw, Trash2,
} from "lucide-react";
import { useDB, store, lessonAvg } from "../lib/store";
import { formatDot, formatLong } from "../lib/date";
import { buzz, formatAvg } from "../lib/grades";
import { navigate, goBack } from "../lib/router";
import { Btn, Chip, ConfirmSheet, GradeChip, IconBtn, Sheet, useToast } from "../components/ui";
import { cn } from "../utils/cn";
import type { Lesson, Student } from "../lib/types";

/* ── Ячейка студента с двусторонним тапом ─────────────────── */
function StudentCell({
  lesson, student, disabled,
}: { lesson: Lesson; student: Student; disabled: boolean }) {
  const rec = store.gradeOf(lesson.id, student.id);
  const value = rec?.value ?? null;
  const present = rec?.present ?? true;

  const step = (e: React.MouseEvent<HTMLElement>) => {
    if (disabled || !present) return;
    const r = e.currentTarget.getBoundingClientRect();
    const dir = e.clientX - r.left < r.width / 2 ? -1 : 1;
    store.cycleGrade(lesson.id, student.id, dir);
    buzz(6);
  };

  return (
    <div
      role="button"
      aria-disabled={disabled}
      tabIndex={0}
      onClick={step}
      onKeyDown={(e) => {
        if ((e.key === "Enter" || e.key === " ") && !disabled && present) {
          e.preventDefault();
          store.cycleGrade(lesson.id, student.id, 1);
          buzz(6);
        }
      }}
      className={cn(
        "relative h-[62px] px-2.5 pb-3 rounded-xl border text-left select-none cursor-pointer",
        "flex items-center gap-2 transition-colors duration-150",
        present
          ? "bg-surface border-line active:border-linestrong active:bg-surface2"
          : "bg-surface2 border-line opacity-80",
        disabled && "opacity-60 pointer-events-none",
      )}
    >
      {/* Точка присутствия */}
      <span
        role="button"
        aria-label={present ? "Отметить отсутствующим" : "Отметить присутствующим"}
        onClick={(e) => {
          e.stopPropagation();
          if (disabled) return;
          store.togglePresent(lesson.id, student.id);
          buzz(10);
        }}
        className={cn(
          "shrink-0 w-[26px] h-[26px] grid place-items-center rounded-full",
        )}
      >
        <span
          className={cn(
            "block w-2.5 h-2.5 rounded-full transition-colors",
            present ? "bg-g5" : "bg-g2 an-pulse-dot",
          )}
        />
      </span>

      <span
        className={cn(
          "flex-1 min-w-0 text-[13px] leading-[1.15] font-semibold clamp2",
          !present && "text-muted line-through decoration-linestrong",
        )}
      >
        {student.name}
      </span>

      <GradeChip
        value={value}
        present={present}
        animateKey={`${value}-${present}`}
        size="md"
      />

      {/* Подсказки направления перебора */}
      <span className="absolute bottom-[3px] left-2.5 text-faint">
        <ChevronsLeft size={10} />
      </span>
      <span className="absolute bottom-[3px] right-2.5 text-faint">
        <ChevronsRight size={10} />
      </span>
    </div>
  );
}

/* ── Экран ────────────────────────────────────────────────── */
export default function LessonRunScreen({ id }: { id: number }) {
  useDB();
  const toast = useToast();
  const lesson = store.lesson(id);

  const [menuOpen, setMenuOpen] = useState(false);
  const [cancelConfirm, setCancelConfirm] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);

  const siblings = useMemo(
    () => (lesson ? store.lessonsOfPair(lesson.groupId, lesson.subjectId) : []),
    [lesson?.id, lesson?.status],
  );

  useEffect(() => {
    // PROD: подтянуть свежие данные урока с сервера (attendance + adjacent).
    store.loadLesson(id);
    // Если студентов добавили после создания занятия — досоздать пустые записи.
    store.ensureGrades(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (!lesson) {
    return (
      <div className="pt-safe px-4">
        <header className="flex items-center gap-1 py-2.5">
          <IconBtn icon={ChevronLeft} label="Назад" onClick={() => goBack("/today")} />
          <h1 className="text-[16px] font-bold">Занятие не найдено</h1>
        </header>
      </div>
    );
  }

  const subject = store.subject(lesson.subjectId);
  const group = store.group(lesson.groupId);
  const students = store.studentsOf(lesson.groupId);
  const recs = store.gradesOfLesson(lesson.id);
  const graded = recs.filter((r) => r.present && r.value !== null).length;
  const presentCount = recs.filter((r) => r.present).length;
  const avg = lessonAvg(recs);
  const cancelled = lesson.status === "cancelled";

  const idx = siblings.findIndex((l) => l.id === lesson.id);
  const prev = idx > 0 ? siblings[idx - 1] : null;
  const next = idx >= 0 && idx < siblings.length - 1 ? siblings[idx + 1] : null;

  const finish = () => {
    store.setLessonStatus(lesson.id, "held");
    toast("Занятие сохранено · ср. " + formatAvg(lessonAvg(store.gradesOfLesson(lesson.id))));
  };

  return (
    <div className="min-h-screen flex flex-col bg-bg">
      {/* Шапка: компактная, фиксированная */}
      <header className="sticky top-0 z-30 bg-surface border-b border-line pt-safe">
        <div className="flex items-center gap-1 px-2 py-1.5 h-[54px]">
          <IconBtn icon={ChevronLeft} label="Назад" onClick={() => goBack("/today")} />
          <div className="flex-1 min-w-0">
            <div className="text-[14px] font-bold leading-tight truncate">
              {subject?.name}
            </div>
            <div className="text-[11px] text-muted leading-tight truncate">
              {group?.name} · {formatDot(lesson.date)}
              {lesson.lessonNumber > 0 && <> · пара №{lesson.lessonNumber}</>}
            </div>
          </div>
          <Chip tone={lesson.status === "held" ? "success" : lesson.status === "scheduled" ? "warn" : "danger"}>
            {graded}/{students.length}
          </Chip>
          <IconBtn icon={MoreVertical} label="Действия" onClick={() => setMenuOpen(true)} />
        </div>
        <div className="px-4 pb-1.5 text-[10.5px] text-faint leading-tight">
          Тап по правой половине — оценка вперёд, по левой — назад. Точка — отсутствие.
        </div>
      </header>

      {cancelled && (
        <div className="mx-4 mt-3 p-3 rounded-xl bg-dangerbg text-danger text-[13px] font-semibold flex items-center gap-2">
          <Ban size={15} className="shrink-0" />
          Занятие отменено. Оценки скрыты из ведомости.
        </div>
      )}

      {/* Сетка студентов: 2 колонки */}
      <main className="flex-1 px-4 pt-3 pb-24">
        <div className="grid grid-cols-2 gap-2">
          {students.map((st) => (
            <StudentCell key={st.id} lesson={lesson} student={st} disabled={cancelled} />
          ))}
        </div>
        {students.length === 0 && (
          <div className="py-10 text-center text-[13.5px] text-muted">
            В группе нет студентов.
          </div>
        )}
      </main>

      {/* Подвал: компактный, ≤10% экрана */}
      <footer className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[480px] z-30
        bg-surface border-t border-line pb-safe">
        <div className="flex items-center gap-3 px-4 py-2 min-h-[52px]">
          <div className="flex-1 min-w-0 text-[11.5px] text-muted leading-tight">
            <span className="font-bold text-ink tabular-nums">{presentCount}</span> присут. ·{" "}
            ср. <span className="font-bold text-ink tabular-nums">{formatAvg(avg)}</span>
          </div>
          {lesson.status === "scheduled" ? (
            <Btn size="md" icon={CircleCheck} onClick={finish} className="shrink-0">
              Завершить
            </Btn>
          ) : (
            <Chip tone={lesson.status === "held" ? "success" : "danger"} className="h-7">
              {lesson.status === "held" ? "Проведено" : "Отменено"}
            </Chip>
          )}
        </div>
      </footer>

      {/* Меню действий */}
      <Sheet open={menuOpen} onClose={() => setMenuOpen(false)} title="Занятие">
        <div className="flex flex-col gap-1.5">
          <div className="text-[12px] text-muted mb-2">{formatLong(lesson.date)}</div>

          <Btn
            variant="muted" className="justify-start" icon={ChevronLeft}
            disabled={!prev}
            onClick={() => { setMenuOpen(false); if (prev) navigate("/lesson/" + prev.id); }}
          >
            Предыдущее занятие{prev ? ` · ${formatDot(prev.date)}` : ""}
          </Btn>
          <Btn
            variant="muted" className="justify-start" icon={ChevronRight}
            disabled={!next}
            onClick={() => { setMenuOpen(false); if (next) navigate("/lesson/" + next.id); }}
          >
            Следующее занятие{next ? ` · ${formatDot(next.date)}` : ""}
          </Btn>

          <div className="h-px bg-line my-1.5" />

          {!cancelled ? (
            <Btn
              variant="muted" className="justify-start" icon={Ban}
              onClick={() => { setMenuOpen(false); setCancelConfirm(true); }}
            >
              Отменить занятие
            </Btn>
          ) : (
            <Btn
              variant="muted" className="justify-start" icon={RotateCcw}
              onClick={() => {
                store.setLessonStatus(lesson.id, "scheduled");
                setMenuOpen(false);
                toast("Занятие возвращено в расписание");
              }}
            >
              Вернуть в расписание
            </Btn>
          )}
          <Btn
            variant="danger" className="justify-start" icon={Trash2}
            onClick={() => { setMenuOpen(false); setDeleteConfirm(true); }}
          >
            Удалить занятие
          </Btn>
        </div>
      </Sheet>

      <ConfirmSheet
        open={cancelConfirm}
        onClose={() => setCancelConfirm(false)}
        title="Отменить занятие?"
        body={`На занятии уже выставлено оценок: ${graded}. Занятие будет помечено отменённым, оценки сохранятся, но уйдут из ведомости.`}
        confirmLabel="Отменить занятие"
        danger
        onConfirm={() => {
          store.setLessonStatus(lesson.id, "cancelled");
          toast("Занятие отменено");
        }}
      />

      <ConfirmSheet
        open={deleteConfirm}
        onClose={() => setDeleteConfirm(false)}
        title="Удалить занятие?"
        body={`Будут безвозвратно удалены занятие от ${formatDot(lesson.date)} и ${graded} оценок.`}
        confirmLabel="Удалить"
        danger
        onConfirm={() => {
          store.removeLesson(lesson.id);
          navigate("/today");
          toast("Занятие удалено");
        }}
      />
    </div>
  );
}
