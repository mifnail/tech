const API = '';
const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);

function notify(msg) { const n = $('#notif'); n.textContent = msg; n.style.display = 'block'; setTimeout(() => n.style.display = 'none', 2500); }

function api(method, path, body) {
  return fetch(API + path, {
    method,
    headers: body ? {'Content-Type': 'application/json'} : {},
    body: body ? JSON.stringify(body) : undefined
  }).then(r => r.ok ? r.json() : r.json().then(e => { throw e; }));
}

function nav() {
  const pages = [
    {hash:'#home', label:'Главная'}, {hash:'#today', label:'Сегодня'},
    {hash:'#schedule', label:'Расписание'}, {hash:'#subjects', label:'Предметы'}
  ];
  const active = location.hash.split('?')[0] || '#home';
  return `<div class="nav">${pages.map(p => `<a href="${p.hash}" class="${active === p.hash ? 'active' : ''}">${p.label}</a>`).join('')}</div>`;
}

function router() {
  const hash = location.hash || '#home';
  if (hash === '#home') renderHome();
  else if (hash.startsWith('#today')) {
    const params = new URLSearchParams(hash.split('?')[1] || '');
    renderToday(params.get('subject') || null);
  }
  else if (hash.startsWith('#schedule')) renderSchedule();
  else if (hash.startsWith('#subjects')) renderSubjects();
  else if (hash.startsWith('#subject/')) renderSubject(hash.split('/')[1]);
  else if (hash.startsWith('#lesson/')) renderLesson(hash.split('/')[1]);
  else if (hash.startsWith('#students/')) renderStudents(hash.split('/')[1]);
  else renderHome();
}

window.addEventListener('hashchange', router);

// ===== HOME =====
async function renderHome() {
  const subjects = await api('GET', '/api/subjects');
  const groups = await api('GET', '/api/groups');
  const today = await api('GET', '/api/schedule/today');

  let html = nav();
  html += `<h1>Учёт занятий</h1>`;

  html += `<div class="card" style="cursor:pointer" onclick="location='#today'">
    <div class="card-title">Сегодня (${today.date})</div>
    <div class="card-sub">${today.schedule.length} пар · ${today.lessons.length} занятий</div>
  </div>`;

  html += `<h2>Предметы</h2>`;
  for (const s of subjects) {
    const pct = s.total_hours > 0 ? Math.round(s.held_lessons / s.total_hours * 100) : 0;
    html += `<div class="card" style="cursor:pointer" onclick="location='#today?subject=${s.id}'">
      <div class="card-title">${s.name}</div>
      <div class="card-sub">${s.group_name} · ${s.held_lessons}/${s.total_hours} (осталось ${s.remaining})</div>
      <div class="bar"><div class="bar-fill" style="width:${pct}%"></div></div>
    </div>`;
  }

  if (groups.length) {
    html += `<h2>Группы</h2><div class="grid-2">`;
    for (const g of groups) {
      html += `<div class="card" style="cursor:pointer;text-align:center" onclick="location='#students/${g.id}'">
        <div class="card-title">${g.name}</div>
      </div>`;
    }
    html += `</div>`;
  }

  html += `<button class="btn btn-primary" onclick="location='#subjects'" style="margin-top:8px">+ Добавить предмет</button>`;
  $('#app').innerHTML = html;
}

