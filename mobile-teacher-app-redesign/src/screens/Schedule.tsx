/* Расписание: понедельная лента дат (пн–вс, стрелки ←/→ в обе стороны)
   + день выбранной даты: реальные занятия журнала и незакрытые слоты шаблона
   (day_of_week, чёт/нечёт) строкой «по расписанию». Ручные занятия
   (созданные через «Начать занятие» вне расписания) помечаются чипом «вручную». */

import { useMemo, useState } from "react";
import {
  CalendarOff, ChevronLeft, ChevronRight, Pencil, Play, Plus,
} from "lucide-react";
import { useDB, useVersion, store } from "../lib/store";
import {
  addDaysISO, formatDotShort, formatLong, mondayOfWeek, todayISO, weekTypeOf, weekdayOf, weekdayShort,
} from "../lib/date";
import { navigate } from "../lib/router";
import { BigHeader, Screen, PairNumber, StatusDot, groupInk, dayRows } from "../components/shell";
import type { DayRow } from "../components/shell";
import {
  Btn, Card, Chip, EmptyState, Field, IconBtn,
  Input, Select, Sheet, SectionTitle, useToast,
} from "../components/ui";
import { NewLessonSheet } from "../components/NewLessonSheet";
import { cn } from "../utils/cn";
import type { LessonStatus, ScheduleItem } from "../lib/types";

const WD = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
const DAY_FULL = ["", "Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"];

/* Паритет в форме — в шкале UI (1 = чётные, 2 = нечётные),
   в БД — наоборот (week_type 1 = нечётная, 2 = чётная). Одна точка перевода. */
const toDbParity = (ui: string): 0 | 1 | 2 => (ui === "1" ? 2 : ui === "2" ? 1 : 0);
const toUiParity = (db: number): string => (db === 2 ? "1" : db === 1 ? "2" : "0");

