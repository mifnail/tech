import React, { useEffect, useRef, useState } from 'react';
import { motion } from 'motion/react';
import { House, CalendarRange, ChartColumnBig, Settings2, Signal, Wifi, BatteryMedium } from 'lucide-react';
import { nav } from '../lib/core';
import { spring } from './ui';

/* ================= ambient фон ================= */

function Ambient({ px, py }: { px: number; py: number }) {
  return (
    <div className="absolute inset-0 overflow-hidden bg-ink">
      <div className="absolute inset-0 bg-grid" />
      <div
        className="blob-a absolute w-[62vw] h-[62vw] rounded-full blur-[120px] opacity-25"
        style={{
          background: 'radial-gradient(circle, #4b5bd5 0%, transparent 65%)',
          top: '-18%', left: '-12%',
          transform: `translate(${px * 30}px, ${py * 24}px)`,
        }}
      />
      <div
        className="blob-b absolute w-[48vw] h-[48vw] rounded-full blur-[110px] opacity-20"
        style={{
          background: 'radial-gradient(circle, #8b5cf6 0%, transparent 65%)',
          bottom: '-14%', right: '-8%',
          transform: `translate(${px * -36}px, ${py * -28}px)`,
        }}
      />
      <div
        className="absolute w-[26vw] h-[26vw] rounded-full blur-[90px] opacity-[0.13]"
        style={{
          background: 'radial-gradient(circle, #3ddc97 0%, transparent 62%)',
          top: '38%', right: '16%',
          transform: `translate(${px * 20}px, ${py * -16}px)`,
        }}
      />
      {/* гигантская призрачная типографика */}
      <div
        className="absolute top-1/2 -translate-y-1/2 left-0 font-display select-none pointer-events-none hidden md:block"
        style={{
          writingMode: 'vertical-rl',
          fontSize: '11vh',
          fontWeight: 800,
          letterSpacing: '0.04em',
          color: 'transparent',
          WebkitTextStroke: '1px rgba(255,255,255,.055)',
          transform: `translateY(-50%) translateX(${px * -8}px)`,
        }}
      >
        ЖУРНАЛ
      </div>
      <div className="absolute inset-0 noise" />
    </div>
  );
}

/* ================= статус-бар ================= */

function useClock() {
  const [t, setT] = useState(new Date());
  useEffect(() => {
    const i = setInterval(() => setT(new Date()), 20000);
    return () => clearInterval(i);
  }, []);
  return `${String(t.getHours()).padStart(2, '0')}:${String(t.getMinutes()).padStart(2, '0')}`;
}

export function StatusBar() {
  const time = useClock();
  return (
    <div className="relative z-30 flex items-center justify-between px-7 pt-4 pb-1 text-[12px] font-semibold text-white/85 shrink-0">
      <span className="tabular font-mono">{time}</span>
      <div className="flex items-center gap-1.5 opacity-80">
        <Signal size={13} /> <Wifi size={13} /> <BatteryMedium size={15} />
      </div>
    </div>
  );
}

/* ================= таб-бар ================= */

const TABS = [
  { hash: '#home', label: 'Главная', icon: House },
  { hash: '#schedule', label: 'Расписание', icon: CalendarRange },
  { hash: '#analytics', label: 'Аналитика', icon: ChartColumnBig },
  { hash: '#settings', label: 'Настройки', icon: Settings2 },
];

