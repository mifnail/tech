import { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  ChevronLeft, ChevronRight, ArrowLeftRight, Ban, Trash2, BookOpen,
  CopyCheck, Undo2, MousePointerClick,
} from 'lucide-react';
import {
  useStore, nav, fmtDate, avgOfGrades, lessonsOfSubject,
  studentsOfSubject, groupOf, GRADE_META, type Grade,
} from '../lib/core';
import { GradeOrb, Sheet, CountUp, spring } from '../components/ui';

/* ---------- плитка студента с двусторонним тапом ---------- */

function StudentTile({ lessonId, student, grade }: {
  lessonId: number;
  student: { id: number; last: string; first: string };
  grade: Grade;
}) {
  const { cycleGrade } = useStore();
  const [fx, setFx] = useState<{ dir: 1 | -1; k: number } | null>(null);

  const onTap = (e: React.MouseEvent<HTMLButtonElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const dir: 1 | -1 = (e.clientX - r.left) / r.width < 0.5 ? -1 : 1;
    cycleGrade(lessonId, student.id, dir);
    setFx({ dir, k: Date.now() });
    window.setTimeout(() => setFx(null), 320);
  };

  const meta = grade ? GRADE_META[grade] : null;

  return (
    <motion.button
      layout
      onClick={onTap}
      whileTap={{ scale: 0.94 }}
      transition={spring}
      className="relative overflow-hidden rounded-2xl p-2 pr-1.5 flex items-center gap-2 min-h-[58px] text-left"
      style={{
        background: meta ? `linear-gradient(140deg, ${meta.c}14, rgba(255,255,255,.02))` : 'rgba(255,255,255,.035)',
        boxShadow: meta ? `inset 0 0 0 1px ${meta.c}30` : 'inset 0 0 0 1px rgba(255,255,255,.06)',
      }}
    >
      {/* вспышка направления тапа */}
      <AnimatePresence>
        {fx && (
          <motion.span
            key={fx.k}
            className="absolute inset-y-0 w-1/2 pointer-events-none grid place-items-center"
            style={{
              [fx.dir === 1 ? 'right' : 'left']: 0,
              background: `linear-gradient(${fx.dir === 1 ? '270deg' : '90deg'}, rgba(124,140,255,.22), transparent)`,
            } as React.CSSProperties}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.28 }}
          >
            <span className="text-white/60 font-mono text-[13px] font-bold">{fx.dir === 1 ? '›' : '‹'}</span>
          </motion.span>
        )}
      </AnimatePresence>

      <GradeOrb grade={grade} size={42} />
      <div className="min-w-0 flex-1 relative z-10">
        <div className="text-[12.5px] font-bold leading-tight truncate">{student.last}</div>
        <div className="text-[10.5px] text-white/40 truncate">{student.first}</div>
      </div>
    </motion.button>
  );
}

/* ---------- полоса распределения оценок ---------- */

function Distribution({ grades }: { grades: Grade[] }) {
  const counts: Record<string, number> = {};
  for (const g of grades) if (g) counts[g] = (counts[g] || 0) + 1;
  const total = grades.filter(Boolean).length || 1;
  const order = ['5', '4', '3', '2', '0', 'absent'];
  return (
    <div className="flex h-2 rounded-full overflow-hidden gap-[2px]">
      {order.map(g => counts[g] ? (
        <motion.div
          key={g}
          layout
          className="h-full rounded-full"
          style={{ background: GRADE_META[g].c, boxShadow: `0 0 8px ${GRADE_META[g].c}55` }}
          initial={{ width: 0 }}
          animate={{ width: `${(counts[g] / total) * 100}%` }}
          transition={spring}
        />
      ) : null)}
    </div>
  );
}

/* ================= страница занятия ================= */

