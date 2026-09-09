import { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { ChevronLeft, Search, UserPlus, Send, MessageSquareText, ShieldCheck, Copy, Check } from 'lucide-react';
import { useStore, nav } from '../lib/core';
import { spring } from '../components/ui';

export default function Students({ groupId }: { groupId: number }) {
  const { st, toast } = useStore();
  const [q, setQ] = useState('');
  const [copied, setCopied] = useState(false);
  const grp = st.groups.find(g => g.id === groupId);

  const list = useMemo(() => {
    const all = st.students.filter(s => s.groupId === groupId);
    const t = q.trim().toLowerCase();
    if (!t) return all;
    return all.filter(s => `${s.last} ${s.first} ${s.middle}`.toLowerCase().includes(t));
  }, [st, groupId, q]);

  if (!grp) return null;
  const tgCount = st.students.filter(s => s.groupId === groupId && s.tg).length;
  const maxCount = st.students.filter(s => s.groupId === groupId && s.max).length;

  const copyCode = () => {
    navigator.clipboard?.writeText(grp.curatorCode).catch(() => {});
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
    toast({ title: 'Код куратора скопирован', sub: 'отправьте его куратору группы в MAX', tone: 'ok' });
  };

  return (
    <div className="px-5 pt-3 pb-36">
      {/* шапка */}
      <div className="flex items-center gap-3">
        <button onClick={() => nav('#home')} className="w-9 h-9 grid place-items-center rounded-full hairline text-white/60 active:scale-90 transition shrink-0">
          <ChevronLeft size={17} />
        </button>
        <div className="flex-1">
          <h1 className="font-display text-[20px] font-bold tracking-tight">{grp.name}</h1>
          <div className="text-[11px] text-white/40 font-semibold">{list.length} студентов · TG {tgCount} · MAX {maxCount}</div>
        </div>
        <motion.button
          whileTap={{ scale: 0.92 }}
          onClick={() => toast({ title: 'Добавление студентов', sub: 'массовый ввод списком — в полной сборке', tone: 'info' })}
          className="w-11 h-11 rounded-2xl grid place-items-center text-[#0a0d13]"
          style={{ background: 'linear-gradient(150deg,#3ddc97,#34c7f0)', boxShadow: '0 10px 22px -8px rgba(61,220,151,.7)' }}
        >
          <UserPlus size={18} strokeWidth={2.5} />
        </motion.button>
      </div>

      {/* карточка куратора */}
      <motion.div
        initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ ...spring, delay: 0.05 }}
        className="glass rounded-[20px] p-4 card-inset mt-4 flex items-center gap-3 relative overflow-hidden"
      >
        <div className="absolute -top-8 -right-8 w-28 h-28 rounded-full blur-[45px] opacity-20 bg-cyn pointer-events-none" />
        <div className="w-10 h-10 rounded-xl grid place-items-center shrink-0" style={{ background: 'rgba(92,214,240,.12)', color: '#5cd6f0' }}>
          <ShieldCheck size={17} />
        </div>
        <div className="flex-1 min-w-0 relative">
          <div className="text-[12.5px] font-bold">Куратор группы</div>
          <div className="text-[10.5px] text-white/40 mt-0.5">
            {grp.curatorBound ? 'привязан · пуши оценок с дебаунсом 3 мин' : 'не привязан · отправьте код в MAX'}
          </div>
        </div>
        <button
          onClick={copyCode}
          className="relative flex items-center gap-1.5 px-3 py-2 rounded-xl font-mono text-[12px] font-bold active:scale-95 transition"
          style={{ background: 'rgba(92,214,240,.1)', color: '#5cd6f0', boxShadow: 'inset 0 0 0 1px rgba(92,214,240,.28)' }}
        >
          {copied ? <Check size={12} /> : <Copy size={12} />} {grp.curatorCode}
        </button>
      </motion.div>

      {/* поиск (roadmap №4) */}
      <motion.div
        initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ ...spring, delay: 0.1 }}
        className="mt-3 glass rounded-2xl card-inset flex items-center gap-2.5 px-4"
      >
        <Search size={15} className="text-white/35 shrink-0" />
        <input
          value={q}
          onChange={e => setQ(e.target.value)}
          placeholder="Поиск по фамилии, имени…"
          className="flex-1 bg-transparent py-3.5 text-[13.5px] font-semibold placeholder:text-white/25 outline-none"
        />
        {q && <button onClick={() => setQ('')} className="text-[11px] font-bold text-white/40">Сброс</button>}
      </motion.div>

      {/* список */}
      <motion.div layout className="mt-3 glass rounded-[22px] card-inset overflow-hidden">
        <AnimatePresence initial={false}>
          {list.map((s, i) => (
            <motion.div
              key={s.id}
              layout
              initial={{ opacity: 0, x: -14 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 14 }}
              transition={{ ...spring, delay: Math.min(i * 0.03, 0.3) }}
              className="flex items-center gap-3 px-4 py-3 border-b border-white/[.05] last:border-0"
            >
              <div className="w-10 h-10 rounded-xl grid place-items-center font-display text-[12px] font-bold shrink-0 bg-white/[.05] text-white/70"
                style={{ boxShadow: 'inset 0 0 0 1px rgba(255,255,255,.08)' }}>
                {s.last[0]}{s.first[0]}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[13.5px] font-bold truncate">{s.last} {s.first}</div>
                <div className="text-[10.5px] text-white/35 truncate">{s.middle}</div>
              </div>
              <div className="flex gap-1.5 shrink-0">
                {s.tg && (
                  <span title="Привязан к Telegram-боту «Мои оценки»"
                    className="w-7 h-7 rounded-lg grid place-items-center"
                    style={{ background: 'rgba(124,140,255,.12)', color: '#8ea2ff', boxShadow: 'inset 0 0 0 1px rgba(124,140,255,.3)' }}>
                    <Send size={12} />
                  </span>
                )}
                {s.max && (
                  <span title="Привязан к MAX: пуши оценок, /vedomost, /debts"
                    className="w-7 h-7 rounded-lg grid place-items-center"
                    style={{ background: 'rgba(92,214,240,.12)', color: '#5cd6f0', boxShadow: 'inset 0 0 0 1px rgba(92,214,240,.3)' }}>
                    <MessageSquareText size={12} />
                  </span>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        {list.length === 0 && (
          <div className="py-10 text-center text-[12.5px] text-white/35">Никого не найдено по «{q}»</div>
        )}
      </motion.div>

      <div className="mt-5 text-center text-[11px] text-white/30 leading-relaxed">
        Привязка — по фамилии через бота.<br />Студент видит только свои оценки (read-only).
      </div>
    </div>
  );
}
