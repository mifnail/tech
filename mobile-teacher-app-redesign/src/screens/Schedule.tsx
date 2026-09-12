/* Расписание недели: лента дней, чёт/неч, пары, добавление и удаление. */

import { useMemo, useState } from "react";
import { ChevronRight, Plus, Repeat, Trash2 } from "lucide-react";
import { useDB, store } from "../lib/store";
import {
  addDaysISO, mondayOfWeek, parityLabel, todayISO, weekParity, weekdayOf,
} from "../lib/date";
import { navigate } from "../lib/router";
import { BigHeader, Screen, AvatarTile } from "../components/shell";
import {
  Btn, Card, Chip, ConfirmSheet, EmptyState, Field, IconBtn,
  Input, Segmented, Select, Sheet, useToast,
} from "../components/ui";
import { CalendarOff } from "lucide-react";
import { cn } from "../utils/cn";
import type { ScheduleItem } from "../lib/types";

const WD = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

export default function ScheduleScreen() {
  const db = useDB();
  const toast = useToast();
  const today = todayISO();

  const [parity, setParity] = useState<"1" | "2">(String(weekParity(today)) as "1" | "2");
  const [selectedISO, setSelectedISO] = useState(today);
  const [actionItem, setActionItem] = useState<ScheduleItem | null>(null);
  const [removeConfirm, setRemoveConfirm] = useState(false);
  const [addOpen, setAddOpen] = useState(false);

  // Форма добавления
  const [fGroup, setFGroup] = useState("");
  const [fSubject, setFSubject] = useState("");
  const [fNewSubject, setFNewSubject] = useState("");
  const [fParity, setFParity] = useState("0");

  const monday = mondayOfWeek(selectedISO);
  const weekDays = useMemo(() => Array.from({ length: 7 }, (_, i) => addDaysISO(monday, i)), [monday]);
  const items = store.scheduleFor(weekdayOf(selectedISO), Number(parity) as 1 | 2);

  const openAdd = () => {
    setFGroup(db.groups[0] ? String(db.groups[0].id) : "");
    setFSubject("");
    setFNewSubject("");
    setFParity("0");
    setAddOpen(true);
  };

  const saveItem = () => {
    const gid = Number(fGroup);
    let sid = fSubject ? Number(fSubject) : null;
    if (!sid && fNewSubject.trim()) sid = store.addSubject(fNewSubject).id;
    if (!gid || !sid) { toast("Выберите группу и предмет"); return; }
    store.addScheduleItem({
      groupId: gid,
      subjectId: sid,
      weekday: weekdayOf(selectedISO),
      parity: Number(fParity) as 0 | 1 | 2,
      time: "",
      room: "",
    });
    setAddOpen(false);
    toast("Пара добавлена в расписание");
  };

  return (
    <Screen className="pb-28">
      <BigHeader
        kicker={weekParity(today) === 1 ? "Сейчас чётная неделя" : "Сейчас нечётная неделя"}
        title="Расписание"
        actions={<IconBtn icon={Plus} label="Добавить пару" onClick={openAdd} className="bg-surface border border-line" />}
      />

      <Segmented
        className="mb-3"
        value={parity}
        onChange={setParity}
        options={[
          { value: "1", label: "Чётная" },
          { value: "2", label: "Нечётная" },
        ]}
      />

      {/* Лента дней недели */}
      <div className="grid grid-cols-7 gap-1 mb-4">
        {weekDays.map((iso, i) => {
          const selected = iso === selectedISO;
          const isToday = iso === today;
          return (
            <button
              key={iso}
              onClick={() => setSelectedISO(iso)}
              className={cn(
                "pressable flex flex-col items-center py-2 rounded-xl border",
                selected
                  ? "bg-accent border-accent text-accentink"
                  : "bg-surface border-line",
              )}
            >
              <span className={cn(
                "text-[9.5px] font-bold uppercase tracking-wide",
                selected ? "text-accentink opacity-80" : "text-faint",
              )}>
                {WD[i]}
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

      {items.length === 0 && (
        <Card>
          <EmptyState
            icon={CalendarOff}
            title="Пар нет"
            hint={`На ${WD[weekdayOf(selectedISO) - 1].toLowerCase()} (${parity === "1" ? "чётная" : "нечётная"} нед.) ничего не запланировано.`}
          >
            <Btn icon={Plus} onClick={openAdd}>Добавить пару</Btn>
          </EmptyState>
        </Card>
      )}

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
            .lessonsOn(selectedISO)
            .find((l) => l.groupId === actionItem.groupId && l.subjectId === actionItem.subjectId);
          const canCreate = selectedISO <= today;
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
                  Открыть занятие за этот день
                </Btn>
              ) : (
                <Btn
                  className="justify-start"
                  disabled={!canCreate}
                  onClick={() => {
                    const l = store.createLesson(actionItem.groupId, actionItem.subjectId, selectedISO);
                    setActionItem(null);
                    navigate("/lesson/" + l.id);
                  }}
                >
                  {canCreate ? "Создать занятие на этот день" : "День ещё не наступил"}
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
          <Field label={`Повтор (${WD[weekdayOf(selectedISO) - 1].toLowerCase()})`}>
            <Select value={fParity} onChange={(e) => setFParity(e.target.value)}>
              <option value="0">Каждую неделю</option>
              <option value="1">Только чётные</option>
              <option value="2">Только нечётные</option>
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
