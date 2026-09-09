import { useMemo, useState } from 'react';
import { motion } from 'motion/react';
import {
  Play, ChevronRight, CalendarCheck2, Ban, FileSpreadsheet, Users,
  Clock3, Sparkles, CheckCheck,
} from 'lucide-react';
import {
  useStore, nav, todayIso, fmtDateFull, DAY_FULL, DAY_SHORT, LESSON_TIME,
  matchesWeek, fromIso, iso, subjectStats, fmtAvg, groupOf,
} from '../lib/core';
import { ProgressRing, Sheet, SectionTitle, spring } from '../components/ui';

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.055, delayChildren: 0.05 } },
};
const rise = {
  hidden: { opacity: 0, y: 22, filter: 'blur(6px)' },
  show: { opacity: 1, y: 0, filter: 'blur(0px)', transition: spring },
};

/* ---------- календарная сетка (прошлое + сегодня, будущее закрыто) ---------- */

function CalendarGrid({ value, onPick }: { value: string; onPick: (d: string) => void }) {
  const now = new Date();
  const [month, setMonth] = useState(new Date(now.getFullYear(), now.getMonth(), 1));
  const today = todayIso();
  const y = month.getFullYear(), m = month.getMonth();
  const firstDay = (new Date(y, m, 1).getDay() + 6) % 7; // пн = 0
  const dim = new Date(y, m + 1, 0).getDate();
  const cells: (string | null)[] = [
    ...Array.from({ length: firstDay }, () => null),
    ...Array.from({ length: dim }, (_, i) => iso(new Date(y, m, i + 1))),
  ];
  return (
    <div>
      <div className="flex items-center justify-between mb-2 px-1">
        <button
          className="w-8 h-8 grid place-items-center rounded-full hairline text-white/60 active:scale-90 transition"
          onClick={() => setMonth(new Date(y, m - 1, 1))}
        >‹</button>
        <div className="font-display text-[13px] font-semibold capitalize">
          {month.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })}
        </div>
        <button
          className="w-8 h-8 grid place-items-center rounded-full hairline text-white/25"
          disabled
        >›</button>
      </div>
      <div className="grid grid-cols-7 gap-1 mb-1">
        {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map(d => (
          <div key={d} className="text-center text-[10px] font-bold text-white/30 py-1">{d}</div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {cells.map((dIso, i) => {
          if (!dIso) return <div key={`e${i}`} />;
          const future = dIso > today;
          const sel = dIso === value;
          const isToday = dIso === today;
          return (
            <motion.button
              key={dIso}
              disabled={future}
              onClick={() => onPick(dIso)}
              whileTap={future ? undefined : { scale: 0.82 }}
              className="relative aspect-square grid place-items-center rounded-xl text-[13px] font-semibold tabular"
              style={{
                background: sel ? 'linear-gradient(150deg,#7c8cff,#8b5cf6)' : isToday ? 'rgba(124,140,255,.14)' : 'rgba(255,255,255,.035)',
                color: future ? 'rgba(255,255,255,.16)' : sel ? '#fff' : isToday ? '#aab6ff' : 'rgba(255,255,255,.75)',
                boxShadow: sel ? '0 6px 16px -6px rgba(124,140,255,.7)' : 'none',
              }}
            >
              {fromIso(dIso).getDate()}
              {isToday && !sel && <span className="absolute bottom-1 w-1 h-1 rounded-full bg-iris" />}
            </motion.button>
          );
        })}
      </div>
      <div className="mt-2 text-[11px] text-white/35 text-center">Будущие даты закрыты — занятие создаётся задним числом или сегодня</div>
    </div>
  );
}

/* ================= главная ================= */

export default function Home() {
  const { st, startLesson, toast } = useStore();
  const [sheetOpen, setSheetOpen] = useState(false);
  const [pickedEntry, setPickedEntry] = useState<number | null>(null);
  const [pickedDate, setPickedDate] = useState(todayIso());

  const tIso = todayIso();
  const dow = fromIso(tIso).getDay();
  const todayEntries = st.schedule.filter(e => e.day === dow && matchesWeek(e.week, tIso));
  const todayLessons = st.lessons.filter(l => l.date === tIso);

  const entry = st.schedule.find(e => e.id === pickedEntry);

  const begin = () => {
    if (!entry) return;
    const id = startLesson(entry.subjectId, pickedDate, entry.num);
    const subj = st.subjects.find(s => s.id === entry.subjectId)!;
    setSheetOpen(false);
    toast({ title: 'Занятие создано', sub: `${subj.short} · дата из базы: ${pickedDate.split('-').reverse().join('.')}`, tone: 'ok' });
    nav(`#lesson/${id}`);
  };

  const nearest = useMemo(() => {
    const held = st.lessons.filter(l => l.status === 'held').length;
    const marks = Object.values(st.grades).reduce((n, g) => n + Object.keys(g).length, 0);
    return { held, marks };
  }, [st]);

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="px-5 pt-3 pb-36">
      {/* шапка */}
      <motion.div variants={rise} className="flex items-start justify-between">
        <div>
          <div className="text-[12px] text-white/45 font-semibold capitalize">
            {DAY_FULL[dow]}, {fmtDateFull(tIso)}
          </div>
          <h1 className="font-display text-[26px] leading-[1.12] font-bold tracking-tight mt-1 text-balance">
            Учёт<br />занятий
          </h1>
        </div>
        <div className="flex flex-col items-end gap-2 mt-1">
          <div className="glass rounded-2xl px-3.5 py-2 text-right card-inset">
            <div className="font-display text-[17px] font-bold leading-none tabular">{nearest.marks}</div>
            <div className="text-[9.5px] text-white/40 font-bold uppercase tracking-wider mt-1">оценок</div>
          </div>
          <div className="font-mono text-[9.5px] text-white/30">build 0.2</div>
        </div>
      </motion.div>

      {/* сегодня */}
      <SectionTitle right={
        <span className="text-[11px] text-white/40 font-semibold">{todayEntries.length} в расписании</span>
      }>Сегодня</SectionTitle>

      <motion.div variants={rise} className="glass rounded-[22px] p-4 card-inset relative overflow-hidden">
        <div className="absolute -top-10 -right-10 w-36 h-36 rounded-full blur-[50px] opacity-25 bg-iris pointer-events-none" />
        {todayEntries.length === 0 ? (
          <div className="py-3 text-center">
            <Sparkles size={18} className="mx-auto text-white/30 mb-2" />
            <div className="text-[13.5px] font-semibold text-white/75">Сегодня занятий нет</div>
            <div className="text-[11.5px] text-white/40 mt-1">Можно создать занятие вручную — задним числом</div>
          </div>
        ) : (
          <div className="flex flex-col gap-2.5 relative">
            {todayEntries.map((e) => {
              const subj = st.subjects.find(s => s.id === e.subjectId)!;
              const grp = groupOf(st, e.subjectId);
              const lessons = todayLessons.filter(l => l.subjectId === e.subjectId);
              return (
                <div key={e.id} className="flex items-center gap-3 hairline rounded-2xl p-3 bg-white/[.02]">
                  <div className="w-10 h-10 rounded-xl grid place-items-center font-display text-[11px] font-bold shrink-0"
                    style={{ background: `${subj.hue}1f`, color: subj.hue, boxShadow: `inset 0 0 0 1px ${subj.hue}38` }}>
                    {subj.short}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[13.5px] font-bold truncate">{e.num} пара · {subj.name}</div>
                    <div className="text-[11px] text-white/40 flex items-center gap-1.5 mt-0.5">
                      <Clock3 size={11} /> {LESSON_TIME[e.num]} · {grp?.name}
                    </div>
                    {lessons.map(l => (
                      <button key={l.id} onClick={() => nav(`#lesson/${l.id}`)}
                        className="mt-1.5 inline-flex items-center gap-1.5 text-[11px] font-bold px-2 py-1 rounded-lg active:scale-95 transition"
                        style={l.status === 'cancelled'
                          ? { background: 'rgba(242,98,122,.13)', color: '#f2627a' }
                          : { background: 'rgba(61,220,151,.13)', color: '#3ddc97' }}>
                        {l.status === 'cancelled' ? <Ban size={11} /> : <CheckCheck size={12} />}
                        {l.status === 'cancelled' ? 'Отменено' : 'Проводится · открыть журнал'}
                      </button>
                    ))}
                  </div>
                  {lessons.length === 0 && (
                    <motion.button
                      whileTap={{ scale: 0.9 }}
                      onClick={() => { setPickedEntry(e.id); setPickedDate(tIso); setSheetOpen(true); }}
                      className="w-11 h-11 rounded-2xl grid place-items-center shrink-0 text-[#0a0d13]"
                      style={{ background: 'linear-gradient(150deg,#3ddc97,#34c7f0)', boxShadow: '0 8px 20px -8px rgba(61,220,151,.7)' }}
                    >
                      <Play size={17} strokeWidth={2.6} className="ml-0.5" />
                    </motion.button>
                  )}
                </div>
              );
            })}
          </div>
        )}
        <motion.button
          variants={rise}
          whileTap={{ scale: 0.97 }}
          onClick={() => { setPickedEntry(todayEntries[0]?.id ?? st.schedule[0]?.id ?? null); setPickedDate(tIso); setSheetOpen(true); }}
          className="mt-3 w-full py-3 rounded-2xl text-[13px] font-bold text-white/85 hairline bg-white/[.04] active:bg-white/[.08] transition flex items-center justify-center gap-2"
        >
          <CalendarCheck2 size={15} /> Создать занятие с датой
        </motion.button>
      </motion.div>

      {/* предметы */}
      <SectionTitle right={
        <button onClick={() => toast({ title: 'Ведомость .xlsx', sub: 'сохранена в Загрузки · расшарить можно из системной шторки', tone: 'info' })}
          className="text-[11px] font-bold text-iris flex items-center gap-1 active:opacity-60">
          <FileSpreadsheet size={12} /> отчёт за день
        </button>
      }>Предметы</SectionTitle>

      <div className="flex flex-col gap-2.5">
        {st.subjects.map((s) => {
          const stats = subjectStats(st, s.id);
          const pct = s.totalHours > 0 ? (stats.held / (s.totalHours / 2)) * 100 : 0;
          const grp = groupOf(st, s.id);
          return (
            <motion.button
              key={s.id}
              variants={rise}
              whileTap={{ scale: 0.975 }}
              onClick={() => nav(`#subject/${s.id}`)}
              className="glass rounded-[22px] p-4 card-inset flex items-center gap-4 text-left w-full relative overflow-hidden"
            >
              <div className="absolute -bottom-14 -left-10 w-36 h-36 rounded-full blur-[55px] opacity-20 pointer-events-none" style={{ background: s.hue }} />
              <ProgressRing pct={pct} color={s.hue} size={64} stroke={6}>
                <span className="font-display text-[13px] font-bold tabular">{Math.round(pct)}<span className="text-[9px] text-white/50">%</span></span>
              </ProgressRing>
              <div className="flex-1 min-w-0 relative">
                <div className="text-[14.5px] font-bold truncate">{s.name}</div>
                <div className="text-[11.5px] text-white/40 mt-0.5">{grp?.name} · {stats.held}/{s.totalHours / 2} пар · осталось {stats.remaining}</div>
                <div className="flex items-center gap-3 mt-2">
                  <span className="text-[10.5px] font-bold px-2 py-0.5 rounded-md" style={{ background: `${s.hue}1c`, color: s.hue }}>
                    ср. балл {fmtAvg(stats.avg)}
                  </span>
                  <span className="text-[10.5px] text-white/35 font-semibold">{stats.students} студ.</span>
                </div>
              </div>
              <ChevronRight size={17} className="text-white/25 shrink-0 relative" />
            </motion.button>
          );
        })}
      </div>

      {/* группы */}
      <SectionTitle>Группы</SectionTitle>
      <div className="grid grid-cols-2 gap-2.5">
        {st.groups.map((g) => {
          const count = st.students.filter(s => s.groupId === g.id).length;
          return (
            <motion.button
              key={g.id}
              variants={rise}
              whileTap={{ scale: 0.95 }}
              onClick={() => nav(`#students/${g.id}`)}
              className="glass rounded-[22px] p-4 card-inset text-left relative overflow-hidden"
            >
              <div className="w-9 h-9 rounded-xl grid place-items-center bg-white/[.05] mb-3">
                <Users size={16} className="text-white/60" />
              </div>
              <div className="font-display text-[16px] font-bold">{g.name}</div>
              <div className="text-[11px] text-white/40 mt-0.5">{count} студентов</div>
              {g.curatorBound && (
                <div className="absolute top-3.5 right-3.5 w-2 h-2 rounded-full bg-mint" style={{ boxShadow: '0 0 10px #3ddc97' }} />
              )}
            </motion.button>
          );
        })}
      </div>

      {/* sheet: начать занятие */}
      <Sheet open={sheetOpen} onClose={() => setSheetOpen(false)} title="Начать занятие">
        <div className="text-[11px] font-bold uppercase tracking-wider text-white/40 mb-2">Предмет</div>
        <div className="flex flex-col gap-2 mb-5">
          {(todayEntries.length ? todayEntries : st.schedule.slice(0, 3)).map((e) => {
            const subj = st.subjects.find(s => s.id === e.subjectId)!;
            const on = pickedEntry === e.id;
            return (
              <button
                key={e.id}
                onClick={() => setPickedEntry(e.id)}
                className="flex items-center gap-3 rounded-2xl p-3 text-left transition active:scale-[.98]"
                style={{
                  background: on ? `${subj.hue}17` : 'rgba(255,255,255,.035)',
                  boxShadow: on ? `inset 0 0 0 1.5px ${subj.hue}66` : 'inset 0 0 0 1px rgba(255,255,255,.07)',
                }}
              >
                <div className="w-9 h-9 rounded-xl grid place-items-center font-display text-[10px] font-bold"
                  style={{ background: `${subj.hue}1f`, color: subj.hue }}>{subj.short}</div>
                <div className="flex-1 min-w-0">
                  <div className="text-[13.5px] font-bold truncate">{subj.name}</div>
                  <div className="text-[11px] text-white/40">{e.num} пара · {DAY_SHORT[e.day]} · {LESSON_TIME[e.num]}</div>
                </div>
                <div className="w-5 h-5 rounded-full grid place-items-center"
                  style={{ background: on ? subj.hue : 'rgba(255,255,255,.08)' }}>
                  {on && <CheckCheck size={12} className="text-[#0a0d13]" strokeWidth={3} />}
                </div>
              </button>
            );
          })}
        </div>
        <div className="text-[11px] font-bold uppercase tracking-wider text-white/40 mb-2">Дата занятия</div>
        <CalendarGrid value={pickedDate} onPick={setPickedDate} />
        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={begin}
          disabled={!entry}
          className="mt-5 w-full py-4 rounded-2xl font-bold text-[14px] text-[#0a0d13] flex items-center justify-center gap-2 disabled:opacity-40"
          style={{ background: 'linear-gradient(150deg,#3ddc97,#34c7f0)', boxShadow: '0 12px 28px -10px rgba(61,220,151,.65)' }}
        >
          <Play size={16} strokeWidth={2.6} /> Начать · {pickedDate.split('-').reverse().join('.')}
        </motion.button>
      </Sheet>
    </motion.div>
  );
}
