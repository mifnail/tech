/* Расписание: лента дат (14 дней) + занятия выбранного дня,
   сгруппированные по группам. Ручные занятия (созданные через
   «Начать занятие» вне расписания) помечаются чипом «вручную». */

import { useMemo, useState } from "react";
import {
  Ban, CalendarOff, ChevronRight, CircleAlert, CircleCheck, Play, Plus,
} from "lucide-react";
import { useDB, useVersion, store } from "../lib/store";
import {
  addDaysISO, formatDotShort, formatLong, mondayOfWeek, todayISO, weekdayOf, weekdayShort,
} from "../lib/date";
import { navigate } from "../lib/router";
import { BigHeader, Screen, AvatarTile } from "../components/shell";
import {
  Btn, Card, Chip, EmptyState, Field, IconBtn,
  Input, Select, Sheet, SectionTitle, useToast,
} from "../components/ui";
import { NewLessonSheet } from "../components/NewLessonSheet";
import { cn } from "../utils/cn";
import type { Group, Lesson } from "../lib/types";

const WD = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
const DAY_FULL = ["", "Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"];

export default function ScheduleScreen() {
  const db = useDB();
  const ver = useVersion();
  const toast = useToast();
  const today = todayISO();

  const [addOpen, setAddOpen] = useState(false);
  const [selectedISO, setSelectedISO] = useState(today);
  const [newLessonOpen, setNewLessonOpen] = useState(false);

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

  /** Занятия выбранного дня (по расписанию + ручные), сгруппированные по группам. */
  const dayGroups = useMemo(() => {
    const byGroup = new Map<number, Lesson[]>();
    for (const l of store.lessonsOn(selectedISO)) {
      const arr = byGroup.get(l.groupId);
      if (arr) arr.push(l);
      else byGroup.set(l.groupId, [l]);
    }
    return [...byGroup.entries()]
      .map(([groupId, items]) => ({
        group: store.group(groupId),
        items: items.sort(
          (a, b) => a.lessonNumber - b.lessonNumber || a.time.localeCompare(b.time),
        ),
      }))
      .filter((x): x is { group: Group; items: Lesson[] } => x.group !== undefined)
      .sort((a, b) => a.group.name.localeCompare(b.group.name));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [db, ver, selectedISO]);

  return (
    <Screen className="pb-28">
      <BigHeader
        kicker={`${formatDotShort(monday)} – ${formatDotShort(addDaysISO(monday, 5))}`}
        title="Расписание"
        actions={<IconBtn icon={Plus} label="Добавить пару" onClick={openAdd} className="bg-surface border border-line" />}
      />

      {/* Лента дат: горизонтальный скролл, тап → занятия выбранного дня */}
      <div className="-mx-4 px-4 mb-4 overflow-x-auto no-scrollbar">
        <div className="flex gap-1.5 min-w-max">
          {days.map((iso) => {
            const selected = iso === selectedISO;
            const isToday = iso === today;
            return (
              <button
                key={iso}
                onClick={() => setSelectedISO(iso)}
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

      {/* Занятия выбранной даты */}
      <SectionTitle action={selectedISO === today ? <Chip tone="accent">сегодня</Chip> : undefined}>
        {formatLong(selectedISO)}
      </SectionTitle>

      {dayGroups.length === 0 ? (
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
        dayGroups.map(({ group, items }) => (
          <div key={group.id}>
            <SectionTitle>{group.name}</SectionTitle>
            {items.map((l) => {
              const s = store.subject(l.subjectId);
              if (!s) return null;
              const manual = !store.scheduleItemForDay(
                l.groupId, l.subjectId, weekdayOf(l.date),
              );
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
                  <AvatarTile text={group.name.slice(0, 2)} className="w-9 h-9 text-[11px]" />
                  <div className="min-w-0 flex-1">
                    <div className="text-[14.5px] font-bold truncate">{s.name}</div>
                    <div className="text-[12px] text-muted truncate">{group.name}</div>
                  </div>
                  {l.status === "held" && <Chip tone="success"><CircleCheck size={11} />Проведено</Chip>}
                  {l.status === "scheduled" && <Chip tone="warn"><CircleAlert size={11} />Назначено</Chip>}
                  {l.status === "cancelled" && <Chip tone="danger"><Ban size={11} />Отменено</Chip>}
                  {manual && <Chip tone="accent">вручную</Chip>}
                  <ChevronRight size={16} className="text-faint shrink-0" />
                </Card>
              );
            })}
          </div>
        ))
      )}

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