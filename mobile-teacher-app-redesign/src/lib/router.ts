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

/** Навигация: если есть несохранённые оценки — вернуть флаг unsaved
    вызывающему (LessonRun покажет ConfirmSheet). Иначе меняем hash. */
export function navigate(to: string): { unsaved?: boolean } {
  if (current() === to) return {};
  if (store.isDirty()) {
    return { unsaved: true };
  }
  inAppNav = true;
  window.location.hash = to;
  return {};
}

export function goBack(fallback: string): { unsaved?: boolean } {
  if (store.isDirty()) {
    return { unsaved: true };
  }
  if (inAppNav && window.history.length > 1) {
    window.history.back();
  } else {
    // navigate already checks isDirty internally
    const r = navigate(fallback);
    return r;
  }
  return {};
}
