/* Диагностика на устройстве: любая необработанная ошибка видна прямо в UI. */
window.addEventListener('error', function(e) {
  try {
    if (document.querySelector('.err-overlay')) return;
    var d = document.createElement('div');
    d.className = 'err-overlay';
    d.setAttribute('style', 'position:fixed;top:8px;left:8px;right:8px;z-index:9999;background:#7f1d1d;color:#fff;padding:10px 12px;border-radius:8px;font-size:12px;word-break:break-word');
    d.textContent = 'Ошибка: ' + (e.message || 'unknown error');
    (document.getElementById('app') || document.body).prepend(d);
  } catch (_) {}
});

const App = {
  state: { lessonSubjectId: null }
};

App.API = {
  async request(method, path, body) {
    const res = await fetch(path, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined
    });
    // Read the body exactly once and never call res.json(): an HTML error page
    // would otherwise throw "unexpected token '<'" straight into the UI.
    const text = await res.text();
    let data = null;
    let isJson = false;
    try { data = text ? JSON.parse(text) : null; isJson = true; } catch (e) { isJson = false; }
    if (res.ok) {
      if (!isJson) throw { error: 'Сервер вернул не-JSON (' + res.status + ')' };
      return data;
    }
    if (isJson && data) throw data;
    throw { error: 'HTTP ' + res.status };
  },
  get(path) { return this.request('GET', path); },
  post(path, body) { return this.request('POST', path, body); },
  patch(path, body) { return this.request('PATCH', path, body); },
  _delete(path) { return this.request('DELETE', path); }
};

App.Loading = {
  show() {
    const el = document.getElementById('app');
    if (!el) return;
    el.innerHTML = `<div class="loading"><div class="spinner"></div><div>Загрузка...</div></div>`;
  }
};

App.UI = {
  notify(msg) {
    const n = document.getElementById('notif');
    n.textContent = msg;
    n.style.display = 'block';
    setTimeout(() => n.style.display = 'none', 2500);
  },
  showPopup(html) {
    this.closePopup();
    const div = document.createElement('div');
    div.id = 'popup';
    div.className = 'popup';
    div.innerHTML = `<div class="popup-content">${html}</div>`;
    div.onclick = e => { if (e.target === div) this.closePopup(); };
    document.body.appendChild(div);
  },
  closePopup() {
    const p = document.getElementById('popup');
    if (p) p.remove();
  },
  formatDate(iso) {
    if (!iso) return '';
    const [y, m, d] = iso.split('-');
    return `${d}.${m}.${y}`;
  },
  escHtml(s) {
    return (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  },
  escJs(s) {
    return (s || '').replace(/\\/g,'\\\\').replace(/'/g,"\\'").replace(/"/g,'\\"').replace(/\n/g,'\\n');
  }
};

App.Download = {
  _lastBlob: null,
  _lastName: '',
  async as(name, url) {
    const m = url.match(/\/api\/export\/(grades\/\d+|report\/[0-9-]+)\.xlsx$/);
    if (m && !(navigator.share && navigator.canShare)) {
      // APK без Web Share: сохранить в Загрузки и сразу открыть шторку.
      try {
        const r = await App.API.post(`/api/export/${m[1]}/share`);
        if (r.shared === false) App.UI.notify('Сохранено в Загрузки: ' + (r.path || name) + '. Поделиться не вышло: ' + (r.error || ''));
        else App.UI.notify('Открываю отправку…');
      } catch (e) { App.UI.notify((e && e.error) || 'Ошибка отправки'); }
      return;
    }
    let res;
    try {
      res = await fetch(url);
    } catch (e) {
      App.UI.notify('Ошибка скачивания: нет связи');
      return;
    }
    if (!res.ok) {
      let msg = 'Ошибка скачивания';
      try {
        const j = await res.json();
        if (j && j.error) msg = j.error;
      } catch (e) {}
      App.UI.notify(msg);
      return;
    }
    const blob = await res.blob();
    this._lastBlob = blob;
    this._lastName = name;
    // На Android WebView <a download> часто молча ничего не сохраняет,
    // поэтому сразу пробуем системный шаринг — файл можно отправить.
    if (await this._tryShare(name, blob)) return;
    // Фолбэк: классическое скачивание + ручная кнопка «Поделиться».
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
    if (navigator.share) this._showShare(name, blob);
    else App.UI.notify(`Скачано: ${name}`);
  },
  async _tryShare(name, blob) {
    try {
      if (!navigator.share || !navigator.canShare) return false;
      const file = new File([blob], name, { type: blob.type });
      if (!navigator.canShare({ files: [file] })) return false;
      await navigator.share({ files: [file], title: name });
      App.UI.notify(`Отправлено: ${name}`);
      return true;
    } catch (e) {
      // AbortError (закрыл шторку) — тоже считаем завершённым, чтобы не дублировать.
      if (e && e.name === 'AbortError') { App.UI.notify('Отправка отменена'); return true; }
      // NotAllowedError и прочие (нет жеста после fetch) — ручной фолбэк с кнопкой.
      return false;
    }
  },
  _showShare(name, blob) {
    App.UI.showPopup(`
      <h2>Скачано: ${name}</h2>
      <div class="grid-2">
        <button class="btn btn-primary" onclick="App.Download.share()">Поделиться</button>
        <button class="btn btn-muted" onclick="App.UI.closePopup()">Закрыть</button>
      </div>
    `);
  },
  async share() {
    const blob = this._lastBlob;
    const name = this._lastName;
    if (!blob) { App.UI.notify('Нет файла для отправки'); return; }
    try {
      const file = new File([blob], name, { type: blob.type });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({ files: [file], title: name });
      } else if (navigator.share) {
        await navigator.share({ title: name, text: `Файл: ${name}` });
      } else {
        App.UI.notify('Файл сохранён: ' + name);
      }
    } catch (e) {
      if (e.name !== 'AbortError') App.UI.notify('Ошибка: ' + e.message);
    }
    App.UI.closePopup();
  }
};

App.Update = {
  _updateData: null,
  async checkBanner() {
    try {
      const vr = await App.API.get('/api/version');
      const ver = vr && vr.ver ? vr.ver : '';
      if (!ver) return;
      const r = await App.API.get('/api/update/check?current=' + encodeURIComponent(ver));
      if (!r || !r.update_available) return;
      const dismissed = localStorage.getItem('update_dismiss_ts');
      if (dismissed && (Date.now() - Number(dismissed)) < 24 * 3600 * 1000) return;
      const latest = r.latest || {};
      const verLabel = App.UI.escHtml(latest.version || '');
      const notes = App.UI.escHtml(latest.notes || '');
      App.Update._updateData = latest;
      const h2s = document.querySelectorAll('h2');
      const exportH2 = Array.from(h2s).find(function(el) { return el.textContent === 'Экспорт'; });
      if (!exportH2) return;
      const banner = document.createElement('div');
      banner.id = 'update-banner';
      banner.className = 'card';
      banner.style.cssText = 'border-left:3px solid #007aff;margin-bottom:12px';
      banner.innerHTML =
        '<div class="card-title">Доступно обновление ' + verLabel + (notes ? ' · ' + notes : '') + '</div>' +
        '<div style="display:flex;gap:8px;margin-top:8px">' +
        '<button class="btn btn-primary btn-sm" id="btn-upd-action" onclick="App.Update.download()">Скачать</button>' +
        '<button class="btn btn-muted btn-sm" onclick="App.Update.dismiss()">Скрыть</button>' +
        '</div>';
      exportH2.parentElement.insertBefore(banner, exportH2);
    } catch (_) {}
  },
  async download() {
    var btn = document.getElementById('btn-upd-action');
    if (btn) { btn.textContent = 'Загрузка…'; btn.disabled = true; }
    try {
      var r = await App.API.post('/api/update/download');
      App.Update._updateData = App.Update._updateData || {};
      App.Update._updateData.uri = r.uri;
      if (btn) {
        btn.textContent = 'Установить';
        btn.disabled = false;
        btn.onclick = function() { App.Update.install(); };
      }
    } catch (e) {
      if (btn) { btn.textContent = 'Скачать'; btn.disabled = false; }
    }
  },
  async install() {
    var btn = document.getElementById('btn-upd-action');
    if (btn) { btn.textContent = 'Установка…'; btn.disabled = true; }
    var uri = (App.Update._updateData && App.Update._updateData.uri) || '';
    try {
      await App.API.post('/api/update/install', { uri: uri });
      if (btn) { btn.textContent = 'Установлено'; btn.disabled = true; }
    } catch (e) {
      if (btn) { btn.textContent = 'Установить'; btn.disabled = false; }
    }
  },
  dismiss() {
    localStorage.setItem('update_dismiss_ts', String(Date.now()));
    var el = document.getElementById('update-banner');
    if (el) el.remove();
  }
};