// ===== TODAY (with optional subject filter) =====
async function renderToday(subjectId) {
  const data = await api('GET', '/api/schedule/today');
  const subjects = await api('GET', '/api/subjects');

  // Filter by subject if specified
  let schedule = data.schedule;
  let lessons = data.lessons;
  let currentSubject = null;

  if (subjectId) {
    currentSubject = subjects.find(s => s.id == subjectId);
    schedule = data.schedule.filter(e => e.subject_id == subjectId);
    lessons = data.lessons.filter(l => l.subject_id == subjectId);
  }

  let html = nav();
  const title = currentSubject ? `${currentSubject.name} — сегодня` : 'Сегодня';
  html += `<h1>${title}</h1>`;
  html += `<div class="card"><div class="card-title">${data.date}</div>`;
  html += `<div class="card-sub">День ${data.day_of_week}</div></div>`;

  if (currentSubject) {
    html += `<button class="btn btn-muted btn-sm" style="margin-bottom:8px" onclick="location='#subject/${subjectId}'">📋 Журнал предмета</button>`;
    html += `<button class="btn btn-muted btn-sm" style="margin-bottom:8px" onclick="location='#today'">📅 Все предметы</button>`;
  }

  if (schedule.length) {
    html += `<h2>Расписание</h2>`;
    for (const e of schedule) {
      const existing = lessons.find(l => l.subject_id === e.subject_id && l.status !== 'free');
      if (existing) {
        html += `<div class="card" style="cursor:pointer" onclick="location='#lesson/${existing.id}'">
          <div class="card-title">Пара ${e.lesson_number} · ${e.subject_name}</div>
          <div class="card-sub">${e.group_name} · <span class="badge badge-held">Проведено</span></div>
        </div>`;
      } else {
        const existingFree = lessons.find(l => l.subject_id === e.subject_id && l.status === 'free');
        if (existingFree) {
          html += `<div class="card" style="cursor:pointer" onclick="lessonDialog(${e.subject_id}, '${e.group_name}', ${e.id}, true)">
            <div class="card-title">Пара ${e.lesson_number} · ${e.subject_name}</div>
            <div class="card-sub">${e.group_name} · <span class="badge badge-cancelled">СВОБОДНО</span></div>
          </div>`;
        } else {
          html += `<div class="card">
            <div class="card-title">Пара ${e.lesson_number} · ${e.subject_name}</div>
            <div class="card-sub">${e.group_name}</div>
            <button class="btn btn-success btn-sm" style="margin-top:8px" onclick="lessonDialog(${e.subject_id}, '${e.group_name}')">Начать занятие</button>
          </div>`;
        }
      }
    }
  }

  if (lessons.length && !subjectId) {
    const otherLessons = lessons.filter(l => {
      return !schedule.some(s => s.subject_id === l.subject_id);
    });
    if (otherLessons.length) {
      html += `<h2>Другие занятия</h2>`;
      for (const l of otherLessons) {
        const cls = l.status === 'free' ? 'badge-cancelled' : 'badge-held';
        const label = l.status === 'free' ? 'СВОБОДНО' : 'Проведено';
        html += `<div class="card" style="cursor:pointer" onclick="location='#lesson/${l.id}'">
          <div class="card-title">${l.actual_subject_name}</div>
          <div class="card-sub">${l.group_name} · <span class="badge ${cls}">${label}</span>
            ${l.planned_subject !== l.actual_subject_name && l.status !== 'free' ? '· Замена: ' + l.planned_subject : ''}</div>
        </div>`;
      }
    }
  }

  if (!schedule.length && !lessons.length) {
    html += `<div class="card"><div class="card-sub">${currentSubject ? 'Сегодня пар по этому предмету нет' : 'Сегодня пар нет'}</div></div>`;
  }

  if (!subjectId) {
    html += `<button class="btn btn-primary btn-sm" style="margin-top:8px" onclick="showCustomLesson()">Создать занятие вручную</button>`;
  }

  if (currentSubject) {
    const pct = currentSubject.total_hours > 0 ? Math.round(currentSubject.held_lessons / currentSubject.total_hours * 100) : 0;
    html += `<div class="card" style="margin-top:8px">
      <div class="card-title">Прогресс</div>
      <div class="card-sub">${currentSubject.held_lessons}/${currentSubject.total_hours} (осталось ${currentSubject.remaining})</div>
      <div class="bar"><div class="bar-fill" style="width:${pct}%"></div></div>
    </div>`;
  }

  $('#app').innerHTML = html;
}

