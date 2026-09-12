/* «Ещё»: профиль, тема, боты (Telegram / MAX), код преподавателя,
   бэкап/восстановление, информация о сборке, сброс демо. */

import { useRef, useState } from "react";
import {
  Bot, Check, Code2, Coffee, Copy, DatabaseBackup, Moon, RefreshCw,
  Send, Sun, Trash2, Upload,
} from "lucide-react";
import { useDB, store } from "../lib/store";
import { BigHeader, Screen } from "../components/shell";
import {
  Btn, Card, Chip, ConfirmSheet, Field, IconBtn, Input,
  SectionTitle, Segmented, useToast,
} from "../components/ui";

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
    ta.style.cssText = "position:fixed;opacity:0";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
    return true;
  } catch (_) { return false; }
}

export default function SettingsScreen() {
  const db = useDB();
  const toast = useToast();
  const s = db.settings;

  const [nameDraft, setNameDraft] = useState<string | null>(null);
  const [tgDraft, setTgDraft] = useState<string | null>(null);
  const [maxDraft, setMaxDraft] = useState<string | null>(null);
  const [resetOpen, setResetOpen] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const downloadBackup = () => {
    try {
      const blob = new Blob([store.exportBackup()], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "lessons-backup.json";
      document.body.appendChild(a);
      a.click();
      setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 1200);
      toast("Бэкап сохранён");
    } catch (_) {
      toast("Не удалось сохранить бэкап");
    }
  };

  const restore = (file: File | null) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const ok = store.importBackup(String(reader.result || ""));
      toast(ok ? "Данные восстановлены" : "Файл повреждён или не является бэкапом");
    };
    reader.readAsText(file);
  };

  return (
    <Screen className="pb-28">
      <BigHeader kicker="Приложение" title="Ещё" />

      <SectionTitle className="mt-1">Внешний вид</SectionTitle>
      <Card className="p-3.5">
        <Segmented
          value={s.theme}
          onChange={(v) => { store.updateSettings({ theme: v }); toast(v === "dark" ? "Тёмная тема" : "Светлая тема"); }}
          options={[
            { value: "light", label: "Светлая", icon: Sun },
            { value: "dark", label: "Тёмная", icon: Moon },
          ]}
        />
        <p className="mt-2.5 text-[11.5px] text-faint leading-snug">
          Тема переключается вручную и запоминается — без запросов к системе,
          чтобы стабильно работать на Android 7+.
        </p>
      </Card>

      <SectionTitle>Профиль</SectionTitle>
      <Card className="p-4">
        <Field label="Подпись преподавателя">
          <div className="flex gap-2">
            <Input
              value={nameDraft ?? s.teacherName}
              onChange={(e) => setNameDraft(e.target.value)}
              placeholder="Иванова А. П."
            />
            <Btn
              icon={Check}
              disabled={nameDraft === null || !nameDraft.trim()}
              onClick={() => {
                if (nameDraft) store.updateSettings({ teacherName: nameDraft.trim() });
                setNameDraft(null);
                toast("Сохранено");
              }}
            >
              ОК
            </Btn>
          </div>
        </Field>
      </Card>

      <SectionTitle>Код преподавателя</SectionTitle>
      <Card className="p-4 flex items-center gap-2.5">
        <div className="flex-1 min-w-0">
          <div className="text-[24px] font-extrabold tracking-[0.18em] tabular-nums leading-none">
            {s.teacherCode}
          </div>
          <div className="mt-1.5 text-[12px] text-muted leading-snug">
            Для команды /teacher в MAX-боте: утренний дайджест и пуши о новых привязках.
          </div>
        </div>
        <IconBtn
          icon={Copy} label="Скопировать"
          className="bg-surface2 border border-line"
          onClick={() => copyText(s.teacherCode) && toast("Код скопирован")}
        />
        <IconBtn
          icon={RefreshCw} label="Обновить код"
          className="bg-surface2 border border-line"
          onClick={() => { store.regenerateTeacherCode(); toast("Код обновлён — старый недействителен"); }}
        />
      </Card>

      <SectionTitle>Боты-уведомления</SectionTitle>
      <Card className="p-4 mb-2">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-9 h-9 rounded-xl bg-accentbg grid place-items-center">
            <Send size={16} className="text-accent" />
          </div>
          <div className="flex-1">
            <div className="text-[14.5px] font-bold">Telegram «Мои оценки»</div>
            <div className="text-[11.5px] text-muted">BotFather → /newbot → токен</div>
          </div>
          <Chip tone={s.tgToken ? "success" : "neutral"}>
            {s.tgToken ? "Подключён" : "Не задан"}
          </Chip>
        </div>
        <div className="flex gap-2">
          <Input
            type="password"
            inputMode="text"
            autoComplete="off"
            value={tgDraft ?? s.tgToken}
            onChange={(e) => setTgDraft(e.target.value)}
            placeholder="123456:ABC-DEF…"
          />
          <Btn
            variant="muted" icon={Check}
            disabled={tgDraft === null}
            onClick={() => {
              store.updateSettings({ tgToken: (tgDraft ?? "").trim() });
              setTgDraft(null);
              toast("Токен Telegram сохранён");
            }}
          >
            ОК
          </Btn>
        </div>
      </Card>

      <Card className="p-4">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-9 h-9 rounded-xl bg-g4bg grid place-items-center">
            <Bot size={16} className="text-g4" />
          </div>
          <div className="flex-1">
            <div className="text-[14.5px] font-bold">MAX-бот</div>
            <div className="text-[11.5px] text-muted">@MasterBot → /create → токен</div>
          </div>
          <Chip tone={s.maxToken ? "success" : "neutral"}>
            {s.maxToken ? "Подключён" : "Не задан"}
          </Chip>
        </div>
        <div className="flex gap-2">
          <Input
            type="password"
            inputMode="text"
            autoComplete="off"
            value={maxDraft ?? s.maxToken}
            onChange={(e) => setMaxDraft(e.target.value)}
            placeholder="Токен MAX"
          />
          <Btn
            variant="muted" icon={Check}
            disabled={maxDraft === null}
            onClick={() => {
              store.updateSettings({ maxToken: (maxDraft ?? "").trim() });
              setMaxDraft(null);
              toast("Токен MAX сохранён");
            }}
          >
            ОК
          </Btn>
        </div>
      </Card>

      <SectionTitle>Бэкап</SectionTitle>
      <Card className="p-4">
        <div className="flex flex-col gap-2">
          <Btn variant="muted" icon={DatabaseBackup} onClick={downloadBackup}>
            Скачать бэкап (JSON)
          </Btn>
          <Btn variant="outline" icon={Upload} onClick={() => fileRef.current?.click()}>
            Восстановить из файла
          </Btn>
          <input
            ref={fileRef}
            type="file"
            accept=".json,application/json"
            className="hidden"
            onChange={(e) => { restore(e.target.files?.[0] ?? null); e.target.value = ""; }}
          />
          <p className="text-[11.5px] text-faint leading-snug mt-1">
            Копия содержит токены ботов и привязки студентов — не пересылайте её третьим лицам.
            Перед восстановлением текущие данные лучше сохранить.
          </p>
        </div>
      </Card>

      <SectionTitle>О приложении</SectionTitle>
      <Card className="p-4">
        <div className="flex items-center justify-between text-[13px]">
          <span className="text-muted">Версия</span>
          <span className="font-bold tabular-nums">2.0 · редизайн</span>
        </div>
        <div className="h-px bg-line my-2.5" />
        <div className="flex items-center justify-between text-[13px]">
          <span className="text-muted">Сборка</span>
          <span className="font-bold tabular-nums">0.121</span>
        </div>
        <div className="h-px bg-line my-2.5" />
        <div className="flex items-center justify-between text-[13px]">
          <span className="text-muted">Платформа</span>
          <span className="font-semibold">Android 7+ · WebView</span>
        </div>
        <div className="h-px bg-line my-2.5" />
        <a
          href="https://github.com/mifnail/tech"
          target="_blank"
          rel="noreferrer"
          className="flex items-center justify-between text-[13px] pressable"
        >
          <span className="text-muted">Исходный код</span>
          <span className="font-semibold text-accent inline-flex items-center gap-1.5">
            <Code2 size={14} /> github.com/mifnail/tech
          </span>
        </a>
      </Card>

      <SectionTitle>Поддержать проект</SectionTitle>
      <Card className="p-4 opacity-90">
        <div className="flex items-center gap-2 mb-2.5">
          <div className="w-9 h-9 rounded-xl bg-g2bg grid place-items-center">
            <Coffee size={16} className="text-g2" />
          </div>
          <div className="text-[14.5px] font-bold">Поддержать проект</div>
        </div>
        <p className="text-[12.5px] text-muted leading-snug mb-3">
          Если «Учёт занятий» экономит вам время — можно сказать спасибо <Coffee size={12} className="inline" />
        </p>
        <Btn
          variant="muted"
          className="w-full"
          onClick={() => window.open("https://boosty.to/mifnail/donate", "_blank")}
        >
          Поддержать
        </Btn>
      </Card>

      <SectionTitle>Демо-данные</SectionTitle>
      <Btn variant="danger" icon={Trash2} className="w-full" onClick={() => setResetOpen(true)}>
        Сбросить и заполнить заново
      </Btn>

      <ConfirmSheet
        open={resetOpen}
        onClose={() => setResetOpen(false)}
        title="Сбросить данные?"
        body="Все изменения будут удалены. Журнал заполнится демонстрационными данными заново."
        confirmLabel="Сбросить"
        danger
        onConfirm={() => { store.resetDemo(); toast("Демо-данные восстановлены"); }}
      />
    </Screen>
  );
}