App.Nav = {
  render() {
    const pages = [
      { hash: '#home', label: 'Дом' },
      { hash: '#schedule', label: 'Расп.' },
      { hash: '#settings', label: 'Настр.' }
    ];
    const active = location.hash.split('?')[0] || '#home';
    return `<div class="nav">${
      pages.map(p =>
        `<a href="${p.hash}" class="${active === p.hash ? 'active' : ''}">${p.label}</a>`
      ).join('')
    }</div>${this.showFab() ? '<button class="fab" onclick="App.Pages.showCreateLessonAny()" aria-label="Новое занятие">+</button>' : ''}`;
  },
  showFab() {
    const h = location.hash.split('?')[0];
    return h === '' || h === '#home' || h === '#schedule' || h === '#today';
  }
};

App.Grades = {
  CYCLE: ['', '0', '5', '4', '3', '2'],
  colorClass(grade) {
    if (grade === '0' || grade === 'present') return 'present';
    if (grade === '5') return '5';
    if (grade === '4') return '4';
    if (grade === '3') return '3';
    if (grade === '2') return '2';
    if (grade === 'absent' || grade === 'н/я') return 'absent';
    return 'none';
  },
  async cycle(lessonId, studentId, currentGrade, ev) {
    // Направление перебора от места тапа: правая половина — вперёд, левая — назад.
    let dir = 1;
    try {
      const t = ev && ev.currentTarget ? ev.currentTarget.getBoundingClientRect() : null;
      const x = ev && ev.clientX != null ? ev.clientX : null;
      if (t && x != null && t.width > 0 && ((x - t.left) / t.width) < 0.5) dir = -1;
    } catch (e) {}
    const n = this.CYCLE.length;
    const idx = this.CYCLE.indexOf(currentGrade || '');
    const next = this.CYCLE[(((idx + dir) % n) + n) % n];
    await App.API.post(`/api/lessons/${lessonId}/attendance`, { student_id: studentId, grade: next });
    App.Pages.lesson(lessonId);
  }
};

App.Router = {
  init() {
    window.addEventListener('hashchange', () => this.handle());
    this.handle();
  },
  handle() {
    const hash = location.hash || '#home';
    if (hash === '#home') App.Pages.home();
    else if (hash.startsWith('#today') || hash.startsWith('#subjects')) {
      location.hash = '#home';
    } else if (hash.startsWith('#schedule')) App.Pages.schedule();
    else if (hash.startsWith('#subjects')) App.Pages.subjects();
    else if (hash.startsWith('#subject/')) App.Pages.subject(hash.split('/')[1]);
    else if (hash.startsWith('#lesson/')) App.Pages.lesson(hash.split('/')[1]);
    else if (hash.startsWith('#students/')) App.Pages.students(hash.split('/')[1]);
    else if (hash.startsWith('#settings')) App.Pages.settings();
    else App.Pages.home();
  }
};

