/* Каркас экранов: шапки, плитки/кружки строк дня и нижняя таб-навигация. */

import type { ReactNode } from "react";
import {
  Check, ChevronLeft, CalendarDays, House, Layers, BarChart3, SlidersHorizontal,
} from "lucide-react";
import { cn } from "../utils/cn";
import { navigate, goBack } from "../lib/router";
import { weekTypeOf, weekdayOf } from "../lib/date";
import type { DB, Lesson, LessonStatus, ScheduleItem } from "../lib/types";
import { colorForGroup } from "../lib/groupColors";
import { IconBtn } from "./ui";

// Цвет группы живёт в lib/groupColors (реестр специальностей обновляет App).
export { colorForGroup, groupInk } from "../lib/groupColors";

/* ── Контейнер экрана ─────────────────────────────────────── */
export function Screen({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("px-4 pt-safe", className)}>{children}</div>
  );
}

/* ── Большая шапка (корневые вкладки) ─────────────────────── */
export function BigHeader({
  kicker, title, actions,
}: { kicker?: string; title: string; actions?: ReactNode }) {
  return (
    <header className="pt-5 pb-4 flex items-start justify-between gap-3">
      <div className="min-w-0">
        {kicker && (
          <div className="text-[11px] font-extrabold uppercase tracking-[0.12em] text-muted mb-1">
            {kicker}
          </div>
        )}
        <h1 className="text-[24px] leading-[1.15] font-extrabold tracking-[-0.02em] whitespace-pre-line">
          {title}
        </h1>
      </div>
      {actions && <div className="flex items-center gap-1 pt-1 shrink-0">{actions}</div>}
    </header>
  );
}

/* ── Шапка с возвратом (детальные экраны) ─────────────────── */
export function BackHeader({
  title, sub, fallback = "/today", actions, sticky,
}: {
  title: string;
  sub?: string;
  fallback?: string;
  actions?: ReactNode;
  sticky?: boolean;
}) {
  return (
    <header
      className={cn(
        "flex items-center gap-1 py-2.5 -mx-1 px-1",
        sticky && "sticky top-0 z-20 bg-bg border-b border-line",
      )}
    >
      <IconBtn icon={ChevronLeft} label="Назад" onClick={() => goBack(fallback)} />
      <div className="min-w-0 flex-1">
        <h1 className="text-[16px] font-bold tracking-[-0.01em] leading-tight truncate">
          {title}
        </h1>
        {sub && <div className="text-[12px] text-muted truncate">{sub}</div>}
      </div>
      {actions && <div className="flex items-center gap-0.5 shrink-0">{actions}</div>}
    </header>
  );
}

/* ── Плитка с инициалами ──────────────────────────────────── */
const TILE_TONES = [
  "bg-accentbg text-accent",
  "bg-g5bg text-g5",
  "bg-g3bg text-g3",
  "bg-g4bg text-g4",
];

/** Детерминированный хеш строки (тот же, что был у плиток). */
function hashOf(text: string): number {
  let h = 0;
  for (let i = 0; i < text.length; i++) h = (h * 31 + text.charCodeAt(i)) | 0;
  return Math.abs(h);
}

/* Цвет группы — в lib/groupColors: специальность = семейство hue,
   курс = контрастный тон внутри семейства, текст по контрасту WCAG. */

export function AvatarTile({
  text, group, className,
}: { text: string; group?: string; className?: string }) {
  // Передано имя группы — красим по специальности/курсу; иначе прежние тона.
  const color = group ? colorForGroup(group) : null;
  const tone = color ? null : TILE_TONES[hashOf(text) % TILE_TONES.length];
  return (
    <div
      className={cn(
        "w-10 h-10 rounded-[13px] grid place-items-center font-extrabold text-[13px] tracking-[0.02em] shrink-0",
        tone, className,
      )}
      style={color ? { backgroundColor: color.bg, color: color.fg } : undefined}
    >
      {text}
    </div>
  );
}

/* ── Номер пары: крупная цифра + код группы, фиксированная ширина ── */
/** Крупная цифра без слова «номер», под ней — код группы (АДТ-31).
    Ширина колонки задаётся снаружи (w-[48px]) и не меняется. */
export function PairNumber({
  n, code, codeColor, className,
}: { n: number; code: string; codeColor?: string; className?: string }) {
  return (
    <div className={cn("shrink-0 select-none text-center", className)}>
      <div className="text-[21px] font-extrabold tabular-nums leading-none text-ink">
        {n > 0 ? n : "—"}
      </div>
      <div
        className="mt-0.5 text-[10.5px] font-bold uppercase tracking-[0.01em] text-faint truncate"
        style={codeColor ? { color: codeColor } : undefined}
        title={code}
      >
        {code}
      </div>
    </div>
  );
}

/* ── Статус пары кружком (вместо чипа с текстом) ──────────── */
/** Компактный индикатор: зелёный кружок с галочкой — проведено,
    серый залитый — запланировано, красный с чертой — отменено.
    Подпись остаётся только для скринридеров и title. */
