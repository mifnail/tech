import { useMemo } from 'react';
import { motion } from 'motion/react';
import { ChevronLeft, FileSpreadsheet, Share2, TriangleAlert, UserRound } from 'lucide-react';
import {
  useStore, nav, fmtDate, lessonsOfSubject, studentsOfSubject,
  groupOf, subjectStats, studentStatsInSubject, fmtAvg,
} from '../lib/core';
import { GradeCell, AreaChart, SectionTitle, CountUp } from '../components/ui';

const rise = (i: number) => ({
  initial: { opacity: 0, y: 18, filter: 'blur(5px)' },
  animate: { opacity: 1, y: 0, filter: 'blur(0px)' },
  transition: { delay: 0.05 + i * 0.06, type: 'spring', stiffness: 300, damping: 30 } as const,
});

export default function Gradebook({ id }: { id: number }) {
  const { st, toast } = useStore();
  const subject = st.subjects.find(s => s.id === id);
  const lessons = useMemo(() => lessonsOfSubject(st, id), [st, id]);
  const students = useMemo(() => studentsOfSubject(st, id), [st, id]);
  const grp = groupOf(st, id);

  const trend = useMemo(() =>
    lessons.filter(l => l.status === 'held').map(l => {
      const vals = Object.values(st.grades[l.id] || {}).map(g => (g && g >= '2' && g <= '5') ? Number(g) : null).filter((n): n is number => n != null);
      return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 3;
    }), [lessons, st.grades]);

  const debtors = useMemo(() =>
    students.map(s => ({ s, ...studentStatsInSubject(st, id, s.id) }))
      .filter(d => (d.avg != null && d.avg < 3.5) || d.abs >= 2)
      .sort((a, b) => (a.avg ?? 0) - (b.avg ?? 0)),
    [st, id, students]);

  if (!subject) return null;
  const stats = subjectStats(st, id);
  const pct = stats.held / (subject.totalHours / 2) * 100;

  return (
    <div className="pt-2 pb-40">
      <div className="px-5">
        {/* шапка */}
        <div className="flex items-center gap-3">
          <button onClick={() => nav('#home')} className="w-9 h-9 grid place-items-center rounded-full hairline text-white/60 active:scale-90 transition shrink-0">
            <ChevronLeft size={17} />
          </button>
          <div className="min-w-0 flex-1">
            <h1 className="font-display text-[16px] font-bold truncate tracking-tight">{subject.name}</h1>
            <div className="text-[11px] text-white/40 font-semibold mt-0.5">{grp?.name} · журнал предмета</div>
          </div>
          <motion.button
            whileTap={{ scale: 0.9 }}
            onClick={() => toast({ title: `Ведомость ${subject.short} · .xlsx`, sub: 'сохранена в Загрузки через MediaStore', tone: 'ok' })}
            className="w-10 h-10 grid place-items-center rounded-2xl text-[#0a0d13] shrink-0"
            style={{ background: `linear-gradient(150deg,${subject.hue},${subject.hue}bb)`, boxShadow: `0 8px 20px -8px ${subject.hue}aa` }}
          >
            <FileSpreadsheet size={16} strokeWidth={2.4} />
          </motion.button>
        </div>

        {/* сводка */}
        <motion.div {...rise(0)} className="glass rounded-[22px] p-4 card-inset mt-4 relative overflow-hidden">
          <div className="absolute -top-12 -right-12 w-40 h-40 rounded-full blur-[60px] opacity-20 pointer-events-none" style={{ background: subject.hue }} />
          <div className="grid grid-cols-4 gap-1 text-center relative">
            {[
              { v: stats.held, l: 'проведено' },
              { v: stats.remaining, l: 'осталось' },
              { v: fmtAvg(stats.avg), l: 'ср. балл' },
              { v: stats.students, l: 'студентов' },
            ].map((x) => (
              <div key={x.l}>
                <div className="font-display text-[17px] font-bold tabular">{typeof x.v === 'number' ? <CountUp value={x.v} /> : x.v}</div>
                <div className="text-[9px] font-bold uppercase tracking-wider text-white/35 mt-1">{x.l}</div>
              </div>
            ))}
          </div>
          <div className="mt-4">
            <div className="flex justify-between text-[10px] font-bold text-white/35 mb-1.5">
              <span>освоение курса</span><span className="tabular">{Math.round(pct)}%</span>
            </div>
            <div className="h-1.5 rounded-full bg-white/[.07] overflow-hidden">
              <motion.div className="h-full rounded-full" style={{ background: `linear-gradient(90deg, ${subject.hue}99, ${subject.hue})`, boxShadow: `0 0 10px ${subject.hue}77` }}
                initial={{ width: 0 }} animate={{ width: `${Math.min(100, pct)}%` }} transition={{ type: 'spring', stiffness: 50, damping: 18 }} />
            </div>
          </div>
          <div className="mt-4">
            <div className="text-[10px] font-bold text-white/35 mb-1.5 uppercase tracking-wider">динамика среднего балла</div>
            <AreaChart points={trend} color={subject.hue} height={74} />
          </div>
        </motion.div>

        <SectionTitle right={
          <button onClick={() => toast({ title: 'Ссылка на ведомость', sub: 'шаринг недоступен в демо-сборке', tone: 'info' })}
            className="text-[11px] font-bold text-iris flex items-center gap-1 active:opacity-60">
            <Share2 size={12} /> поделиться
          </button>
        }>Ведомость</SectionTitle>
      </div>

      {/* сетка ведомости */}
      <motion.div {...rise(1)} className="mx-5 glass rounded-[22px] card-inset overflow-hidden">
        <div className="overflow-x-auto nice-scroll">
          <div className="flex min-w-max p-2 gap-1">
            {/* имена — sticky слева */}
            <div className="sticky left-0 z-20 shrink-0 w-[128px] rounded-xl py-1" style={{ background: 'linear-gradient(165deg,#12161f,#0b0e14)', boxShadow: '8px 0 16px -8px rgba(0,0,0,.6)' }}>
              <div className="h-[44px] flex items-end px-2.5 pb-1.5">
                <span className="text-[9.5px] font-bold uppercase tracking-wider text-white/35 flex items-center gap-1"><UserRound size={10} /> студент</span>
              </div>
              {students.map((s) => (
                <div key={s.id} className="h-9 flex items-center px-2.5 mt-1">
                  <span className="text-[12px] font-bold truncate">{s.last} <span className="text-white/35 font-semibold">{s.first[0]}.</span></span>
                </div>
              ))}
            </div>

            {/* колонки занятий */}
            {lessons.map((l) => {
              const cancelled = l.status === 'cancelled';
              return (
                <button
                  key={l.id}
                  onClick={() => nav(`#lesson/${l.id}`)}
                  className={`shrink-0 flex flex-col items-center group ${cancelled ? 'opacity-40' : ''}`}
                >
                  <div className="h-[44px] w-8 grid place-items-center">
                    <div className="text-center leading-[1.05]">
                      <div className={`text-[10.5px] font-bold tabular group-active:scale-90 transition ${cancelled ? 'line-through text-white/40' : 'text-white/75'}`}>
                        {fmtDate(l.date)}
                      </div>
                      <div className="text-[8.5px] text-white/30 font-semibold mt-0.5">№{l.num}</div>
                    </div>
                  </div>
                  {students.map((s, si) => (
                    <div key={s.id} className="mt-1">
                      <GradeCell grade={cancelled ? null : (st.grades[l.id]?.[s.id] ?? null)} odd={si % 2 === 0} />
                    </div>
                  ))}
                </button>
              );
            })}

            {/* средний балл — sticky справа */}
            <div className="sticky right-0 z-20 shrink-0 w-[54px] rounded-xl py-1 ml-1" style={{ background: 'linear-gradient(165deg,#12161f,#0b0e14)', boxShadow: '-8px 0 16px -8px rgba(0,0,0,.6)' }}>
              <div className="h-[44px] grid place-items-center pb-1.5">
                <span className="text-[9.5px] font-bold uppercase tracking-wider text-white/35">ср</span>
              </div>
              {students.map((s) => {
                const ss = studentStatsInSubject(st, id, s.id);
                const c = ss.avg == null ? 'rgba(255,255,255,.25)' : ss.avg >= 4 ? '#3ddc97' : ss.avg >= 3 ? '#f5b93f' : '#f2627a';
                return (
                  <div key={s.id} className="h-9 mt-1 grid place-items-center">
                    <span className="font-mono text-[12px] font-bold tabular" style={{ color: c }}>{fmtAvg(ss.avg)}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </motion.div>

      {/* должники */}
      <div className="px-5">
        <SectionTitle right={
          <span className="text-[11px] font-bold text-rose flex items-center gap-1"><TriangleAlert size={12} /> {debtors.length}</span>
        }>Зона риска</SectionTitle>
        {debtors.length === 0 ? (
          <motion.div {...rise(2)} className="glass rounded-[22px] p-5 card-inset text-center text-[12.5px] text-white/45">
            Должников нет — группа идёт ровно
          </motion.div>
        ) : (
          <div className="flex flex-col gap-2">
            {debtors.map((d, i) => (
              <motion.div key={d.s.id} {...rise(2 + i)} className="glass rounded-[20px] p-3.5 card-inset flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl grid place-items-center font-display text-[12px] font-bold shrink-0"
                  style={{ background: 'rgba(242,98,122,.12)', color: '#f2627a', boxShadow: 'inset 0 0 0 1px rgba(242,98,122,.3)' }}>
                  {d.s.last[0]}{d.s.first[0]}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[13.5px] font-bold truncate">{d.s.last} {d.s.first}</div>
                  <div className="text-[10.5px] text-white/40 mt-0.5">
                    {d.avg != null && d.avg < 3.5 && `средний балл ${fmtAvg(d.avg)}`}
                    {d.avg != null && d.avg < 3.5 && d.abs >= 2 && ' · '}
                    {d.abs >= 2 && `${d.abs} пропуска`}
                  </div>
                </div>
                <div className="font-mono text-[15px] font-bold tabular" style={{ color: '#f2627a' }}>{fmtAvg(d.avg)}</div>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
