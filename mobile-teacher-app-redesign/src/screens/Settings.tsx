/* «Ещё»: профиль, тема, боты (Telegram / MAX), код преподавателя,
   бэкап/восстановление. */

import { useEffect, useState } from "react";
import RestoreDatabase from "../components/RestoreDatabase";
import UpdateBanner from "../components/UpdateBanner";
import {
  Bot, Check, Coffee, Copy, Download, Moon, RefreshCw,
  Send, Sun, Unlink,
} from "lucide-react";
import { useDB, store } from "../lib/store";
import { BigHeader, Screen } from "../components/shell";
import {
  Btn, Card, Chip, ConfirmSheet, Field, IconBtn, Input,
  SectionTitle, Segmented, useToast,
} from "../components/ui";
import { cn } from "../utils/cn";
import { checkUpdate, clearUpdateDismiss, fetchVersion } from "../lib/update";

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

/** Текст ошибки для тоста: j.error сервера из message store-хелперов
    ("STATUS /url: detail"), до 80 символов. */
function errText(e: unknown): string {
  const msg = e instanceof Error ? e.message : String(e);
  const i = msg.indexOf(": ");
  const detail = (i >= 0 ? msg.slice(i + 2) : msg).trim();
  if (!detail) return "Ошибка";
  if (/failed to fetch/i.test(detail)) return "Нет связи с сервером";
  return detail.slice(0, 80);
}

/* ── Тумблер вкл/выкл ─────────────────────────────────────── */
function Toggle({ checked, onChange, label }: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={cn(
        "pressable relative w-11 h-6 rounded-full shrink-0 transition-colors",
        checked ? "bg-accent" : "bg-surface2 border border-linestrong",
      )}
    >
      <span
        className={cn(
          "absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-surface shadow transition-transform",
          checked && "translate-x-5",
        )}
      />
    </button>
  );
}

/* ── Статус бота: тихий GET /api/settings/{bot,maxbot}/check ── */
type BotStatus =
  | { kind: "checking" }
  | { kind: "no-token" }
  | { kind: "ok"; username?: string }
  | { kind: "error"; text: string }
  | { kind: "offline" };

function BotStatusLine({ checkUrl, checkKey }: {
  checkUrl: string;
  checkKey: number;
}) {
  const [st, setSt] = useState<BotStatus>({ kind: "checking" });

  useEffect(() => {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 10000);
    setSt({ kind: "checking" });
    (async () => {
      try {
        const r = await fetch(checkUrl, { signal: ctrl.signal });
        const j = await r.json().catch(() => null) as
          { ok?: boolean; error?: string; username?: string } | null;
        if (ctrl.signal.aborted) return;
        if (r.ok && j && j.ok) {
          setSt({ kind: "ok", username: typeof j.username === "string" ? j.username : undefined });
        } else if (r.status === 400 || (j && j.error === "no bot token")) {
          setSt({ kind: "no-token" });
        } else if (j && typeof j.error === "string") {
          setSt({ kind: "error", text: j.error });
        } else {
          setSt({ kind: "error", text: `HTTP ${r.status}` });
        }
      } catch (_) {
        if (ctrl.signal.aborted) return;
        setSt({ kind: "offline" });
      } finally {
        clearTimeout(timer);
      }
    })();
    return () => { clearTimeout(timer); ctrl.abort(); };
  }, [checkUrl, checkKey]);

  if (st.kind === "checking") {
    return <div className="text-[11px] text-faint">Проверка…</div>;
  }
  if (st.kind === "no-token") {
    return <Chip tone="neutral" className="text-[11px] normal-case">Не задан</Chip>;
  }
  if (st.kind === "ok") {
    return (
      <Chip tone="success" className="text-[11px] normal-case">
        На связи{st.username ? ` · @${st.username}` : ""}
      </Chip>
    );
  }
  if (st.kind === "error") {
    return (
      <Chip tone="danger" className="text-[11px] normal-case whitespace-normal h-auto min-h-[22px] py-[3px] leading-tight">
        {st.text.slice(0, 60)}
      </Chip>
    );
  }
  return <Chip tone="warn" className="text-[11px] normal-case">Нет связи с сервером</Chip>;
}

