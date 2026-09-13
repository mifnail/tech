/* Баннер «Доступно обновление» — зеркало ванильного App.Update.checkBanner()
   (static/app.js:174-237): проверка на монте, скрытие на 24ч, Скачать→Установить.
   Ошибки сети — молча, как в ванили. */

import { useEffect, useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { Btn, Card } from "./ui";
import {
  checkUpdate, dismissUpdate, downloadUpdate, fetchVersion,
  installUpdate, isUpdateDismissed,
} from "../lib/update";

export default function UpdateBanner() {
  const [info, setInfo] = useState<{ version: string; notes: string } | null>(null);
  const [uri, setUri] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const ver = await fetchVersion();
        if (!ver || cancelled) return;
        const r = await checkUpdate(ver);
        if (!r || !r.update_available || cancelled) return;
        if (isUpdateDismissed()) return;
        const latest = r.latest || {};
        setInfo({ version: latest.version || "", notes: latest.notes || "" });
      } catch (_) { /* сеть — молча, как в ванили */ }
    })();
    return () => { cancelled = true; };
  }, []);

  if (!info) return null;

  const onDownload = async () => {
    setBusy(true);
    try {
      const u = await downloadUpdate();
      setUri(u);
    } catch (_) { /* молча: кнопка остаётся «Скачать» */ }
    setBusy(false);
  };

  const onInstall = async () => {
    setBusy(true);
    try {
      await installUpdate(uri || "");
    } catch (_) { /* молча */ }
    setBusy(false);
  };

  const onDismiss = () => {
    dismissUpdate();
    setInfo(null);
  };

  return (
    <Card className="p-3.5 mb-3 border-l-[3px] border-l-accent">
      <div className="text-[14px] font-bold leading-snug">
        Доступно обновление {info.version}
        {info.notes ? " · " + info.notes : ""}
      </div>
      <div className="flex gap-2 mt-2.5">
        {uri === null ? (
          <Btn
            size="sm"
            icon={busy ? Loader2 : Download}
            iconClassName={busy ? "animate-spin" : undefined}
            disabled={busy}
            onClick={onDownload}
          >
            {busy ? "Загрузка…" : "Скачать"}
          </Btn>
        ) : (
          <Btn
            size="sm"
            icon={busy ? Loader2 : Download}
            iconClassName={busy ? "animate-spin" : undefined}
            disabled={busy}
            onClick={onInstall}
          >
            {busy ? "Установка…" : "Установить"}
          </Btn>
        )}
        <Btn size="sm" variant="muted" onClick={onDismiss}>Скрыть</Btn>
      </div>
    </Card>
  );
}