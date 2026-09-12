/* Экран «Группы»: поиск, список групп, создание. */

import { useMemo, useState } from "react";
import { ChevronRight, Plus, Search, UsersRound } from "lucide-react";
import { useDB, useVersion, store } from "../lib/store";
import { avgOf, formatAvg } from "../lib/grades";
import { navigate } from "../lib/router";
import { BigHeader, Screen, AvatarTile } from "../components/shell";
import { Btn, Card, Chip, EmptyState, Field, IconBtn, Input, Sheet, useToast } from "../components/ui";

export default function GroupsScreen() {
  const db = useDB();
  const ver = useVersion();
  const toast = useToast();
  const [query, setQuery] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [name, setName] = useState("");

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = db.groups.filter((g) => {
      if (!q) return true;
      if (g.name.toLowerCase().includes(q)) return true;
      return db.students.some((s) => s.groupId === g.id && s.name.toLowerCase().includes(q));
    });
    return list.map((g) => {
      const students = db.students.filter((s) => s.groupId === g.id);
      const values = db.grades
        .filter((r) => students.some((s) => s.id === r.studentId) && r.present)
        .map((r) => r.value);
      return { g, students, avg: avgOf(values) };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [db, query, ver]);

  const create = () => {
    if (!name.trim()) return;
    const g = store.addGroup(name);
    setName("");
    setAddOpen(false);
    toast("Группа «" + g.name + "» создана");
    navigate("/group/" + g.id);
  };

  return (
    <Screen className="pb-28">
      <BigHeader
        kicker="Журнал"
        title="Группы"
        actions={<IconBtn icon={Plus} label="Новая группа" onClick={() => setAddOpen(true)} className="bg-surface border border-line" />}
      />

      <div className="relative mb-3">
        <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-faint" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Группа или фамилия студента"
          className="pl-10 bg-surface"
        />
      </div>

      {groups.length === 0 && (
        <Card>
          <EmptyState
            icon={UsersRound}
            title={query ? "Ничего не найдено" : "Пока нет групп"}
            hint={query ? "Попробуйте изменить запрос." : "Создайте первую группу и добавьте студентов."}
          >
            {!query && <Btn icon={Plus} onClick={() => setAddOpen(true)}>Новая группа</Btn>}
          </EmptyState>
        </Card>
      )}

      {groups.map(({ g, students, avg }) => (
        <Card
          key={g.id}
          className="p-3.5 mb-2 flex items-center gap-3"
          onClick={() => navigate("/group/" + g.id)}
        >
          <AvatarTile text={g.name.slice(0, 2)} />
          <div className="min-w-0 flex-1">
            <div className="text-[15px] font-bold">{g.name}</div>
            <div className="text-[12px] text-muted">
              {students.length} студентов · {g.subjectIds.length} предмета
            </div>
          </div>
          {avg !== null && <Chip tone={avg >= 4 ? "success" : avg >= 3.5 ? "warn" : "danger"}>{formatAvg(avg)}</Chip>}
          <ChevronRight size={16} className="text-faint shrink-0" />
        </Card>
      ))}

      <Sheet open={addOpen} onClose={() => setAddOpen(false)} title="Новая группа">
        <Field label="Название группы">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Например, ИС-24"
            autoFocus
            onKeyDown={(e) => e.key === "Enter" && create()}
          />
        </Field>
        <Btn size="lg" className="w-full mt-4" onClick={create} disabled={!name.trim()}>
          Создать группу
        </Btn>
      </Sheet>
    </Screen>
  );
}
