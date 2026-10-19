'use client';
import { useEffect } from 'react';
export default function Journal() {
  useEffect(() => {
    let active = true;
    async function load() {
      await fetch('/api/groups');
      if (!active || document.getElementById('teachhelper-source')) return;
      const script = document.createElement('script');
      script.id = 'teachhelper-source';
      script.src = '/static/app.js';
      script.onload = () => { const design = document.createElement('script'); design.src = '/static/redesign.js'; document.body.appendChild(design); };
      script.onerror = () => { const el = document.getElementById('app'); if (el) el.textContent = 'Не удалось загрузить журнал. Обновите страницу.'; };
      document.body.appendChild(script);
    }
    load().catch(() => { const el = document.getElementById('app'); if (el) el.textContent = 'Нет связи с сервером. Обновите страницу.'; });
    return () => { active = false; };
  }, []);
  return <><div id="app"><div className="initial-loading"><div className="loader-mark">T</div><strong>TeachHelper</strong><span>Готовим ваш рабочий день…</span></div></div><div id="notif" className="notif" role="status" aria-live="polite" /></>;
}
