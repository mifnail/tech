/* Ведомость по паре «группа × предмет»: сетка студенты × даты,
   динамика среднего балла, распределение оценок, экспорт .xlsx. */

import { useMemo } from "react";
import { Download, Info } from "lucide-react";
import { useDB, useVersion, store } from "../lib/store";
import { formatDot, formatDotShort } from "../lib/date";
import { formatAvg, avgOf } from "../lib/grades";
import { downloadXlsx, type Cell } from "../lib/xlsx";
import { navigate } from "../lib/router";
import { BackHeader, Screen } from "../components/shell";
import { Btn, Card, Sparkline, GradeChip, useToast } from "../components/ui";
import { cn } from "../utils/cn";

export default function StatementScreen({ groupId, subjectId }: { groupId: number; subjectId: number }) {
  const db = useDB();
  const ver = useVersion();
  const toast = useToast();
  const group = store.group(groupId);
  const subject = store.subject(subjectId);

  const model = useMemo(() => {
    if (!group || !subject) return null;
    const lessons = store
      .lessonsOfPair(groupId, subjectId)
      .filter((l) => l.status === "held");
    const students = store.studentsOf(groupId);
    const rows = students.map((s) => {
      const cells = lessons.map((l) => {
        const rec = store.gradeOf(l.id, s.id);
        return rec ?? null;
      });
      const avg = avgOf(cells.filter((c) => c && c.present).map((c) => (c ? c.value : null)));
      return { s, cells, avg };
    });
    // Динамика среднего по занятиям (для спарклайна)
    const trend = lessons
      .map((l) => {
        const vals = store.gradesOfLesson(l.id).filter((r) => r.present).map((r) => r.value);
        return avgOf(vals);
      })
      .filter((v): v is number => v !== null);
    // Распределение 5/4/3/2
    const dist = { 5: 0, 4: 0, 3: 0, 2: 0 } as Record<number, number>;
    rows.forEach((r) =>
      r.cells.forEach((c) => {
        if (c && c.present && c.value !== null && c.value >= 2) dist[c.value]++;
      }),
    );
    const totalDist = dist[5] + dist[4] + dist[3] + dist[2];
    return { lessons, rows, trend, dist, totalDist };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [db, groupId, subjectId, group, subject, ver]);

  if (!group || !subject || !model) {
    return (
      <Screen>
        <BackHeader title="Ведомость недоступна" fallback="/groups" />
      </Screen>
    );
  }

  const exportXlsx = () => {
    const header: Cell[] = [
      "Студент",
      ...model.lessons.map((l) => formatDot(l.date)),
      "Средний балл",
    ];
    const body: Cell[][] = model.rows.map((r) => [
      r.s.name,
      ...r.cells.map((c): Cell => {
        if (!c) return "";
        if (!c.present) return "н";
        return c.value === null ? "" : c.value;
      }),
      r.avg === null ? "—" : Math.round(r.avg * 100) / 100,
    ]);
    const ok = downloadXlsx(
      `Ведомость_${group.name}_${subject.name.replace(/[\\/:*?"<>|]/g, "_")}.xlsx`,
      `${group.name} · ${subject.name}`.slice(0, 31),
      [header, ...body],
    );
    toast(ok ? "Ведомость сохранена (.xlsx)" : "Не удалось сохранить файл");
  };

  return (
    <Screen className="pb-28">
      <BackHeader
        title={subject.name}
        sub={`${group.name} · ведомость`}
        fallback={"/group/" + groupId}
        actions={
          <Btn size="sm" variant="muted" icon={Download} onClick={exportXlsx}>
            .xlsx
          </Btn>
        }
      />

      {model.lessons.length === 0 && (
        <Card className="p-5 text-center text-[13.5px] text-muted">
          Проведённых занятий пока нет — ведомость появится после первого занятия.
        </Card>
      )}

      {model.lessons.length > 0 && (
        <>
          <Card className="p-4 mb-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-[11px] font-bold uppercase tracking-[0.08em] text-muted">
                  Динамика ср. балла
                </div>
                <div className="mt-1 text-[24px] font-extrabold tabular-nums leading-none">
                  {formatAvg(model.trend.length ? model.trend[model.trend.length - 1] : null)}
                </div>
              </div>
              <Sparkline points={model.trend.slice(-14)} width={128} height={38} />
            </div>
            <div className="mt-4 flex flex-col gap-1.5">
              {[5, 4, 3, 2].map((v) => {
                const n = model.dist[v];
                const pct = model.totalDist ? Math.round((n / model.totalDist) * 100) : 0;
                return (
                  <div key={v} className="flex items-center gap-2.5">
                    <GradeChip value={v} present size="sm" className="shrink-0" />
                    <div className="flex-1 h-[10px] rounded-full bg-surface2 overflow-hidden">
                      <div
                        className={cn(
                          "h-full rounded-full",
                          v === 5 ? "bg-g5" : v === 4 ? "bg-g4" : v === 3 ? "bg-g3" : "bg-g2",
                        )}
                        style={{ width: pct + "%" }}
                      />
                    </div>
                    <span className="w-10 text-right text-[11.5px] font-bold tabular-nums text-muted">
                      {n}
                    </span>
                  </div>
                );
              })}
            </div>
          </Card>

          <Card className="overflow-hidden mb-3">
            <div className="overflow-x-auto no-scrollbar">
              <table className="border-collapse text-[12px]">
                <thead>
                  <tr className="bg-surface2">
                    <th className="sticky left-0 z-10 bg-surface2 text-left font-bold uppercase
                      tracking-[0.06em] text-[10px] text-muted px-3 py-2.5 min-w-[132px] max-w-[132px]">
                      Студент
                    </th>
                    {model.lessons.map((l) => (
                      <th key={l.id} className="px-1 py-1.5 font-bold text-muted">
                        <button
                          onClick={() => navigate("/lesson/" + l.id)}
                          className="pressable px-1.5 py-1 rounded-md tabular-nums hover:text-accent"
                        >
                          {formatDotShort(l.date)}
                          {l.lessonNumber > 0 && (
                            <span className="block text-[9px] font-bold uppercase tracking-wide text-faint">
                              №{l.lessonNumber}
                            </span>
                          )}
                        </button>
                      </th>
                    ))}
                    <th className="px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-[0.06em] text-muted">
                      Ср.
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {model.rows.map((r, ri) => (
                    <tr key={r.s.id} className={ri % 2 ? "bg-surface" : "bg-surface2"}>
                      <td className={cn(
                        "sticky left-0 z-10 px-3 py-1.5 font-semibold truncate min-w-[132px] max-w-[132px] border-t border-line",
                        ri % 2 ? "bg-surface" : "bg-surface2",
                      )}>
                        {r.s.name}
                      </td>
                      {r.cells.map((c, ci) => (
                        <td key={ci} className="px-0.5 py-1.5 text-center border-t border-line">
                          {c === null || (c.present && c.value === null) ? (
                            <span className="text-faint">·</span>
                          ) : (
                            <GradeChip value={c.value} present={c.present} size="sm" />
                          )}
                        </td>
                      ))}
                      <td className="px-2.5 py-1.5 text-center font-extrabold tabular-nums border-t border-line">
                        <span className={cn(
                          r.avg === null ? "text-faint" : r.avg >= 4 ? "text-g5" : r.avg >= 3.5 ? "text-g3" : "text-g2",
                        )}>
                          {formatAvg(r.avg)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <div className="flex items-start gap-2 px-1 text-[11.5px] text-muted leading-snug">
            <Info size={13} className="shrink-0 mt-[1px] text-faint" />
            Нажмите на дату в шапке, чтобы открыть занятие и изменить оценки.
            Кнопка «.xlsx» сохраняет ведомость в файл Excel.
          </div>
        </>
      )}
    </Screen>
  );
}