// ===== LESSON DIALOG =====
window.lessonDialog = async function(subjectId, groupName, scheduleEntryId, isFree) {
  const subs = await api('GET', `/api/subjects/${subjectId}/substitution-list`);
  const opts = subs.map(s => `<option value="${s.id}">${s.name}</option>`).join('');

  if (isFree) {
    showPopup(`
      <h2>Занятие · СВОБОДНО</h2>
      <p style="margin-bottom:12px;color:#86868b">Группа ${groupName}</p>
      <div class="grid-2">
        <button class="btn btn-success" onclick="createHeldLesson(${subjectId}, ${subjectId})">Провести</button>
        <button class="btn btn-muted" onclick="closePopup()">Закрыть</button>
      </div>
    `);
    return;
  }

  showPopup(`
    <h2>Начать занятие</h2>
    <p style="margin-bottom:12px;color:#86868b">Группа ${groupName}</p>
    <div class="grid-2">
      <button class="btn btn-success" onclick="createHeldLesson(${subjectId}, ${subjectId})">✅ Проведено</button>
      <button class="btn btn-warning" onclick="showSubstitution(${subjectId})">🔄 Замена</button>
    </div>
  `);
}

window.createHeldLesson = async function(subjectId, actualSubjectId) {
  const result = await api('POST', '/api/lessons', {
    subject_id: subjectId,
    actual_subject_id: actualSubjectId,
    status: 'held'
  });
  closePopup();
  location = `#lesson/${result.id}`;
}

window.showSubstitution = async function(subjectId) {
  const subs = await api('GET', `/api/subjects/${subjectId}/substitution-list`);
  const opts = subs.map(s => `<option value="${s.id}">${s.name}</option>`).join('');
  showPopup(`
    <h2>Замена</h2>
    <p style="margin-bottom:8px">Выберите предмет:</p>
    <select id="subst-subject">${opts}</select>
    <div class="grid-2" style="margin-top:8px">
      <button class="btn btn-success" onclick="createSubstitution(${subjectId})">Заменить</button>
      <button class="btn btn-muted" onclick="closePopup()">Отмена</button>
    </div>
  `);
}

window.createSubstitution = async function(subjectId) {
  const actualSubjectId = +$('#subst-subject').value;
  const isFree = (await api('GET', '/api/subjects')).find(s => s.id === actualSubjectId);
  const result = await api('POST', '/api/lessons', {
    subject_id: subjectId,
    actual_subject_id: actualSubjectId,
    status: isFree ? 'free' : 'held'
  });
  closePopup();
  notify(isFree ? 'Занятие отменено (СВОБОДНО)' : 'Замена выполнена');
  location = `#today?subject=${subjectId}`;
}

window.showCustomLesson = function() {
  api('GET', '/api/subjects?include_free=1').then(subjects => {
    let filtered = subjects.filter(s => s.name !== 'СВОБОДНО');
    let opts = filtered.map(s => `<option value="${s.id}">${s.name} (${s.group_name})</option>`).join('');
    showPopup(`
      <h2>Создать занятие</h2>
      <select id="custom-subject">${opts}</select>
      <label><input type="checkbox" id="custom-substitute"> Замена</label>
      <select id="custom-actual" style="display:none">${opts}</select>
      <button class="btn btn-primary btn-sm" onclick="createCustomLesson()">Создать</button>
    `);
    $('#custom-substitute').onchange = function() {
      $('#custom-actual').style.display = this.checked ? 'block' : 'none';
    };
  });
}

window.createCustomLesson = async function() {
  const subjectId = +$('#custom-subject').value;
  const actualId = $('#custom-substitute').checked ? +$('#custom-actual').value : subjectId;
  const result = await api('POST', '/api/lessons', {
    subject_id: subjectId,
    actual_subject_id: actualId || subjectId,
    status: 'held'
  });
  notify('Занятие создано');
  closePopup();
  renderToday();
}