export function TabBar({ route }: { route: string }) {
  const active = route.startsWith('#schedule') ? '#schedule'
    : route.startsWith('#analytics') ? '#analytics'
    : route.startsWith('#settings') ? '#settings' : '#home';
  return (
    <div className="absolute bottom-0 inset-x-0 z-40 px-3 pb-3 pt-8 pointer-events-none"
      style={{ background: 'linear-gradient(to top, rgba(6,8,12,.92) 40%, transparent)' }}>
      <div className="pointer-events-auto glass rounded-[22px] p-1.5 flex card-inset">
        {TABS.map((t) => {
          const on = active === t.hash;
          const Icon = t.icon;
          return (
            <button
              key={t.hash}
              onClick={() => nav(t.hash)}
              className="relative flex-1 flex flex-col items-center gap-1 py-2 rounded-[17px] transition-colors"
            >
              {on && (
                <motion.span
                  layoutId="tab-pill"
                  className="absolute inset-0 rounded-[17px]"
                  style={{ background: 'linear-gradient(150deg, rgba(124,140,255,.9), rgba(139,92,246,.85))', boxShadow: '0 6px 18px -6px rgba(124,140,255,.6)' }}
                  transition={spring}
                />
              )}
              <Icon size={17} className={`relative z-10 ${on ? 'text-white' : 'text-white/45'}`} strokeWidth={on ? 2.4 : 2} />
              <span className={`relative z-10 text-[9.5px] font-bold tracking-wide ${on ? 'text-white' : 'text-white/40'}`}>
                {t.label}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ================= плавающие spec-чипы (xl) ================= */

function SpecChips() {
  const chips = [
    { txt: 'spring 420 / 32', cls: 'left-[6%] top-[22%]', d: 0.2 },
    { txt: 'двусторонний тап', cls: 'left-[9%] top-[58%]', d: 1.1 },
    { txt: 'чёт / нечёт недели', cls: 'right-[7%] top-[30%]', d: 0.6 },
    { txt: 'дебаунс-пуш 10 c', cls: 'right-[9%] top-[64%]', d: 1.5 },
  ];
  return (
    <div className="absolute inset-0 pointer-events-none hidden xl:block">
      {chips.map((c, i) => (
        <motion.div
          key={c.txt}
          className={`absolute ${c.cls} float-slow`}
          style={{ animationDelay: `${c.d}s` }}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1.1 + i * 0.14, type: 'spring', stiffness: 120, damping: 16 }}
        >
          <div className="glass rounded-full px-4 py-2 flex items-center gap-2 card-inset">
            <span className="w-1.5 h-1.5 rounded-full bg-mint" style={{ boxShadow: '0 0 8px #3ddc97' }} />
            <span className="font-mono text-[11px] text-white/60 whitespace-nowrap">{c.txt}</span>
          </div>
        </motion.div>
      ))}
    </div>
  );
}

/* ================= сцена ================= */

export function Stage({ children }: { children: React.ReactNode }) {
  const [p, setP] = useState({ x: 0, y: 0 });
  const raf = useRef(0);
  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      cancelAnimationFrame(raf.current);
      raf.current = requestAnimationFrame(() => {
        setP({
          x: (e.clientX / window.innerWidth - 0.5) * 2,
          y: (e.clientY / window.innerHeight - 0.5) * 2,
        });
      });
    };
    window.addEventListener('pointermove', onMove);
    return () => { window.removeEventListener('pointermove', onMove); cancelAnimationFrame(raf.current); };
  }, []);

  return (
    <div className="relative h-full w-full overflow-hidden">
      <Ambient px={p.x} py={p.y} />
      <SpecChips />

      {/* подпись слева снизу */}
      <motion.div
        className="absolute left-8 bottom-7 z-20 hidden lg:block"
        initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 1.4 }}
      >
        <div className="font-mono text-[11px] text-white/35 leading-relaxed">
          teachhelper · redesign concept<br />
          <span className="text-white/55">build 0.2 · flask + react</span>
        </div>
      </motion.div>

      <div className="relative z-10 h-full flex items-center justify-center">
        {/* мобильный: на весь экран · десктоп: рамка устройства */}
        <motion.div
          className="relative w-full h-full md:w-auto md:h-auto"
          initial={{ opacity: 0, scale: 0.96, y: 24 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ type: 'spring', stiffness: 90, damping: 18, delay: 0.15 }}
        >
          <div
            className="hidden md:block absolute -inset-16 rounded-full blur-[70px] opacity-30 -z-10"
            style={{ background: 'radial-gradient(circle, rgba(124,140,255,.5), transparent 68%)' }}
          />
          <div
            className="relative w-full h-full md:w-[402px] md:h-[min(852px,94vh)] md:rounded-[54px] md:p-[11px]"
            style={{
              background: 'linear-gradient(160deg, #2a2f3c, #0c0e14 30%, #1a1e28 70%, #252a36)',
              boxShadow: '0 60px 120px -40px rgba(0,0,0,.9), 0 0 0 1px rgba(255,255,255,.07), inset 0 0 0 1px rgba(255,255,255,.05)',
              transform: `perspective(1400px) rotateY(${p.x * -2.2}deg) rotateX(${p.y * 1.8}deg)`,
              transition: 'transform .25s cubic-bezier(.2,.8,.2,1)',
            }}
          >
            {/* кнопки корпуса */}
            <div className="hidden md:block absolute -left-[2.5px] top-28 w-[3px] h-9 rounded-l-md bg-[#2c3140]" />
            <div className="hidden md:block absolute -left-[2.5px] top-40 w-[3px] h-14 rounded-l-md bg-[#2c3140]" />
            <div className="hidden md:block absolute -right-[2.5px] top-36 w-[3px] h-20 rounded-r-md bg-[#2c3140]" />

            <div className="relative w-full h-full md:rounded-[43px] overflow-hidden bg-panel noise flex flex-col">
              {/* dynamic island */}
              <div className="hidden md:block absolute top-2.5 left-1/2 -translate-x-1/2 z-50 w-[112px] h-[30px] bg-black rounded-full" />
              {children}
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