export default function ScheduleScreen() {
  const db = useDB();
  const ver = useVersion();
  const toast = useToast();
  const today = todayISO();

  const [addOpen, setAddOpen] = useState(false);
  const [selectedISO, setSelectedISO] = useState(today);
  const [newLessonOpen, setNewLessonOpen] = useState(false);
  const [weekOffset, setWeekOffset] = useState(0);

  // Форма добавления
  const [fGroup, setFGroup] = useState("");
  const [fSubject, setFSubject] = useState("");
  const [fNewSubject, setFNewSubject] = useState("");
  const [fParity, setFParity] = useState("0");
  const [fLessonNum, setFLessonNum] = useState("1");
  const [fWeekday, setFWeekday] = useState(String(weekdayOf(today)));
  const [editScheduleId, setEditScheduleId] = useState<number | null>(null);

  const monday = addDaysISO(mondayOfWeek(today), weekOffset * 7);

  // Предметы выбранной группы: в списке только свои — иначе после перезагрузки
  // сервер вернёт пару в группу предмета, и она «переедет» из выбранной.
  const groupSubjectIds = useMemo(
    () => store.group(Number(fGroup))?.subjectIds ?? [],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [db, fGroup],
  );
  const subjectOptions = useMemo(
    () => db.subjects.filter(
      (s) => groupSubjectIds.includes(s.id) || String(s.id) === fSubject,
    ),
    [db, groupSubjectIds, fSubject],
  );

  /** Лента дат: неделя (пн–вс) от monday текущего weekOffset. */
  const days = useMemo(
    () => Array.from({ length: 7 }, (_, i) => addDaysISO(monday, i)),
    [monday],
  );

  const goToday = () => {
    setWeekOffset(0);
    setSelectedISO(today);
  };

  /** Листание недель: выбранный день недели сохраняется.
      Без этого лента уезжает, а панель дня остаётся на старой дате —
      выглядит так, будто добавленная пара «не отображается». */
  const shiftWeek = (delta: number) => {
    const nextOffset = weekOffset + delta;
    setWeekOffset(nextOffset);
    const sameWeekday = weekdayOf(selectedISO); // 1 = понедельник
    setSelectedISO(addDaysISO(addDaysISO(mondayOfWeek(today), nextOffset * 7), sameWeekday - 1));
  };

  const openAdd = () => {
    setFGroup(db.groups[0] ? String(db.groups[0].id) : "");
    setFSubject("");
    setFNewSubject("");
    setFParity("0");
    setFLessonNum("1");
    setFWeekday(String(weekdayOf(today)));
    setAddOpen(true);
  };

  const saveItem = async () => {
    const gid = Number(fGroup);
    if (!gid) { toast("Выберите группу"); return; }
    let sid = fSubject ? Number(fSubject) : null;
    if (!sid && fNewSubject.trim()) {
      try {
        sid = (await store.addSubject(fNewSubject, gid)).id;
      } catch {
        toast("Не удалось создать предмет");
        return;
      }
    }
    if (!sid) { toast("Выберите предмет"); return; }
    const num = Number(fLessonNum);
    const wd = Number(fWeekday);
    const parity = toDbParity(fParity);

    if (editScheduleId !== null) {
      try {
        await store.updateScheduleItem(editScheduleId, {
          subjectId: sid, weekday: wd, parity, lessonNumber: num,
        });
      } catch {
        toast("Не удалось сохранить пару");
        return;
      }
      setAddOpen(false);
      setEditScheduleId(null);
      toast("Пара обновлена");
      return;
    }

    // Мягкая проверка дубля — только внутри своей группы (в одно время у
    // разных групп бывают пары с одинаковым номером). Сообщаем, какой
    // предмет уже занимает слот: иначе «уже есть» выглядит как ошибка,
    // если строку не видно из-за фильтра по чётности.
    const dup = db.schedule.find(
      (it) => it.groupId === gid && it.weekday === wd && it.lessonNumber === num,
    );
    if (dup) {
      const dupName = store.subject(dup.subjectId)?.name ?? "другой предмет";
      toast(`В ${num}-й паре у группы уже стоит «${dupName}»`, 3200);
      return;
    }

    try {
      await store.addScheduleItem({
        groupId: gid,
        subjectId: sid,
        weekday: wd,
        parity,
        time: "",
        room: "",
        lessonNumber: num,
      });
    } catch {
      toast("Не удалось сохранить пару");
      return;
    }
    setAddOpen(false);

    // Сразу показываем день, в который пара попала. Пара действует с
    // сегодняшнего дня, поэтому целимся не раньше сегодня: иначе после
    // добавления открывается прошедшая дата, где пары ещё не было.
    let target = addDaysISO(monday, wd - 1);
    let offset = weekOffset;
    while (target < today || (parity !== 0 && weekTypeOf(target) !== parity)) {
      target = addDaysISO(target, 7);
      offset += 1;
    }
    setWeekOffset(offset);
    setSelectedISO(target);

    const parityNote = parity === 0 ? "" : parity === 2 ? " · чётные недели" : " · нечётные недели";
    toast(`Пара добавлена: ${DAY_FULL[wd]}, ${num}-я пара${parityNote}`);
  };

  /** Тап по слоту шаблона = открыть занятие этой даты.
      Если занятия ещё нет — создаём его и сразу ведём в ведомость:
      преподаватель хочет ставить оценки и отмечать посещаемость, а не
      редактировать шаблон. Шаблон правится карандашом в строке. */
  const openPlanRow = async (it: ScheduleItem) => {
    if (selectedISO > today) {
      toast("Занятие ещё не наступило");
      return;
    }
    const existing = db.lessons.find(
      (l) => l.date === selectedISO
        && l.groupId === it.groupId
        && l.lessonNumber === it.lessonNumber,
    );
    if (existing) { navigate("/lesson/" + existing.id); return; }
    try {
      const lesson = await store.createLesson(
        it.groupId, it.subjectId, selectedISO, it.lessonNumber);
      navigate("/lesson/" + lesson.id);
    } catch {
      toast("Не удалось открыть занятие");
    }
  };

  /** Занятия выбранного дня + незакрытые слоты шаблона расписания (по дню недели),
      сгруппированные по группам. Реальные занятия приоритетнее шаблона. */
  /** Плоский список дня: без группировки по группам, только по номеру пары.
      Пары без номера (старые записи) уезжают в конец, чтобы не сбивать порядок. */
  const dayRowsList = useMemo(() => {
    const num = (row: DayRow) => {
      const n = row.kind === "lesson" ? row.lesson.lessonNumber : row.item.lessonNumber;
      return n > 0 ? n : 999;
    };
    return dayRows(db, selectedISO).slice().sort((a, b) => num(a) - num(b));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [db, ver, selectedISO]);

  return (
    <Screen className="pb-28">
      <BigHeader
        kicker={`${formatDotShort(monday)} – ${formatDotShort(addDaysISO(monday, 6))}`}
        title="Расписание"
        actions={<IconBtn icon={Plus} label="Добавить пару" onClick={openAdd} className="bg-surface border border-line" />}
      />

      {/* Лента дат: неделя (пн–вс) со стрелками ←/→ и кнопкой «Сегодня» */}
      <div className="flex items-center gap-1.5 mb-2">
        <IconBtn
          icon={ChevronLeft}
          label="Предыдущая неделя"
          onClick={() => shiftWeek(-1)}
          className="shrink-0 bg-surface border border-line"
        />
        <div className="flex flex-1 gap-1">
          {days.map((iso) => {
            const selected = iso === selectedISO;
            const isToday = iso === today;
            return (
              <button
                key={iso}
                onClick={() => setSelectedISO(iso)}
                className={cn(
                  "pressable flex flex-col items-center flex-1 py-2 rounded-xl border",
                  selected
                    ? "bg-accent border-accent text-accentink"
                    : "bg-surface border-line",
                )}
              >
                <span className={cn(
                  "text-[9.5px] font-bold uppercase tracking-wide",
                  selected ? "text-accentink opacity-80" : "text-faint",
                )}>
                  {weekdayShort(iso)}
                </span>
                <span className={cn(
                  "text-[15px] font-extrabold tabular-nums leading-tight",
                  !selected && isToday && "text-accent",
                )}>
                  {Number(iso.slice(8))}
                </span>
                <span className={cn(
                  "w-1 h-1 rounded-full mt-0.5",
                  isToday && !selected ? "bg-accent" : selected ? "bg-accentink" : "bg-transparent",
                )} />
              </button>
            );
          })}
        </div>
        <IconBtn
          icon={ChevronRight}
          label="Следующая неделя"
          onClick={() => shiftWeek(1)}
          className="shrink-0 bg-surface border border-line"
        />
      </div>
      <div className="flex justify-end mb-4">
        <Btn size="sm" variant="muted" onClick={goToday}>
          Сегодня
        </Btn>
      </div>

      {/* Занятия выбранной даты */}
      <SectionTitle action={selectedISO === today ? <Chip tone="accent">сегодня</Chip> : undefined}>
        {formatLong(selectedISO)}
      </SectionTitle>

      {dayRowsList.length === 0 ? (
        <EmptyState
          icon={CalendarOff}
          title="В этот день занятий нет"
          hint="Начните занятие вручную или выберите другую дату."
        >
          <Btn icon={Play} onClick={() => setNewLessonOpen(true)}>
            Начать занятие
          </Btn>
        </EmptyState>
      ) : (
        <>
          {dayRowsList.map((row) => {
              const src = row.kind === "lesson" ? row.lesson : row.item;
              const s = store.subject(src.subjectId);
              if (!s) return null;
              const group = store.group(
                row.kind === "lesson" ? row.lesson.groupId : row.item.groupId,
              );
              const groupName = group?.name ?? "";
              const schedItem = row.kind === "plan"
                ? row.item
                : store.scheduleItemForDay(
                    row.lesson.groupId, row.lesson.subjectId,
                    weekdayOf(row.lesson.date), row.lesson.date,
                  );
              const manual = row.kind === "lesson" && !schedItem;
              const status: LessonStatus =
                row.kind === "lesson" ? row.lesson.status : "scheduled";
              const startEdit = () => {
                if (!schedItem) return;
                setEditScheduleId(schedItem.id);
                setFGroup(String(schedItem.groupId));
                setFSubject(String(schedItem.subjectId));
                setFNewSubject("");
                setFParity(toUiParity(schedItem.parity));
                setFLessonNum(String(schedItem.lessonNumber));
                setFWeekday(String(schedItem.weekday));
                setAddOpen(true);
              };
              // Группа подписана под номером пары — строкой ниже не дублируем.
              const meta = src.time
                ? `${src.time}${src.room ? " · " + src.room : ""}`
                : "";
              const groupColor = group ? groupInk(group.name) : undefined;
              return (
                <Card
                  key={row.key}
                  className="relative p-3.5 mb-2 flex items-center gap-3"
                  onClick={
                    row.kind === "plan"
                      ? () => { void openPlanRow(row.item); }
                      : () => navigate("/lesson/" + src.id)
                  }
                >
                  <PairNumber
                    n={src.lessonNumber}
                    code={groupName}
                    codeColor={groupColor}
                    className="w-[48px]"
                  />
                  <div className="w-px self-stretch bg-line" />
                  <div className="min-w-0 flex-1">
                    <div className="text-[14.5px] font-bold leading-snug line-clamp-2 min-h-[2.6em]">
                      {s.name}
                    </div>
                    <div className="mt-1 flex items-center gap-1.5 min-w-0">
                      {meta && <span className="min-w-0 truncate text-[12px] text-muted">{meta}</span>}
                      {row.kind === "plan" && <Chip tone="neutral">по расписанию</Chip>}
                      {manual && <Chip tone="accent">вручную</Chip>}
                    </div>
                  </div>
                  <StatusDot status={status} />
                  {(row.kind === "plan" || (row.kind === "lesson" && !manual)) && (
                    <IconBtn
                      icon={Pencil}
                      label="Редактировать пару"
                      className="w-8 h-8 text-faint"
                      onClick={(e) => {
                        e.stopPropagation();
                        startEdit();
                      }}
                    />
                  )}
                  <ChevronRight size={16} className="text-faint shrink-0" />
                </Card>
              );
            })}
          <Btn variant="muted" icon={Play} onClick={() => setNewLessonOpen(true)} className="w-full mt-2">
            Начать занятие
          </Btn>
        </>
      )}

      {/* Добавление/редактирование пары */}
      <Sheet
        open={addOpen}
        onClose={() => { setAddOpen(false); setEditScheduleId(null); }}
        title={editScheduleId !== null ? "Редактировать пару" : "Новая пара"}
      >
        <div className="flex flex-col gap-4">
          <Field label="Группа">
            <Select
              value={fGroup}
              onChange={(e) => {
                setFGroup(e.target.value);
                setFSubject("");
                setFNewSubject("");
              }}
            >
              {db.groups.map((g) => (
                <option key={g.id} value={g.id}>{g.name}</option>
              ))}
            </Select>
          </Field>
          <Field label="Предмет">
            <Select value={fSubject} onChange={(e) => { setFSubject(e.target.value); setFNewSubject(""); }}>
              <option value="">— выбрать —</option>
              {subjectOptions.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </Select>
          </Field>
          <Field label="Или новый предмет">
            <Input
              value={fNewSubject}
              onChange={(e) => { setFNewSubject(e.target.value); setFSubject(""); }}
              placeholder="Например, Компьютерные сети"
            />
          </Field>
          <Field label="День недели">
            <Select value={fWeekday} onChange={(e) => setFWeekday(e.target.value)}>
              {[1, 2, 3, 4, 5, 6].map((d) => (
                <option key={d} value={d}>{DAY_FULL[d]}</option>
              ))}
            </Select>
          </Field>
          <Field label={`Повтор (${WD[Number(fWeekday) - 1].toLowerCase()})`}>
            <Select value={fParity} onChange={(e) => setFParity(e.target.value)}>
              <option value="0">Каждую неделю</option>
              <option value="1">Только чётные</option>
              <option value="2">Только нечётные</option>
            </Select>
          </Field>
          <Field label="Номер пары">
            <Select value={fLessonNum} onChange={(e) => setFLessonNum(e.target.value)}>
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>Пара {n}</option>
              ))}
            </Select>
          </Field>
          <Btn size="lg" onClick={saveItem}>
            {editScheduleId !== null ? "Сохранить" : "Добавить"}
          </Btn>
        </div>
      </Sheet>

      <NewLessonSheet
        open={newLessonOpen}
        onClose={() => setNewLessonOpen(false)}
        date={selectedISO}
        onCreated={(lesson) => {
          navigate("/lesson/" + lesson.id);
        }}
      />
    </Screen>
  );
}