// ===== SUBJECTS (manage) =====
async function renderSubjects() {
  const groups = await api('GET', '/api/groups');
  const subjects = await api('GET', '/api/subjects');

  let html = nav();
  html += `<h1>Предметы</h1>`;
  html += `<button class="btn btn-primary" onclick="showAddSubject()">+ Добавить предмет</button>`;

  if (!groups.length) {
    html += `<div class="card" style="margin-top:12px"><div class="card-sub">Сначала создайте группу</div>`;
    html += `<button class="btn btn-primary btn-sm" style="margin-top:8px" onclick="showAddGroup()">+ Создать группу</button></div>`;
  }

  for (const s of subjects) {
    const pct = s.total_hours > 0 ? Math.round(s.held_lessons / s.total_hours * 100) : 0;
    html += `<div class="card" style="cursor:pointer" onclick="location='#subject/${s.id}'">
      <div class="card-title">${s.name}</div>
      <div class="card-sub">${s.group_name} · ${s.held_lessons}/${s.total_hours} · осталось ${s.remaining}</div>
      <div class="bar"><div class="bar-fill" style="width:${pct}%"></div></div>
    </div>`;
  }

  html += `<button class="btn btn-muted btn-sm" style="margin-top:8px" onclick="showAddGroup()">+ Управление группами</button>`;
  $('#app').innerHTML = html;
}

window.showAddSubject = async function() {
  const groups = await api('GET', '/api/groups');
  const groupOpts = groups.map(g => `<option value="${g.id}">${g.name}</option>`).join('');
  showPopup(`
    <h2>Новый предмет</h2>
    <input id="subj-name" placeholder="Название предмета">
    <input id="subj-hours" type="number" placeholder="Всего часов" min="1">
    <select id="subj-group">${groupOpts}</select>
    <button class="btn btn-primary" onclick="createSubject()">Создать</button>
  `);
}

window.createSubject = async function() {
  const name = $('#subj-name').value;
  const hours = +$('#subj-hours').value;
  const groupId = +$('#subj-group').value;
  if (!name || !hours) return notify('Заполните все поля');
  await api('POST', '/api/subjects', { name, total_hours: hours, group_id: groupId });
  notify('Предмет создан');
  closePopup();
  renderSubjects();
}

window.showAddGroup = function() {
  showPopup(`
    <h2>Новая группа</h2>
    <input id="group-name" placeholder="Название группы (например ИС-11)">
    <button class="btn btn-primary" onclick="createGroup()">Создать</button>
  `);
}

window.createGroup = async function() {
  const name = $('#group-name').value;
  if (!name) return notify('Введите название');
  await api('POST', '/api/groups', { name });
  notify('Группа создана');
  closePopup();
  router();
}

