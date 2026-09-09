import { useState } from 'react';
import { motion } from 'motion/react';
import {
  Send, MessageSquareText, DatabaseBackup, Download, UploadCloud,
  ShieldAlert, KeyRound, Heart, MoonStar, Check,
} from 'lucide-react';
import { useStore } from '../lib/core';
import { SectionTitle, spring } from '../components/ui';

function Toggle({ on, onChange, hue = '#3ddc97' }: { on: boolean; onChange: (v: boolean) => void; hue?: string }) {
  return (
    <button
      onClick={() => onChange(!on)}
      className="relative w-[46px] h-[27px] rounded-full shrink-0 transition-colors"
      style={{
        background: on ? hue : 'rgba(255,255,255,.1)',
        boxShadow: on ? `0 0 14px ${hue}55` : 'inset 0 0 0 1px rgba(255,255,255,.12)',
      }}
    >
      <motion.span
        layout
        className="absolute top-[3.5px] w-5 h-5 rounded-full bg-white grid place-items-center"
        animate={{ left: on ? 22 : 4 }}
        transition={spring}
      >
        {on && <Check size={11} strokeWidth={3.5} style={{ color: hue }} />}
      </motion.span>
    </button>
  );
}

const rise = (i: number) => ({
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
  transition: { delay: 0.05 + i * 0.06, type: 'spring', stiffness: 300, damping: 30 } as const,
});

