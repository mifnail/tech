import { useMemo } from 'react';
import { motion } from 'motion/react';
import { TrendingUp, TrendingDown, Flame, Award, TriangleAlert } from 'lucide-react';
import {
  useStore, avgOfGrades, fmtAvg, studentStatsInSubject, subjectStats,
} from '../lib/core';
import { AreaChart, ProgressRing, SectionTitle, CountUp } from '../components/ui';

const rise = (i: number) => ({
  initial: { opacity: 0, y: 20, filter: 'blur(5px)' },
  animate: { opacity: 1, y: 0, filter: 'blur(0px)' },
  transition: { delay: 0.05 + i * 0.07, type: 'spring', stiffness: 280, damping: 28 } as const,
});

export default function Analytics() {
  const { st } = useStore();

  const data = useMemo(() => {
    const held = st.lessons.filter(l => l.status === 'held').sort((a, b) => a.date.localeCompare(b.date));
    const allVals = held.flatMap(l => Object.values(st.grades[l.id] || {}));
    const avg = avgOfGrades(allVals);

    let present = 0, marked = 0;
    for (const g of allVals) if (g) { marked++; if (g !== 'absent') present++; }
    const att = marked ? Math.round((present / marked) * 100) : 0;

    /* динамика среднего по занятиям */
    const series = held.map(l => {
      const vals = Object.values(st.grades[l.id] || {});
      return { date: l.date, avg: avgOfGrades(vals) ?? 0, n: vals.filter(Boolean).length };
    }).filter(p => p.n > 0);

    const last = series.slice(-3).map(p => p.avg);
    const delta = last.length >= 2 ? (last[last.length - 1] - last[0]) : 0;

    /* активность по дням для тепловой полосы */
    const byDay: Record<string, number> = {};
    for (const p of series) byDay[p.date] = (byDay[p.date] || 0) + p.n;
    const maxDay = Math.max(1, ...Object.values(byDay));
    const days: { d: Date; v: number }[] = [];
    for (let i = 13; i >= 0; i--) {
      const d = new Date(); d.setDate(d.getDate() - i);
      const k = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
      days.push({ d, v: (byDay[k] || 0) / maxDay });
    }

    /* доски почёта и риска по всем предметам */
    const board = st.students.map(s => {
      let sum = 0, cnt = 0, abs = 0;
      for (const subj of st.subjects.filter(x => x.groupId === s.groupId)) {
        const r = studentStatsInSubject(st, subj.id, s.id);
        if (r.avg != null) { sum += r.avg; cnt++; }
        abs += r.abs;
      }
      return { s, avg: cnt ? sum / cnt : null, abs };
    }).filter(b => b.avg != null);

    return {
      avg, att, marked, series: series.map(p => p.avg),
      delta, days,
      top: [...board].sort((a, b) => (b.avg ?? 0) - (a.avg ?? 0)).slice(0, 3),
      risk: [...board].filter(b => (b.avg ?? 5) < 3.4 || b.abs >= 3).sort((a, b) => (a.avg ?? 0) - (b.avg ?? 0)).slice(0, 3),
    };
  }, [st]);

  const up = data.delta >= 0;

  return (
    <div className="px-5 pt-3 pb-36">
      <div className="text-[12px] text-white/45 font-semibold">roadmap №2 · реализовано</div>
      <h1 className="font-display text-[24px] font-bold tracking-tight mt-1">Аналитика</h1>

      {/* главные метрики */}
      <motion.div {...rise(0)} className="glass rounded-[22px] p-4 card-inset mt-4 relative overflow-hidden">
        <div className="absolute -top-14 -right-14 w-44 h-44 rounded-full blur-[60px] opacity-20 bg-mint pointer-events-none" />
        <div className="flex items-center gap-5 relative">
          <ProgressRing pct={data.att} size={92} stroke={8} color="#3ddc97">
            <div className="text-center">
              <div className="font-display text-[19px] font-bold leading-none tabular"><CountUp value={data.att} /><span className="text-[11px] text-white/40">%</span></div>
              <div className="text-[8px] font-bold uppercase tracking-wider text-white/35 mt-1">посещ.</div>
            </div>
          </ProgressRing>
          <div className="flex-1">
            <div className="flex items-baseline gap-2">
              <span className="font-display text-[34px] font-bold leading-none" style={{ color: (data.avg ?? 0) >= 4 ? '#3ddc97' : '#f5b93f' }}>{fmtAvg(data.avg)}</span>
              <span className="flex items-center gap-1 text-[12px] font-bold" style={{ color: up ? '#3ddc97' : '#f2627a' }}>
                {up ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                {up ? '+' : ''}{(Math.round(data.delta * 100) / 100).toString().replace('.', ',')}
              </span>
            </div>
            <div className="text-[11px] text-white/40 mt-1.5">средний балл по всем предметам</div>
            <div className="text-[11px] text-white/40"><span className="font-bold text-white/70 tabular">{data.marked}</span> оценок за период</div>
          </div>
        </div>
        <div className="mt-4">
          <div className="text-[10px] font-bold text-white/35 mb-1.5 uppercase tracking-wider">динамика среднего балла</div>
          <AreaChart points={data.series} color="#3ddc97" height={86} />
        </div>
      </motion.div>

      {/* тепловая полоса активности */}
      <motion.div {...rise(1)} className="glass rounded-[22px] p-4 card-inset mt-3">
        <div className="flex items-center gap-2 mb-3">
          <Flame size={13} className="text-ambr" />
          <span className="text-[12px] font-bold text-white/70">активность · 14 дней</span>
        </div>
        <div className="flex gap-1.5">
          {data.days.map((d, i) => (
            <motion.div
              key={i}
              initial={{ scaleY: 0.2, opacity: 0 }}
              animate={{ scaleY: 1, opacity: 1 }}
              transition={{ delay: 0.2 + i * 0.04, type: 'spring', stiffness: 300, damping: 20 }}
              className="flex-1 h-9 rounded-lg origin-bottom"
              style={{
                background: d.v > 0 ? `linear-gradient(180deg, rgba(245,185,63,${0.25 + d.v * 0.65}), rgba(245,185,63,${0.1 + d.v * 0.25}))` : 'rgba(255,255,255,.04)',
                boxShadow: d.v > 0.5 ? '0 0 12px rgba(245,185,63,.25)' : 'none',
              }}
              title={`${d.d.getDate()}.${d.d.getMonth() + 1}`}
            />
          ))}
        </div>
        <div className="flex justify-between text-[9px] text-white/25 font-mono mt-1.5 tabular">
          <span>-14д</span><span>сегодня</span>
        </div>
      </motion.div>

      {/* по предметам */}
      <SectionTitle>По предметам</SectionTitle>
      <div className="flex flex-col gap-2">
        {st.subjects.map((s, i) => {
          const stats = subjectStats(st, s.id);
          const pct = stats.avg != null ? (stats.avg / 5) * 100 : 0;
          return (
            <motion.div key={s.id} {...rise(2 + i)} className="glass rounded-[20px] p-4 card-inset">
              <div className="flex items-center justify-between mb-2.5">
                <div className="text-[13px] font-bold truncate">{s.name}</div>
                <div className="font-mono text-[13px] font-bold tabular" style={{ color: s.hue }}>{fmtAvg(stats.avg)}</div>
              </div>
              <div className="h-2 rounded-full bg-white/[.06] overflow-hidden">
                <motion.div className="h-full rounded-full"
                  style={{ background: `linear-gradient(90deg, ${s.hue}aa, ${s.hue})`, boxShadow: `0 0 10px ${s.hue}66` }}
                  initial={{ width: 0 }} animate={{ width: `${pct}%` }}
                  transition={{ delay: 0.3 + i * 0.1, type: 'spring', stiffness: 60, damping: 18 }} />
              </div>
              <div className="flex justify-between mt-2 text-[10px] text-white/35 font-semibold">
                <span>{stats.held} занятий</span><span>{stats.students} студентов</span>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* доски */}
      <SectionTitle>Тренды по студентам</SectionTitle>
      <div className="grid grid-cols-2 gap-2.5">
        <motion.div {...rise(5)} className="glass rounded-[20px] p-4 card-inset">
          <div className="flex items-center gap-1.5 mb-3 text-mint">
            <Award size={13} /><span className="text-[11px] font-bold">Лидеры</span>
          </div>
          {data.top.map((b, i) => (
            <div key={b.s.id} className="flex items-center gap-2 py-1.5">
              <span className="font-mono text-[10px] text-white/25 w-3">{i + 1}</span>
              <span className="text-[12px] font-bold truncate flex-1">{b.s.last} {b.s.first[0]}.</span>
              <span className="font-mono text-[12px] font-bold text-mint tabular">{fmtAvg(b.avg)}</span>
            </div>
          ))}
        </motion.div>
        <motion.div {...rise(6)} className="glass rounded-[20px] p-4 card-inset">
          <div className="flex items-center gap-1.5 mb-3 text-rose">
            <TriangleAlert size={13} /><span className="text-[11px] font-bold">Зона риска</span>
          </div>
          {data.risk.length === 0 && <div className="text-[11.5px] text-white/35 py-2">все в порядке</div>}
          {data.risk.map((b) => (
            <div key={b.s.id} className="flex items-center gap-2 py-1.5">
              <span className="text-[12px] font-bold truncate flex-1">{b.s.last} {b.s.first[0]}.</span>
              <span className="text-[9.5px] font-bold text-white/30 tabular">{b.abs}пр</span>
              <span className="font-mono text-[12px] font-bold text-rose tabular">{fmtAvg(b.avg)}</span>
            </div>
          ))}
        </motion.div>
      </div>
    </div>
  );
}