// ===== SUBJECT (gradebook + lesson log) =====
async function renderSubject(subjectId) {
  const data = await api('GET', `/api/subjects/${subjectId}/gradebook`);
  const avg = await api('GET', `/api/reports/average/${subjectId}`);
  const allLessons = await api('GET', `/api/subjects/${subjectId}/lessons`);

  let html = nav();

  if (data.summary) {
    const s = data.summary;
    const pct = s.total_hours > 0 ? Math.round(s.held_lessons / s.total_hours * 100) : 0;
    html += `<h1>${s.name}</h1>`;
    html += `<div class="card"><div class="grid-2">
      <div class="stat"><div class="stat-value">${s.held_lessons}</div><div class="stat-label">Проведено</div></div>
      <div class="stat"><div class="stat-value">${s.remaining}</div><div class="stat-label">Осталось</div></div>
      <div class="stat"><div class="stat-value">${s.average_grade || '-'}</div><div class="stat-label">Ср. балл</div></div>
      <div class="stat"><div class="stat-value">${s.total_students}</div><div class="stat-label">Студентов</div></div>
    </div>
    <div class="bar"><div class="bar-fill" style="width:${pct}%"></div></div>
    <div class="card-sub" style="margin-top:8px">Группа: ${s.group_name}</div>`;
    html += `<div class="grid-2" style="margin-top:8px">
      <button class="btn btn-primary btn-sm" onclick="location='#today?subject=${subjectId}'">На сегодня</button>
      <button class="btn btn-muted btn-sm" onclick="location='#students/${s.group_id}'">Студенты</button>
    </div>`;
    html += `</div>`;
  }

  if (avg.length) {
    const maxAvg = Math.max(...avg.map(a => a.average));
    html += `<h2>Средний балл</h2><div class="card">`;
    for (const a of avg) {
      const pct = maxAvg > 0 ? (a.average / maxAvg * 100) : 0;
      html += `<div style="margin-bottom:8px">
        <div style="font-size:13px">${a.last_name} ${a.first_name}</div>
        <div class="chart-bar"><div class="chart-bar-fill" style="width:${pct}%">${a.average}</div></div>
      </div>`;
    }
    html += `</div>`;
  }

  // All lessons log
  html += `<h2>Все занятия</h2>`;
  if (allLessons.length) {
    html += `<div class="card">`;
    for (const l of allLessons) {
      const cls = l.status === 'free' ? 'badge-cancelled' : 'badge-held';
      const label = l.status === 'free' ? 'СВОБОДНО' : 'Проведено';
      html += `<div class="row" style="cursor:pointer" onclick="location='#lesson/${l.id}'">
        <div style="flex:1">
          <div style="font-weight:500">${l.date}</div>
          <div><span class="badge ${cls}">${label}</span> ${l.actual_subject_name !== l.planned_subject && l.status !== 'free' ? '· Замена' : ''}</div>
        </div>
        <span style="color:#007aff;font-size:20px">›</span>
      </div>`;
    }
    html += `</div>`;
  } else {
    html += `<div class="card"><div class="card-sub">Занятий пока нет</div></div>`;
  }

  // Grade table
  html += `<h2>Ведомость</h2><div class="card" style="overflow-x:auto">`;
  html += `<table style="width:100%;font-size:13px;border-collapse:collapse">`;
  html += `<tr><th style="text-align:left;padding:4px">Студент</th><th style="padding:4px">Оценка</th><th style="padding:4px">Дата</th></tr>`;
  for (const r of data.grades || []) {
    const gradeClass = gradeColorClass(r.grade);
    html += `<tr><td style="padding:4px">${r.last_name} ${r.first_name}</td>
      <td style="padding:4px;text-align:center"><span class="grade grade-${gradeClass}" style="display:inline-flex;width:28px;height:28px">${r.grade}</span></td>
      <td style="padding:4px">${r.date || ''}</td></tr>`;
  }
  html += `</table></div>`;

  html += `<button class="btn btn-muted btn-sm" style="margin-top:8px" onclick="history.back()">Назад</button>`;
  $('#app').innerHTML = html;
}

function gradeColorClass(grade) {
  if (grade === '0' || grade === 'present') return 'present';
  if (grade === '5') return '5';
  if (grade === '4') return '4';
  if (grade === '3') return '3';
  if (grade === '2') return '2';
  if (grade === 'absent' || grade === 'н/я') return 'absent';
  return 'none';
}

// ===== LESSON (attendance with arrows) =====
let _lessonSubjectId = null;

