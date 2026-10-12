/* Мини hash-роутер: надёжен в WebView, не требует history API. */

import { useEffect, useState } from "react";

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

/** Навигация: всегда переходит (LessonRun сам сторожит несохранённое
    диалогом через requestNav/requestBack; pagehide сохраняет тихо).
    Возвращает {} для совместимости вызывающих. */
export function navigate(to: string): { unsaved?: boolean } {
  if (current() === to) return {};
  inAppNav = true;
  window.location.hash = to;
  return {};
}

export function goBack(fallback: string): { unsaved?: boolean } {
  if (inAppNav && window.history.length > 1) {
    window.history.back();
  } else {
    // navigate already checks isDirty internally
    const r = navigate(fallback);
    return r;
  }
  return {};
}
