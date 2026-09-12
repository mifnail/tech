/* Карточка группы: метрики, предметы, студенты, код куратора, удаление. */

import { useMemo, useState } from "react";
import {
  BookOpen, ChevronRight, Copy, Plus, Send, MessageCircle, Trash2, Unlink, UserPlus, X,
} from "lucide-react";
import { useDB, useVersion, store } from "../lib/store";
import { avgOf, formatAvg, isDebtor } from "../lib/grades";
import { navigate } from "../lib/router";
import { BackHeader, Screen } from "../components/shell";
import {
  Btn, Card, Chip, ConfirmSheet, Field, IconBtn, Input, SectionTitle,
  Select, Sheet, useToast,
} from "../components/ui";
import { cn } from "../utils/cn";

function copyText(text: string): boolean {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text);
      return true;
    }
  } catch (_) {}
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
    return true;
  } catch (_) {
    return false;
  }
}

export default function GroupDetailScreen({ id }: { id: number }) {
  const db = useDB();
  const ver = useVersion();
  const toast = useToast();
  const group = store.group(id);

  const [addStudentOpen, setAddStudentOpen] = useState(false);
  const [studentName, setStudentName] = useState("");
  const [addSubjectOpen, setAddSubjectOpen] = useState(false);
  const [subjectPick, setSubjectPick] = useState("");
  const [subjectNew, setSubjectNew] = useState("");
  const [subjectHours, setSubjectHours] = useState("");
  const [removeStudentId, setRemoveStudentId] = useState<number | null>(null);
  const [removeGroupOpen, setRemoveGroupOpen] = useState(false);
  const [curatorUnbindOpen, setCuratorUnbindOpen] = useState(false);
  const [unbindStudent, setUnbindStudent] = useState<{ id: number; kind: "tg" | "max" } | null>(null);
  const [filter, setFilter] = useState("");

  const unbindCurator = async () => {
    if (!group) return;
    try {
      await store.unbindCurator(group.id);
      toast("Куратор отвязан");
    } catch (_) {
      toast("Ошибка");
    }
  };

  const unbindStudentBot = async () => {
    if (!unbindStudent) return;
    try {
      await store.unbindStudentBot(unbindStudent.id, unbindStudent.kind);
      toast(unbindStudent.kind === "tg" ? "Чат Telegram отвязан" : "Чат MAX отвязан");
    } catch (_) {
      toast("Ошибка");
    }
  };

  const students = useMemo(
    () => (group ? store.studentsOf(group.id) : []),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [db, group, ver],
  );

  const data = useMemo(() => {
    if (!group) return null;
    // Средние считаем только по проведённым занятиям (паритет с сервером).
    const heldIds = new Set(db.lessons.filter((l) => l.status === "held").map((l) => l.id));
    const studentIds = new Set(students.map((s) => s.id));
    const perStudent = students.map((s) => {
      const recs = store.gradesOfStudent(s.id);
      // Должник — по всем отмеченным оценкам (правило не трогаем).
      const allVals = recs.filter((r) => r.present).map((r) => r.value);
      const heldVals = recs.filter((r) => r.present && heldIds.has(r.lessonId)).map((r) => r.value);
      return { s, avg: avgOf(heldVals), debtor: isDebtor(allVals) };
    });
    // Общий средний группы = mean ВСЕХ числовых записей (не mean-of-means).
    const allAvg = avgOf(
      db.grades
        .filter((g) => heldIds.has(g.lessonId) && g.present && studentIds.has(g.studentId))
        .map((g) => g.value),
    );
    const debtors = perStudent.filter((p) => p.debtor).length;
    const subjects = group.subjectIds
      .map((sid) => {
        const subj = store.subject(sid);
        if (!subj) return null;
        const lessons = store.lessonsOfPair(group.id, sid).filter((l) => l.status === "held");
        const vals = lessons.flatMap((l) =>
          store.gradesOfLesson(l.id).filter((r) => r.present).map((r) => r.value),
        );
        return { subj, count: lessons.length, avg: avgOf(vals) };
      })
      .filter((x): x is NonNullable<typeof x> => x !== null);
    return { perStudent, allAvg, debtors, subjects };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [db, group, students, ver]);

  if (!group || !data) {
    return (
      <Screen>
        <BackHeader title="Группа не найдена" fallback="/groups" />
      </Screen>
    );
  }

  const filtered = data.perStudent.filter((p) =>
    p.s.name.toLowerCase().includes(filter.trim().toLowerCase()),
  );

  const addStudent = () => {
    if (!studentName.trim()) return;
    store.addStudent(group.id, studentName);
    setStudentName("");
    setAddStudentOpen(false);
    toast("Студент добавлен");
  };

  const assignSubject = () => {
    let sid = subjectPick ? Number(subjectPick) : null;
    if (!sid && subjectNew.trim()) {
      sid = store.addSubject(subjectNew, group.id, Number(subjectHours) || 0).id;
    }
    if (!sid) return;
    store.assignSubject(group.id, sid);
    setSubjectPick("");
    setSubjectNew("");
    setSubjectHours("");
    setAddSubjectOpen(false);
    toast("Предмет добавлен группе");
  };

  const lessonCount = db.lessons.filter((l) => l.groupId === group.id).length;

  return (
    <Screen className="pb-28">
      <BackHeader title={group.name} sub="Группа" fallback="/groups" />

      <Card className="grid grid-cols-3 divide-x divide-line mb-1">
        {[
          { label: "Студентов", value: String(students.length) },
          { label: "Ср. балл", value: formatAvg(data.allAvg) },
          {
            label: "Должники",
            value: String(data.debtors),
            cls: data.debtors > 0 ? "text-g2" : "",
          },
        ].map((s) => (
          <div key={s.label} className="px-3 py-3 text-center">
            <div className={cn("text-[20px] font-extrabold tabular-nums leading-none", s.cls)}>
              {s.value}
            </div>
            <div className="mt-1 text-[10px] font-bold uppercase tracking-[0.07em] text-muted">
              {s.label}
            </div>
          </div>
        ))}
      </Card>

      <SectionTitle>Предметы</SectionTitle>

      {data.subjects.length === 0 ? (
        <Card className="p-4 mb-2">
          <div className="text-[13px] text-muted text-center mb-3">
            Пока нет предметов — добавьте, чтобы вести ведомость.
          </div>
          <Btn size="md" variant="muted" icon={Plus} className="w-full" onClick={() => setAddSubjectOpen(true)}>
            Добавить предмет
          </Btn>
        </Card>
      ) : (
        <Btn size="md" variant="muted" icon={Plus} className="w-full mb-2" onClick={() => setAddSubjectOpen(true)}>
          Добавить предмет
        </Btn>
      )}
      {data.subjects.map(({ subj, count, avg }) => (
        <Card
          key={subj.id}
          className="p-3.5 mb-2 flex items-center gap-3"
          onClick={() => navigate(`/statement/${group.id}/${subj.id}`)}
        >
          <div className="w-9 h-9 rounded-xl bg-accentbg grid place-items-center shrink-0">
            <BookOpen size={16} className="text-accent" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-[14.5px] font-bold truncate">{subj.name}</div>
            <div className="text-[12px] text-muted">
              {count} проведённых занятий · открыть ведомость
            </div>
          </div>
          {avg !== null && (
            <Chip tone={avg >= 4 ? "success" : avg >= 3.5 ? "warn" : "danger"}>
              {formatAvg(avg)}
            </Chip>
          )}
          <ChevronRight size={16} className="text-faint shrink-0" />
        </Card>
      ))}

      <SectionTitle
        action={
          <Btn size="sm" variant="muted" icon={UserPlus} onClick={() => setAddStudentOpen(true)}>
            Студент
          </Btn>
        }
      >
        Студенты · {students.length}
      </SectionTitle>

      {students.length > 6 && (
        <Input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Фамилия или имя"
          className="mb-2 bg-surface"
        />
      )}

      <Card className="divide-y divide-line">
        {filtered.map(({ s, avg, debtor }) => (
          <div key={s.id} className="flex items-center gap-2.5 pl-4 pr-2 py-2.5">
            <div className="min-w-0 flex-1">
              <div className={cn("text-[14px] font-semibold truncate", debtor && "text-g2")}>
                {s.name}
              </div>
              <div className="flex items-center gap-1.5 mt-0.5">
                {s.tg && (
                  <button
                    onClick={() => setUnbindStudent({ id: s.id, kind: "tg" })}
                    className="pressable inline-flex items-center gap-1 px-1.5 h-[18px] rounded-md bg-surface2 border border-line text-[10px] font-bold text-faint"
                    title="Отвязать Telegram"
                  >
                    <Send size={10} /> TG
                  </button>
                )}
                {s.max && (
                  <button
                    onClick={() => setUnbindStudent({ id: s.id, kind: "max" })}
                    className="pressable inline-flex items-center gap-1 px-1.5 h-[18px] rounded-md bg-surface2 border border-line text-[10px] font-bold text-faint"
                    title="Отвязать MAX"
                  >
                    <MessageCircle size={10} /> MAX
                  </button>
                )}
                {(s.tg || s.max) && (
                  <span className="text-[10.5px] text-faint">бот привязан</span>
                )}
              </div>
            </div>
            {avg !== null && (
              <span
                className={cn(
                  "text-[13px] font-bold tabular-nums",
                  avg >= 4 ? "text-g5" : avg >= 3.5 ? "text-g3" : "text-g2",
                )}
              >
                {formatAvg(avg)}
              </span>
            )}
            <IconBtn
              icon={X}
              label={"Удалить " + s.name}
              onClick={() => setRemoveStudentId(s.id)}
              className="w-8 h-8 text-faint"
            />
          </div>
        ))}
        {filtered.length === 0 && (
          <div className="py-6 text-center text-[13px] text-muted">
            {filter ? "Не найдено" : "Список пуст"}
          </div>
        )}
      </Card>

      <SectionTitle>Куратор группы</SectionTitle>
      <Card className="p-4 flex items-center gap-3">
        <div className="flex-1 min-w-0">
          <div className="text-[22px] font-extrabold tracking-[0.18em] tabular-nums">
            {group.curatorCode}
          </div>
          <div className="mt-0.5 text-[12px] text-muted leading-snug">
            Код для MAX-бота: пуши оценок группы и ведомость по запросу.
            {group.curatorBound && <span className="text-g5"> · привязан</span>}
          </div>
        </div>
        <IconBtn
          icon={Copy}
          label="Скопировать код"
          className="bg-surface2 border border-line"
          onClick={() => copyText(group.curatorCode) && toast("Код куратора скопирован")}
        />
        {group.curatorBound && (
          <IconBtn
            icon={Unlink}
            label="Отвязать куратора"
            className="bg-surface2 border border-line"
            onClick={() => setCuratorUnbindOpen(true)}
          />
        )}
      </Card>

      <SectionTitle>Опасная зона</SectionTitle>
      <Btn
        variant="danger"
        icon={Trash2}
        className="w-full"
        onClick={() => setRemoveGroupOpen(true)}
      >
        Удалить группу
      </Btn>

      {/* Листы */}
      <Sheet open={addStudentOpen} onClose={() => setAddStudentOpen(false)} title="Новый студент">
        <Field label="Фамилия и имя">
          <Input
            value={studentName}
            onChange={(e) => setStudentName(e.target.value)}
            placeholder="Иванова Мария"
            autoFocus
            onKeyDown={(e) => e.key === "Enter" && addStudent()}
          />
        </Field>
        <Btn size="lg" className="w-full mt-4" onClick={addStudent} disabled={!studentName.trim()}>
          Добавить
        </Btn>
      </Sheet>

      <Sheet open={addSubjectOpen} onClose={() => setAddSubjectOpen(false)} title="Предмет группы">
        <div className="flex flex-col gap-4">
          <Field label="Из существующих">
            <Select value={subjectPick} onChange={(e) => { setSubjectPick(e.target.value); setSubjectNew(""); }}>
              <option value="">— не выбрано —</option>
              {db.subjects
                .filter((s) => !group.subjectIds.includes(s.id))
                .map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
            </Select>
          </Field>
          <div className="h-px bg-line" />
          <Field label="Новый предмет — название">
            <Input
              value={subjectNew}
              onChange={(e) => { setSubjectNew(e.target.value); setSubjectPick(""); }}
              placeholder="Например, Компьютерные сети"
            />
          </Field>
          <Field label="Часов (всего)">
            <Input
              type="number"
              inputMode="numeric"
              min={1}
              value={subjectHours}
              onChange={(e) => { setSubjectHours(e.target.value); setSubjectPick(""); }}
              placeholder="Например, 72"
            />
          </Field>
          <Btn size="lg" onClick={assignSubject} disabled={!subjectPick && !subjectNew.trim()}>
            Добавить
          </Btn>
        </div>
      </Sheet>

      <ConfirmSheet
        open={removeStudentId !== null}
        onClose={() => setRemoveStudentId(null)}
        title="Удалить студента?"
        body="Оценки и посещаемость студента будут удалены из всех ведомостей безвозвратно."
        confirmLabel="Удалить"
        danger
        onConfirm={() => {
          if (removeStudentId !== null) store.removeStudent(removeStudentId);
          toast("Студент удалён");
        }}
      />

      <ConfirmSheet
        open={removeGroupOpen}
        onClose={() => setRemoveGroupOpen(false)}
        title={`Удалить «${group.name}»?`}
        body={`Будут удалены: ${students.length} студентов, ${lessonCount} занятий и все оценки. Действие необратимо.`}
        confirmLabel="Удалить группу"
        danger
        onConfirm={() => {
          store.removeGroup(group.id);
          navigate("/groups");
          toast("Группа удалена");
        }}
      />

      <ConfirmSheet
        open={curatorUnbindOpen}
        onClose={() => setCuratorUnbindOpen(false)}
        title="Отвязать куратора?"
        body="Куратор перестанет получать пуши об оценках группы. Код группы сохранится."
        confirmLabel="Отвязать"
        danger
        onConfirm={unbindCurator}
      />

      <ConfirmSheet
        open={unbindStudent !== null}
        onClose={() => setUnbindStudent(null)}
        title={unbindStudent?.kind === "tg" ? "Отвязать Telegram?" : "Отвязать MAX?"}
        body="Студент перестанет получать уведомления об оценках через этого бота."
        confirmLabel="Отвязать"
        danger
        onConfirm={unbindStudentBot}
      />
    </Screen>
  );
}