async function renderLesson(lessonId) {
  const data = await api('GET', `/api/lessons/${lessonId}/attendance`);
  const adjacent = await api('GET', `/api/lessons/${lessonId}/adjacent`);

  let html = nav();
  if (!data.lesson) { html += `<div class="card">Занятие не найдено</div>`; $('#app').innerHTML = html; return; }

  const l = data.lesson;
  _lessonSubjectId = l.subject_id;

  // Navigation arrows
  html += `<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">`;
  if (adjacent.prev_id) {
    html += `<button class="btn btn-muted btn-sm" style="width:auto;padding:8px 16px" onclick="location='#lesson/${adjacent.prev_id}'">‹</button>`;
  } else {
    html += `<div style="width:44px"></div>`;
  }
  html += `<div style="flex:1;text-align:center">`;
  if (l.status === 'free') {
    html += `<h1 style="margin:0">СВОБОДНО</h1>`;
  } else {
    html += `<h1 style="margin:0">${l.actual_subject_name}</h1>`;
  }
  html += `</div>`;
  if (adjacent.next_id) {
    html += `<button class="btn btn-muted btn-sm" style="width:auto;padding:8px 16px" onclick="location='#lesson/${adjacent.next_id}'">›</button>`;
  } else {
    html += `<div style="width:44px"></div>`;
  }
  html += `</div>`;

  html += `<div class="card">
    <div class="card-sub">${l.date} · ${l.group_name}</div>
    ${l.planned_subject !== l.actual_subject_name && l.status !== 'free' ? `<div class="badge badge-warning">Замена вместо: ${l.planned_subject}</div>` : ''}
    ${l.status === 'free' ? `<div class="badge badge-cancelled">Занятие отменено</div>` : `<span class="badge badge-held">Проведено</span>`}
  </div>`;

  if (l.status === 'free') {
    html += `<button class="btn btn-muted btn-sm" onclick="location='#subject/${_lessonSubjectId}'">Журнал</button>`;
    $('#app').innerHTML = html;
    return;
  }

  // Attendance
  const attMap = {};
  for (const a of data.attendance) attMap[a.student_id] = a.grade;

  html += `<h2>Отметки</h2><div class="card">`;
  for (const s of data.students || []) {
    const grade = attMap[s.id] || null;
    const cls = gradeColorClass(grade);
    const label = (grade === null || grade === '') ? '—' : grade;
    const bgStyle = grade === null ? '' : `background:${gradeBgColor(grade)}`;
    html += `<div class="attendance-row ${grade ? 'marked' : ''}" onclick="cycleGrade(${lessonId}, ${s.id}, '${grade || ''}')" style="${bgStyle}">
      <div class="grade grade-${cls}">${label}</div>
      <div style="flex:1"><div style="font-weight:500">${s.last_name} ${s.first_name}</div><div style="font-size:12px;color:#86868b">${s.middle_name || ''}</div></div>
    </div>`;
  }
  html += `</div>`;

  html += `<div style="display:flex;gap:8px;margin-top:8px">
    <button class="btn btn-success" style="flex:1" onclick="location='#subject/${_lessonSubjectId}'">Готово</button>
  </div>`;
  $('#app').innerHTML = html;
}

function gradeBgColor(grade) {
  if (grade === '0' || grade === 'present') return '#e8f5e9';
  if (grade === '5') return '#ffebee';
  if (grade === '4') return '#e3f2fd';
  if (grade === '3') return '#fff8e1';
  if (grade === '2') return '#e0e0e0';
  return '';
}

window.cycleGrade = async function(lessonId, studentId, currentGrade) {
  const grades = ['', '0', '5', '4', '3', '2'];
  const cleanGrade = currentGrade || '';
  const idx = grades.indexOf(cleanGrade);
  const next = grades[(idx + 1) % grades.length];
  const grade = next || '0';
  await api('POST', `/api/lessons/${lessonId}/attendance`, { student_id: studentId, grade });
  renderLesson(lessonId);
}

// ===== SCHEDULE =====
async function renderSchedule() {
  const schedule = await api('GET', '/api/schedule');
  const subjects = await api('GET', '/api/subjects');
  const days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];
  const weekTypes = ['Каждую', 'Числитель', 'Знаменатель'];

  let html = nav();
  html += `<h1>Расписание</h1>`;
  html += `<button class="btn btn-primary btn-sm" onclick="showAddScheduleEntry()">+ Добавить пару</button>`;

  for (const d of days) {
    const entries = schedule.filter(e => e.day_of_week === days.indexOf(d) + 1);
    if (!entries.length) continue;
    html += `<h2>${d}</h2>`;
    for (const e of entries) {
      html += `<div class="card">
        <div class="row">
          <div style="flex:1">
            <div class="card-title">Пара ${e.lesson_number}</div>
            <div class="card-sub">${e.subject_name} · ${e.group_name} · ${weekTypes[e.week_type] || 'Каждую'}</div>
          </div>
          <button class="btn btn-danger btn-sm" style="width:auto" onclick="deleteScheduleEntry(${e.id})">✕</button>
        </div>
      </div>`;
    }
  }

  html += `<button class="btn btn-muted btn-sm" style="margin-top:8px" onclick="history.back()">Назад</button>`;
  $('#app').innerHTML = html;
}

