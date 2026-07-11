/* LessonTracker SPA — все экраны, маршрутизация, API */
const S = (sel, parent=document) => parent.querySelector(sel);
const SA = (sel, parent) => [...(parent||document).querySelectorAll(sel)];
const ESC = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const $id = id => document.getElementById(id);

// ------ API helper
async function api(method, url, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
const apiGet = url => api('GET', url);
const apiPost = (url, b) => api('POST', url, b);
const apiPatch = (url, b) => api('PATCH', url, b);

// ------ notification
let notifTimer;
function notify(msg) {
  clearTimeout(notifTimer);
  const n = $id('notif'); n.textContent = msg; n.classList.add('show');
  notifTimer = setTimeout(() => n.classList.remove('show'), 2000);
}

// ------ popup
function popup(title, bodyHtml, btns) {
  const ov = document.createElement('div'); ov.className = 'popup-overlay active';
  ov.innerHTML = `<div class="popup"><h2>${ESC(title)}</h2><div>${bodyHtml}</div>
    <div class="popup-btns">${btns.map(b => `<button class="btn ${b.cls||'btn-primary'}">${ESC(b.text)}</button>`).join('')}</div></div>`;
  document.body.appendChild(ov);
  SA('button', ov).forEach((btn, i) => btn.onclick = () => { ov.remove(); if (btns[i].cb) btns[i].cb(); });
}

// ------ router
const PAGES = {
  home: renderHome,
  today: renderToday,
  'add-subject': renderAddSubject,
  students: renderStudents,
  lesson: renderLesson,
  gradebook: renderGradebook,
};

function navigate(hash) {
  const page = hash.replace('#', '').split('?')[0] || 'home';
  if (PAGES[page]) PAGES[page]();
}
window.addEventListener('hashchange', () => navigate(location.hash));
window.addEventListener('DOMContentLoaded', () => navigate(location.hash || '#home'));

function go(screen) { location.hash = '#' + screen; }

// ------ render helpers
function header(title, backTo) {
  return `<div class="flex items-center gap-10 mb-8" style="height:52px">
    ${backTo ? `<button class="btn btn-muted btn-sm" onclick="go('${backTo}')">← Назад</button>` : ''}
    <h1 class="flex-1" style="margin:0">${ESC(title)}</h1>
  </div>`;
}

function makeBtn(text, cls, onClick) {
  return `<button class="btn ${cls}" onclick="(${onClick})()">${ESC(text)}</button>`;
}

function statusBadge(status) {
  const labels = { scheduled: 'по расписанию', held: 'проведено ✓', cancelled: 'отменено ✕' };
  return `<span class="status-badge status-${status}">${labels[status] || status}</span>`;
}

// ------ PAGE: home
async function renderHome() {
  const app = $id('app'); app.innerHTML = '<div class="spinner"></div>';
  try {
    const subjects = await apiGet('/api/subjects');
    let html = `<div class="page active" id="page-home">
      <div class="flex items-center gap-10 mb-8" style="height:52px">
        <h1 style="margin:0;flex:1">Мои предметы</h1>
        <button class="btn btn-primary" onclick="go('add-subject')">+ Предмет</button>
      </div>
      <div class="flex gap-10 mb-12">
        <button class="btn btn-primary btn-block" onclick="go('today')">Расписание</button>
        <button class="btn btn-success btn-block" onclick="go('gradebook')">Ведомость</button>
      </div>`;
    if (!subjects.length) {
      html += `<div class="card text-center text-muted" style="padding:40px 16px">
        <div style="font-size:16px;margin-bottom:6px">Предметов пока нет.</div>
        <div style="font-size:14px">Нажмите «+ Предмет», чтобы добавить.</div>
      </div>`;
    } else {
      for (const s of subjects) {
        const p = s.planned > 0 ? Math.round((s.held||0)/s.planned*100) : 0;
        const over = p > 100;
        html += `<div class="card subject-row" onclick="go('today')">
          <div class="subject-progress${over?' over':''}" style="width:${Math.min(p,100)}%"></div>
          <div class="subject-title">
            <div style="font-weight:600;font-size:15px;position:relative;z-index:1">${ESC(s.name)}  (${ESC(s.group_name||'')})</div>
            <div style="font-size:13px;color:#737373;position:relative;z-index:1">
              Проведено: ${s.held||0} / ${s.planned||0} • Осталось: ${s.remaining||0} (${p}%)
            </div>
          </div>
        </div>`;
      }
    }
    html += '</div>';
    app.innerHTML = html;
  } catch(e) { notify('Ошибка загрузки: '+e.message); }
}

// ------ PAGE: today
async function renderToday() {
  const app = $id('app'); app.innerHTML = '<div class="spinner"></div>';
  try {
    const lessons = await apiGet('/api/schedule/today');
    const today = new Date().toLocaleDateString('ru-RU', { day:'numeric', month:'long', year:'numeric' });
    let html = `<div class="page active" id="page-today">
      ${header('Сегодня', 'home')}
      <div class="text-muted text-sm mb-8">${today}</div>`;
    if (!lessons.length) {
      html += `<div class="card text-center text-muted" style="padding:30px 16px;font-size:15px">
        На сегодня занятий нет.<br>Нажмите «+ ДОБАВИТЬ».</div>`;
    } else {
      for (const l of lessons) {
        const time = l.held_at && l.held_at.includes('T') ? l.held_at.split('T')[1].slice(0,5) : '';
        html += `<div class="card lesson-row">
          <div class="lesson-info">
            <div class="lesson-title">${time ? time+' ' : ''}${ESC(l.subject_name)} (${ESC(l.group_name)})</div>
            <div class="lesson-sub">${statusBadge(l.status)} • отмечено: ${l.present_count}, с оценкой: ${l.graded_count}</div>
          </div>
          <button class="btn btn-primary btn-sm" onclick="openLesson(${l.id})">Открыть</button>
        </div>`;
      }
    }
    html += `<div class="flex gap-10 mt-12">
      <button class="btn btn-success btn-block" onclick="addLessonDialog()">+ ДОБАВИТЬ</button>
      <button class="btn btn-primary btn-block" onclick="exportIcs()">ICS</button>
    </div></div>`;
    app.innerHTML = html;
  } catch(e) { notify('Ошибка: '+e.message); }
}

async function openLesson(lessonId) {
  location.hash = '#lesson';
  await new Promise(r => setTimeout(r, 50));
  if (window._pageLesson) window._pageLesson.lessonId = lessonId;
}

async function addLessonDialog() {
  try {
    const subjects = await apiGet('/api/subjects');
    if (!subjects.length) { notify('Сначала добавьте предмет.'); return; }
    const opts = subjects.map((s,i) =>
      `<option value="${i}">${ESC(s.name)} (${ESC(s.group_name)})</option>`).join('');
    const now = new Date();
    const time = String(now.getHours()).padStart(2,'0')+':'+String(now.getMinutes()).padStart(2,'0');
    popup('Новое занятие',
      `<label>Предмет</label><select id="dlg-subj">${opts}</select>
       <label>Время (ЧЧ:ММ)</label><input id="dlg-time" value="${time}">`,
      [{ text:'Отмена' }, { text:'Добавить', cls:'btn-success', cb: async () => {
        const idx = +$id('dlg-subj').value;
        const heldAt = new Date().toISOString().slice(0,10)+'T'+$id('dlg-time').value+':00';
        await apiPost('/api/lessons', { subject_id: subjects[idx].id, held_at: heldAt, status:'held' });
        notify('Занятие добавлено');
        renderToday();
      }}]);
  } catch(e) { notify('Ошибка: '+e.message); }
}

async function exportIcs() {
  try {
    const r = await fetch('/api/export/ics');
    const blob = await r.blob();
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = 'schedule.ics'; a.click();
    notify('Расписание выгружено');
  } catch(e) { notify('Ошибка: '+e.message); }
}

// ------ PAGE: add-subject
async function renderAddSubject() {
  const app = $id('app');
  try {
    const groups = await apiGet('/api/groups');
    const groupOpts = groups.map(g => `<option value="${ESC(g.name)}">${ESC(g.name)}</option>`).join('');
    const newGroupOpt = '<option value="__new__">➕ Новая группа…</option>';
    app.innerHTML = `<div class="page active" id="page-add-subject">
      ${header('Новый предмет', 'home')}
      <label>Название предмета</label><input id="as-name">
      <label>План (в занятиях)</label><input id="as-planned" type="number" value="0" min="0">
      <label>Группа</label><select id="as-group">${groupOpts}${newGroupOpt}</select>
      <div id="as-new-group-wrap" style="display:none">
        <label>Название новой группы</label><input id="as-new-group">
      </div>
      <div id="as-status" class="text-sm text-muted mt-8"></div>
      <div class="flex gap-10 mt-12">
        <button class="btn btn-muted btn-block" onclick="go('home')">Назад</button>
        <button class="btn btn-success btn-block" onclick="saveSubject()">Сохранить</button>
      </div>
    </div>`;
    S('#as-group').onchange = () => {
      S('#as-new-group-wrap').style.display = S('#as-group').value === '__new__' ? 'block' : 'none';
    };
  } catch(e) { notify('Ошибка: '+e.message); }
}

async function saveSubject() {
  const name = S('#as-name').value.trim();
  const planned = parseInt(S('#as-planned').value) || 0;
  let group = S('#as-group').value;
  if (group === '__new__') {
    group = S('#as-new-group').value.trim();
    if (!group) { notify('Укажите название группы.'); return; }
  }
  if (!name) { notify('Укажите название предмета.'); return; }
  try {
    await apiPost('/api/subjects', { name, planned, group });
    notify('Предмет создан');
    go('students?group='+encodeURIComponent(group));
  } catch(e) { notify('Ошибка: '+e.message); }
}

// ------ PAGE: students
async function renderStudents() {
  const app = $id('app');
  const group = new URLSearchParams(location.hash.split('?')[1]).get('group') || '';
  try {
    const students = await apiGet('/api/students?group='+encodeURIComponent(group));
    const existing = students.map(s => `<div style="font-size:14px;padding:4px 0">${ESC(s.name)}</div>`).join('');
    app.innerHTML = `<div class="page active" id="page-students">
      ${header('Студенты группы '+group, 'home')}
      <div class="card">
        <div class="text-sm text-muted mb-8">Уже в группе (${students.length}):</div>
        ${existing || '<div class="text-sm text-muted">— пока никого —</div>'}
      </div>
      <label>Добавить студентов (каждый с новой строки)</label>
      <textarea id="st-bulk" rows="4" placeholder="Иванов Иван\nПетров Пётр\n…"></textarea>
      <div id="st-status" class="text-sm text-muted mt-8"></div>
      <div class="flex gap-10 mt-12">
        <button class="btn btn-muted btn-block" onclick="go('home')">На главный</button>
        <button class="btn btn-success btn-block" onclick="saveStudents('${ESC(group)}')">Добавить</button>
      </div>
    </div>`;
  } catch(e) { notify('Ошибка: '+e.message); }
}

async function saveStudents(group) {
  const text = S('#st-bulk').value;
  const names = text.split('\n').map(s => s.trim()).filter(Boolean);
  if (!names.length) { notify('Введите хотя бы одного студента.'); return; }
  try {
    const data = await apiPost('/api/students/bulk', { group, names });
    notify(`Добавлено новых: ${data.added}`);
    renderStudents();
  } catch(e) { notify('Ошибка: '+e.message); }
}

// ------ PAGE: lesson
const ATT_CYCLE = ['absent','present',5,4,3,2];
const ATT_CYCLE_LEN = ATT_CYCLE.length;
const ATT_LABELS = {
  absent: 'отсутствует', present: '✓ присутствует',
  5: '✓ оценка: 5', 4: '✓ оценка: 4', 3: '✓ оценка: 3', 2: '✓ оценка: 2'
};
const ATT_CLS = { absent:'', present:'present', 5:'grade-5', 4:'grade-4', 3:'grade-3', 2:'grade-2' };

window._pageLesson = { lessonId: null, rows: [] };

async function renderLesson() {
  const lid = window._pageLesson.lessonId;
  const app = $id('app'); app.innerHTML = '<div class="spinner"></div>';
  try {
    const lesson = await apiGet('/api/lessons/'+lid);
    if (!lesson || lesson.error) { notify('Занятие не найдено'); go('today'); return; }
    await apiPatch('/api/lessons/'+lid+'/status', { status:'held' });
    const students = await apiGet('/api/students?group='+encodeURIComponent(lesson.group_name));
    const saved = await apiGet('/api/lessons/'+lid+'/attendance');
    let html = `<div class="page active" id="page-lesson">
      ${header(lesson.subject_name+' ('+lesson.group_name+')', 'today')}
      <div class="text-xs text-muted mb-8">Нажимайте на ФИО: отсутствует → ✓ → оценка 5→4→3→2 → отсутствует</div>`;
    const rows = [];
    for (const st of students) {
      const savedState = saved[st.id];
      let idx = 0;
      if (savedState && savedState.present) {
        if (savedState.grade != null) {
          idx = ATT_CYCLE.indexOf(Number(savedState.grade));
          if (idx < 0) idx = 1;
        } else idx = 1;
      }
      rows.push({ student: st, idx });
      const cls = ATT_CLS[ATT_CYCLE[idx]] || '';
      html += `<div class="attendance-row ${cls}" id="ar-${st.id}" onclick="cycleAtt(${st.id})">
        <span class="attendance-name">${ESC(st.name)}</span>
        <span class="attendance-status">${ATT_LABELS[ATT_CYCLE[idx]]}</span>
      </div>`;
    }
    window._pageLesson.rows = rows;
    html += `<button class="btn btn-success btn-block mt-12" onclick="finishLesson()">Готово</button></div>`;
    app.innerHTML = html;
  } catch(e) { notify('Ошибка: '+e.message); }
}

function cycleAtt(studentId) {
  const rows = window._pageLesson.rows;
  const row = rows.find(r => r.student.id === studentId);
  if (!row) return;
  row.idx = (row.idx + 1) % ATT_CYCLE_LEN;
  const st = ATT_CYCLE[row.idx];
  const el = $id('ar-'+studentId);
  if (el) {
    el.className = 'attendance-row ' + (ATT_CLS[st] || '');
    S('.attendance-status', el).textContent = ATT_LABELS[st] || '';
  }
  const lid = window._pageLesson.lessonId;
  const present = st !== 'absent';
  const grade = typeof st === 'number' ? st : null;
  apiPost('/api/lessons/'+lid+'/attendance', { student_id: studentId, present, grade }).catch(()=>{});
}

async function finishLesson() {
  const lid = window._pageLesson.lessonId;
  const rows = window._pageLesson.rows;
  for (const row of rows) {
    const st = ATT_CYCLE[row.idx];
    await apiPost('/api/lessons/'+lid+'/attendance', {
      student_id: row.student.id,
      present: st !== 'absent',
      grade: typeof st === 'number' ? st : null
    }).catch(()=>{});
  }
  notify('Занятие и отметки сохранены');
  go('today');
}

// ------ PAGE: gradebook
async function renderGradebook() {
  const app = $id('app'); app.innerHTML = '<div class="spinner"></div>';
  try {
    const subjects = await apiGet('/api/subjects');
    if (!subjects.length) {
      app.innerHTML = `<div class="page active">${header('Ведомость','home')}
        <div class="card text-center text-muted" style="padding:30px">Предметов пока нет.</div></div>`;
      return;
    }
    const labelled = subjects.map(s => ({ label: s.name+' ('+s.group_name+')', id: s.id }));
    const opts = labelled.map((l,i) => `<option value="${i}">${ESC(l.label)}</option>`).join('');
    app.innerHTML = `<div class="page active" id="page-gradebook">
      ${header('Ведомость','home')}
      <select id="gb-subj" onchange="renderGradebookSubject()">${opts}</select>
      <div id="gb-content"></div>
    </div>`;
    renderGradebookSubject();
  } catch(e) { notify('Ошибка: '+e.message); }
}

async function renderGradebookSubject() {
  const sel = $id('gb-subj'); if (!sel) return;
  const content = $id('gb-content'); content.innerHTML = '<div class="spinner"></div>';
  const subjects = await apiGet('/api/subjects');
  const idx = +sel.value;
  const subj = subjects[idx]; if (!subj) return;
  try {
    const data = await apiGet('/api/subjects/'+subj.id+'/gradebook');
    const summary = data.summary;
    const gb = data.gradebook;
    let html = '';
    if (summary) {
      html += `<div class="card">
        <div>Занятия: план <b>${summary.planned}</b> • проведено <b>${summary.held}</b> • осталось <b>${summary.remaining}</b></div>
      </div>`;
    }
    const avgs = gb.filter(d => d.avg_grade != null).map(d => Number(d.avg_grade));
    const overall = avgs.length ? (avgs.reduce((a,b)=>a+b,0)/avgs.length).toFixed(2) : '—';
    html += `<div class="card">Средний балл по предмету: <b>${overall}</b></div>`;
    const graded = gb.filter(d => d.avg_grade != null);
    if (graded.length) {
      const maxBar = Math.max(...graded.map(d => Number(d.avg_grade)));
      const GRADE_COLORS = {5:'#339933',4:'#4a7fc4',3:'#d9a633',2:'#bf4040'};
      html += `<div class="card"><b style="font-size:15px">Средний балл по студентам</b>
        <div class="bar-group">`;
      for (const d of graded) {
        const avg = Number(d.avg_grade);
        const pct = avg > 2 ? (avg-2)/3*100 : 0;
        const color = GRADE_COLORS[Math.round(avg)] || '#888';
        html += `<div class="bar-wrap">
          <div class="bar-value">${avg.toFixed(2)}</div>
          <div class="bar" style="height:80px">
            <div class="bar-fill" style="height:${pct}%;background:${color}"></div>
          </div>
          <div class="bar-label">${ESC(d.name.split(' ')[0])}</div>
        </div>`;
      }
      html += `</div></div>`;
    }
    html += `<div class="card"><b style="font-size:15px">Пофамильно</b>
      <div class="table-header">
        <div class="table-col">ФИО</div>
        <div class="table-col">Ср. балл</div>
        <div class="table-col">Оценок</div>
        <div class="table-col">Прис./Отс.</div>
      </div>`;
    for (const d of gb) {
      const avg = d.avg_grade != null ? Number(d.avg_grade).toFixed(2) : '—';
      html += `<div class="table-row">
        <div class="table-col">${ESC(d.name)}</div>
        <div class="table-col">${avg}</div>
        <div class="table-col">${d.grades_count||0}</div>
        <div class="table-col">${d.present_count||0}/${d.absent_count||0}</div>
      </div>`;
    }
    html += `</div>`;
    content.innerHTML = html;
  } catch(e) { content.innerHTML = '<div class="text-muted">Ошибка загрузки</div>'; }
}


