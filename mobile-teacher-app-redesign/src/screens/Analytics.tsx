/* Аналитика (read-only): агрегация на клиенте из журнала.
   Порт ванильного App.Pages.analytics: посещаемость/среднее/динамика,
   тепловая полоса 14 дней, по предметам, лидеры top-3 и зона риска. */

import { useMemo } from "react";
import { AlertTriangle, BarChart3, Check } from "lucide-react";
import { useDB, useVersion } from "../lib/store";
import { addDaysISO, todayISO } from "../lib/date";
import { avgOf, formatAvg } from "../lib/grades";
import { BigHeader, Screen } from "../components/shell";
import { Card, EmptyState, SectionTitle, Sparkline } from "../components/ui";
import { cn } from "../utils/cn";

export default function AnalyticsScreen() {
  const db = useDB();
  const ver = useVersion();

  const model = useMemo(() => {
    // Все проведённые занятия + их оценки
    const heldLessons = db.lessons.filter((l) => l.status === "held");
    const heldIds = new Set(heldLessons.map((l) => l.id));
    const allGrades = db.grades.filter((g) => heldIds.has(g.lessonId));

    // Средний балл по всем оценкам (2–5)
    const allVals = allGrades.filter((g) => g.present && g.value !== null).map((g) => g.value);
    const avg = avgOf(allVals);

    // Посещаемость: present / все отмеченные (present или absent)
    const marked = allGrades.length;
    const present = allGrades.filter((g) => g.present).length;
    const att = marked ? Math.round((present / marked) * 100) : 0;

    // Динамика среднего по занятиям (только с оценками)
    const series: number[] = [];
    for (const l of heldLessons) {
      const vals = db.grades
        .filter((g) => g.lessonId === l.id && g.present && g.value !== null)
        .map((g) => g.value);
      const la = avgOf(vals);
      if (vals.length > 0 && la != null) series.push(la);
    }
    const last3 = series.slice(-3);
    const delta = last3.length >= 2 ? last3[last3.length - 1] - last3[0] : 0;

    // Тепловая полоса активности за 14 дней (оценок в день)
    const byDay = new Map<string, number>();
    for (const l of heldLessons) {
      const n = db.grades.filter((g) => g.lessonId === l.id && g.present).length;
      if (n > 0) byDay.set(l.date, (byDay.get(l.date) ?? 0) + n);
    }
    let maxDay = 1;
    for (const v of byDay.values()) if (v > maxDay) maxDay = v;
    const today = todayISO();
    const days = Array.from({ length: 14 }, (_, i) => {
      const iso = addDaysISO(today, i - 13);
      return { iso, v: (byDay.get(iso) ?? 0) / maxDay };
    });

    // Доски: лидеры top-3 и зона риска (avg < 3.4 или abs ≥ 3) — та же математика, что в ванилле.
    const stMap = new Map<number, { id: number; name: string; avgSum: number; avgCnt: number; abs: number }>();
    for (const st of db.students) {
      stMap.set(st.id, { id: st.id, name: st.name, avgSum: 0, avgCnt: 0, abs: 0 });
    }
    for (const g of allGrades) {
      const e = stMap.get(g.studentId);
      if (!e) continue;
      if (!g.present) e.abs++;
      else if (g.value !== null && g.value >= 2) {
        e.avgSum += g.value;
        e.avgCnt++;
      }
    }
    const board = [...stMap.values()]
      .filter((b) => b.avgCnt > 0)
      .map((b) => ({ id: b.id, name: b.name, avg: b.avgSum / b.avgCnt, abs: b.abs }));
    const top = board.slice().sort((a, b) => b.avg - a.avg).slice(0, 3);
    const risk = board.filter((b) => b.avg < 3.4 || b.abs >= 3).sort((a, b) => a.avg - b.avg).slice(0, 3);

    // По предметам: средний балл, занятий, студентов
    const perSubject = db.subjects.map((s) => {
      const lessons = heldLessons.filter((l) => l.subjectId === s.id);
      const vals = lessons.flatMap((l) =>
        db.grades.filter((g) => g.lessonId === l.id && g.present && g.value !== null).map((g) => g.value),
      );
      const sAvg = avgOf(vals);
      const students = new Set(
        lessons.flatMap((l) => db.grades.filter((g) => g.lessonId === l.id).map((g) => g.studentId)),
      );
      return { subj: s, count: lessons.length, avg: sAvg, students: students.size };
    });

    return { avg, att, marked, series, delta, days, top, risk, perSubject };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [db, ver]);

  const { avg, att, marked, series, delta, days, top, risk, perSubject } = model;
  const up = delta >= 0;
  const avgColor = avg == null ? "text-faint" : avg >= 4 ? "text-g5" : avg >= 3 ? "text-g3" : "text-g2";

  // Кольцо посещаемости
  const ringSize = 92, ringStroke = 8;
  const ringR = (ringSize - ringStroke) / 2;
  const ringC = 2 * Math.PI * ringR;
  const ringOff = ringC * (1 - Math.min(100, Math.max(0, att)) / 100);

  return (
    <Screen className="pb-28">
      <BigHeader kicker="Read-only · из журнала" title="Аналитика" />

      {db.subjects.length === 0 && (
        <Card>
          <EmptyState
            icon={BarChart3}
            title="Пока нет данных для аналитики"
            hint="Создайте предмет и проведите первое занятие."
          />
        </Card>
      )}

      {db.subjects.length > 0 && (
        <>
          {/* Hero: кольцо посещаемости + средний балл + динамика */}
          <Card className="p-4 mb-3">
            <div className="flex items-center gap-3.5">
              <div className="relative shrink-0" style={{ width: ringSize, height: ringSize }}>
                <svg width={ringSize} height={ringSize} viewBox={`0 0 ${ringSize} ${ringSize}`}>
                  <circle cx={ringSize / 2} cy={ringSize / 2} r={ringR} fill="none"
                    stroke="var(--surface2)" strokeWidth={ringStroke} />
                  <circle cx={ringSize / 2} cy={ringSize / 2} r={ringR} fill="none"
                    stroke="var(--g5)" strokeWidth={ringStroke} strokeLinecap="round"
                    strokeDasharray={ringC.toFixed(1)} strokeDashoffset={ringOff.toFixed(1)}
                    transform={`rotate(-90 ${ringSize / 2} ${ringSize / 2})`} />
                </svg>
                <div className="absolute inset-0 grid place-items-center text-center leading-tight">
                  <div>
                    <div className="text-[19px] font-extrabold tabular-nums">{att}%</div>
                    <div className="text-[8px] font-extrabold uppercase tracking-[0.06em] text-faint">посещ.</div>
                  </div>
                </div>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline gap-2">
                  <span className={cn("text-[34px] font-extrabold leading-none tabular-nums", avgColor)}>
                    {formatAvg(avg)}
                  </span>
                  <span className={cn("text-[12px] font-bold", up ? "text-g5" : "text-g2")}>
                    {up ? "▲" : "▼"} {Math.abs(Math.round(delta * 100) / 100).toString().replace(".", ",")}
                  </span>
                </div>
                <div className="mt-1 text-[12px] text-muted">средний балл по всем предметам</div>
                <div className="text-[12px] text-muted">
                  <span className="font-bold text-ink tabular-nums">{marked}</span> оценок за период
                </div>
              </div>
            </div>
            <div className="mt-3 mb-1.5 text-[10px] font-extrabold uppercase tracking-[0.06em] text-muted">
              динамика среднего балла
            </div>
            <Sparkline points={series} width={400} height={40} className="w-full" />
          </Card>

          {/* Тепловая полоса 14 дней */}
          <Card className="p-4 mb-3">
            <div className="flex items-center gap-2 mb-3">
              <BarChart3 size={15} className="text-faint" />
              <span className="text-[11px] font-extrabold uppercase tracking-[0.06em] text-muted">
                активность · 14 дней
              </span>
            </div>
            <div className="flex gap-1">
              {days.map((d) => (
                <div
                  key={d.iso}
                  title={d.iso}
                  className="flex-1 h-8 rounded-md"
                  style={{
                    background: d.v > 0
                      ? `linear-gradient(180deg, color-mix(in srgb, var(--g3) ${Math.round(25 + d.v * 65)}%, transparent), color-mix(in srgb, var(--g3) ${Math.round(10 + d.v * 25)}%, transparent))`
                      : "var(--surface2)",
                  }}
                />
              ))}
            </div>
            <div className="flex justify-between mt-1.5 text-[10px] text-faint tabular-nums">
              <span>-14д</span><span>сегодня</span>
            </div>
          </Card>

          {/* По предметам */}
          <SectionTitle>По предметам</SectionTitle>
          {perSubject.map(({ subj, count, avg: sAvg, students: sCount }) => (
            <Card key={subj.id} className="p-3.5 mb-2">
              <div className="flex items-center justify-between gap-3">
                <div className="text-[14px] font-bold truncate">{subj.name}</div>
                <div className="text-[13px] font-extrabold tabular-nums text-accent">{formatAvg(sAvg)}</div>
              </div>
              <div className="mt-2 h-[10px] rounded-full bg-surface2 overflow-hidden">
                <div
                  className="h-full rounded-full bg-accent"
                  style={{ width: (sAvg != null ? (sAvg / 5) * 100 : 0) + "%" }}
                />
              </div>
              <div className="flex justify-between mt-1.5 text-[11px] text-faint">
                <span>{count} занятий</span>
                <span>{sCount} студентов</span>
              </div>
            </Card>
          ))}

          {/* Тренды по студентам: лидеры и зона риска */}
          <SectionTitle>Тренды по студентам</SectionTitle>
          <div className="grid grid-cols-2 gap-2">
            <Card className="p-3.5">
              <div className="flex items-center gap-1.5 mb-2.5 text-g5">
                <Check size={14} strokeWidth={2.5} />
                <span className="text-[11px] font-extrabold uppercase tracking-[0.06em]">Лидеры</span>
              </div>
              {top.length === 0 && <div className="text-[12px] text-faint py-2">нет данных</div>}
              {top.map((t, i) => (
                <div key={t.id} className="flex items-center gap-2 py-1.5">
                  <span className="w-3 text-[11px] font-bold tabular-nums text-faint">{i + 1}</span>
                  <span className="flex-1 min-w-0 text-[12px] font-semibold truncate">{t.name}</span>
                  <span className="text-[12px] font-extrabold tabular-nums text-g5">{formatAvg(t.avg)}</span>
                </div>
              ))}
            </Card>
            <Card className="p-3.5">
              <div className="flex items-center gap-1.5 mb-2.5 text-g2">
                <AlertTriangle size={14} strokeWidth={2.5} />
                <span className="text-[11px] font-extrabold uppercase tracking-[0.06em]">Зона риска</span>
              </div>
              {risk.length === 0 && <div className="text-[12px] text-faint py-2">все в порядке</div>}
              {risk.map((r) => (
                <div key={r.id} className="flex items-center gap-2 py-1.5">
                  <span className="flex-1 min-w-0 text-[12px] font-semibold truncate">{r.name}</span>
                  <span className="text-[10px] font-bold tabular-nums text-faint">{r.abs}пр</span>
                  <span className="text-[12px] font-extrabold tabular-nums text-g2">{formatAvg(r.avg)}</span>
                </div>
              ))}
            </Card>
          </div>
        </>
      )}
    </Screen>
  );
}