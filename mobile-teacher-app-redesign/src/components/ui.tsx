/* UI-кит: плоский, лёгкий, тач-таргеты от 44px. */

import {
  createContext, useCallback, useContext, useEffect, useRef, useState,
  type ReactNode, type ButtonHTMLAttributes, type InputHTMLAttributes,
} from "react";
import { X, type LucideIcon } from "lucide-react";
import { cn } from "../utils/cn";
import { gradeLabel, gradeTone, type GradeTone } from "../lib/grades";

/* ── Кнопки ───────────────────────────────────────────────── */
type BtnVariant = "primary" | "muted" | "danger" | "ghost" | "outline";

interface BtnProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: BtnVariant;
  size?: "lg" | "md" | "sm";
  icon?: LucideIcon;
}

export function Btn({
  variant = "primary", size = "md", icon: Icon, className, children, ...rest
}: BtnProps) {
  const styles: Record<BtnVariant, string> = {
    primary: "bg-accent text-accentink active:bg-accentdeep",
    muted: "bg-surface2 text-ink border border-line",
    danger: "bg-dangerbg text-danger",
    ghost: "bg-transparent text-accent",
    outline: "bg-surface text-ink border border-linestrong",
  };
  const sizes = {
    lg: "h-[52px] px-5 text-[15px] rounded-[14px]",
    md: "h-11 px-4 text-[14px] rounded-xl",
    sm: "h-9 px-3 text-[13px] rounded-[10px]",
  };
  return (
    <button
      className={cn(
        "pressable inline-flex items-center justify-center gap-2 font-semibold select-none",
        "disabled:opacity-40 disabled:pointer-events-none",
        styles[variant], sizes[size], className,
      )}
      {...rest}
    >
      {Icon && <Icon size={size === "sm" ? 15 : 17} strokeWidth={2.2} />}
      {children}
    </button>
  );
}

export function IconBtn({
  icon: Icon, className, label, ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { icon: LucideIcon; label: string }) {
  return (
    <button
      aria-label={label}
      title={label}
      className={cn(
        "pressable w-10 h-10 inline-flex items-center justify-center rounded-xl",
        "text-muted active:bg-surface2",
        className,
      )}
      {...rest}
    >
      <Icon size={20} strokeWidth={2} />
    </button>
  );
}

/* ── Карточка ─────────────────────────────────────────────── */
export function Card({
  className, children, onClick,
}: { className?: string; children: ReactNode; onClick?: () => void }) {
  return (
    <div
      onClick={onClick}
      className={cn(
        "bg-surface border border-line rounded-2xl",
        "shadow-[0_1px_2px_rgba(16,24,40,0.04)]",
        onClick && "pressable cursor-pointer",
        className,
      )}
    >
      {children}
    </div>
  );
}

/* ── Чипы и бейджи ────────────────────────────────────────── */
type ChipTone = "accent" | "success" | "warn" | "danger" | "neutral";

const chipStyles: Record<ChipTone, string> = {
  accent: "bg-accentbg text-accent",
  success: "bg-g5bg text-g5",
  warn: "bg-g3bg text-g3",
  danger: "bg-g2bg text-g2",
  neutral: "bg-nabg text-na",
};

export function Chip({
  tone = "neutral", className, children,
}: { tone?: ChipTone; className?: string; children: ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 h-[22px] px-2 rounded-full",
        "text-[10.5px] font-bold uppercase tracking-[0.06em] whitespace-nowrap",
        chipStyles[tone], className,
      )}
    >
      {children}
    </span>
  );
}

/* ── Чип оценки ───────────────────────────────────────────── */
const gradeStyles: Record<GradeTone, string> = {
  g5: "bg-g5bg text-g5",
  g4: "bg-g4bg text-g4",
  g3: "bg-g3bg text-g3",
  g2: "bg-g2bg text-g2",
  na: "bg-nabg text-na",
  none: "bg-transparent text-faint border border-dashed border-linestrong",
};

export function GradeChip({
  value, present, size = "md", animateKey, className,
}: {
  value: number | null;
  present: boolean;
  size?: "md" | "sm";
  animateKey?: string | number;
  className?: string;
}) {
  const tone = gradeTone(value, present);
  return (
    <span
      key={animateKey}
      className={cn(
        "inline-flex items-center justify-center rounded-[9px] font-bold tabular-nums",
        size === "md" ? "h-8 min-w-[38px] px-2 text-[15px]" : "h-6 min-w-[26px] px-1 text-[12px]",
        animateKey !== undefined && "an-pop",
        gradeStyles[tone], className,
      )}
    >
      {gradeLabel(value, present)}
    </span>
  );
}

/* ── Сегмент-контрол ──────────────────────────────────────── */
export function Segmented<T extends string>({
  options, value, onChange, className,
}: {
  options: { value: T; label: string; icon?: LucideIcon }[];
  value: T;
  onChange: (v: T) => void;
  className?: string;
}) {
  return (
    <div className={cn("flex p-1 gap-1 bg-surface2 rounded-xl border border-line", className)}>
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            onClick={() => onChange(o.value)}
            className={cn(
              "pressable flex-1 h-9 rounded-[9px] text-[13px] font-semibold",
              "inline-flex items-center justify-center gap-1.5",
              active
                ? "bg-surface text-ink border border-linestrong"
                : "text-muted border border-transparent",
            )}
          >
            {o.icon && <o.icon size={14} strokeWidth={2.2} />}
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

/* ── Поля ввода ───────────────────────────────────────────── */
export function Input({
  className, ...rest
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "w-full h-11 px-3.5 rounded-xl bg-surface border border-linestrong",
        "text-[15px] placeholder:text-faint",
        className,
      )}
      {...rest}
    />
  );
}

