/* «Начать занятие»: выбор предмета → календарь-сетка
   (прошлое и сегодня доступны, будущее закрыто). */

import { useMemo, useState } from "react";
import { ArrowLeft, Check } from "lucide-react";
import type { ID, Lesson } from "../lib/types";
import { store } from "../lib/store";
import {
  addDaysISO, fromISO, formatDot, monthYearLabel, todayISO, toISO, weekdayShort,
} from "../lib/date";
import { cn } from "../utils/cn";
import { Btn, Sheet } from "./ui";
import { AvatarTile } from "./shell";

const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

export function NewLessonSheet({
  open, onClose, onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (lesson: Lesson) => void;
}) {
  const today = todayISO();
  const [pair, setPair] = useState<{ groupId: ID; subjectId: ID } | null>(null);
  const [month, setMonth] = useState(today.slice(0, 7));
  const [date, setDate] = useState(today);
  const [fNum, setFNum] = useState(0); // 0 = авто (из расписания)

  const pairs = useMemo(() => store.scheduledPairs(), [open]);

  const fromSchedule = pair ? store.scheduleItemFor(pair, date) : undefined;
  const effNum = fNum || fromSchedule?.lessonNumber || 0;

  const cells = useMemo(() => {
    const [y, m] = month.split("-").map(Number);
    const firstISO = `${month}-01`;
    const blanks = (fromISO(firstISO).getDay() + 6) % 7;
    const days = new Date(y, m, 0).getDate();
    const out: (string | null)[] = Array(blanks).fill(null);
    for (let d = 1; d <= days; d++) out.push(addDaysISO(firstISO, d - 1));
    return out;
  }, [month]);

  const shiftMonth = (dir: 1 | -1) => {
    const [y, m] = month.split("-").map(Number);
    setMonth(toISO(new Date(y, m - 1 + dir, 1)).slice(0, 7));
  };

  const close = () => {
    setPair(null);
    setDate(todayISO());
    setMonth(todayISO().slice(0, 7));
    setFNum(0);
    onClose();
  };

  const create = async () => {
    if (!pair) return;
    const lesson = await store.createLesson(pair.groupId, pair.subjectId, date, effNum);
    close();
    onCreated(lesson);
  };

  return (
    <Sheet open={open} onClose={close} title={pair ? "Дата занятия" : "Начать занятие"}>
      {!pair && (
        <div className="flex flex-col gap-2">
          <div className="text-[11px] font-bold uppercase tracking-[0.08em] text-muted mb-1">
            Выберите предмет
          </div>
          {pairs.length === 0 && (
            <p className="text-[14px] text-muted py-4 text-center">
              Нет предметов в расписании — добавьте пару на вкладке «Расписание».
            </p>
          )}
          {pairs.map((p) => {
            const g = store.group(p.groupId);
            const s = store.subject(p.subjectId);
            if (!g || !s) return null;
            return (
              <button
                key={p.groupId + "/" + p.subjectId}
                onClick={() => setPair(p)}
                className="pressable flex items-center gap-3 p-3 rounded-xl border border-line
                  bg-surface text-left active:bg-surface2"
              >
                <AvatarTile text={s.name.slice(0, 2)} />
                <span className="min-w-0">
                  <span className="block text-[14.5px] font-bold truncate">{s.name}</span>
                  <span className="block text-[12px] text-muted">{g.name}</span>
                </span>
              </button>
            );
          })}
        </div>
      )}

      {pair && (
        <div>
          <button
            onClick={() => setPair(null)}
            className="pressable inline-flex items-center gap-1.5 text-[13px] font-semibold
              text-accent mb-4 -ml-1 px-1"
          >
            <ArrowLeft size={15} strokeWidth={2.4} />
            {store.subject(pair.subjectId)?.name} · {store.group(pair.groupId)?.name}
          </button>

          <div className="flex items-center justify-between mb-2 px-1">
            <button
              onClick={() => shiftMonth(-1)}
              className="pressable w-9 h-9 grid place-items-center rounded-lg text-muted text-[18px]"
            >
              ‹
            </button>
            <span className="text-[14px] font-bold">{monthYearLabel(month + "-01")}</span>
            <button
              onClick={() => shiftMonth(1)}
              className="pressable w-9 h-9 grid place-items-center rounded-lg text-muted text-[18px]"
            >
              ›
            </button>
          </div>

          <div className="grid grid-cols-7 gap-1 mb-1">
            {WEEKDAYS.map((w) => (
              <div key={w} className="text-center text-[10px] font-bold uppercase text-faint py-1">
                {w}
              </div>
            ))}
            {cells.map((iso, i) => {
              if (!iso) return <div key={"b" + i} />;
              const future = iso > today;
              const selected = iso === date;
              const isToday = iso === today;
              return (
                <button
                  key={iso}
                  disabled={future}
                  onClick={() => setDate(iso)}
                  className={cn(
                    "pressable h-10 rounded-[10px] text-[13.5px] font-semibold tabular-nums",
                    selected
                      ? "bg-accent text-accentink"
                      : future
                        ? "text-faint opacity-35"
                        : isToday
                          ? "bg-accentbg text-accent"
                          : "text-ink active:bg-surface2",
                  )}
                >
                  {Number(iso.slice(8))}
                </button>
              );
            })}
          </div>

          <div className="mt-3 mb-4 text-center text-[12.5px] text-muted">
            {weekdayShort(date)}, {formatDot(date)}
          </div>

          <div className="mb-4">
            <div className="text-[11px] font-extrabold uppercase tracking-[0.06em] text-muted mb-2">
              Номер пары
            </div>
            <div className="flex gap-1.5">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  onClick={() => setFNum(n)}
                  className={cn(
                    "pressable flex-1 h-10 rounded-xl text-[14px] font-bold tabular-nums border",
                    effNum === n
                      ? "bg-accent text-accentink border-accent"
                      : "bg-surface border-line text-ink active:bg-surface2",
                  )}
                >
                  {n}
                </button>
              ))}
            </div>
            {fNum === 0 && fromSchedule && (
              <div className="mt-1.5 text-[11.5px] text-muted">
                Авто: пара №{fromSchedule.lessonNumber} из расписания
              </div>
            )}
          </div>

          <Btn size="lg" className="w-full" icon={Check} onClick={create}>
            Создать занятие
          </Btn>
        </div>
      )}
    </Sheet>
  );
}