App.Pages = {
  _showToday: false,

  _renderTodaySchedule(schedule, lessons, opts) {
    opts = opts || {};
    let html = '';
    if (schedule.length) {
      html += `<h2>Расписание</h2>`;
      for (const e of schedule) {
        const existing = lessons.filter(l => l.subject_id === e.subject_id
          && (l.lesson_number == null || e.lesson_number == null || l.lesson_number === e.lesson_number));
        html += `<div class="card">
          <div class="card-title">Занятие ${e.lesson_number} · ${App.UI.escHtml(e.subject_name)}</div>
          <div class="card-sub">${App.UI.escHtml(e.group_name)}</div>`;
          for (const l of existing) {
          const cls = l.status === 'cancelled' ? 'badge-cancelled' : 'badge-held';
          const label = l.status === 'cancelled' ? 'Отменено' : 'Проведено';
          html += `<div style="display:flex;align-items:center;gap:4px;margin-top:4px">
            <a href="#lesson/${l.id}" style="flex:1">${label} · ${App.UI.formatDate(l.date)}</a>
            <button class="btn btn-danger btn-sm" style="width:auto" onclick="event.stopPropagation();App.Pages.confirmDeleteLesson(${l.id})">✕</button>
          </div>`;
        }
        html += `<button class="btn btn-success btn-sm" style="margin-top:8px" onclick="App.Pages.startLesson(${e.subject_id}, ${e.lesson_number})">Начать занятие</button>`;
        html += `</div>`;
      }
    }
    const otherLessons = lessons.filter(l => !schedule.some(s => s.subject_id === l.subject_id));
    if (otherLessons.length) {
      html += `<h2>Другие занятия</h2>`;
      for (const l of otherLessons) {
        const cls = l.status === 'cancelled' ? 'badge-cancelled' : 'badge-held';
        const label = l.status === 'cancelled' ? 'Отменено' : 'Проведено';
        html += `<div class="card" style="cursor:pointer" onclick="location='#lesson/${l.id}'">
          <div class="card-title">${App.UI.escHtml(l.actual_subject_name)}</div>
          <div class="card-sub">${App.UI.escHtml(l.group_name)} · <span class="badge ${cls}">${label}</span></div>
        </div>`;
      }
    }
    if (!schedule.length && !lessons.length) {
      const emptyText = opts.emptyText || 'Сегодня занятий нет';
      html += `<div class="card"><div class="card-sub">${emptyText}</div></div>`;
    }
    if (opts.showGlobalCreate === false) {
      // hide global create button when opts explicitly false
    } else {
      const label = opts.globalLabel || '+ Создать занятие';
      html += `<button class="btn btn-success btn-sm" style="margin-top:8px" onclick="App.Pages.showCreateLessonAny()">${label}</button>`;
    }
    return html;
  },

  async home() {
    App.Loading.show();
    const [subjects, groups, today] = await Promise.all([
      App.API.get('/api/subjects'),
      App.API.get('/api/groups'),
      App.API.get('/api/schedule/today'),
    ]);

    let html = App.Nav.render();
    html += `<h1>Учёт занятий</h1>`;

    html += `<div class="card" style="cursor:pointer" onclick="App.Pages._showToday = !App.Pages._showToday; App.Pages.home()">
      <div class="card-title">Сегодня (${App.UI.formatDate(today.date)})</div>
      <div class="card-sub">${today.schedule.length} запланировано · ${today.lessons.length} занятий · ${App.Pages._showToday ? '▲' : '▼'}</div>
    </div>`;

    if (App.Pages._showToday) {
      html += App.Pages._renderTodaySchedule(today.schedule, today.lessons);
    }

    html += `<h2>Предметы</h2>`;
    for (const s of subjects) {
      const pct = s.total_hours > 0 ? Math.round(s.held_lessons / s.total_hours * 100) : 0;
      html += `<div class="card">
        <div class="row" style="cursor:pointer" onclick="location='#subject/${s.id}'">
          <div style="flex:1">
            <div class="card-title">${App.UI.escHtml(s.name)}</div>
            <div class="card-sub">${App.UI.escHtml(s.group_name)} · ${s.held_lessons}/${s.total_hours} (осталось ${s.remaining})</div>
            <div class="bar"><div class="bar-fill" style="width:${pct}%"></div></div>
          </div>
        </div>
        <button class="btn btn-muted btn-sm" style="width:auto" onclick="event.stopPropagation();App.Pages.showEditSubject(${s.id}, '${App.UI.escJs(s.name)}', ${s.total_hours})">✎</button>
        <button class="btn btn-danger btn-sm" style="margin-top:4px;width:auto" onclick="event.stopPropagation();App.Pages.confirmDeleteSubject(${s.id}, '${App.UI.escJs(s.name)}')">✕</button>
      </div>`;
    }

    if (!groups.length) {
      html += `<div class="card"><div class="card-sub">Сначала создайте группу</div>`;
      html += `<button class="btn btn-primary btn-sm" style="margin-top:8px" onclick="App.Pages.showAddGroup()">+ Создать группу</button></div>`;
    }

    if (groups.length) {
      html += `<h2>Группы</h2><div class="grid-2">`;
      for (const g of groups) {
        html += `<div class="card" style="cursor:pointer;text-align:center" onclick="location='#students/${g.id}'">
          <div class="card-title">${App.UI.escHtml(g.name)}</div>
          <div style="display:flex;gap:4px;justify-content:center;margin-top:4px">
            <button class="btn btn-muted btn-sm" style="width:auto" onclick="event.stopPropagation();App.Pages.showEditGroup(${g.id}, '${App.UI.escJs(g.name)}')">✎</button>
            <button class="btn btn-danger btn-sm" style="width:auto" onclick="event.stopPropagation();App.Pages.confirmDeleteGroup(${g.id}, '${App.UI.escJs(g.name)}')">✕</button>
          </div>
        </div>`;
      }
      html += `</div>`;
    }

    html += `<div style="display:flex;gap:8px;margin-top:8px">
      <button class="btn btn-primary" style="flex:1" onclick="App.Pages.showAddSubject()">+ Предмет</button>
      <button class="btn btn-muted" style="flex:1" onclick="App.Pages.showAddGroup()">+ Группа</button>
    </div>
    <h2>Экспорт</h2><div class="grid-2">
      <button class="btn btn-muted btn-sm" onclick="App.Pages.shareReport('${today.date}')">Поделиться отчётом</button>
    </div>`;
    document.getElementById('app').innerHTML = html;
    App.Update.checkBanner();
  },

  async today(subjectId) {
    App.Loading.show();
    const [data, subjects] = await Promise.all([
      App.API.get('/api/schedule/today'),
      App.API.get('/api/subjects')
    ]);

    let schedule = data.schedule;
    let lessons = data.lessons;
    let currentSubject = null;

    if (subjectId) {
      currentSubject = subjects.find(s => s.id == subjectId);
      schedule = data.schedule.filter(e => e.subject_id == subjectId);
      lessons = data.lessons.filter(l => l.subject_id == subjectId);
    }

    let html = App.Nav.render();
    const title = currentSubject ? `${currentSubject.name} — сегодня` : 'Сегодня';
    html += `<h1>${title}</h1>`;
    html += `<div class="card"><div class="card-title">${App.UI.formatDate(data.date)}</div>`;
    html += `<div class="card-sub">День ${data.day_of_week}</div></div>`;

    if (currentSubject) {
      html += `<button class="btn btn-muted btn-sm" style="margin-bottom:8px" onclick="location='#subject/${subjectId}'">📋 Журнал предмета</button>`;
      html += `<button class="btn btn-muted btn-sm" style="margin-bottom:8px" onclick="location='#today'">📅 Все предметы</button>`;
    }

    html += App.Pages._renderTodaySchedule(schedule, lessons, {
      emptyText: currentSubject ? 'Сегодня занятий по этому предмету нет' : 'Сегодня занятий нет',
      globalLabel: subjectId ? '+ Создать занятие' : 'Создать занятие вручную',
      showGlobalCreate: subjectId ? false : true
    });

    if (currentSubject) {
      const pct = currentSubject.total_hours > 0 ? Math.round(currentSubject.held_lessons / currentSubject.total_hours * 100) : 0;
      html += `<div class="card" style="margin-top:8px">
        <div class="card-title">Прогресс</div>
        <div class="card-sub">${currentSubject.held_lessons}/${currentSubject.total_hours} (осталось ${currentSubject.remaining})</div>
        <div class="bar"><div class="bar-fill" style="width:${pct}%"></div></div>
      </div>`;
    }

    document.getElementById('app').innerHTML = html;
  },

  /* ----- Subject journal ----- */
  async subject(subjectId) {
    App.Loading.show();
    const [data, avg] = await Promise.all([
      App.API.get(`/api/subjects/${subjectId}/gradebook`),
      App.API.get(`/api/reports/average/${subjectId}`)
    ]);
    const allLessons = await App.API.get(`/api/subjects/${subjectId}/lessons`);

    let html = App.Nav.render();
    if (data.summary) {
      const s = data.summary;
      const pct = s.total_hours > 0 ? Math.round(s.held_lessons / s.total_hours * 100) : 0;
      html += `<h1>${App.UI.escHtml(s.name)}</h1>`;
      html += `<div class="card"><div class="grid-2">
        <div class="stat"><div class="stat-value">${s.held_lessons}</div><div class="stat-label">Проведено</div></div>
        <div class="stat"><div class="stat-value">${s.remaining}</div><div class="stat-label">Осталось</div></div>
        <div class="stat"><div class="stat-value">${s.average_grade || '-'}</div><div class="stat-label">Ср. балл</div></div>
        <div class="stat"><div class="stat-value">${s.total_students}</div><div class="stat-label">Студентов</div></div>
      </div>
      <div class="bar"><div class="bar-fill" style="width:${pct}%"></div></div>
      <div class="card-sub" style="margin-top:8px">Группа: ${App.UI.escHtml(s.group_name)}</div>`;
      html += `<div class="grid-2" style="margin-top:8px">
        <button class="btn btn-muted btn-sm" onclick="App.Pages.shareGrades(${subjectId})">Поделиться</button>
        <button class="btn btn-muted btn-sm" onclick="location='#students/${s.group_id}'">Студенты</button>
      </div></div>`;
    }

    if (avg.length) {
      const maxAvg = Math.max(...avg.map(a => a.average));
      html += `<h2>Средний балл</h2><div class="card">`;
      for (const a of avg) {
        const pct = maxAvg > 0 ? (a.average / maxAvg * 100) : 0;
        html += `<div style="margin-bottom:8px">
          <div style="font-size:13px">${App.UI.escHtml(a.last_name)} ${App.UI.escHtml(a.first_name)}</div>
          <div class="chart-bar"><div class="chart-bar-fill" style="width:${pct}%">${a.average}</div></div>
        </div>`;
      }
      html += `</div>`;
    }

    html += `<h2>Все занятия</h2>`;
    if (allLessons.length) {
      html += `<div class="card">`;
      for (const l of allLessons) {
        const cls = l.status === 'cancelled' ? 'badge-cancelled' : 'badge-held';
        const label = l.status === 'cancelled' ? 'Отменено' : 'Проведено';
        html += `<div class="row" style="cursor:pointer" onclick="location='#lesson/${l.id}'">
          <div style="flex:1">
            <div style="font-weight:500">${App.UI.formatDate(l.date)}${l.lesson_number != null ? ` · Занятие №${l.lesson_number}` : ''}</div>
            <div><span class="badge ${cls}">${label}</span></div>
          </div>
          <span style="color:#007aff;font-size:20px">›</span>
        </div>`;
      }
      html += `</div>`;
    } else {
      html += `<div class="card"><div class="card-sub">Занятий пока нет</div></div>`;
    }

    html += `<h2>Ведомость</h2><div class="card" style="overflow-x:auto">`;
    html += `<table style="width:100%;font-size:13px;border-collapse:collapse">`;
    html += `<tr><th style="text-align:left;padding:4px;position:sticky;left:0;background:#fff">Студент</th>`;
    for (let i = 0; i < data.lessons.length; i++) {
      const _l = data.lessons[i];
      const _tip = `${App.UI.formatDate(_l.date)}${_l.lesson_number != null ? ` · №${_l.lesson_number}` : ''}`;
      html += `<th style="padding:4px;text-align:center;min-width:32px"><a href="#lesson/${_l.id}" title="${_tip}" style="text-decoration:underline dotted">${i + 1}</a></th>`;
    }
    html += `</tr>`;
    for (const s of data.students) {
      html += `<tr><td style="padding:4px;position:sticky;left:0;background:#fff;font-weight:500">${App.UI.escHtml(s.last_name)} ${App.UI.escHtml(s.first_name)}</td>`;
      for (const l of data.lessons) {
        const grade = (data.grades[s.id] || {})[l.id] || '';
        const gc = App.Grades.colorClass(grade);
        html += `<td style="padding:4px;text-align:center"><span class="grade grade-${gc}" style="display:inline-flex;width:28px;height:28px">${grade || '—'}</span></td>`;
      }
      html += `</tr>`;
    }
    html += `</table></div>`;
    html += `<button class="btn btn-muted btn-sm" style="margin-top:8px" onclick="history.back()">Назад</button>`;
    document.getElementById('app').innerHTML = html;
  },

  /* ----- Lesson page ----- */
  async lesson(lessonId) {
    App.Loading.show();
    const [data, adjacent] = await Promise.all([
      App.API.get(`/api/lessons/${lessonId}/attendance`),
      App.API.get(`/api/lessons/${lessonId}/adjacent`)
    ]);

    let html = App.Nav.render();
    if (!data.lesson) {
      html += `<div class="card">Занятие не найдено</div>`;
      document.getElementById('app').innerHTML = html;
      return;
    }

    const l = data.lesson;
    App.state.lessonSubjectId = l.subject_id;

    html += `<div style="display:flex;align-items:center;gap:6px;margin-bottom:6px">`;
    html += adjacent.prev_id
      ? `<button class="btn btn-muted btn-sm" style="width:auto;padding:4px 10px;font-size:12px" onclick="location='#lesson/${adjacent.prev_id}'">‹</button>`
      : `<div style="width:28px"></div>`;
    html += `<div class="lesson-header-wrap">`;
    html += `<h1 class="lesson-header-title" title="${App.UI.escHtml(l.actual_subject_name)}">${App.UI.escHtml(l.actual_subject_name)}</h1>`;
    html += `<div style="font-size:11px;opacity:0.75;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${App.UI.formatDate(l.date)} · ${App.UI.escHtml(l.group_name)}${l.lesson_number != null ? ` · Занятие №${l.lesson_number}` : ''} ${l.status === 'cancelled' ? '· (Отменено)' : ''}</div>`;
    html += `</div>`;
    html += adjacent.next_id
      ? `<button class="btn btn-muted btn-sm" style="width:auto;padding:4px 10px;font-size:12px" onclick="location='#lesson/${adjacent.next_id}'">›</button>`
      : `<div style="width:28px"></div>`;
    html += `</div>`;

    if (l.status === 'cancelled') {
      html += `<div class="card"><div class="badge badge-cancelled" style="margin-bottom:8px">Занятие отменено</div></div>`;
      html += `<button class="btn btn-muted btn-sm" onclick="location='#subject/${App.state.lessonSubjectId}'">Журнал</button>`;
      document.getElementById('app').innerHTML = html;
      return;
    }

    const attMap = {};
    for (const a of data.attendance) attMap[a.student_id] = a.grade;

    html += `<div style="display:flex;justify-content:space-between;align-items:center;margin:4px 0 6px 0">`;
    html += `<h2 style="margin:0;font-size:14px">Отметки (${(data.students || []).length})</h2>`;
    html += `</div>`;
    html += `<div class="card" style="padding:8px">`;
    html += `<div class="attendance-list-2col">`;
    for (const s of data.students || []) {
      const grade = attMap[s.id] || null;
      const label = (grade === null || grade === '') ? '—' : grade;
      const fullName = `${s.last_name} ${s.first_name || ''} ${s.middle_name || ''}`.trim();
      const displayName = `${s.last_name} ${s.first_name ? s.first_name[0] + '.' : ''}`;
      html += `<div class="att-row-2col ${grade ? 'marked' : ''} grade-tint-${App.Grades.colorClass(grade).replace('0','present')}" onclick="App.Grades.cycle(${lessonId}, ${s.id}, '${grade || ''}', event)" title="${App.UI.escHtml(fullName)}">
        <div class="att-name">${App.UI.escHtml(displayName)}</div>
        <div class="att-badge grade-${App.Grades.colorClass(grade)}">${label}</div>
      </div>`;
    }
    html += `</div></div>`;

    html += `<div style="display:flex;gap:6px;margin-top:6px">
      <button class="btn btn-warning btn-sm" style="flex:1;min-height:44px;padding:6px 4px;font-size:11px" onclick="App.Pages.showLessonSubstitution(${lessonId})">🔄 Замена</button>
      <button class="btn btn-danger btn-sm" style="flex:1;min-height:44px;padding:6px 4px;font-size:11px" onclick="App.Pages.confirmCancelLesson(${lessonId})">✕ Отмена</button>
      <button class="btn btn-danger btn-sm" style="flex:1;min-height:44px;padding:6px 4px;font-size:11px" onclick="App.Pages.confirmDeleteLesson(${lessonId})">🗑 Удал.</button>
      <button class="btn btn-success btn-sm" style="flex:1;min-height:44px;padding:6px 4px;font-size:11px" onclick="location='#subject/${App.state.lessonSubjectId}'">📖 Журнал</button>
    </div>`;
    document.getElementById('app').innerHTML = html;
  },

  /* ----- Schedule management ----- */
  async schedule() {
    App.Loading.show();
    const [schedule, subjects] = await Promise.all([
      App.API.get('/api/schedule'),
      App.API.get('/api/subjects')
    ]);
    const days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];
    const weekTypes = ['Каждую', 'Нечетная', 'Четная'];

    let html = App.Nav.render();
    html += `<h1>Расписание</h1>`;
    html += `<button class="btn btn-primary btn-sm" onclick="App.Pages.showAddScheduleEntry()">+ Добавить в расписание</button>`;

    for (const d of days) {
      const entries = schedule.filter(e => e.day_of_week === days.indexOf(d) + 1);
      if (!entries.length) continue;
      html += `<h2>${d}</h2>`;
      for (const e of entries) {
        html += `<div class="card">
          <div class="row">
            <div style="flex:1">
              <div class="card-title">Занятие ${e.lesson_number}</div>
              <div class="card-sub">${App.UI.escHtml(e.subject_name)} · ${App.UI.escHtml(e.group_name)} · ${weekTypes[e.week_type] || 'Каждую'}</div>
            </div>
            <button class="btn btn-muted btn-sm" style="width:auto" onclick="App.Pages.showEditScheduleEntry(${e.id}, ${JSON.stringify(e).replace(/"/g, '&quot;')})">✎</button>
            <button class="btn btn-danger btn-sm" style="width:auto" onclick="App.Pages.confirmDeleteScheduleEntry(${e.id})">✕</button>
          </div>
        </div>`;
      }
    }

    html += `<button class="btn btn-muted btn-sm" style="margin-top:8px" onclick="history.back()">Назад</button>`;
    document.getElementById('app').innerHTML = html;
  },

  /* ----- Student list ----- */
  async students(groupId) {
    App.Loading.show();
    const [students, groups] = await Promise.all([
      App.API.get(`/api/students?group_id=${groupId}`),
      App.API.get('/api/groups')
    ]);
    let botBound = {};
    try {
      const links = await App.API.get('/api/bot/links');
      for (const l of links) botBound[l.student_id] = true;
    } catch (e) {}
    let maxBound = {};
    try {
      const mlinks = await App.API.get('/api/maxbot/links');
      for (const l of mlinks) maxBound[l.student_id] = true;
    } catch (e) {}
    let curator = {code: '', bound: false};
    try {
      const c = await App.API.get(`/api/groups/${groupId}/curator`);
      curator = c;
    } catch (e) {}
    const group = groups.find(g => g.id == groupId);

    let html = App.Nav.render();
    html += `<h1>${group ? group.name : 'Студенты'}</h1>`;
    html += `<div class="card"><div class="card-sub">Куратор: код ${App.UI.escHtml(curator.code) || '—'} · ${curator.bound ? 'привязан' : 'не привязан'}</div>${curator.bound ? `<button class="btn btn-muted btn-sm" style="margin-top:4px" onclick="App.Pages.unbindGroupCurator(${groupId})">Отвязать</button>` : ''}</div>`;
    html += `<button class="btn btn-primary btn-sm" onclick="App.Pages.showAddStudents(${groupId})">+ Добавить студентов</button>`;
    html += `<div class="card">`;
    for (const s of students) {
      html += `<div class="row">
        <div style="flex:1"><span style="font-weight:500">${App.UI.escHtml(s.last_name)} ${App.UI.escHtml(s.first_name)}</span> ${App.UI.escHtml(s.middle_name || '')}${botBound[s.id] ? ' <span title="Привязан к Telegram-боту">📱</span>' : ''}${maxBound[s.id] ? ' <span title="Привязан к MAX">📨</span>' : ''}</div>
        <div style="display:flex;gap:4px">
        ${botBound[s.id] ? `<button class="btn btn-muted btn-sm" style="width:auto" onclick="App.Pages.unbindBot(${s.id})">TG</button>` : ''}
        ${maxBound[s.id] ? `<button class="btn btn-muted btn-sm" style="width:auto" onclick="App.Pages.unbindMaxBot(${s.id})">MAX</button>` : ''}
        <button class="btn btn-muted btn-sm" style="width:auto" onclick="App.Pages.showEditStudent(${s.id}, '${App.UI.escJs(s.last_name)}', '${App.UI.escJs(s.first_name)}', '${App.UI.escJs(s.middle_name || '')}')">✎</button>
        <button class="btn btn-danger btn-sm" style="width:auto" onclick="App.Pages.confirmDeleteStudent(${s.id})">✕</button>
        </div>
      </div>`;
    }
    html += `</div>`;
    html += `<button class="btn btn-muted btn-sm" onclick="history.back()">Назад</button>`;
    document.getElementById('app').innerHTML = html;
  },

  /* ----- Subjects management ----- */
  async subjects() {
    App.Loading.show();
    const [groups, subjects] = await Promise.all([
      App.API.get('/api/groups'),
      App.API.get('/api/subjects')
    ]);

    let html = App.Nav.render();
    html += `<h1>Предметы</h1>`;
    html += `<button class="btn btn-primary" onclick="App.Pages.showAddSubject()">+ Добавить предмет</button>`;

    if (!groups.length) {
      html += `<div class="card" style="margin-top:12px"><div class="card-sub">Сначала создайте группу</div>`;
      html += `<button class="btn btn-primary btn-sm" style="margin-top:8px" onclick="App.Pages.showAddGroup()">+ Создать группу</button></div>`;
    }

    for (const s of subjects) {
      const pct = s.total_hours > 0 ? Math.round(s.held_lessons / s.total_hours * 100) : 0;
      html += `<div class="card" style="cursor:pointer" onclick="location='#subject/${s.id}'">
        <div class="card-title">${App.UI.escHtml(s.name)}</div>
        <div class="card-sub">${App.UI.escHtml(s.group_name)} · ${s.held_lessons}/${s.total_hours} · осталось ${s.remaining}</div>
        <div class="bar"><div class="bar-fill" style="width:${pct}%"></div></div>
      </div>`;
    }

    html += `<button class="btn btn-muted btn-sm" style="margin-top:8px" onclick="App.Pages.showAddGroup()">+ Управление группами</button>`;
    document.getElementById('app').innerHTML = html;
  }
};