export function Select({
  className, children, ...rest
}: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "w-full h-11 px-3 rounded-xl bg-surface border border-linestrong text-[15px]",
        className,
      )}
      {...rest}
    >
      {children}
    </select>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="block mb-1.5 text-[11px] font-bold uppercase tracking-[0.08em] text-muted">
        {label}
      </span>
      {children}
    </label>
  );
}

/* ── Заголовок секции ─────────────────────────────────────── */
export function SectionTitle({
  children, action, className,
}: { children: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-end justify-between mt-6 mb-2.5 px-1", className)}>
      <h2 className="text-[11px] font-extrabold uppercase tracking-[0.1em] text-muted">
        {children}
      </h2>
      {action}
    </div>
  );
}

/* ── Нижний лист (bottom sheet) ───────────────────────────── */
export function Sheet({
  open, onClose, title, children,
}: {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, [open]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center">
      <div
        className="an-fade absolute inset-0"
        style={{ background: "rgba(9,13,19,0.72)" }}
        onClick={onClose}
      />
      <div
        className="an-sheet relative w-full max-w-[480px] bg-surface rounded-t-[22px]
          border-t border-line max-h-[85dvh] flex flex-col"
        role="dialog"
        aria-modal="true"
      >
        <div className="pt-2.5 pb-1 grid place-items-center shrink-0" onClick={onClose}>
          <div className="w-9 h-1 rounded-full bg-linestrong" />
        </div>
        <div className="px-5 pt-1 pb-4 flex items-center justify-between shrink-0">
          <h3 className="text-[17px] font-bold tracking-[-0.01em]">{title}</h3>
          <IconBtn icon={X} label="Закрыть" onClick={onClose} className="-mr-2" />
        </div>
        <div className="px-5 pb-[calc(env(safe-area-inset-bottom,0px)+16px)] overflow-y-auto min-h-0">
          {children}
        </div>
      </div>
    </div>
  );
}

/* ── Тост ─────────────────────────────────────────────────── */
const ToastCtx = createContext<(msg: string) => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [msg, setMsg] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const show = useCallback((m: string) => {
    setMsg(m);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setMsg(null), 2400);
  }, []);

  return (
    <ToastCtx.Provider value={show}>
      {children}
      {msg && (
        <div className="fixed left-0 right-0 bottom-[86px] z-[60] flex justify-center px-6 pointer-events-none">
          <div
            key={msg}
            className="an-toast bg-ink text-bg text-[13.5px] font-semibold
              px-4 py-2.5 rounded-full shadow-lg max-w-full text-center"
          >
            {msg}
          </div>
        </div>
      )}
    </ToastCtx.Provider>
  );
}

/* ── Пустое состояние ─────────────────────────────────────── */
export function EmptyState({
  icon: Icon, title, hint, children,
}: { icon: LucideIcon; title: string; hint?: string; children?: ReactNode }) {
  return (
    <div className="py-10 flex flex-col items-center text-center px-8">
      <div className="w-14 h-14 rounded-2xl bg-surface2 border border-line grid place-items-center mb-3">
        <Icon size={24} className="text-faint" strokeWidth={1.8} />
      </div>
      <div className="text-[15px] font-bold">{title}</div>
      {hint && <div className="mt-1 text-[13px] text-muted leading-snug">{hint}</div>}
      {children && <div className="mt-4">{children}</div>}
    </div>
  );
}

/* ── Спарклайн (мини-график, голый SVG) ───────────────────── */
export function Sparkline({
  points, width = 120, height = 34, className,
}: { points: number[]; width?: number; height?: number; className?: string }) {
  if (points.length < 2) return null;
  const min = 1, max = 5;
  const stepX = width / (points.length - 1);
  const y = (v: number) => height - 4 - ((v - min) / (max - min)) * (height - 8);
  const d = points.map((p, i) => `${i === 0 ? "M" : "L"}${(i * stepX).toFixed(1)},${y(p).toFixed(1)}`).join(" ");
  const last = points[points.length - 1];
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className={className}>
      <path d={d} fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={width} cy={y(last)} r="3" fill="var(--accent)" />
    </svg>
  );
}

/* ── Подтверждение действия ───────────────────────────────── */
export function ConfirmSheet({
  open, onClose, title, body, confirmLabel = "Подтвердить", onConfirm, danger,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  body?: string;
  confirmLabel?: string;
  onConfirm: () => void;
  danger?: boolean;
}) {
  return (
    <Sheet open={open} onClose={onClose} title={title}>
      {body && <p className="text-[14px] text-muted leading-relaxed mb-5">{body}</p>}
      <div className="flex gap-2.5">
        <Btn variant="muted" className="flex-1" onClick={onClose}>Отмена</Btn>
        <Btn
          variant={danger ? "danger" : "primary"}
          className="flex-1"
          onClick={() => { onConfirm(); onClose(); }}
        >
          {confirmLabel}
        </Btn>
      </div>
    </Sheet>
  );
}