window.showAddScheduleEntry = async function() {
  const subjects = await api('GET', '/api/subjects');
  const opts = subjects.map(s => `<option value="${s.id}">${s.name} (${s.group_name})</option>`).join('');
  showPopup(`
    <h2>Добавить в расписание</h2>
    <select id="sch-day">${[1,2,3,4,5,6].map(d => `<option value="${d}">${['Пн','Вт','Ср','Чт','Пт','Сб'][d-1]}</option>`).join('')}</select>
    <input id="sch-num" type="number" placeholder="Номер пары" min="1" max="8">
    <select id="sch-subject">${opts}</select>
    <select id="sch-week">
      <option value="0">Каждую неделю</option>
      <option value="1">Числитель</option>
      <option value="2">Знаменатель</option>
    </select>
    <button class="btn btn-primary" onclick="createScheduleEntry()">Добавить</button>
  `);
}

window.createScheduleEntry = async function() {
  await api('POST', '/api/schedule', {
    day_of_week: +$('#sch-day').value,
    lesson_number: +$('#sch-num').value,
    subject_id: +$('#sch-subject').value,
    week_type: +$('#sch-week').value
  });
  notify('Добавлено в расписание');
  closePopup();
  renderSchedule();
}

window.deleteScheduleEntry = async function(id) {
  if (!confirm('Удалить?')) return;
  await api('DELETE', `/api/schedule/${id}`);
  renderSchedule();
}

// ===== STUDENTS =====
async function renderStudents(groupId) {
  const students = await api('GET', `/api/students?group_id=${groupId}`);
  const groups = await api('GET', '/api/groups');
  const group = groups.find(g => g.id == groupId);

  let html = nav();
  html += `<h1>${group ? group.name : 'Студенты'}</h1>`;
  html += `<button class="btn btn-primary btn-sm" onclick="showAddStudents(${groupId})">+ Добавить студентов</button>`;

  html += `<div class="card">`;
  for (const s of students) {
    html += `<div class="row">
      <div style="flex:1"><span style="font-weight:500">${s.last_name} ${s.first_name}</span> ${s.middle_name || ''}</div>
    </div>`;
  }
  html += `</div>`;
  html += `<button class="btn btn-muted btn-sm" onclick="history.back()">Назад</button>`;
  $('#app').innerHTML = html;
}

window.showAddStudents = function(groupId) {
  showPopup(`
    <h2>Добавить студентов</h2>
    <textarea id="students-text" placeholder="Иванов Иван Иванович&#10;Петров Петр Петрович&#10;..."></textarea>
    <div style="font-size:12px;color:#86868b">Каждая строка: Фамилия Имя Отчество</div>
    <button class="btn btn-primary btn-sm" onclick="createStudents(${groupId})">Добавить</button>
  `);
}

window.createStudents = async function(groupId) {
  const text = $('#students-text').value.trim();
  if (!text) return notify('Введите данные');
  const students = text.split('\n').filter(Boolean).map(line => {
    const parts = line.trim().split(/\s+/);
    return { last_name: parts[0] || '', first_name: parts[1] || '', middle_name: parts[2] || null };
  }).filter(s => s.last_name && s.first_name);
  await api('POST', '/api/students/bulk', { group_id: groupId, students });
  notify(`Добавлено ${students.length} студентов`);
  closePopup();
  renderStudents(groupId);
}

// ===== POPUP =====
function showPopup(html) {
  closePopup();
  const div = document.createElement('div');
  div.id = 'popup';
  div.className = 'popup';
  div.innerHTML = `<div class="popup-content">${html}</div>`;
  div.onclick = e => { if (e.target === div) closePopup(); };
  document.body.appendChild(div);
}

window.closePopup = function() {
  const p = $('#popup'); if (p) p.remove();
}

// ===== INIT =====
router();