/* ===== Dialog / Action helpers (on window for onclick access) ===== */

App.Pages.settings = async function() {
  App.Loading.show();
  let st = { has_token: false, enabled: false };
  try { st = await App.API.get('/api/settings/bot'); } catch (e) {}
  let mx = { has_token: false, enabled: false };
  try { mx = await App.API.get('/api/settings/maxbot'); } catch (e) {}
  let appVer = '';
  try { const vv = await App.API.get('/api/version'); appVer = (vv && vv.ver) || ''; } catch (e) {}
  let android = false;
  let pickerAvailable = false;
  try {
    const d = await App.API.get('/api/restore/pick/diag');
    android = !!(d && d.android);
    pickerAvailable = !!(d && d.picker_available);
  } catch (e) {}
  let html = App.Nav.render();
  html += `<h1>Настройки</h1>`;
  html += `<div class="card"><div class="card-title">Telegram-бот «Мои оценки»</div>`;
  html += `<div class="card-sub" style="margin-bottom:8px">Студенты смотрят оценки через бота, пока приложение открыто. Токен: <a href="https://t.me/BotFather" target="_blank">BotFather → /newbot</a></div>`;
  html += `<div style="font-size:12px;margin-bottom:4px">Статус: ${st.has_token ? 'токен есть' : 'нет токена'}${st.enabled ? ' · включён' : ''}</div>`;
  html += `<input id="set-btoken" type="password" placeholder="Токен бота" autocomplete="off">`;
  html += `<label style="display:flex;align-items:center;gap:8px;margin-top:8px;font-size:14px"><input id="set-benabled" type="checkbox" ${st.enabled ? 'checked' : ''} style="width:auto"> Включить бота</label>`;
  html += `<div style="font-size:11px;color:#b91c1c;margin-top:4px">⚠️ Для госучреждений использование Telegram для ПД запрещено 41-ФЗ с 01.06.2025 — включайте только для частного использования с согласия студентов. Основной канал — MAX.</div>`;
  html += `<div class="grid-2" style="margin-top:8px">
    <button class="btn btn-primary btn-sm" onclick="App.Pages.saveBot()">Сохранить</button>
    <button class="btn btn-muted btn-sm" onclick="App.Pages.checkBot()">Проверить</button>
  </div>`;
  if (st.has_token) html += `<button class="btn btn-danger btn-sm" style="margin-top:8px" onclick="App.Pages.dropBot()">Отключить</button>`;
  html += `</div>`;
  html += `<div class="card"><div class="card-title">MAX-бот «Мои оценки»</div>`;
  html += `<div class="card-sub" style="margin-bottom:8px">Студенты смотрят оценки через MAX-бота. Токен: <a href="https://max.ru" target="_blank">MAX Platform</a></div>`;
  html += `<div style="font-size:12px;margin-bottom:4px">Статус: ${mx.has_token ? 'токен есть' : 'нет токена'}${mx.enabled ? ' · включён' : ''}</div>`;
  html += `<input id="set-mtoken" type="password" placeholder="Токен MAX-бота" autocomplete="off">`;
  html += `<label style="display:flex;align-items:center;gap:8px;margin-top:8px;font-size:14px"><input id="set-mlenabled" type="checkbox" ${mx.enabled ? 'checked' : ''} style="width:auto"> Включить бота</label>`;
  html += `<div class="grid-2" style="margin-top:8px">
    <button class="btn btn-primary btn-sm" onclick="App.Pages.saveMaxBot()">Сохранить</button>
    <button class="btn btn-muted btn-sm" onclick="App.Pages.checkMaxBot()">Проверить</button>
  </div>`;
  if (mx.has_token) html += `<button class="btn btn-danger btn-sm" style="margin-top:8px" onclick="App.Pages.dropMaxBot()">Отключить</button>`;
  html += `<div style="font-size:12px;margin-top:8px">Код преподавателя: ${mx.teacher_code || '—'} ${mx.teacher_bound ? '· привязан' : '· не привязан'}</div>`;
  if (mx.teacher_bound) html += `<button class="btn btn-muted btn-sm" style="margin-top:4px" onclick="App.Pages.unbindMaxTeacher()">Отвязать преподавателя</button>`;
  html += `</div>`;
  html += `<div class="card"><div class="card-title">Бэкап</div>`;
  html += `<div class="card-sub" style="margin-bottom:8px">Создать резервную копию или восстановить данные.</div>`;
  html += `<button class="btn btn-primary btn-sm" style="margin-top:8px" onclick="App.Pages.doBackup()">Выгрузить копию</button>`;
  html += `<button class="btn btn-muted btn-sm" style="margin-top:4px" onclick="App.Pages.confirmRestoreList()">Восстановить из копии…</button>`;
  if (android) {
    if (pickerAvailable) {
      html += `<button class="btn btn-primary btn-sm" style="margin-top:4px" onclick="App.Pages.restoreByPicker()">Выбрать файл (Android)</button>`;
    } else {
      html += `<div style="font-size:12px;color:var(--color-text-muted);margin-top:6px">Нативный выбор файла недоступен на этом устройстве</div>`;
    }
  } else {
    html += `<div style="margin-top:8px"><input type="file" id="restore-file" accept=".db" style="font-size:12px"></div>`;
    html += `<button class="btn btn-danger btn-sm" style="margin-top:4px" onclick="App.Pages.doRestore()">Восстановить из файла</button>`;
  }
  html += `</div>`;
  html += `<div class="card" style="opacity:0.85"><div class="card-title">Поддержать проект</div>`;
  html += `<div class="card-sub" style="margin-bottom:8px">Если «Учет занятий» экономит вам время — можно сказать спасибо ☕</div>`;
  html += `<button class="btn btn-muted btn-sm" onclick="window.open('https://boosty.to/mifnail/donate', '_blank')">Поддержать</button>`;
  html += `</div>`;
  html += `<div style="font-size:11px;color:var(--color-text-muted);text-align:center;margin-top:4px">сборка ${App.UI.escHtml(appVer) || '?'}</div>`;
  document.getElementById('app').innerHTML = html;
};

