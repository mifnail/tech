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
    if (res.ok) return res.json();
    const err = await res.json();
    throw err;
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
  }
};

App.Nav = {
  render() {
    const pages = [
      { hash: '#home', label: 'Дом' },
      { hash: '#schedule', label: 'Расп.' }
    ];
    const active = location.hash.split('?')[0] || '#home';
    return `<div class="nav">${
      pages.map(p =>
        `<a href="${p.hash}" class="${active === p.hash ? 'active' : ''}">${p.label}</a>`
      ).join('')
    }</div>`;
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
  bgColor(grade) {
    const map = { '0': '#e8f5e9', 'present': '#e8f5e9', '5': '#ffebee', '4': '#e3f2fd', '3': '#fff8e1', '2': '#e0e0e0' };
    return map[grade] || '';
  },
  async cycle(lessonId, studentId, currentGrade) {
    const idx = this.CYCLE.indexOf(currentGrade || '');
    const next = this.CYCLE[(idx + 1) % this.CYCLE.length];
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
    else App.Pages.home();
  }
};

App.Pages = {
  _showToday: false,

  _renderTodaySchedule(schedule, lessons) {
    let html = '';
    if (schedule.length) {
      html += `<h2>Расписание</h2>`;
      for (const e of schedule) {
        const existing = lessons.find(l => l.subject_id === e.subject_id && l.status === 'held');
        if (existing) {
          html += `<div class="card" style="cursor:pointer" onclick="location='#lesson/${existing.id}'">
            <div class="card-title">Занятие ${e.lesson_number} · ${e.subject_name}</div>
            <div class="card-sub">${e.group_name} · <span class="badge badge-held">Проведено</span></div>
          </div>`;
        } else {
          const existingCancelled = lessons.find(l => l.subject_id === e.subject_id && l.status === 'cancelled');
          if (existingCancelled) {
            html += `<div class="card" style="cursor:pointer" onclick="location='#lesson/${existingCancelled.id}'">
            <div class="card-title">Занятие ${e.lesson_number} · ${e.subject_name}</div>
            <div class="card-sub">${e.group_name} · <span class="badge badge-cancelled">Отменено</span></div>
            </div>`;
          } else {
            html += `<div class="card">
            <div class="card-title">Занятие ${e.lesson_number} · ${e.subject_name}</div>
            <div class="card-sub">${e.group_name}</div>
              <button class="btn btn-success btn-sm" style="margin-top:8px" onclick="App.Pages.startLesson(${e.subject_id})">Начать занятие</button>
            </div>`;
          }
        }
      }
    }
    const otherLessons = lessons.filter(l => !schedule.some(s => s.subject_id === l.subject_id));
    if (otherLessons.length) {
      html += `<h2>Другие занятия</h2>`;
      for (const l of otherLessons) {
        const cls = l.status === 'cancelled' ? 'badge-cancelled' : 'badge-held';
        const label = l.status === 'cancelled' ? 'Отменено' : 'Проведено';
        html += `<div class="card" style="cursor:pointer" onclick="location='#lesson/${l.id}'">
          <div class="card-title">${l.actual_subject_name}</div>
          <div class="card-sub">${l.group_name} · <span class="badge ${cls}">${label}</span></div>
        </div>`;
      }
    }
    if (!schedule.length && !lessons.length) {
      html += `<div class="card"><div class="card-sub">Сегодня занятий нет</div></div>`;
    }
    html += `<button class="btn btn-primary btn-sm" style="margin-top:8px" onclick="App.Pages.showCustomLesson()">+ Создать занятие</button>`;
    return html;
  },

  async home() {
    App.Loading.show();
    const [subjects, groups, today] = await Promise.all([
      App.API.get('/api/subjects'),
      App.API.get('/api/groups'),
      App.API.get('/api/schedule/today')
    ]);

    let html = App.Nav.render();
    html += `<h1>Учёт занятий</h1>`;

    html += `<div class="card" style="cursor:pointer" onclick="App.Pages._showToday = !App.Pages._showToday; App.Pages.home()">
      <div class="card-title">Сегодня (${today.date})</div>
      <div class="card-sub">${today.schedule.length} запланировано · ${today.lessons.length} занятий · ${App.Pages._showToday ? '▲' : '▼'}</div>
    </div>`;

    if (App.Pages._showToday) {
      html += App.Pages._renderTodaySchedule(today.schedule, today.lessons);
    }

    html += `<h2>Предметы</h2>`;
    for (const s of subjects) {
      const pct = s.total_hours > 0 ? Math.round(s.held_lessons / s.total_hours * 100) : 0;
      html += `<div class="card" style="cursor:pointer" onclick="location='#subject/${s.id}'">
        <div class="card-title">${s.name}</div>
        <div class="card-sub">${s.group_name} · ${s.held_lessons}/${s.total_hours} (осталось ${s.remaining})</div>
        <div class="bar"><div class="bar-fill" style="width:${pct}%"></div></div>
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
          <div class="card-title">${g.name}</div>
        </div>`;
      }
      html += `</div>`;
    }

    html += `<div style="display:flex;gap:8px;margin-top:8px">
      <button class="btn btn-primary" style="flex:1" onclick="App.Pages.showAddSubject()">+ Предмет</button>
      <button class="btn btn-muted" style="flex:1" onclick="App.Pages.showAddGroup()">+ Группа</button>
    </div>
    <h2>Экспорт</h2><div class="grid-2">
      <button class="btn btn-muted btn-sm" onclick="window.open('/api/export/report/${today.date}.pdf')">Отчёт (PDF)</button>
      <button class="btn btn-muted btn-sm" onclick="window.open('/api/export/report/${today.date}.xlsx')">Отчёт (Excel)</button>
      <button class="btn btn-muted btn-sm" onclick="window.open('/api/export/lessons.ics')">Занятия (ICS)</button>
      <button class="btn btn-muted btn-sm" onclick="window.open('/api/export/schedule.ics')">Расписание (ICS)</button>
    </div>`;

    document.getElementById('app').innerHTML = html;
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
    html += `<div class="card"><div class="card-title">${data.date}</div>`;
    html += `<div class="card-sub">День ${data.day_of_week}</div></div>`;

    if (currentSubject) {
      html += `<button class="btn btn-muted btn-sm" style="margin-bottom:8px" onclick="location='#subject/${subjectId}'">📋 Журнал предмета</button>`;
      html += `<button class="btn btn-muted btn-sm" style="margin-bottom:8px" onclick="location='#today'">📅 Все предметы</button>`;
    }

      if (schedule.length) {
        html += `<h2>Расписание</h2>`;
        for (const e of schedule) {
          const existing = lessons.find(l => l.subject_id === e.subject_id && l.status === 'held');
          if (existing) {
            html += `<div class="card" style="cursor:pointer" onclick="location='#lesson/${existing.id}'">
              <div class="card-title">Занятие ${e.lesson_number} · ${e.subject_name}</div>
              <div class="card-sub">${e.group_name} · <span class="badge badge-held">Проведено</span></div>
            </div>`;
          } else {
            const existingCancelled = lessons.find(l => l.subject_id === e.subject_id && l.status === 'cancelled');
            if (existingCancelled) {
              html += `<div class="card" style="cursor:pointer" onclick="location='#lesson/${existingCancelled.id}'">
              <div class="card-title">Занятие ${e.lesson_number} · ${e.subject_name}</div>
              <div class="card-sub">${e.group_name} · <span class="badge badge-cancelled">Отменено</span></div>
              </div>`;
            } else {
              html += `<div class="card">
              <div class="card-title">Занятие ${e.lesson_number} · ${e.subject_name}</div>
              <div class="card-sub">${e.group_name}</div>
                <button class="btn btn-success btn-sm" style="margin-top:8px" onclick="App.Pages.startLesson(${e.subject_id})">Начать занятие</button>
              </div>`;
            }
          }
        }
      }

      if (lessons.length && !subjectId) {
        const otherLessons = lessons.filter(l => !schedule.some(s => s.subject_id === l.subject_id));
        if (otherLessons.length) {
          html += `<h2>Другие занятия</h2>`;
          for (const l of otherLessons) {
            const cls = l.status === 'cancelled' ? 'badge-cancelled' : 'badge-held';
            const label = l.status === 'cancelled' ? 'Отменено' : 'Проведено';
            html += `<div class="card" style="cursor:pointer" onclick="location='#lesson/${l.id}'">
              <div class="card-title">${l.actual_subject_name}</div>
              <div class="card-sub">${l.group_name} · <span class="badge ${cls}">${label}</span>
                ${l.status === 'cancelled' ? '· Отменено' : ''}</div>
            </div>`;
          }
        }
      }

    if (!schedule.length && !lessons.length) {
      html += `<div class="card"><div class="card-sub">${currentSubject ? 'Сегодня занятий по этому предмету нет' : 'Сегодня занятий нет'}</div></div>`;
    }

    if (!subjectId) {
      html += `<button class="btn btn-primary btn-sm" style="margin-top:8px" onclick="App.Pages.showCustomLesson()">Создать занятие вручную</button>`;
    }

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
        <button class="btn btn-muted btn-sm" onclick="window.open('/api/export/grades/${subjectId}.pdf')">PDF</button>
        <button class="btn btn-muted btn-sm" onclick="window.open('/api/export/grades/${subjectId}.xlsx')">Excel</button>
        <button class="btn btn-muted btn-sm" onclick="location='#students/${s.group_id}'">Студенты</button>
      </div></div>`;
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

    html += `<h2>Все занятия</h2>`;
    if (allLessons.length) {
      html += `<div class="card">`;
      for (const l of allLessons) {
        const cls = l.status === 'cancelled' ? 'badge-cancelled' : 'badge-held';
        const label = l.status === 'cancelled' ? 'Отменено' : 'Проведено';
        html += `<div class="row" style="cursor:pointer" onclick="location='#lesson/${l.id}'">
          <div style="flex:1">
            <div style="font-weight:500">${l.date}</div>
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
      html += `<th style="padding:4px;text-align:center;min-width:32px">${i + 1}</th>`;
    }
    html += `</tr>`;
    for (const s of data.students) {
      html += `<tr><td style="padding:4px;position:sticky;left:0;background:#fff;font-weight:500">${s.last_name} ${s.first_name}</td>`;
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

    html += `<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">`;
    html += adjacent.prev_id
      ? `<button class="btn btn-muted btn-sm" style="width:auto;padding:8px 16px" onclick="location='#lesson/${adjacent.prev_id}'">‹</button>`
      : `<div style="width:44px"></div>`;
    html += `<div style="flex:1;text-align:center">`;
    html += `<h1 style="margin:0">${l.actual_subject_name}</h1>`;
    html += `</div>`;
    html += adjacent.next_id
      ? `<button class="btn btn-muted btn-sm" style="width:auto;padding:8px 16px" onclick="location='#lesson/${adjacent.next_id}'">›</button>`
      : `<div style="width:44px"></div>`;
    html += `</div>`;

    html += `<div class="card">
      <div class="card-sub">${l.date} · ${l.group_name}</div>
      ${l.status === 'cancelled' ? `<div class="badge badge-cancelled">Отменено</div>` : `<span class="badge badge-held">Проведено</span>`}
    </div>`;

    if (l.status === 'cancelled') {
      html += `<button class="btn btn-muted btn-sm" onclick="location='#subject/${App.state.lessonSubjectId}'">Журнал</button>`;
      document.getElementById('app').innerHTML = html;
      return;
    }

    const attMap = {};
    for (const a of data.attendance) attMap[a.student_id] = a.grade;

    html += `<h2>Отметки</h2><div class="card">`;
    for (const s of data.students || []) {
      const grade = attMap[s.id] || null;
      const label = (grade === null || grade === '') ? '—' : grade;
      const bgStyle = grade === null ? '' : `background:${App.Grades.bgColor(grade)}`;
      html += `<div class="attendance-row ${grade ? 'marked' : ''}" onclick="App.Grades.cycle(${lessonId}, ${s.id}, '${grade || ''}')" style="${bgStyle}">
        <div class="grade grade-${App.Grades.colorClass(grade)}">${label}</div>
        <div style="flex:1"><div style="font-weight:500">${s.last_name} ${s.first_name}</div><div style="font-size:12px;color:#86868b">${s.middle_name || ''}</div></div>
      </div>`;
    }
    html += `</div>`;

    html += `<div style="display:flex;gap:8px;margin-top:8px">
      <button class="btn btn-warning btn-sm" style="flex:1" onclick="App.Pages.showLessonSubstitution(${lessonId})">🔄 Заменить</button>
      <button class="btn btn-danger btn-sm" style="flex:1" onclick="App.Pages.confirmCancelLesson(${lessonId})">✕ Отменить</button>
      <button class="btn btn-success" style="flex:1" onclick="location='#subject/${App.state.lessonSubjectId}'">Журнал</button>
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
              <div class="card-sub">${e.subject_name} · ${e.group_name} · ${weekTypes[e.week_type] || 'Каждую'}</div>
            </div>
            <button class="btn btn-muted btn-sm" style="width:auto" onclick="App.Pages.showEditScheduleEntry(${e.id}, ${JSON.stringify(e).replace(/"/g, '&quot;')})">✎</button>
            <button class="btn btn-danger btn-sm" style="width:auto" onclick="App.Pages.deleteScheduleEntry(${e.id})">✕</button>
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
    const group = groups.find(g => g.id == groupId);

    let html = App.Nav.render();
    html += `<h1>${group ? group.name : 'Студенты'}</h1>`;
    html += `<button class="btn btn-primary btn-sm" onclick="App.Pages.showAddStudents(${groupId})">+ Добавить студентов</button>`;
    html += `<div class="card">`;
    for (const s of students) {
      html += `<div class="row"><div style="flex:1"><span style="font-weight:500">${s.last_name} ${s.first_name}</span> ${s.middle_name || ''}</div></div>`;
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
        <div class="card-title">${s.name}</div>
        <div class="card-sub">${s.group_name} · ${s.held_lessons}/${s.total_hours} · осталось ${s.remaining}</div>
        <div class="bar"><div class="bar-fill" style="width:${pct}%"></div></div>
      </div>`;
    }

    html += `<button class="btn btn-muted btn-sm" style="margin-top:8px" onclick="App.Pages.showAddGroup()">+ Управление группами</button>`;
    document.getElementById('app').innerHTML = html;
  }
};

