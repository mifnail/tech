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
  const active = location.hash || '#home';
  return `<div class="nav">${pages.map(p => `<a href="${p.hash}" class="${active === p.hash ? 'active' : ''}">${p.label}</a>`).join('')}</div>`;
}

function router() {
  const hash = location.hash || '#home';
  if (hash === '#home') renderHome();
  else if (hash.startsWith('#today')) renderToday();
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

  // Today summary
  html += `<div class="card" style="cursor:pointer" onclick="location='#today'">
    <div class="card-title">Сегодня (${today.date})</div>
    <div class="card-sub">${today.schedule.length} пар в расписании · ${today.lessons.length} занятий проведено</div>
  </div>`;

  // Subjects progress
  html += `<h2>Предметы</h2>`;
  for (const s of subjects) {
    const pct = s.total_hours > 0 ? Math.round(s.held_lessons / s.total_hours * 100) : 0;
    html += `<div class="card" style="cursor:pointer" onclick="location='#subject/${s.id}'">
      <div class="card-title">${s.name}</div>
      <div class="card-sub">${s.group_name} · ${s.held_lessons}/${s.total_hours} (осталось ${s.remaining})</div>
      <div class="bar"><div class="bar-fill" style="width:${pct}%"></div></div>
    </div>`;
  }

  // Groups quick links
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

// ===== TODAY =====
async function renderToday() {
  const data = await api('GET', '/api/schedule/today');

  let html = nav();
  html += `<h1>Сегодня</h1>`;
  html += `<div class="card"><div class="card-title">${data.date}</div>`;
  html += `<div class="card-sub">День ${data.day_of_week}</div></div>`;

  // Schedule (planned)
  if (data.schedule.length) {
    html += `<h2>Расписание</h2>`;
    for (const e of data.schedule) {
      html += `<div class="card">
        <div class="card-title">Пара ${e.lesson_number}</div>
        <div class="card-sub">${e.subject_name} · ${e.group_name}</div>
        <button class="btn btn-success btn-sm" style="margin-top:8px" onclick="startLesson(${e.subject_id})">Начать занятие</button>
      </div>`;
    }
  }

  // Existing lessons today
  if (data.lessons.length) {
    html += `<h2>Проведённые занятия</h2>`;
    for (const l of data.lessons) {
      html += `<div class="card" style="cursor:pointer" onclick="location='#lesson/${l.id}'">
        <div class="card-title">${l.actual_subject_name}</div>
        <div class="card-sub">${l.group_name} · ${l.planned_subject !== l.actual_subject_name ? 'Замена: ' + l.planned_subject : ''}</div>
      </div>`;
    }
  }

  if (!data.schedule.length && !data.lessons.length) {
    html += `<div class="card"><div class="card-sub">Сегодня пар нет</div></div>`;
  }

  html += `<button class="btn btn-primary btn-sm" style="margin-top:8px" onclick="showCustomLesson()">Создать занятие вручную</button>`;
  $('#app').innerHTML = html;
}

window.startLesson = async function(subjectId) {
  await api('POST', '/api/lessons', { subject_id: subjectId, actual_subject_id: subjectId });
  notify('Занятие создано');
  renderToday();
}

window.showCustomLesson = function() {
  api('GET', '/api/subjects').then(subjects => {
    let opts = subjects.map(s => `<option value="${s.id}">${s.name} (${s.group_name})</option>`).join('');
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
  const actualId = $('#custom-substitute').checked ? +$('#custom-actual').value : null;
  await api('POST', '/api/lessons', { subject_id: subjectId, actual_subject_id: actualId || subjectId });
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

// ===== SUBJECT (gradebook) =====
async function renderSubject(subjectId) {
  const data = await api('GET', `/api/subjects/${subjectId}/gradebook`);
  const avg = await api('GET', `/api/reports/average/${subjectId}`);
  const subj = await api('GET', `/api/subjects?group_id=${data.summary?.group_id || 0}`);
  const current = subj.find(s => s.id == subjectId);

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
    html += `<button class="btn btn-primary btn-sm" style="margin-top:8px" onclick="startLesson(${subjectId})">Начать занятие</button>`;
    html += `<button class="btn btn-muted btn-sm" onclick="location='#students/${s.group_id}'">Студенты группы</button>`;
    html += `</div>`;
  }

  // Average grades chart
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

  // Grade table
  html += `<h2>Ведомость</h2><div class="card" style="overflow-x:auto">`;
  html += `<table style="width:100%;font-size:13px;border-collapse:collapse">`;
  html += `<tr><th style="text-align:left;padding:4px">Студент</th><th style="padding:4px">Оценка</th><th style="padding:4px">Дата</th></tr>`;
  for (const r of data.grades || []) {
    html += `<tr><td style="padding:4px">${r.last_name} ${r.first_name}</td>
      <td style="padding:4px;text-align:center"><span class="grade-${r.grade === 'absent' ? 'absent' : r.grade} grade" style="display:inline-flex;width:28px;height:28px">${r.grade}</span></td>
      <td style="padding:4px">${r.date || ''}</td></tr>`;
  }
  html += `</table></div>`;

  html += `<button class="btn btn-muted btn-sm" style="margin-top:8px" onclick="history.back()">Назад</button>`;
  $('#app').innerHTML = html;
}

// ===== LESSON (attendance) =====
async function renderLesson(lessonId) {
  const data = await api('GET', `/api/lessons/${lessonId}/attendance`);

  let html = nav();
  if (!data.lesson) { html += `<div class="card">Занятие не найдено</div>`; $('#app').innerHTML = html; return; }

  const l = data.lesson;
  html += `<h1>${l.actual_subject_name}</h1>`;
  html += `<div class="card">
    <div class="card-sub">${l.date} · ${l.group_name}</div>
    ${l.planned_subject !== l.actual_subject_name ? `<div class="badge badge-warning">Замена вместо: ${l.planned_subject}</div>` : ''}
  </div>`;

  // Build attendance map
  const attMap = {};
  for (const a of data.attendance) attMap[a.student_id] = a.grade;

  const gradeCycle = [null, 'absent', '5', '4', '3', '2'];

  html += `<h2>Отметки</h2><div class="card">`;
  for (const s of data.students || []) {
    const grade = attMap[s.id] || null;
    const cls = grade === null ? 'grade-none' : grade === 'absent' ? 'grade-absent' : `grade-${grade}`;
    const label = grade || '—';
    html += `<div class="attendance-row" onclick="cycleGrade(${lessonId}, ${s.id}, '${grade || ''}')">
      <div class="grade ${cls}">${label}</div>
      <div style="flex:1"><div style="font-weight:500">${s.last_name} ${s.first_name}</div><div style="font-size:12px;color:#86868b">${s.middle_name || ''}</div></div>
    </div>`;
  }
  html += `</div>`;

  html += `<button class="btn btn-muted btn-sm" onclick="history.back()">Готово</button>`;
  $('#app').innerHTML = html;
}

window.cycleGrade = async function(lessonId, studentId, currentGrade) {
  const grades = ['absent', '5', '4', '3', '2', ''];
  const idx = grades.indexOf(currentGrade);
  const next = grades[(idx + 1) % grades.length];
  const grade = next || 'absent';
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