App.Pages.saveBot = async function() {
  const token = document.getElementById('set-btoken').value;
  const enabled = document.getElementById('set-benabled').checked;
  const body = { enabled };
  if (token) body.token = token;
  try { await App.API.post('/api/settings/bot', body); App.UI.notify('Сохранено. Перезапусти приложение для старта бота.'); }
  catch (e) { App.UI.notify(e.error || 'Ошибка'); }
  App.Pages.settings();
};

App.Pages.checkBot = async function() {
  try {
    const r = await App.API.get('/api/settings/bot/check');
    App.UI.notify(r.username ? ('Бот доступен: @' + r.username) : 'Бот доступен');
  } catch (e) { App.UI.notify(e.error || 'Ошибка'); }
};

App.Pages.dropBot = async function() {
  try { await App.API._delete('/api/settings/bot'); App.UI.notify('Отключено'); }
  catch (e) { App.UI.notify(e.error || 'Ошибка'); }
  App.Pages.settings();
};

App.Pages.saveMaxBot = async function() {
  const token = document.getElementById('set-mtoken').value;
  const enabled = document.getElementById('set-mlenabled').checked;
  const body = { enabled };
  if (token) body.token = token;
  try { await App.API.post('/api/settings/maxbot', body); App.UI.notify('Сохранено. Перезапусти приложение для старта бота.'); }
  catch (e) { App.UI.notify(e.error || 'Ошибка'); }
  App.Pages.settings();
};

App.Pages.checkMaxBot = async function() {
  try {
    const r = await App.API.get('/api/settings/maxbot/check');
    App.UI.notify(r.ok ? 'MAX-бот доступен' : 'Бот доступен');
  } catch (e) { App.UI.notify(e.error || 'Ошибка'); }
};

App.Pages.dropMaxBot = async function() {
  try { await App.API._delete('/api/settings/maxbot'); App.UI.notify('Отключено'); }
  catch (e) { App.UI.notify(e.error || 'Ошибка'); }
  App.Pages.settings();
};

App.Pages.unbindMaxTeacher = async function() {
  try { await App.API.post('/api/settings/maxbot/teacher/unbind'); App.UI.notify('Преподаватель отвязан'); }
  catch (e) { App.UI.notify(e.error || 'Ошибка'); }
  App.Pages.settings();
};

App.Pages.doBackup = async function() {
  try {
    const r = await App.API.post('/api/backup/share');
    if (r.shared) {
      App.UI.notify('Бэкап создан и отправлен: ' + (r.path || 'OK'));
    } else if (r.path) {
      App.UI.notify('Бэкап сохранён: ' + r.path);
    } else {
      App.UI.notify('Бэкап создан');
    }
  } catch (e) {
    // Fallback: plain POST /api/backup (desktop where share unavailable)
    try {
      const r = await App.API.post('/api/backup');
      App.UI.notify('Бэкап сохранён: ' + (r.path || 'OK'));
    } catch (e2) { App.UI.notify(e2.error || e.error || 'Ошибка'); }
  }
};

App.Pages.doRestore = async function() {
  const fileInput = document.getElementById('restore-file');
  if (!fileInput || !fileInput.files.length) {
    App.UI.notify('Выберите файл .db');
    return;
  }
  App.UI.showPopup(`
    <h2>Восстановить данные?</h2>
    <p style="margin-bottom:12px">Текущая база данных будет заменена. Все несохранённые изменения будут потеряны.</p>
    <div class="grid-2">
      <button class="btn btn-danger" onclick="App.Pages.confirmRestore()">Да, заменить</button>
      <button class="btn btn-muted" onclick="App.UI.closePopup()">Отмена</button>
    </div>
  `);
};

