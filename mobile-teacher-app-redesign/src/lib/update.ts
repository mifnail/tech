/* In-app updater: зеркало ванильного App.Update (static/app.js:174-237).
   GET /api/version → GET /api/update/check?current=ver → баннер/тосты.
   Ошибки сети — молча (как в ванили). Бэкенд update_bp не трогаем.
   Phase 2 iOS gate: APK updater выключен на iOS (TestFlight/App Store). */
import { isIOS } from "./platform";

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

export interface VersionInfo {
  ver: string;
  app_version: string;
  static_ver: string;
}

const DISMISS_KEY = "update_dismiss_ts";
const DISMISS_TTL = 24 * 3600 * 1000;

/** Версии с /api/version: ver/static_ver = mtime dist (кэш-бастер), app_version = semver. */
export async function fetchVersion(): Promise<VersionInfo> {
  try {
    const r = await fetch("/api/version");
    if (!r.ok) return { ver: "", app_version: "", static_ver: "" };
    const j = (await r.json()) as Partial<VersionInfo>;
    return {
      ver: (j && j.ver) || "",
      app_version: (j && j.app_version) || "",
      static_ver: (j && j.static_ver) || "",
    };
  } catch (_) {
    return { ver: "", app_version: "", static_ver: "" };
  }
}

/** Проверка обновления: update_available = latest > current (считает сервер). */
export async function checkUpdate(current: string): Promise<UpdateCheckResult | null> {
  if (isIOS()) return null;
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

/** Сбросить dismiss (24ч-скрытие) — чтобы баннер показался снова. */
export function clearUpdateDismiss(): void {
  try {
    localStorage.removeItem(DISMISS_KEY);
  } catch (_) {}
}

const INSTALLED_KEY = "update_installed_version";
export function markInstalled(version: string): void {
  try {
    localStorage.setItem(INSTALLED_KEY, version);
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
  } catch (_) {}
}
export function isAlreadyInstalled(version: string): boolean {
  try {
    return localStorage.getItem(INSTALLED_KEY) === version;
  } catch (_) {
    return false;
  }
}

/** Phase 2 iOS gate — re-export for tests/convenience */
export { isIOS, isApkUpdaterAvailable } from "./platform";

/** POST /api/update/download → uri APK (Android-only; вне Android — 400). */
export async function downloadUpdate(): Promise<string> {
  if (isIOS()) throw new Error("APK not available on iOS");
  const r = await fetch("/api/update/download", { method: "POST" });
  if (!r.ok) throw new Error("download failed");
  const j = (await r.json()) as { uri?: string };
  return (j && j.uri) || "";
}

/** POST /api/update/install {uri} — системный интент установки APK. */
export async function installUpdate(uri: string): Promise<void> {
  if (isIOS()) throw new Error("APK not available on iOS");
  const r = await fetch("/api/update/install", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ uri }),
  });
  if (!r.ok) throw new Error("install failed");
}