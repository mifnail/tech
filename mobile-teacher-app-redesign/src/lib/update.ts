/* In-app updater: зеркало ванильного App.Update (static/app.js:174-237).
   GET /api/version → GET /api/update/check?current=ver → баннер/тосты.
   Ошибки сети — молча (как в ванили). Бэкенд update_bp не трогаем. */

export interface UpdateInfo {
  version: string;
  url: string;
  notes: string;
  published_at: string;
}

export interface UpdateCheckResult {
  update_available: boolean;
  latest: UpdateInfo;
}

const DISMISS_KEY = "update_dismiss_ts";
const DISMISS_TTL = 24 * 3600 * 1000;

/** Текущая версия статики (mtime dist/index.html) с /api/version. */
export async function fetchVersion(): Promise<string> {
  try {
    const r = await fetch("/api/version");
    if (!r.ok) return "";
    const j = (await r.json()) as { ver?: string };
    return (j && j.ver) || "";
  } catch (_) {
    return "";
  }
}

/** Проверка обновления: update_available = latest > current (считает сервер). */
export async function checkUpdate(current: string): Promise<UpdateCheckResult | null> {
  try {
    const r = await fetch("/api/update/check?current=" + encodeURIComponent(current));
    if (!r.ok) return null;
    return (await r.json()) as UpdateCheckResult;
  } catch (_) {
    return null;
  }
}

/** Баннер скрыт на 24ч (localStorage.update_dismiss_ts). */
export function isUpdateDismissed(): boolean {
  try {
    const d = localStorage.getItem(DISMISS_KEY);
    if (!d) return false;
    return Date.now() - Number(d) < DISMISS_TTL;
  } catch (_) {
    return false;
  }
}

export function dismissUpdate(): void {
  try {
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
  } catch (_) {}
}

/** POST /api/update/download → uri APK (Android-only; вне Android — 400). */
export async function downloadUpdate(): Promise<string> {
  const r = await fetch("/api/update/download", { method: "POST" });
  if (!r.ok) throw new Error("download failed");
  const j = (await r.json()) as { uri?: string };
  return (j && j.uri) || "";
}

/** POST /api/update/install {uri} — системный интент установки APK. */
export async function installUpdate(uri: string): Promise<void> {
  const r = await fetch("/api/update/install", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ uri }),
  });
  if (!r.ok) throw new Error("install failed");
}