App.Pages.confirmRestore = async function() {
  const fileInput = document.getElementById('restore-file');
  const file = fileInput.files[0];
  App.UI.closePopup();
  App.Loading.show();
  try {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch('/api/restore', { method: 'POST', body: fd });
    const r = await res.json();
    if (!res.ok || !r.ok) {
      App.UI.notify(r.error || 'Ошибка восстановления');
      App.Pages.settings();
      return;
    }
    App.UI.notify('Данные восстановлены');
    App.Pages.settings();
  } catch (e) {
    App.UI.notify('Ошибка сети');
    App.Pages.settings();
  }
};

App.Pages.confirmRestoreList = async function() {
  let r;
  try {
    r = await App.API.get('/api/backup/list');
  } catch (e) {
    App.UI.notify(e.error || 'Ошибка получения списка');
    return;
  }
  const backups = r.backups || [];
  if (!backups.length) {
    App.UI.notify('Бэкапы не найдены — сначала выгрузите копию');
    return;
  }
  const fmtSize = s => s == null ? '' : (s / 1048576 >= 1 ? (s / 1048576).toFixed(1) + ' МБ' : Math.round(s / 1024) + ' КБ');
  const fmtMtime = t => t == null ? '' : new Date(t * 1000).toLocaleString();
  const rows = backups.map(b =>
    `<button class="backup-row" style="display:block;width:100%;text-align:left;padding:10px 12px;margin-bottom:6px;border:1px solid var(--color-border);border-radius:var(--radius-sm);background:var(--color-surface);cursor:pointer" onclick="App.Pages.confirmRestoreNamed('${App.UI.escJs(b.name)}')">
      <div style="font-weight:600">${App.UI.escHtml(b.name)}</div>
      <div style="font-size:12px;color:var(--color-text-muted);margin-top:2px">${App.UI.escHtml(fmtSize(b.size))}${b.mtime != null ? ' · ' : ''}${App.UI.escHtml(fmtMtime(b.mtime))}</div>
      ${b.path ? `<div style="font-size:11px;color:var(--color-text-muted);margin-top:1px;word-break:break-all">${App.UI.escHtml(b.path)}</div>` : ''}
    </button>`
  ).join('');
  App.UI.showPopup(`
    <h2>Восстановить из копии</h2>
    <p style="margin-bottom:12px">Выберите бэкап из «Загрузок»:</p>
    <div style="max-height:300px;overflow-y:auto">${rows}</div>
    <div class="grid-2" style="margin-top:4px">
      <button class="btn btn-muted" onclick="App.UI.closePopup()">Отмена</button>
    </div>
  `);
};

App.Pages.confirmRestoreNamed = function(name) {
  App.UI.showPopup(`
    <h2>Восстановить данные?</h2>
    <p style="margin-bottom:12px">База будет заменена копией <b>${App.UI.escHtml(name)}</b>. Все несохранённые изменения будут потеряны.</p>
    <div class="grid-2">
      <button class="btn btn-danger" onclick="App.Pages.restoreNamed('${App.UI.escJs(name)}')">Да, заменить</button>
      <button class="btn btn-muted" onclick="App.UI.closePopup()">Отмена</button>
    </div>
  `);
};

App.Pages.restoreNamed = async function(name) {
  App.UI.closePopup();
  App.Loading.show();
  try {
    const r = await App.API.post('/api/restore/named', { name });
    App.UI.notify('Данные восстановлены из ' + (r.name || name));
    App.Pages.settings();
  } catch (e) {
    App.UI.notify(e.error || 'Ошибка восстановления');
    App.Pages.settings();
  }
};

App.Pages.restoreByPicker = async function() {
  App.UI.notify('Выберите файл базы…');
  try {
    const r = await App.API.post('/api/restore/pick', {});
    App.UI.notify('Восстановлено из ' + (r.name || 'выбранного файла'));
    App.Pages.settings();
  } catch (e) {
    const msg = (e && e.error) ? e.error : ((e && e.message) ? e.message : 'Ошибка восстановления');
    App.UI.notify(msg);
  }
};

App.Pages.unbindBot = async function(studentId) {
  try {
    await App.API._delete(`/api/bot/links/by-student/${studentId}`);
    App.UI.notify('Чат отвязан');
  } catch (e) { App.UI.notify(e.error || 'Ошибка'); }
  App.Router.handle();
};

App.Pages.unbindMaxBot = async function(studentId) {
  try {
    await App.API._delete(`/api/maxbot/links/by-student/${studentId}`);
    App.UI.notify('MAX чат отвязан');
  } catch (e) { App.UI.notify(e.error || 'Ошибка'); }
  App.Router.handle();
};

App.Pages.unbindGroupCurator = async function(groupId) {
  try {
    await App.API._delete(`/api/groups/${groupId}/curator`);
    App.UI.notify('Куратор отвязан');
  } catch (e) { App.UI.notify(e.error || 'Ошибка'); }
  App.Router.handle();
};

App.Pages.shareGrades = async function(subjectId) {
  try {
    const r = await App.API.post(`/api/export/grades/${subjectId}/share`);
    App.UI.notify(r.shared === false ? ('Файл сохранён, шторка не открылась: ' + (r.error || '')) : 'Шторка открыта');
  } catch (e) { App.UI.notify((e && e.error) || 'Ошибка'); }
};

App.Pages.shareReport = async function(dateStr) {
  try {
    const r = await App.API.post(`/api/export/report/${dateStr}/share`);
    App.UI.notify(r.shared === false ? ('Файл сохранён, шторка не открылась: ' + (r.error || '')) : 'Шторка открыта');
  } catch (e) { App.UI.notify((e && e.error) || 'Ошибка'); }
};

App.Pages.startLesson = async function(subjectId, lessonNumber) {
  await App.Pages.showCreateLessonAny(subjectId, lessonNumber);
};

App.Pages._isoLocal = function(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

App.Pages._calMonths = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];

App.Pages.showCreateLessonAny = async function(preselectId, lessonNumber) {
  App.Pages._newLessonNumber = (lessonNumber == null ? null : lessonNumber);
  const subjects = await App.API.get('/api/subjects');
  App.Pages._newLessonSubjects = subjects;
  App.Pages._newLessonSubject = preselectId || null;
  const t = new Date();
  App.Pages._cal = { y: t.getFullYear(), m: t.getMonth(), sel: App.Pages._isoLocal(t) };
  App.UI.showPopup(`
    <h2>Создать занятие</h2>
    <div id="new-lesson-subjects" style="max-height:130px;overflow-y:auto"></div>
    <div id="lesson-cal" style="margin-top:8px"></div>
    <div class="grid-2" style="margin-top:8px">
      <button class="btn btn-success" onclick="App.Pages.createLessonCalPicked()">Создать</button>
      <button class="btn btn-muted" onclick="App.UI.closePopup()">Отмена</button>
    </div>
  `);
  App.Pages._renderLessonSubjects(subjects);
  App.Pages._renderCal();
};

App.Pages._renderLessonSubjects = function(subjects) {
  const box = document.getElementById('new-lesson-subjects');
  if (!box) return;
  box.innerHTML = subjects.map(s => {
    const sel = s.id === App.Pages._newLessonSubject;
    return `<button class="btn ${sel ? 'btn-success' : 'btn-muted'} btn-sm" style="display:block;width:100%;margin-bottom:4px;text-align:left" onclick="App.Pages._pickLessonSubject(${s.id})">${App.UI.escHtml(s.name)} · ${App.UI.escHtml(s.group_name || '')}</button>`;
  }).join('');
};

App.Pages._pickLessonSubject = function(id) {
  App.Pages._newLessonSubject = id;
  App.Pages._renderLessonSubjects(App.Pages._newLessonSubjects || []);
};

App.Pages._renderCal = function() {
  const box = document.getElementById('lesson-cal');
  if (!box) return;
  const st = App.Pages._cal;
  const todayIso = App.Pages._isoLocal(new Date());
  const startDay = (new Date(st.y, st.m, 1).getDay() + 6) % 7;
  const dim = new Date(st.y, st.m + 1, 0).getDate();
  const pad = n => String(n).padStart(2, '0');
  let cells = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map(n => `<div style="text-align:center;font-size:11px;color:#888">${n}</div>`).join('');
  for (let i = 0; i < startDay; i++) cells += `<div></div>`;
  for (let d = 1; d <= dim; d++) {
    const iso = `${st.y}-${pad(st.m + 1)}-${pad(d)}`;
    if (iso > todayIso) {
      cells += `<div style="text-align:center;padding:6px 0;color:#ccc">${d}</div>`;
    } else {
      const sel = iso === st.sel ? 'background:#007aff;color:#fff;' : '';
      cells += `<div onclick="App.Pages._calPick('${iso}')" style="min-height:44px;display:flex;align-items:center;justify-content:center;cursor:pointer;border-radius:6px;${sel}">${d}</div>`;
    }
  }
  box.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
      <button class="btn btn-muted btn-sm" style="width:auto" onclick="App.Pages._calNav(-1)">◀</button>
      <div style="font-weight:600;font-size:14px">${App.Pages._calMonths[st.m]} ${st.y}</div>
      <button class="btn btn-muted btn-sm" style="width:auto" onclick="App.Pages._calNav(1)">▶</button>
    </div>
    <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:2px">${cells}</div>`;
};