export function StatusDot({ status }: { status: LessonStatus }) {
  const label =
    status === "held" ? "Проведено" : status === "cancelled" ? "Отменено" : "Запланировано";
  return (
    <>
      <span className="sr-only">{label}</span>
      {status === "held" && (
        <span
          title={label}
          aria-label={label}
          className="w-[19px] h-[19px] shrink-0 rounded-full bg-g5 grid place-items-center"
        >
          <Check size={12} strokeWidth={3.2} className="text-white" />
        </span>
      )}
      {status === "cancelled" && (
        <span
          title={label}
          aria-label={label}
          className="w-[19px] h-[19px] shrink-0 rounded-full bg-g2 grid place-items-center"
        >
          <span className="block w-[9px] h-[2px] rounded-full bg-white -rotate-45" />
        </span>
      )}
      {status === "scheduled" && (
        <span
          title={label}
          aria-label={label}
          className="block w-[19px] h-[19px] shrink-0 rounded-full bg-na"
        />
      )}
    </>
  );
}

/* ── План дня: занятия даты + слоты шаблона расписания ────── */
/** Строка дня: реальное занятие (lessons) или незакрытый слот шаблона (schedule). */
export type DayRow =
  | { kind: "lesson"; key: string; lesson: Lesson }
  | { kind: "plan"; key: string; item: ScheduleItem };

/**
 * Занятия даты + слоты шаблона расписания (day_of_week + чёт/нечёт).
 * Реальный lesson приоритетнее шаблона: слот не показывается, если на эту
 * дату уже занят тот же номер пары у той же группы — дублей не бывает.
 *
 * Дедуп идёт по слоту «группа#номер пары», а НЕ по паре «группа+предмет»:
 * один предмет законно стоит дважды в день (1-я и 2-я пара). Дедуп по
 * группе+предмету прятал вторую пару — в журнале её не было, хотя в шаблоне
 * она есть и проверка дублей на добавление её видела.
 *
 * Занятия без номера пары (старые записи) сравниваем по группе+предмету.
 * Данные — только локальные db.schedule / db.lessons.
 * Паритет берём в шкале БД через date.ts#weekTypeOf — одна точка перевода.
 */
export function dayRows(db: DB, date: string): DayRow[] {
  const weekday = weekdayOf(date);
  const weekType = weekTypeOf(date);
  const lessons = db.lessons.filter((l) => l.date === date);
  const rows: DayRow[] = lessons.map((l) => ({
    kind: "lesson", key: "l" + l.id, lesson: l,
  }));

  const usedSlots = new Set<string>();      // группа#номер пары
  const usedUnnumbered = new Set<string>(); // группа/предмет — только для пар без номера
  for (const l of lessons) {
    if (l.lessonNumber > 0) usedSlots.add(l.groupId + "#" + l.lessonNumber);
    else usedUnnumbered.add(l.groupId + "/" + l.subjectId);
  }

  const plannedSlots = new Set<string>(); // чтобы шаблон не дал два ряда на один слот
  for (const it of db.schedule) {
    if (it.weekday !== weekday) continue;
    if (it.parity !== 0 && it.parity !== weekType) continue;
    // Пара действует только с даты, когда её завели. Раньше этого дня её
    // не существовало — «задним числом» в журнале она появляться не должна.
    if (it.validFrom && date < it.validFrom) continue;
    // Занятие без номера пары (старая запись) закрывает шаблон этой
    // группы+предмета целиком — номер слота сравнить не с чем.
    if (usedUnnumbered.has(it.groupId + "/" + it.subjectId)) continue;
    if (it.lessonNumber > 0) {
      const slot = it.groupId + "#" + it.lessonNumber;
      if (usedSlots.has(slot) || plannedSlots.has(slot)) continue;
      plannedSlots.add(slot);
    }
    rows.push({ kind: "plan", key: "p" + it.id, item: it });
  }

  rows.sort((a, b) => {
    const na = a.kind === "lesson" ? a.lesson.lessonNumber : a.item.lessonNumber;
    const nb = b.kind === "lesson" ? b.lesson.lessonNumber : b.item.lessonNumber;
    if (na !== nb) return na - nb;
    const ta = a.kind === "lesson" ? a.lesson.time : a.item.time;
    const tb = b.kind === "lesson" ? b.lesson.time : b.item.time;
    return ta.localeCompare(tb);
  });
  return rows;
}

/* ── Нижняя навигация ─────────────────────────────────────── */
const TABS = [
  { path: "today", label: "Сегодня", icon: House },
  { path: "groups", label: "Предметы и группы", icon: Layers },
  { path: "schedule", label: "Расписание", icon: CalendarDays },
  { path: "analytics", label: "Аналитика", icon: BarChart3 },
  { path: "more", label: "Ещё", icon: SlidersHorizontal },
];

const TAB_ROOTS: Record<string, string> = {
  today: "today", groups: "groups", group: "groups", statement: "groups",
  schedule: "schedule", analytics: "analytics", more: "more",
};

export function BottomNav({ segment }: { segment: string }) {
  const active = TAB_ROOTS[segment] ?? "today";
  return (
    <nav
      className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[480px] z-40
        bg-surface border-t border-line pb-safe"
    >
      <div className="grid grid-cols-5 h-[60px]">
        {TABS.map((t) => {
          const is = active === t.path;
          return (
            <button
              key={t.path}
              onClick={() => navigate("/" + t.path)}
              className="pressable flex flex-col items-center justify-center gap-[3px]"
            >
              <span
                className={cn(
                  "grid place-items-center w-12 h-7 rounded-full transition-colors duration-150",
                  is ? "bg-accentbg text-accent" : "text-faint",
                )}
              >
                <t.icon size={20} strokeWidth={is ? 2.3 : 1.9} />
              </span>
              <span
                className={cn(
                  "text-[9px] leading-[1.2] max-w-full text-center",
                  is ? "font-bold text-accent" : "font-semibold text-faint",
                )}
              >
                {t.label}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