export default function Settings() {
  const { toast } = useStore();
  const [tgOn, setTgOn] = useState(false);
  const [maxOn, setMaxOn] = useState(true);
  const [dark, setDark] = useState(true);

  return (
    <div className="px-5 pt-3 pb-36">
      <h1 className="font-display text-[24px] font-bold tracking-tight">Настройки</h1>

      {/* боты */}
      <SectionTitle>Уведомления студентов</SectionTitle>

      <motion.div {...rise(0)} className="glass rounded-[22px] p-4 card-inset relative overflow-hidden">
        <div className="absolute -top-10 -left-10 w-32 h-32 rounded-full blur-[50px] opacity-20 bg-cyn pointer-events-none" />
        <div className="flex items-center gap-3 relative">
          <div className="w-11 h-11 rounded-2xl grid place-items-center shrink-0" style={{ background: 'rgba(92,214,240,.12)', color: '#5cd6f0' }}>
            <MessageSquareText size={19} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[14px] font-bold">MAX-бот · основной канал</div>
            <div className="text-[10.5px] text-white/40 mt-0.5">пуши оценок, /vedomost, дайджест 7:00, кураторы</div>
          </div>
          <Toggle on={maxOn} onChange={(v) => { setMaxOn(v); toast({ title: v ? 'MAX-бот включён' : 'MAX-бот остановлен', tone: v ? 'ok' : 'warn' }); }} hue="#5cd6f0" />
        </div>
        <div className="mt-3.5 relative flex items-center gap-2 hairline rounded-xl px-3 py-2.5 bg-white/[.02]">
          <KeyRound size={13} className="text-white/35 shrink-0" />
          <span className="font-mono text-[11px] text-white/45 truncate">@MasterBot → /create · токен •••••4Kp9</span>
        </div>
      </motion.div>

      <motion.div {...rise(1)} className="glass rounded-[22px] p-4 card-inset mt-3 relative overflow-hidden">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl grid place-items-center shrink-0" style={{ background: 'rgba(124,140,255,.12)', color: '#8ea2ff' }}>
            <Send size={17} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[14px] font-bold">Telegram «Мои оценки»</div>
            <div className="text-[10.5px] text-white/40 mt-0.5">read-only · постоянная клавиатура</div>
          </div>
          <Toggle on={tgOn} onChange={(v) => { setTgOn(v); toast({ title: v ? 'TG-бот включён' : 'TG-бот остановлен', tone: v ? 'ok' : 'warn' }); }} hue="#8ea2ff" />
        </div>
        <div className="mt-3.5 flex items-start gap-2 rounded-xl px-3 py-2.5" style={{ background: 'rgba(245,185,63,.07)', boxShadow: 'inset 0 0 0 1px rgba(245,185,63,.2)' }}>
          <ShieldAlert size={13} className="text-ambr shrink-0 mt-0.5" />
          <span className="text-[10.5px] leading-relaxed" style={{ color: 'rgba(245,185,63,.85)' }}>
            Для госучреждений передача ПД через Telegram запрещена (41-ФЗ, с 01.06.2025). Только частное использование с согласия студентов.
          </span>
        </div>
      </motion.div>

      {/* бэкап */}
      <SectionTitle>Бэкап lessons.db</SectionTitle>
      <motion.div {...rise(2)} className="glass rounded-[22px] p-4 card-inset">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-11 h-11 rounded-2xl grid place-items-center shrink-0" style={{ background: 'rgba(61,220,151,.12)', color: '#3ddc97' }}>
            <DatabaseBackup size={18} />
          </div>
          <div className="flex-1">
            <div className="text-[14px] font-bold">Локальная база SQLite</div>
            <div className="text-[10.5px] text-white/40 mt-0.5">WAL-режим · чекпоинт перед заменой</div>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => toast({ title: 'lessons.db выгружена', sub: 'Загрузки · копия содержит токены — не пересылать', tone: 'ok' })}
            className="flex-1 py-3.5 rounded-2xl text-[12.5px] font-bold flex items-center justify-center gap-2 active:scale-95 transition"
            style={{ background: 'linear-gradient(150deg,#3ddc97,#34c7f0)', color: '#0a0d13', boxShadow: '0 10px 24px -10px rgba(61,220,151,.6)' }}
          >
            <Download size={14} strokeWidth={2.5} /> Выгрузить
          </button>
          <button
            onClick={() => toast({ title: 'Автобэкап создан', sub: 'текущая копия сохранена перед заменой', tone: 'info' })}
            className="flex-1 py-3.5 rounded-2xl text-[12.5px] font-bold hairline bg-white/[.04] flex items-center justify-center gap-2 active:scale-95 transition"
          >
            <UploadCloud size={14} /> Восстановить
          </button>
        </div>
      </motion.div>

      {/* внешний вид */}
      <SectionTitle>Внешний вид</SectionTitle>
      <motion.div {...rise(3)} className="glass rounded-[22px] p-4 card-inset flex items-center gap-3">
        <div className="w-11 h-11 rounded-2xl grid place-items-center shrink-0" style={{ background: 'rgba(167,139,250,.12)', color: '#a78bfa' }}>
          <MoonStar size={18} />
        </div>
        <div className="flex-1">
          <div className="text-[14px] font-bold">Тёмная тема</div>
          <div className="text-[10.5px] text-white/40 mt-0.5">roadmap №6 · теперь это тема по умолчанию</div>
        </div>
        <Toggle on={dark} onChange={(v) => { setDark(v); toast({ title: v ? 'Тёмная тема' : 'Светлая тема', sub: v ? '' : 'в концепте доступна только тёмная', tone: 'info' }); if (!v) setTimeout(() => setDark(true), 900); }} hue="#a78bfa" />
      </motion.div>

      {/* футер */}
      <motion.div {...rise(4)} className="mt-8 text-center">
        <div className="font-mono text-[10px] text-white/25 leading-relaxed">
          teachhelper · build 0.2 · flask + sqlite + react<br />сборка и подпись APK — GitHub Actions
        </div>
        <button
          onClick={() => toast({ title: 'Спасибо!', sub: 'поддержка проекта — boosty.to/mifnail', tone: 'info' })}
          className="mt-3 inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-[11.5px] font-bold text-rose hairline bg-rose/[.05] active:scale-95 transition"
        >
          <Heart size={12} /> Поддержать проект
        </button>
      </motion.div>
    </div>
  );
}