App.Pages._calNav = function(delta) {
  const st = App.Pages._cal;
  const d = new Date(st.y, st.m + delta, 1);
  const t = new Date();
  if (d.getFullYear() > t.getFullYear() || (d.getFullYear() === t.getFullYear() && d.getMonth() > t.getMonth())) {
    App.UI.notify('Будущие месяцы закрыты');
    return;
  }
  st.y = d.getFullYear();
  st.m = d.getMonth();
  App.Pages._renderCal();
};

App.Pages._calPick = function(iso) {
  App.Pages._cal.sel = iso;
  App.Pages._renderCal();
};

App.Pages.createLessonCalPicked = async function() {
  const sid = App.Pages._newLessonSubject;
  if (!sid) { App.UI.notify('Выбери предмет'); return; }
  await App.Pages._createLessonAt(sid, App.Pages._newLessonNumber || null, App.Pages._cal.sel);
};

App.Pages._createLessonAt = async function(subjectId, lessonNumber, iso) {
  try {
    const result = await App.API.post('/api/lessons', {
      subject_id: subjectId, actual_subject_id: subjectId, status: 'held', lesson_number: lessonNumber, date: iso
    });
    const lesson = await App.API.get(`/api/lessons/${result.id}`);
    const stored = (lesson && lesson.date) || '?';
    App.UI.showPopup(`<h2>Занятие создано</h2>
      <div style="font-size:13px;margin-bottom:8px">id ${result.id}, дата в базе: ${App.UI.escHtml(App.UI.formatDate(stored))}</div>
      <div class="grid-2">
        <button class="btn btn-success" onclick="location='#lesson/${result.id}'">Открыть</button>
        <button class="btn btn-muted" onclick="App.UI.closePopup()">Закрыть</button>
      </div>`);
  } catch (e) { App.UI.notify((e && e.error) || 'Ошибка'); }
};

App.Pages.showLessonSubstitution = async function(lessonId) {
  const lesson = await App.API.get(`/api/lessons/${lessonId}`);
  const subs = await App.API.get(`/api/subjects/${lesson.subject_id}/substitution-list`);
  const opts = subs.map(s => `<option value="${s.id}">${App.UI.escHtml(s.name)}</option>`).join('');
  App.UI.showPopup(`
    <h2>Замена</h2>
    <p style="margin-bottom:8px">Выберите предмет:</p>
    <select id="subst-subject">${opts}</select>
    <div class="grid-2" style="margin-top:8px">
      <button class="btn btn-success" onclick="App.Pages.createSubstitution(${lessonId})">Заменить</button>
      <button class="btn btn-muted" onclick="App.UI.closePopup()">Отмена</button>
    </div>
  `);
};

App.Pages.createSubstitution = async function(lessonId) {
  const actualSubjectId = +document.getElementById('subst-subject').value;
  const result = await App.API.patch(`/api/lessons/${lessonId}/substitute`, { new_subject_id: actualSubjectId });
  App.UI.closePopup();
  App.UI.notify('Замена выполнена');
  location = `#lesson/${result.new_lesson_id}`;
};

App.Pages.confirmCancelLesson = async function(lessonId) {
  let n = 0;
  try {
    const data = await App.API.get(`/api/lessons/${lessonId}/attendance`);
    n = (data.attendance || []).length;
  } catch (e) {}
  App.UI.showPopup(`
    <h2>Отменить занятие?</h2>
    <p style="margin-bottom:12px;color:#86868b">Оценки будут удалены${n ? ` (${n} шт.)` : ''}. Действие необратимо.</p>
    <div class="grid-2">
      <button class="btn btn-danger" onclick="App.Pages.cancelLesson(${lessonId})">Отменить</button>
      <button class="btn btn-muted" onclick="App.UI.closePopup()">Нет</button>
    </div>
  `);
};

App.Pages.cancelLesson = async function(lessonId) {
  await App.API.patch(`/api/lessons/${lessonId}/cancel`);
  App.UI.closePopup();
  location = `#lesson/${lessonId}`;
};

App.Pages.confirmDeleteLesson = function(lessonId) {
  App.UI.showPopup(`
    <h2>Удалить занятие?</h2>
    <p style="margin-bottom:12px;color:#86868b">Занятие и оценки будут полностью удалены.</p>
    <div class="grid-2">
      <button class="btn btn-danger" onclick="App.Pages.deleteLesson(${lessonId})">Удалить</button>
      <button class="btn btn-muted" onclick="App.UI.closePopup()">Нет</button>
    </div>
  `);
};

App.Pages.deleteLesson = async function(lessonId) {
  try {
    await App.API._delete(`/api/lessons/${lessonId}`);
    App.UI.closePopup();
    App.UI.notify('Занятие удалено');
    // если были на странице занятия — уходим на главную, иначе просто обновляем
    if (location.hash.startsWith('#lesson/')) location.hash = '#home';
    else App.Router.handle();
  } catch (e) {
    App.UI.notify(e.error || 'Ошибка удаления занятия');
  }
};

// showCustomLesson/createCustomLesson removed — creation goes via showCreateLessonAny.

App.Pages.showAddSubject = async function() {
  const groups = await App.API.get('/api/groups');
  const groupOpts = groups.map(g => `<option value="${g.id}">${App.UI.escHtml(g.name)}</option>`).join('');
  App.UI.showPopup(`
    <h2>Новый предмет</h2>
    <input id="subj-name" placeholder="Название предмета">
    <input id="subj-hours" type="number" placeholder="Всего часов" min="1">
    <select id="subj-group">${groupOpts}</select>
    <button class="btn btn-primary" onclick="App.Pages.createSubject()">Создать</button>
  `);
};

App.Pages.createSubject = async function() {
  const name = document.getElementById('subj-name').value;
  const hours = +document.getElementById('subj-hours').value;
  const groupId = +document.getElementById('subj-group').value;
  if (!name || !hours) return App.UI.notify('Заполните все поля');
  await App.API.post('/api/subjects', { name, total_hours: hours, group_id: groupId });
  App.UI.notify('Предмет создан');
  App.UI.closePopup();
  App.Pages.home();
};

App.Pages.showAddGroup = function() {
  App.UI.showPopup(`
    <h2>Новая группа</h2>
    <input id="group-name" placeholder="Название группы (например ИС-11)">
    <button class="btn btn-primary" onclick="App.Pages.createGroup()">Создать</button>
  `);
};

App.Pages.createGroup = async function() {
  const name = document.getElementById('group-name').value;
  if (!name) return App.UI.notify('Введите название');
  await App.API.post('/api/groups', { name });
  App.UI.notify('Группа создана');
  App.UI.closePopup();
  App.Router.handle();
};

App.Pages.showAddScheduleEntry = async function() {
  const subjects = await App.API.get('/api/subjects');
  const opts = subjects.map(s => `<option value="${s.id}">${App.UI.escHtml(s.name)} (${App.UI.escHtml(s.group_name)})</option>`).join('');
  App.UI.showPopup(`
    <h2>Добавить в расписание</h2>
    <select id="sch-day">${[1,2,3,4,5,6].map(d => `<option value="${d}">${['Пн','Вт','Ср','Чт','Пт','Сб'][d-1]}</option>`).join('')}</select>
    <input id="sch-num" type="number" placeholder="Номер занятия" min="1" max="8">
    <select id="sch-subject">${opts}</select>
    <select id="sch-week">
      <option value="0">Каждую неделю</option>
      <option value="1">Нечетная</option>
      <option value="2">Четная</option>
    </select>
    <button class="btn btn-primary" onclick="App.Pages.createScheduleEntry()">Добавить</button>
  `);
};

App.Pages.createScheduleEntry = async function() {
  await App.API.post('/api/schedule', {
    day_of_week: +document.getElementById('sch-day').value,
    lesson_number: +document.getElementById('sch-num').value,
    subject_id: +document.getElementById('sch-subject').value,
    week_type: +document.getElementById('sch-week').value
  });
  App.UI.notify('Добавлено в расписание');
  App.UI.closePopup();
  App.Pages.schedule();
};

