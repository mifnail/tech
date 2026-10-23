/* Незаполненные прошедшие занятия.

   Правило журнала: у прошедшей пары может быть только два состояния —
   проведена или отменена. Если статус другой, приложение обязано сказать
   об этом при запуске и дать ссылку на занятие: либо заполнить ведомость,
   либо отменить пару. */
import { useEffect, useState } from "react";
import { ChevronRight, ClipboardList } from "lucide-react";
import { navigate } from "../lib/router";
import { formatDotShort } from "../lib/date";
import { Card, Sheet } from "./ui";

interface PendingLesson {
  id: number;
  date: string;
  lesson_number: number | null;
  subject_name: string;
  group_name: string;
}

/** Сколько строк показываем в карточке до «Показать все». */
const PREVIEW = 3;

function Row({ it, onGo }: { it: PendingLesson; onGo: () => void }) {
  const pair = it.lesson_number && it.lesson_number > 0 ? `пара ${it.lesson_number}` : "без номера";
  return (
    <button
      className="w-full text-left px-3.5 py-2.5 flex items-center gap-2 active:bg-surface2"
      onClick={onGo}
    >
      <div className="min-w-0 flex-1">
        <div className="text-[13px] font-bold leading-snug truncate">
          {formatDotShort(it.date)} · {pair} · {it.group_name}
        </div>
        <div className="text-[12px] text-muted truncate mt-0.5">{it.subject_name}</div>
      </div>
      <ChevronRight size={15} className="text-faint shrink-0" />
    </button>
  );
}

export function PendingLessonsCard() {
  const [items, setItems] = useState<PendingLesson[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let alive = true;
    fetch("/api/lessons/pending")
      .then((r) => (r.ok ? r.json() : []))
      .then((j) => {
        if (alive) setItems(Array.isArray(j) ? j : []);
      })
      .catch(() => {
        if (alive) setItems([]);
      });
    return () => {
      alive = false;
    };
  }, []);

  if (items.length === 0) return null;

  const go = (id: number) => {
    setOpen(false);
    navigate("/lesson/" + id);
  };

  return (
    <>
      <Card className="p-0 mb-3 border-l-[3px] border-l-danger overflow-hidden">
        <button
          className="w-full text-left p-3.5 flex items-start gap-2.5 active:bg-surface2"
          onClick={() => setOpen(true)}
        >
          <ClipboardList size={17} className="text-danger shrink-0 mt-0.5" />
          <div className="min-w-0 flex-1">
            <div className="text-[14px] font-bold leading-snug">
              Незаполненные занятия · {items.length}
            </div>
            <div className="text-[12px] text-muted mt-0.5 leading-snug">
              Прошедшую пару надо провести или отменить
            </div>
          </div>
          <ChevronRight size={16} className="text-faint shrink-0 mt-0.5" />
        </button>
        <div className="border-t border-line divide-y divide-line">
          {items.slice(0, PREVIEW).map((it) => (
            <Row key={it.id} it={it} onGo={() => go(it.id)} />
          ))}
        </div>
        {items.length > PREVIEW && (
          <button
            className="w-full text-left px-3.5 py-2.5 text-[13px] font-bold text-accent active:bg-surface2 border-t border-line"
            onClick={() => setOpen(true)}
          >
            Показать все {items.length}
          </button>
        )}
      </Card>

      <Sheet open={open} onClose={() => setOpen(false)} title={`Незаполненные занятия · ${items.length}`}>
        <p className="text-[13px] text-muted leading-relaxed mb-3">
          Прошедшую пару надо провести или отменить. Откройте занятие и нажмите «Провести»,
          либо отмените пару в меню занятия.
        </p>
        <div className="rounded-xl border border-line overflow-hidden divide-y divide-line">
          {items.map((it) => (
            <Row key={it.id} it={it} onGo={() => go(it.id)} />
          ))}
        </div>
      </Sheet>
    </>
  );
}
