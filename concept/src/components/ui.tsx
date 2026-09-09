import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence, useMotionValue, animate } from 'motion/react';
import { X, Check, MessageSquareText, Info, TriangleAlert, Send } from 'lucide-react';
import { GRADE_META, type Grade, type Toast } from '../lib/core';

export const spring = { type: 'spring', stiffness: 420, damping: 32 } as const;
export const springSoft = { type: 'spring', stiffness: 260, damping: 26 } as const;

/* ================= GradeOrb — ядро визуальной системы ================= */

export function GradeOrb({ grade, size = 44, fontSize }: { grade: Grade; size?: number; fontSize?: number }) {
  const g = grade ?? null;
  const meta = g ? GRADE_META[g] : null;
  const isAbsent = g === 'absent';
  const isPresent = g === '0';
  const fs = fontSize ?? Math.round(size * 0.34);

  return (
    <div
      className="relative grid place-items-center rounded-full select-none shrink-0"
      style={{
        width: size, height: size,
        background: meta && !isAbsent
          ? `radial-gradient(120% 120% at 30% 25%, ${meta.c}33, ${meta.c}14 45%, transparent 70%)`
          : 'rgba(255,255,255,.04)',
        boxShadow: isAbsent
          ? 'inset 0 0 0 1.5px rgba(242,98,122,.65)'
          : meta
            ? `inset 0 0 0 1.5px ${meta.c}55, 0 0 ${size * 0.5}px -${size * 0.12}px ${meta.c}66`
            : 'inset 0 0 0 1.5px rgba(255,255,255,.10)',
      }}
    >
      <AnimatePresence mode="popLayout" initial={false}>
        <motion.span
          key={g ?? 'none'}
          initial={{ scale: 0.4, opacity: 0, rotate: g ? -30 : 0, filter: 'blur(4px)' }}
          animate={{ scale: 1, opacity: 1, rotate: 0, filter: 'blur(0px)' }}
          exit={{ scale: 0.5, opacity: 0, rotate: 24, filter: 'blur(4px)' }}
          transition={spring}
          className="font-mono font-semibold tabular grid place-items-center"
          style={{
            fontSize: fs,
            color: meta ? meta.c : 'rgba(255,255,255,.30)',
            lineHeight: 1,
          }}
        >
          {g == null ? '—' : isPresent ? <Check size={fs + 4} strokeWidth={3} /> : GRADE_META[g].label}
        </motion.span>
      </AnimatePresence>
    </div>
  );
}

/* ================= мини-ячейка журнала ================= */

export function GradeCell({ grade, odd }: { grade: Grade; odd?: boolean }) {
  const meta = grade ? GRADE_META[grade] : null;
  return (
    <div
      className="grid place-items-center w-8 h-9 rounded-[10px] font-mono text-[12px] font-semibold tabular shrink-0"
      style={{
        background: meta ? `${meta.c}${grade === 'absent' ? '1f' : '22'}` : odd ? 'rgba(255,255,255,.015)' : 'rgba(255,255,255,.03)',
        color: meta ? meta.c : 'rgba(255,255,255,.14)',
        boxShadow: meta ? `inset 0 0 0 1px ${meta.c}30` : 'inset 0 0 0 1px rgba(255,255,255,.03)',
      }}
    >
      {grade ? GRADE_META[grade].label : ''}
    </div>
  );
}

/* ================= ProgressRing ================= */

export function ProgressRing({ pct, size = 84, stroke = 7, color = '#7c8cff', children }: {
  pct: number; size?: number; stroke?: number; color?: string; children?: React.ReactNode;
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,.07)" strokeWidth={stroke} />
        <motion.circle
          cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke={color} strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: c - (c * Math.min(100, Math.max(0, pct))) / 100 }}
          transition={{ type: 'spring', stiffness: 60, damping: 20 }}
          style={{ filter: `drop-shadow(0 0 6px ${color}88)` }}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center">{children}</div>
    </div>
  );
}

/* ================= CountUp ================= */

export function CountUp({ value, decimals = 0, className = '' }: { value: number; decimals?: number; className?: string }) {
  const mv = useMotionValue(0);
  const [txt, setTxt] = useState('0');
  useEffect(() => {
    const ctrl = animate(mv, value, { type: 'spring', stiffness: 70, damping: 18, onUpdate: (v) => setTxt(v.toFixed(decimals).replace('.', ',')) });
    return () => ctrl.stop();
  }, [value, decimals]);
  return <span className={`tabular ${className}`}>{txt}</span>;
}

/* ================= Sheet — bottom sheet с drag-to-dismiss ================= */