App.Pages.showEditScheduleEntry = async function(id, entry) {
  const subjects = await App.API.get('/api/subjects');
  const opts = subjects.map(s => `<option value="${s.id}" ${s.id === entry.subject_id ? 'selected' : ''}>${App.UI.escHtml(s.name)} (${App.UI.escHtml(s.group_name)})</option>`).join('');
  App.UI.showPopup(`
    <h2>Редактировать расписание</h2>
    <select id="edit-sch-day">${[1,2,3,4,5,6].map(d => `<option value="${d}" ${d === entry.day_of_week ? 'selected' : ''}>${['Пн','Вт','Ср','Чт','Пт','Сб'][d-1]}</option>`).join('')}</select>
    <input id="edit-sch-num" type="number" placeholder="Номер занятия" min="1" max="8" value="${entry.lesson_number}">
    <select id="edit-sch-subject">${opts}</select>
    <select id="edit-sch-week">
      <option value="0" ${entry.week_type === 0 ? 'selected' : ''}>Каждую неделю</option>
      <option value="1" ${entry.week_type === 1 ? 'selected' : ''}>Нечетная</option>
      <option value="2" ${entry.week_type === 2 ? 'selected' : ''}>Четная</option>
    </select>
    <button class="btn btn-primary" onclick="App.Pages.updateScheduleEntry(${id})">Сохранить</button>
  `);
};

App.Pages.updateScheduleEntry = async function(id) {
  await App.API.patch(`/api/schedule/${id}`, {
    day_of_week: +document.getElementById('edit-sch-day').value,
    lesson_number: +document.getElementById('edit-sch-num').value,
    subject_id: +document.getElementById('edit-sch-subject').value,
    week_type: +document.getElementById('edit-sch-week').value
  });
  App.UI.notify('Расписание обновлено');
  App.UI.closePopup();
  App.Pages.schedule();
};

App.Pages.confirmDeleteScheduleEntry = function(id) {
  App.UI.showPopup(`
    <h2>Удалить запись расписания?</h2>
    <div class="grid-2">
      <button class="btn btn-danger" onclick="App.Pages.deleteScheduleEntry(${id})">Удалить</button>
      <button class="btn btn-muted" onclick="App.UI.closePopup()">Отмена</button>
    </div>
  `);
};

App.Pages.deleteScheduleEntry = async function(id) {
  try {
    await App.API._delete(`/api/schedule/${id}`);
    App.UI.closePopup();
    App.UI.notify('Запись удалена');
    App.Pages.schedule();
  } catch (e) {
    App.UI.notify(e.error || 'Ошибка удаления');
  }
};

App.Pages.showAddStudents = function(groupId) {
  App.UI.showPopup(`
    <h2>Добавить студентов</h2>
    <textarea id="students-text" placeholder="Иванов Иван Иванович\nПетров Петр Петрович\n..."></textarea>
    <div style="font-size:12px;color:#86868b">Каждая строка: Фамилия Имя Отчество</div>
    <button class="btn btn-primary btn-sm" onclick="App.Pages.createStudents(${groupId})">Добавить</button>
  `);
};

App.Pages.createStudents = async function(groupId) {
  const text = document.getElementById('students-text').value.trim();
  if (!text) return App.UI.notify('Введите данные');
  const students = text.split('\n').filter(Boolean).map(line => {
    const parts = line.trim().split(/\s+/);
    return { last_name: parts[0] || '', first_name: parts[1] || '', middle_name: parts[2] || null };
  }).filter(s => s.last_name && s.first_name);
  await App.API.post('/api/students/bulk', { group_id: groupId, students });
  App.UI.notify(`Добавлено ${students.length} студентов`);
  App.UI.closePopup();
  App.Pages.students(groupId);
};

App.Pages.showEditStudent = function(studentId, lastName, firstName, middleName) {
  App.UI.showPopup(`
    <h2>Редактировать студента</h2>
    <input id="edit-student-last" class="input" value="${lastName}" placeholder="Фамилия">
    <input id="edit-student-first" class="input" value="${firstName}" placeholder="Имя">
    <input id="edit-student-middle" class="input" value="${middleName}" placeholder="Отчество">
    <div class="grid-2">
      <button class="btn btn-primary" onclick="App.Pages.editStudent(${studentId})">Сохранить</button>
      <button class="btn btn-muted" onclick="App.UI.closePopup()">Отмена</button>
    </div>
  `);
};

App.Pages.editStudent = async function(studentId) {
  const last = document.getElementById('edit-student-last').value.trim();
  const first = document.getElementById('edit-student-first').value.trim();
  const middle = document.getElementById('edit-student-middle').value.trim();
  if (!last || !first) { App.UI.notify('Фамилия и имя обязательны'); return; }
  try {
    await App.API.patch(`/api/students/${studentId}`, { last_name: last, first_name: first, middle_name: middle });
    App.UI.closePopup();
    App.UI.notify('Студент обновлён');
    App.Router.handle();
  } catch (e) {
    App.UI.notify(e.error || 'Ошибка сохранения');
  }
};

App.Pages.confirmDeleteStudent = function(studentId) {
  App.UI.showPopup(`
    <h2>Удалить студента?</h2>
    <p style="margin-bottom:12px;color:#86868b">Оценки будут удалены.</p>
    <div class="grid-2">
      <button class="btn btn-danger" onclick="App.Pages.deleteStudent(${studentId})">Удалить</button>
      <button class="btn btn-muted" onclick="App.UI.closePopup()">Нет</button>
    </div>
  `);
};

App.Pages.deleteStudent = async function(studentId) {
  try {
    await App.API._delete(`/api/students/${studentId}`);
    App.UI.closePopup();
    App.UI.notify('Студент удалён');
    App.Router.handle();
  } catch (e) {
    App.UI.notify(e.error || 'Ошибка удаления студента');
  }
};

App.Pages.confirmDeleteGroup = function(groupId, name) {
  App.UI.showPopup(`
    <h2>Удалить группу «${name}»?</h2>
    <p style="margin-bottom:12px;color:#86868b">Все студенты, предметы и занятия будут удалены.</p>
    <div class="grid-2">
      <button class="btn btn-danger" onclick="App.Pages.deleteGroup(${groupId})">Удалить</button>
      <button class="btn btn-muted" onclick="App.UI.closePopup()">Нет</button>
    </div>
  `);
};

App.Pages.deleteGroup = async function(groupId) {
  try {
    await App.API._delete(`/api/groups/${groupId}`);
    App.UI.closePopup();
    App.UI.notify('Группа удалена');
    location.hash = '#home';
  } catch (e) {
    App.UI.notify(e.error || 'Ошибка удаления группы');
  }
};

App.Pages.confirmDeleteSubject = function(subjectId, name) {
  App.UI.showPopup(`
    <h2>Удалить предмет «${name}»?</h2>
    <p style="margin-bottom:12px;color:#86868b">Занятия и оценки будут удалены.</p>
    <div class="grid-2">
      <button class="btn btn-danger" onclick="App.Pages.deleteSubject(${subjectId})">Удалить</button>
      <button class="btn btn-muted" onclick="App.UI.closePopup()">Нет</button>
    </div>
  `);
};

App.Pages.deleteSubject = async function(subjectId) {
  try {
    await App.API._delete(`/api/subjects/${subjectId}`);
    App.UI.closePopup();
    App.UI.notify('Предмет удалён');
    App.Router.handle();
  } catch (e) {
    App.UI.notify(e.error || 'Ошибка удаления предмета');
  }
};

App.Pages.showEditGroup = function(groupId, name) {
  const safe = (name || '').replace(/"/g, '&quot;');
  App.UI.showPopup(`
    <h2>Редактировать группу</h2>
    <input id="edit-group-name" value="${safe}" placeholder="Название группы">
    <div class="grid-2">
      <button class="btn btn-primary" onclick="App.Pages.editGroup(${groupId})">Сохранить</button>
      <button class="btn btn-muted" onclick="App.UI.closePopup()">Отмена</button>
    </div>
  `);
};

App.Pages.editGroup = async function(groupId) {
  const name = document.getElementById('edit-group-name').value.trim();
  if (!name) { App.UI.notify('Введите название'); return; }
  try {
    await App.API.patch(`/api/groups/${groupId}`, { name });
    App.UI.closePopup();
    App.UI.notify('Группа обновлена');
    App.Router.handle();
  } catch (e) {
    App.UI.notify(e.error || 'Ошибка сохранения');
  }
};

App.Pages.showEditSubject = function(subjectId, name, totalHours) {
  const safe = (name || '').replace(/"/g, '&quot;');
  App.UI.showPopup(`
    <h2>Редактировать предмет</h2>
    <input id="edit-subj-name" value="${safe}" placeholder="Название предмета">
    <input id="edit-subj-hours" type="number" value="${totalHours}" placeholder="Всего часов" min="1">
    <div class="grid-2">
      <button class="btn btn-primary" onclick="App.Pages.editSubject(${subjectId})">Сохранить</button>
      <button class="btn btn-muted" onclick="App.UI.closePopup()">Отмена</button>
    </div>
  `);
};

App.Pages.editSubject = async function(subjectId) {
  const name = document.getElementById('edit-subj-name').value.trim();
  const hours = +document.getElementById('edit-subj-hours').value;
  if (!name || !hours) { App.UI.notify('Заполните все поля'); return; }
  try {
    await App.API.patch(`/api/subjects/${subjectId}`, { name, total_hours: hours });
    App.UI.closePopup();
    App.UI.notify('Предмет обновлён');
    App.Router.handle();
  } catch (e) {
    App.UI.notify(e.error || 'Ошибка сохранения');
  }
};

/* ===== INIT ===== */
App.Router.init();
