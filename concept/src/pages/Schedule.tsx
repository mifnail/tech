import { useState } from 'react';
import { motion } from 'motion/react';
import { CalendarRange, Clock3, Plus, Repeat } from 'lucide-react';
import {
  useStore, todayIso, weekParity, LESSON_TIME, DAY_FULL, type WeekType,
} from '../lib/core';
import { SectionTitle } from '../components/ui';

type Filter = 'all' | 'odd' | 'even';
const WEEK_LABEL: Record<WeekType, string> = { every: 'каждую', odd: 'нечёт', even: 'чёт' };
const WEEK_HUE: Record<WeekType, string> = { every: '#8b96ab', odd: '#5cd6f0', even: '#a78bfa' };

export default function Schedule() {
  const { st, toast } = useStore();
  const [filter, setFilter] = useState<Filter>('all');

  const now = new Date();
  const todayDow = ((now.getDay() + 6) % 7) + 1; // 1=пн
  const parity = weekParity(todayIso());

  const days = [1, 2, 3, 4, 5, 6];

  return (
    <div className="px-5 pt-3 pb-36">
      <div className="flex items-end justify-between">
        <div>
          <div className="text-[12px] text-white/45 font-semibold flex items-center gap-1.5">
            <Repeat size={12} /> сейчас {parity === 'odd' ? 'нечётная' : 'чётная'} неделя
          </div>
          <h1 className="font-display text-[24px] font-bold tracking-tight mt-1">Расписание</h1>
        </div>
        <motion.button
          whileTap={{ scale: 0.92 }}
          onClick={() => toast({ title: 'Новая запись расписания', sub: 'форма добавления — в полной сборке', tone: 'info' })}
          className="w-11 h-11 rounded-2xl grid place-items-center text-[#0a0d13]"
          style={{ background: 'linear-gradient(150deg,#7c8cff,#8b5cf6)', boxShadow: '0 10px 22px -8px rgba(124,140,255,.7)' }}
        >
          <Plus size={19} strokeWidth={2.6} />
        </motion.button>
      </div>

      {/* фильтр чётности */}
      <div className="mt-4 glass rounded-2xl p-1 flex card-inset">
        {([['all', 'Все'], ['odd', 'Нечётная'], ['even', 'Чётная']] as [Filter, string][]).map(([f, label]) => (
          <button key={f} onClick={() => setFilter(f)} className="relative flex-1 py-2.5 rounded-xl text-[12px] font-bold transition-colors"
            style={{ color: filter === f ? '#0a0d13' : 'rgba(255,255,255,.5)' }}>
            {filter === f && (
              <motion.span layoutId="week-pill" className="absolute inset-0 rounded-xl bg-white"
                transition={{ type: 'spring', stiffness: 420, damping: 34 }} />
            )}
            <span className="relative z-10">{label}</span>
          </button>
        ))}
      </div>

      {days.map((d, di) => {
        const entries = st.schedule
          .filter(e => e.day === d)
          .filter(e => filter === 'all' || e.week === 'every' || e.week === filter);
        if (!entries.length) return null;
        const isToday = d === todayDow;
        return (
          <motion.div
            key={d}
            initial={{ opacity: 0, y: 20, filter: 'blur(5px)' }}
            animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
            transition={{ delay: 0.05 + di * 0.06, type: 'spring', stiffness: 280, damping: 28 }}
          >
            <SectionTitle right={isToday ? (
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-md" style={{ background: 'rgba(61,220,151,.13)', color: '#3ddc97' }}>сегодня</span>
            ) : undefined}>
              <span className="capitalize">{DAY_FULL[d]}</span>
            </SectionTitle>
            <div className="flex flex-col gap-2">
              {entries.sort((a, b) => a.num - b.num).map((e) => {
                const subj = st.subjects.find(s => s.id === e.subjectId)!;
                const grp = st.groups.find(g => g.id === subj.groupId);
                const inactive = filter !== 'all' ? false : (isToday && e.week !== 'every' && e.week !== parity);
                return (
                  <div
                    key={e.id}
                    className="glass rounded-[20px] p-3.5 card-inset flex items-center gap-3"
                    style={{ opacity: inactive ? 0.45 : 1 }}
                  >
                    <div className="w-11 h-11 rounded-xl grid place-items-center font-display text-[11px] font-bold shrink-0"
                      style={{ background: `${subj.hue}1c`, color: subj.hue, boxShadow: `inset 0 0 0 1px ${subj.hue}38` }}>
                      {subj.short}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-[13.5px] font-bold truncate">{e.num} пара · {subj.name}</div>
                      <div className="text-[11px] text-white/40 mt-0.5 flex items-center gap-1.5">
                        <Clock3 size={11} /> {LESSON_TIME[e.num]} · {grp?.name}
                      </div>
                    </div>
                    <span className="text-[9.5px] font-bold px-2 py-1 rounded-lg uppercase tracking-wide shrink-0"
                      style={{ background: `${WEEK_HUE[e.week]}16`, color: WEEK_HUE[e.week] }}>
                      {WEEK_LABEL[e.week]}
                    </span>
                  </div>
                );
              })}
            </div>
          </motion.div>
        );
      })}

      <div className="mt-8 text-center text-[11px] text-white/30 flex items-center justify-center gap-2">
        <CalendarRange size={12} /> дубли занятий в один день поддерживаются
      </div>
    </div>
  );
}