export function Sheet({ open, onClose, title, children }: {
  open: boolean; onClose: () => void; title?: string; children: React.ReactNode;
}) {
  const y = useMotionValue(0);
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="absolute inset-0 z-50 flex items-end justify-center"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        >
          <motion.div className="absolute inset-0 bg-black/55" style={{ backdropFilter: 'blur(6px)' }} onClick={onClose} />
          <motion.div
            className="relative w-full glass-deep rounded-t-[28px] px-5 pt-3 pb-7 max-h-[88%] overflow-y-auto nice-scroll"
            style={{ y }}
            initial={{ y: '104%' }}
            animate={{ y: 0 }}
            exit={{ y: '104%' }}
            transition={springSoft}
            drag="y"
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={{ top: 0, bottom: 0.6 }}
            onDragEnd={(_, info) => { if (info.offset.y > 110 || info.velocity.y > 600) onClose(); }}
          >
            <div className="mx-auto w-10 h-1.5 rounded-full bg-white/15 mb-4" />
            {title && <div className="font-display text-[15px] font-semibold tracking-tight mb-4">{title}</div>}
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/* ================= Toasts ================= */

const TONE_ICON: Record<string, React.ReactNode> = {
  ok: <Check size={15} strokeWidth={3} />,
  info: <Info size={15} />,
  warn: <TriangleAlert size={15} />,
  push: <Send size={14} />,
};
const TONE_COLOR: Record<string, string> = {
  ok: '#3ddc97', info: '#7c8cff', warn: '#f5b93f', push: '#5cd6f0',
};

export function Toasts({ toasts, onDismiss }: {
  toasts: Toast[];
  onDismiss: (id: number) => void;
}) {
  return (
    <div className="absolute left-3 right-3 bottom-[92px] z-[60] flex flex-col gap-2 pointer-events-none">
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            layout
            initial={{ opacity: 0, y: 24, scale: 0.94 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.96 }}
            transition={spring}
            className="pointer-events-auto glass-deep rounded-2xl px-3.5 py-3 flex items-center gap-3 shadow-2xl"
          >
            <div
              className="w-7 h-7 rounded-full grid place-items-center shrink-0"
              style={{ background: `${TONE_COLOR[t.tone ?? 'info']}22`, color: TONE_COLOR[t.tone ?? 'info'] }}
            >
              {t.tone === 'push' ? <MessageSquareText size={14} /> : TONE_ICON[t.tone ?? 'info']}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[13px] font-semibold leading-tight truncate">{t.title}</div>
              {t.sub && <div className="text-[11px] text-white/45 leading-tight mt-0.5 truncate">{t.sub}</div>}
            </div>
            {t.action && (
              <button
                onClick={() => { t.action!.fn(); onDismiss(t.id); }}
                className="text-[12px] font-bold px-2.5 py-1.5 rounded-lg shrink-0"
                style={{ color: TONE_COLOR[t.tone ?? 'info'], background: 'rgba(255,255,255,.06)' }}
              >
                {t.action.label}
              </button>
            )}
            <button onClick={() => onDismiss(t.id)} className="text-white/30 hover:text-white/70 shrink-0 p-1">
              <X size={14} />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

/* ================= мелочи ================= */

export function SectionTitle({ children, right }: { children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="flex items-end justify-between mt-7 mb-3 px-1">
      <h2 className="font-display text-[12px] font-semibold uppercase tracking-[0.18em] text-white/55">{children}</h2>
      {right}
    </div>
  );
}

export function Bar({ pct, color = '#3ddc97', height = 6 }: { pct: number; color?: string; height?: number }) {
  return (
    <div className="w-full rounded-full overflow-hidden" style={{ height, background: 'rgba(255,255,255,.07)' }}>
      <motion.div
        className="h-full rounded-full"
        style={{ background: `linear-gradient(90deg, ${color}bb, ${color})`, boxShadow: `0 0 12px ${color}66` }}
        initial={{ width: 0 }}
        animate={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
        transition={{ type: 'spring', stiffness: 50, damping: 18 }}
      />
    </div>
  );
}

export function Chip({ active, onClick, children }: { active?: boolean; onClick?: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`relative px-3.5 py-2 rounded-full text-[12px] font-semibold transition-colors ${
        active ? 'text-[#0a0d13]' : 'text-white/55'
      }`}
    >
      {active && (
        <motion.span
          layoutId={undefined}
          className="absolute inset-0 rounded-full bg-white"
          transition={spring}
        />
      )}
      <span className="relative z-10">{children}</span>
    </button>
  );
}

/* ============ AreaChart — динамика среднего балла ============ */

export function AreaChart({ points, height = 96, color = '#7c8cff' }: { points: number[]; height?: number; color?: string }) {
  const w = 320, h = height, pad = 8;
  if (points.length < 2) points = [0, ...points, 5];
  const min = Math.min(...points) - 0.4, max = Math.max(...points) + 0.4;
  const step = (w - pad * 2) / (points.length - 1);
  const xy = points.map((p, i) => [pad + i * step, h - pad - ((p - min) / (max - min)) * (h - pad * 2)] as const);
  const path = xy.map(([x, y], i) => (i === 0 ? `M${x},${y}` : `L${x},${y}`)).join(' ');
  const area = `${path} L${xy[xy.length - 1][0]},${h} L${xy[0][0]},${h} Z`;
  const gid = useRef(`g${Math.random().toString(36).slice(2, 8)}`).current;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ height }}>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.35" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <motion.path d={area} fill={`url(#${gid})`} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.8, delay: 0.3 }} />
      <motion.path
        d={path} fill="none" stroke={color} strokeWidth="2.4" strokeLinecap="round"
        initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
        transition={{ duration: 1.1, ease: [0.16, 1, 0.3, 1] }}
        style={{ filter: `drop-shadow(0 2px 8px ${color}66)` }}
      />
      {xy.map(([x, y], i) => (
        <motion.circle
          key={i} cx={x} cy={y} r="3" fill="#0b0e14" stroke={color} strokeWidth="2"
          initial={{ scale: 0, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.35 + i * 0.07, ...spring }}
        />
      ))}
    </svg>
  );
}