export default function Lesson({ id }: { id: number }) {
  const { st, cancelLesson, restoreLesson, removeLesson, toast } = useStore();
  const [confirm, setConfirm] = useState<null | 'cancel' | 'delete'>(null);

  const lesson = st.lessons.find(l => l.id === id);
  const subject = lesson ? st.subjects.find(s => s.id === lesson.subjectId) : null;
  const students = lesson ? studentsOfSubject(st, lesson.subjectId) : [];
  const grp = lesson ? groupOf(st, lesson.subjectId) : null;
  const marks = st.grades[id] || {};

  const adjacent = useMemo(() => {
    if (!lesson) return { prev: null, next: null };
    const all = lessonsOfSubject(st, lesson.subjectId);
    const i = all.findIndex(l => l.id === id);
    return { prev: all[i - 1] ?? null, next: all[i + 1] ?? null };
  }, [st, id, lesson]);

  const stat = useMemo(() => {
    const vals = Object.values(marks);
    const marked = vals.filter(Boolean).length;
    const avg = avgOfGrades(vals);
    const present = vals.filter(g => g && g !== 'absent').length;
    return { marked, avg, att: marked ? Math.round((present / marked) * 100) : 0 };
  }, [marks]);

  if (!lesson || !subject) {
    return (
      <div className="px-5 pt-10 text-center">
        <div className="text-white/50 text-sm">Занятие не найдено</div>
        <button onClick={() => nav('#home')} className="mt-4 px-5 py-2.5 rounded-xl hairline text-[13px] font-bold">На главную</button>
      </div>
    );
  }

  const cancelled = lesson.status === 'cancelled';

  return (
    <div className="px-4 pt-2 pb-40">
      {/* шапка со смежными занятиями */}
      <div className="flex items-center gap-1 mb-1">
        <button
          disabled={!adjacent.prev}
          onClick={() => adjacent.prev && nav(`#lesson/${adjacent.prev.id}`)}
          className="w-9 h-9 grid place-items-center rounded-full hairline text-white/60 disabled:opacity-20 active:scale-90 transition shrink-0"
        >
          <ChevronLeft size={17} />
        </button>
        <div className="flex-1 min-w-0 text-center">
          <h1 className="font-display text-[14.5px] font-bold truncate tracking-tight">{subject.name}</h1>
          <div className="text-[10.5px] text-white/40 font-semibold mt-0.5 truncate">
            {fmtDate(lesson.date)} · {grp?.name} · {lesson.num} пара {cancelled && '· отменено'}
          </div>
        </div>
        <button
          disabled={!adjacent.next}
          onClick={() => adjacent.next && nav(`#lesson/${adjacent.next.id}`)}
          className="w-9 h-9 grid place-items-center rounded-full hairline text-white/60 disabled:opacity-20 active:scale-90 transition shrink-0"
        >
          <ChevronRight size={17} />
        </button>
      </div>

      {cancelled ? (
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="glass rounded-[22px] p-6 card-inset text-center mt-6">
          <div className="w-12 h-12 mx-auto rounded-2xl grid place-items-center mb-3" style={{ background: 'rgba(242,98,122,.12)', color: '#f2627a' }}>
            <Ban size={20} />
          </div>
          <div className="font-display text-[15px] font-bold">Занятие отменено</div>
          <div className="text-[12px] text-white/40 mt-1.5 leading-relaxed">Студенты группы {grp?.name} получили пуш в MAX об отмене</div>
          <button
            onClick={() => { restoreLesson(id); toast({ title: 'Занятие восстановлено', tone: 'ok' }); }}
            className="mt-4 px-5 py-3 rounded-2xl text-[13px] font-bold hairline bg-white/[.05] active:scale-95 transition inline-flex items-center gap-2"
          >
            <Undo2 size={14} /> Восстановить
          </button>
        </motion.div>
      ) : (
        <>
          {/* живые статы */}
          <motion.div layout className="glass rounded-[22px] p-4 card-inset mt-2">
            <div className="grid grid-cols-3 gap-2 text-center">
              <div>
                <div className="font-display text-[19px] font-bold" style={{ color: stat.avg != null ? (stat.avg >= 4 ? '#3ddc97' : stat.avg >= 3 ? '#f5b93f' : '#f2627a') : 'rgba(255,255,255,.3)' }}>
                  {stat.avg != null ? <CountUp value={Math.round(stat.avg * 10) / 10} decimals={1} /> : '—'}
                </div>
                <div className="text-[9.5px] font-bold uppercase tracking-wider text-white/35 mt-0.5">ср. балл</div>
              </div>
              <div>
                <div className="font-display text-[19px] font-bold text-white/90">
                  <CountUp value={stat.marked} /><span className="text-white/30 text-[13px]">/{students.length}</span>
                </div>
                <div className="text-[9.5px] font-bold uppercase tracking-wider text-white/35 mt-0.5">отмечено</div>
              </div>
              <div>
                <div className="font-display text-[19px] font-bold text-cyn"><CountUp value={stat.att} /><span className="text-[12px]">%</span></div>
                <div className="text-[9.5px] font-bold uppercase tracking-wider text-white/35 mt-0.5">посещаем.</div>
              </div>
            </div>
            <div className="mt-3.5"><Distribution grades={Object.values(marks)} /></div>
          </motion.div>

          {/* подсказка */}
          <div className="flex items-center justify-center gap-2 mt-3 mb-2.5 text-[10px] text-white/30 font-semibold">
            <MousePointerClick size={11} />
            тап слева — назад · тап справа — вперёд
            <ArrowLeftRight size={11} />
          </div>

          {/* 2-колоночная сетка */}
          <motion.div layout className="grid grid-cols-2 gap-1.5">
            {students.map((s) => (
              <StudentTile key={s.id} lessonId={id} student={s} grade={marks[s.id] ?? null} />
            ))}
          </motion.div>

          {/* действия */}
          <div className="flex gap-1.5 mt-3">
            {[
              { icon: CopyCheck, label: 'Замена', hue: '#f5b93f', fn: () => toast({ title: 'Замена предмета', sub: 'в демо занятие остаётся без изменений', tone: 'info' }) },
              { icon: Ban, label: 'Отмена', hue: '#f2627a', fn: () => setConfirm('cancel') },
              { icon: Trash2, label: 'Удалить', hue: '#f2627a', fn: () => setConfirm('delete') },
              { icon: BookOpen, label: 'Журнал', hue: '#3ddc97', fn: () => nav(`#subject/${subject.id}`) },
            ].map(a => (
              <motion.button
                key={a.label}
                whileTap={{ scale: 0.92 }}
                onClick={a.fn}
                className="flex-1 rounded-2xl py-3 flex flex-col items-center gap-1.5 hairline bg-white/[.03]"
              >
                <a.icon size={15} style={{ color: a.hue }} />
                <span className="text-[9.5px] font-bold text-white/50">{a.label}</span>
              </motion.button>
            ))}
          </div>
        </>
      )}

      {/* подтверждения */}
      <Sheet open={confirm === 'cancel'} onClose={() => setConfirm(null)} title="Отменить занятие?">
        <div className="text-[12.5px] text-white/50 leading-relaxed mb-5">
          Оценки ({stat.marked}) сохранятся в базе, но занятие будет помечено отменённым.
          Студенты получат пуш-уведомление в MAX.
        </div>
        <div className="flex gap-2">
          <button onClick={() => setConfirm(null)} className="flex-1 py-3.5 rounded-2xl hairline bg-white/[.04] text-[13px] font-bold active:scale-95 transition">Назад</button>
          <button
            onClick={() => { cancelLesson(id); setConfirm(null); toast({ title: 'Занятие отменено', sub: `пуш группе ${grp?.name} отправлен`, tone: 'warn' }); }}
            className="flex-1 py-3.5 rounded-2xl text-[13px] font-bold text-white active:scale-95 transition"
            style={{ background: 'linear-gradient(150deg,#f2627a,#e0405f)', boxShadow: '0 10px 24px -10px rgba(242,98,122,.7)' }}
          >Отменить занятие</button>
        </div>
      </Sheet>

      <Sheet open={confirm === 'delete'} onClose={() => setConfirm(null)} title="Удалить безвозвратно?">
        <div className="text-[12.5px] text-white/50 leading-relaxed mb-5">
          Будет удалено занятие и {stat.marked} оценок. Действие нельзя отменить — в отличие от бэкапа lessons.db.
        </div>
        <div className="flex gap-2">
          <button onClick={() => setConfirm(null)} className="flex-1 py-3.5 rounded-2xl hairline bg-white/[.04] text-[13px] font-bold active:scale-95 transition">Назад</button>
          <button
            onClick={() => { removeLesson(id); setConfirm(null); toast({ title: 'Занятие удалено', tone: 'warn' }); nav(`#subject/${subject.id}`); }}
            className="flex-1 py-3.5 rounded-2xl text-[13px] font-bold text-white active:scale-95 transition"
            style={{ background: 'linear-gradient(150deg,#f2627a,#e0405f)', boxShadow: '0 10px 24px -10px rgba(242,98,122,.7)' }}
          >Удалить</button>
        </div>
      </Sheet>
    </div>
  );
}
