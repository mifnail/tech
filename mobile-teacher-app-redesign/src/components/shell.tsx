/* Каркас экранов: шапки и нижняя таб-навигация (под большой палец). */

import type { ReactNode } from "react";
import { ChevronLeft, CalendarDays, House, Layers, BarChart3, SlidersHorizontal } from "lucide-react";
import { cn } from "../utils/cn";
import { navigate, goBack } from "../lib/router";
import { IconBtn } from "./ui";

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

export function AvatarTile({ text, className }: { text: string; className?: string }) {
  let h = 0;
  for (let i = 0; i < text.length; i++) h = (h * 31 + text.charCodeAt(i)) | 0;
  const tone = TILE_TONES[Math.abs(h) % TILE_TONES.length];
  return (
    <div
      className={cn(
        "w-10 h-10 rounded-[13px] grid place-items-center font-extrabold text-[13px] tracking-[0.02em] shrink-0",
        tone, className,
      )}
    >
      {text}
    </div>
  );
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