/* ===== Dialog / Action helpers (on window for onclick access) ===== */

App.Pages.startLesson = async function(subjectId) {
  const result = await App.API.post('/api/lessons', {
    subject_id: subjectId, actual_subject_id: subjectId, status: 'held'
  });
  location = `#lesson/${result.id}`;
};

App.Pages.showLessonSubstitution = async function(lessonId) {
  const lesson = await App.API.get(`/api/lessons/${lessonId}`);
  const subs = await App.API.get(`/api/subjects/${lesson.subject_id}/substitution-list`);
  const opts = subs.map(s => `<option value="${s.id}">${s.name}</option>`).join('');
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

App.Pages.confirmCancelLesson = function(lessonId) {
  App.UI.showPopup(`
    <h2>Отменить занятие?</h2>
    <p style="margin-bottom:12px;color:#86868b">Оценки будут удалены.</p>
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

App.Pages.showCustomLesson = function() {
  App.API.get('/api/subjects').then(subjects => {
    const opts = subjects.map(s => `<option value="${s.id}">${s.name} (${s.group_name})</option>`).join('');
    App.UI.showPopup(`
      <h2>Создать занятие</h2>
      <select id="custom-subject">${opts}</select>
      <button class="btn btn-primary btn-sm" onclick="App.Pages.createCustomLesson()">Создать</button>
    `);
  });
};

App.Pages.createCustomLesson = async function() {
  const subjectId = +document.getElementById('custom-subject').value;
  await App.API.post('/api/lessons', {
    subject_id: subjectId, actual_subject_id: subjectId, status: 'held'
  });
  App.UI.notify('Занятие создано');
  App.UI.closePopup();
  App.Pages.today();
};

App.Pages.showAddSubject = async function() {
  const groups = await App.API.get('/api/groups');
  const groupOpts = groups.map(g => `<option value="${g.id}">${g.name}</option>`).join('');
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
  const opts = subjects.map(s => `<option value="${s.id}">${s.name} (${s.group_name})</option>`).join('');
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
  const opts = subjects.map(s => `<option value="${s.id}" ${s.id === entry.subject_id ? 'selected' : ''}>${s.name} (${s.group_name})</option>`).join('');
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

App.Pages.deleteScheduleEntry = async function(id) {
  if (!confirm('Удалить?')) return;
  await App.API._delete(`/api/schedule/${id}`);
  App.Pages.schedule();
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

/* ===== INIT ===== */
App.Router.init();