export default function SettingsScreen() {
  const db = useDB();
  const toast = useToast();
  const s = db.settings;

  const [nameDraft, setNameDraft] = useState<string | null>(null);
  const [tgDraft, setTgDraft] = useState<string | null>(null);
  const [maxDraft, setMaxDraft] = useState<string | null>(null);
  const [dropTgOpen, setDropTgOpen] = useState(false);
  const [dropMaxOpen, setDropMaxOpen] = useState(false);
  const [unbindTeacherOpen, setUnbindTeacherOpen] = useState(false);
  /* Ключи ре-проверки статуса ботов (после сохранения/отвязки токена) */
  const [tgCheckKey, setTgCheckKey] = useState(0);
  const [maxCheckKey, setMaxCheckKey] = useState(0);

  /* ── Обновления: ключ ремоунта баннера после ручной проверки ── */
  const [updateCheckKey, setUpdateCheckKey] = useState(0);

  const checkForUpdates = async () => {
    try {
      const v = await fetchVersion();
      const ver = v.app_version || v.ver;
      if (!ver) { toast("Ошибка проверки"); return; }
      const r = await checkUpdate(ver);
      if (!r) { toast("Ошибка проверки"); return; }
      if (r.update_available) {
        const latest = r.latest || {};
        const latestVer = latest.version || "";
        clearUpdateDismiss();
        setUpdateCheckKey((k) => k + 1); // ремоунт баннера → авто-проверка покажет его
        toast(latestVer ? `Доступно обновление ${latestVer}` : "Доступно обновление");
      } else {
        toast("Вы используете последнюю версию");
      }
    } catch (_) {
      toast("Ошибка проверки");
    }
  };

  /* ── Версия с /api/version (подпись внизу экрана) ── */
  const [appVer, setAppVer] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const v = await fetchVersion();
      if (!cancelled) setAppVer(v.app_version || v.ver);
    })();
    return () => { cancelled = true; };
  }, []);

  /* ── Боты: тумблеры вкл/выкл (POST enabled → перезагрузка среза) ── */
  const toggleTg = async (v: boolean) => {
    try {
      await store.updateSettings({ tgEnabled: v });
      await store.reloadBotState();
      toast(v ? "Бот включён" : "Бот выключен");
    } catch (e) {
      toast("Ошибка: " + errText(e));
    }
  };
  const toggleMax = async (v: boolean) => {
    try {
      await store.updateSettings({ maxEnabled: v });
      await store.reloadBotState();
      toast(v ? "Бот включён" : "Бот выключен");
    } catch (e) {
      toast("Ошибка: " + errText(e));
    }
  };

  /* ── Отвязать токен целиком (DELETE) ── */
  const dropTg = async () => {
    try {
      await store.dropBotToken("tg");
      toast("Токен Telegram отвязан");
      setTgCheckKey((k) => k + 1);
    } catch (e) {
      toast("Ошибка: " + errText(e));
    }
  };
  const dropMax = async () => {
    try {
      await store.dropBotToken("max");
      toast("Токен MAX отвязан");
      setMaxCheckKey((k) => k + 1);
    } catch (e) {
      toast("Ошибка: " + errText(e));
    }
  };

  /* ── Отвязать преподавателя (POST teacher/unbind) ── */
  const unbindTeacher = async () => {
    try {
      await store.unbindTeacher();
      toast("Преподаватель отвязан");
    } catch (e) {
      toast("Ошибка: " + errText(e));
    }
  };

  /* ── База данных: скачать .db (сервер сохраняет в Загрузки) ── */
  const downloadDb = async () => {
    try {
      const r = await fetch("/api/backup/share", { method: "POST" });
      const j = await r.json().catch(() => null);
      if (!r.ok || !j || !j.ok) throw new Error((j && j.error) || "backup/share failed");
      if (j.shared) toast("Бэкап создан и отправлен: " + (j.path || "OK"));
      else if (j.path) toast("Бэкап сохранён: " + j.path);
      else toast("Бэкап создан");
    } catch (e) {
      // Fallback: plain POST /api/backup (desktop where share unavailable)
      try {
        const r2 = await fetch("/api/backup", { method: "POST" });
        const j2 = await r2.json().catch(() => null);
        if (!r2.ok || !j2 || !j2.ok) {
          toast((j2 && j2.error) || (e instanceof Error && e.message) || "Ошибка");
          return;
        }
        toast("Бэкап сохранён: " + (j2.path || "OK"));
      } catch (_) {
        toast("Ошибка");
      }
    }
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
          <Chip tone={s.tgHasToken ? "success" : "neutral"}>
            {s.tgHasToken ? "Подключён" : "Не задан"}
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
            onClick={async () => {
              const token = (tgDraft ?? "").trim();
              try {
                await store.updateSettings({ tgToken: token });
                setTgDraft(null);
                toast("Токен Telegram сохранён");
                setTgCheckKey((k) => k + 1);
              } catch (e) {
                toast("Ошибка: " + errText(e));
              }
            }}
          >
            ОК
          </Btn>
        </div>
        <div className="mt-2 flex items-center gap-1.5 min-h-[22px]">
          <BotStatusLine checkUrl="/api/settings/bot/check" checkKey={tgCheckKey} />
        </div>
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-line">
          <div>
            <div className="text-[13.5px] font-semibold">Включить бота</div>
            <div className="text-[11.5px] text-muted">Приём сообщений от студентов</div>
          </div>
          <Toggle checked={s.tgEnabled} onChange={toggleTg} label="Включить Telegram-бота" />
        </div>
        {s.tgHasToken && (
          <Btn variant="danger" icon={Unlink} className="w-full mt-3" onClick={() => setDropTgOpen(true)}>
            Отвязать токен
          </Btn>
        )}
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
          <Chip tone={s.maxHasToken ? "success" : "neutral"}>
            {s.maxHasToken ? "Подключён" : "Не задан"}
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
            onClick={async () => {
              const token = (maxDraft ?? "").trim();
              try {
                await store.updateSettings({ maxToken: token });
                setMaxDraft(null);
                toast("Токен MAX сохранён");
                setMaxCheckKey((k) => k + 1);
              } catch (e) {
                toast("Ошибка: " + errText(e));
              }
            }}
          >
            ОК
          </Btn>
        </div>
        <div className="mt-2 flex items-center gap-1.5 min-h-[22px]">
          <BotStatusLine checkUrl="/api/settings/maxbot/check" checkKey={maxCheckKey} />
        </div>
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-line">
          <div>
            <div className="text-[13.5px] font-semibold">Включить бота</div>
            <div className="text-[11.5px] text-muted">Приём сообщений от студентов</div>
          </div>
          <Toggle checked={s.maxEnabled} onChange={toggleMax} label="Включить MAX-бота" />
        </div>
        {s.maxHasToken && (
          <Btn variant="danger" icon={Unlink} className="w-full mt-3" onClick={() => setDropMaxOpen(true)}>
            Отвязать токен
          </Btn>
        )}
        <div className="flex items-center justify-between gap-2 mt-3 pt-3 border-t border-line">
          <div className="min-w-0 text-[12px] text-muted leading-snug">
            Код преподавателя:{" "}
            <span className="font-bold text-ink tracking-[0.12em]">{s.teacherCode || "—"}</span>
            <span className={cn("ml-1.5", s.teacherBound ? "text-g5" : "text-faint")}>
              {s.teacherBound ? "· привязан" : "· не привязан"}
            </span>
          </div>
          {s.teacherBound && (
            <Btn size="sm" variant="muted" icon={Unlink} onClick={() => setUnbindTeacherOpen(true)}>
              Отвязать
            </Btn>
          )}
        </div>
      </Card>

      <SectionTitle>База данных (.db)</SectionTitle>
      <Card className="p-4">
        <div className="flex flex-col gap-2">
          <Btn variant="muted" icon={Download} onClick={downloadDb}>
            Скачать базу
          </Btn>
          <RestoreDatabase />
        </div>
      </Card>

      <SectionTitle>Обновления</SectionTitle>
      <UpdateBanner key={updateCheckKey} />
      <Btn variant="muted" icon={RefreshCw} className="w-full" onClick={checkForUpdates}>
        Проверить обновления
      </Btn>

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

      <div className="mt-8 text-center text-[11px] text-faint">
        версия {appVer}
      </div>

      {/* Подтверждения деструктивных действий */}
      <ConfirmSheet
        open={dropTgOpen}
        onClose={() => setDropTgOpen(false)}
        title="Отвязать токен Telegram?"
        body="Токен будет удалён, бот перестанет отвечать студентам. Привязки чатов сохранятся."
        confirmLabel="Отвязать"
        danger
        onConfirm={dropTg}
      />
      <ConfirmSheet
        open={dropMaxOpen}
        onClose={() => setDropMaxOpen(false)}
        title="Отвязать токен MAX?"
        body="Токен будет удалён, бот перестанет отвечать студентам. Привязки чатов сохранятся."
        confirmLabel="Отвязать"
        danger
        onConfirm={dropMax}
      />
      <ConfirmSheet
        open={unbindTeacherOpen}
        onClose={() => setUnbindTeacherOpen(false)}
        title="Отвязать преподавателя?"
        body="Код преподавателя перестанет быть привязан к MAX-боту: дайджесты и пуши о привязках отключатся."
        confirmLabel="Отвязать"
        danger
        onConfirm={unbindTeacher}
      />
    </Screen>
  );
}
