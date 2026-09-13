/* Расписание недели: единый список по дням (пн–сб), без чёт/нечёт,
   + ручные занятия (созданные через «Начать занятие» вне расписания). */

import { useMemo, useState } from "react";
import { ChevronRight, Plus, Repeat, Trash2 } from "lucide-react";
import { useDB, store } from "../lib/store";
import {
  addDaysISO, formatDotShort, mondayOfWeek, parityLabel, todayISO, weekdayOf, weekdayShort,
} from "../lib/date";
import { navigate } from "../lib/router";
import { BigHeader, Screen, AvatarTile } from "../components/shell";
import {
  Btn, Card, Chip, ConfirmSheet, Field, IconBtn,
  Input, Select, Sheet, SectionTitle, useToast,
} from "../components/ui";
import { cn } from "../utils/cn";
import type { ScheduleItem } from "../lib/types";

const WD = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
const DAY_FULL = ["", "Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"];

export default function ScheduleScreen() {
  const db = useDB();
  const toast = useToast();
  const today = todayISO();

  const [actionItem, setActionItem] = useState<ScheduleItem | null>(null);
  const [removeConfirm, setRemoveConfirm] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [selectedISO, setSelectedISO] = useState(today);

  // Форма добавления
  const [fGroup, setFGroup] = useState("");
  const [fSubject, setFSubject] = useState("");
  const [fNewSubject, setFNewSubject] = useState("");
  const [fParity, setFParity] = useState("0");
  const [fLessonNum, setFLessonNum] = useState("1");
  const [fWeekday, setFWeekday] = useState(String(weekdayOf(today)));

  const monday = mondayOfWeek(today);

  /** Лента дат: две недели от понедельника текущей недели (горизонтальный скролл). */
  const days = useMemo(
    () => Array.from({ length: 14 }, (_, i) => addDaysISO(monday, i)),
    [monday],
  );

  /** Тап по дате → переход к занятиям этого дня (первое занятие дня). */
  const goToDay = (iso: string) => {
    setSelectedISO(iso);
    const lessons = store.lessonsOn(iso);
    if (lessons.length > 0) {
      navigate("/lesson/" + lessons[0].id);
    } else {
      toast("В этот день занятий нет");
    }
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

  const saveItem = () => {
    const gid = Number(fGroup);
    let sid = fSubject ? Number(fSubject) : null;
    if (!sid && fNewSubject.trim()) sid = store.addSubject(fNewSubject, gid).id;
    if (!gid || !sid) { toast("Выберите группу и предмет"); return; }
    // Мягкая валидация дублирующегося номера в тот же день — сервер остаётся источником истины.
    const num = Number(fLessonNum);
    const wd = Number(fWeekday);
    const dup = db.schedule.some((it) => it.weekday === wd && it.lessonNumber === num);
    if (dup) toast("Номер пары уже занят в этот день — сервер решит");
    store.addScheduleItem({
      groupId: gid,
      subjectId: sid,
      weekday: wd,
      parity: Number(fParity) as 0 | 1 | 2,
      time: "",
      room: "",
      lessonNumber: num,
    });
    setAddOpen(false);
    toast("Пара добавлена в расписание");
  };

  /** Пары дня (все чётности) по номеру пары. */
  const itemsOf = (day: number) =>
    db.schedule
      .filter((it) => it.weekday === day)
      .sort((a, b) => a.lessonNumber - b.lessonNumber || a.time.localeCompare(b.time));

  /** Ручные занятия дня: созданы вручную и не имеют пары в расписании этого дня. */
  const manualOf = (day: number) =>
    db.lessons
      .filter((l) => weekdayOf(l.date) === day)
      .filter((l) => !store.scheduleItemForDay(l.groupId, l.subjectId, day))
      .sort((a, b) => a.lessonNumber - b.lessonNumber || a.time.localeCompare(b.time));

  return (
    <Screen className="pb-28">
      <BigHeader
        kicker={`${formatDotShort(monday)} – ${formatDotShort(addDaysISO(monday, 5))}`}
        title="Расписание"
        actions={<IconBtn icon={Plus} label="Добавить пару" onClick={openAdd} className="bg-surface border border-line" />}
      />

      {/* Лента дат: горизонтальный скролл, тап → занятия дня */}
      <div className="-mx-4 px-4 mb-4 overflow-x-auto no-scrollbar">
        <div className="flex gap-1.5 min-w-max">
          {days.map((iso) => {
            const selected = iso === selectedISO;
            const isToday = iso === today;
            return (
              <button
                key={iso}
                onClick={() => goToDay(iso)}
                className={cn(
                  "pressable flex flex-col items-center w-[52px] py-2 rounded-xl border shrink-0",
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
      </div>

      {[1, 2, 3, 4, 5, 6].map((day) => {
        const items = itemsOf(day);
        const manual = manualOf(day);
        const isToday = day === weekdayOf(today);
        return (
          <div key={day}>
            <SectionTitle action={isToday ? <Chip tone="accent">сегодня</Chip> : undefined}>
              {DAY_FULL[day]}
            </SectionTitle>

            {items.map((it) => {
              const g = store.group(it.groupId);
              const s = store.subject(it.subjectId);
              if (!g || !s) return null;
              return (
                <Card
                  key={it.id}
                  className="p-3.5 mb-2 flex items-center gap-3"
                  onClick={() => setActionItem(it)}
                >
                  <div className="w-[44px] shrink-0 text-center">
                    <div className="text-[15px] font-extrabold tabular-nums leading-none">
                      №{it.lessonNumber}
                    </div>
                    <div className="mt-0.5 text-[9.5px] font-bold uppercase tracking-wide text-faint">
                      пара
                    </div>
                  </div>
                  <div className="w-px self-stretch bg-line" />
                  <AvatarTile text={g.name.slice(0, 2)} className="w-9 h-9 text-[11px]" />
                  <div className="min-w-0 flex-1">
                    <div className="text-[14.5px] font-bold truncate">{s.name}</div>
                    <div className="text-[12px] text-muted truncate">
                      {g.name}
                    </div>
                  </div>
                  {it.parity !== 0 && (
                    <Chip tone="neutral" className="normal-case">
                      <Repeat size={10} />{parityLabel(it.parity)}
                    </Chip>
                  )}
                  <ChevronRight size={16} className="text-faint shrink-0" />
                </Card>
              );
            })}

            {manual.length > 0 && (
              <>
                {manual.map((l) => {
                  const g = store.group(l.groupId);
                  const s = store.subject(l.subjectId);
                  if (!g || !s) return null;
                  return (
                    <Card
                      key={l.id}
                      className="p-3.5 mb-2 flex items-center gap-3"
                      onClick={() => navigate("/lesson/" + l.id)}
                    >
                      <div className="w-[44px] shrink-0 text-center">
                        <div className="text-[15px] font-extrabold tabular-nums leading-none">
                          {l.lessonNumber > 0 ? `№${l.lessonNumber}` : "—"}
                        </div>
                        <div className="mt-0.5 text-[9.5px] font-bold uppercase tracking-wide text-faint">
                          пара
                        </div>
                      </div>
                      <div className="w-px self-stretch bg-line" />
                      <AvatarTile text={g.name.slice(0, 2)} className="w-9 h-9 text-[11px]" />
                      <div className="min-w-0 flex-1">
                        <div className="text-[14.5px] font-bold truncate">{s.name}</div>
                        <div className="text-[12px] text-muted truncate">{g.name}</div>
                      </div>
                      <Chip tone="accent">вручную</Chip>
                      <ChevronRight size={16} className="text-faint shrink-0" />
                    </Card>
                  );
                })}
              </>
            )}

            {items.length === 0 && manual.length === 0 && (
              <div className="px-1 py-1.5 text-[12.5px] text-faint">Пар нет</div>
            )}
          </div>
        );
      })}

      {/* Действия с парой */}
      <Sheet
        open={actionItem !== null}
        onClose={() => setActionItem(null)}
        title="Пара в расписании"
      >
        {actionItem && (() => {
          const g = store.group(actionItem.groupId);
          const s = store.subject(actionItem.subjectId);
          const lesson = store
            .lessonsOn(today)
            .find((l) => l.groupId === actionItem.groupId && l.subjectId === actionItem.subjectId);
          return (
            <div className="flex flex-col gap-1.5">
              <div className="mb-3 text-[14px]">
                <span className="font-bold">{s?.name}</span>
                <span className="text-muted"> · {g?.name}</span>
              </div>
              {lesson ? (
                <Btn
                  className="justify-start"
                  onClick={() => { setActionItem(null); navigate("/lesson/" + lesson.id); }}
                >
                  Открыть занятие за сегодня
                </Btn>
              ) : (
                <Btn
                  className="justify-start"
                  onClick={async () => {
                    const l = await store.createLesson(actionItem.groupId, actionItem.subjectId, today);
                    setActionItem(null);
                    navigate("/lesson/" + l.id);
                  }}
                >
                  Создать занятие на сегодня
                </Btn>
              )}
              <Btn
                variant="danger" className="justify-start" icon={Trash2}
                onClick={() => setRemoveConfirm(true)}
              >
                Удалить из расписания
              </Btn>
            </div>
          );
        })()}
      </Sheet>

      {/* Добавление пары */}
      <Sheet open={addOpen} onClose={() => setAddOpen(false)} title="Новая пара">
        <div className="flex flex-col gap-4">
          <Field label="Группа">
            <Select value={fGroup} onChange={(e) => setFGroup(e.target.value)}>
              {db.groups.map((g) => (
                <option key={g.id} value={g.id}>{g.name}</option>
              ))}
            </Select>
          </Field>
          <Field label="Предмет">
            <Select value={fSubject} onChange={(e) => { setFSubject(e.target.value); setFNewSubject(""); }}>
              <option value="">— выбрать —</option>
              {db.subjects.map((s) => (
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
                <option key={n} value={n}>Пара №{n}</option>
              ))}
            </Select>
          </Field>
          <Btn size="lg" onClick={saveItem}>Добавить</Btn>
        </div>
      </Sheet>

      <ConfirmSheet
        open={removeConfirm}
        onClose={() => setRemoveConfirm(false)}
        title="Удалить из расписания?"
        body="Пара исчезнет из расписания на следующие недели. Проведённые занятия и оценки сохранятся."
        confirmLabel="Удалить"
        danger
        onConfirm={() => {
          if (actionItem) store.removeScheduleItem(actionItem.id);
          setActionItem(null);
          toast("Пара удалена из расписания");
        }}
      />
    </Screen>
  );
}