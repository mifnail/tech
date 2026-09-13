/* Мини hash-роутер: надёжен в WebView, не требует history API. */

import { useEffect, useState } from "react";
import { store } from "./store";

function current(): string {
  const h = window.location.hash.replace(/^#/, "");
  return h.startsWith("/") ? h : "/today";
}

export function useRoute(): string[] {
  const [path, setPath] = useState(current);
  useEffect(() => {
    const on = () => {
      setPath(current);
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return path.split("/").filter(Boolean);
}

/* Была ли навигация внутри приложения (иначе history.back может выйти из WebView) */
let inAppNav = false;

/** Навигация: сначала флашим «грязные» оценки (чтобы быстрый уход не ронял запись),
    затем меняем hash. Быстрые тапы по-прежнему коалесцируются дебаунсом. */
export async function navigate(to: string): Promise<void> {
  if (current() === to) return;
  inAppNav = true;
  await store.flushAttendance();
  window.location.hash = to;
}

export function goBack(fallback: string): void {
  if (inAppNav && window.history.length > 1) {
    window.history.back();
  } else {
    void navigate(fallback);
  }
}
