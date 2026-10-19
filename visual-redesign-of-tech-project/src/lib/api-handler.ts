import { NextRequest, NextResponse } from 'next/server';
import { demoRequest, getDemo, saveDemo, todayISO } from '@/lib/demo';
import ExcelJS from 'exceljs';

export async function handle(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const pathname = path.join('/');
  const backend = process.env.TEACHHELPER_API_URL;
  if (pathname === 'connection') return NextResponse.json({ mode: backend ? 'connected' : 'demo' });
  if (backend) {
    try {
      const headers = new Headers();
      for (const key of ['content-type', 'accept', 'authorization', 'cookie']) { const value = request.headers.get(key); if (value) headers.set(key, value); }
      const res = await fetch(`${backend.replace(/\/$/, '')}/api/${path.map(encodeURIComponent).join('/')}${request.nextUrl.search}`, { method: request.method, headers, body: ['GET', 'HEAD'].includes(request.method) ? undefined : await request.arrayBuffer(), cache: 'no-store', signal: AbortSignal.timeout(25000), redirect: 'manual' });
      const output = new Headers();
      for (const key of ['content-type', 'content-disposition', 'set-cookie']) { const value = res.headers.get(key); if (value) output.set(key, value); }
      output.set('Cache-Control', 'no-store');
      return new NextResponse(res.body, { status: res.status, headers: output });
    } catch { return NextResponse.json({ error: 'Нет связи с сервером журнала. Данные не изменены.' }, { status: 502 }); }
  }
  const { id, data } = await getDemo(request.cookies.get('teachhelper_demo')?.value);
  const respond = (value: unknown, status = 200) => { const res = NextResponse.json(value, { status }); res.cookies.set('teachhelper_demo', id, { httpOnly: true, sameSite: 'lax', path: '/', maxAge: 2592000 }); res.headers.set('Cache-Control', 'no-store'); return res; };
  try {
    if (path[0] === 'export') {
      if (!pathname.endsWith('.xlsx')) return respond({ error: 'В предпросмотре используйте скачивание Excel.' }, 400);
      const workbook = new ExcelJS.Workbook();
      workbook.creator = 'TeachHelper — демоданные';
      const sheet = workbook.addWorksheet('Ведомость');
      const subjectId = Number(path[2]?.replace('.xlsx', ''));
      const subject = data.subjects.find(s => s.id === subjectId);
      const lessons = path[1] === 'grades' ? data.lessons.filter(l => l.subject_id === subjectId) : data.lessons.filter(l => l.date === path[2]?.replace('.xlsx', ''));
      sheet.addRow(['TeachHelper · Демонстрационные данные', subject?.name || `Отчёт за ${todayISO()}`]);
      sheet.addRow(['Студент', 'Группа', ...lessons.map(l => l.date)]);
      const students = subject ? data.students.filter(s => s.group_id === subject.group_id) : data.students;
      for (const s of students) sheet.addRow([`${s.last_name} ${s.first_name}`, data.groups.find(g => g.id === s.group_id)?.name, ...lessons.map(l => data.grades[l.id]?.[s.id] || '—')]);
      sheet.getColumn(1).width = 42; sheet.getColumn(2).width = 30;
      sheet.getRow(2).font = { bold: true, color: { argb: 'FFFFFFFF' } };
      sheet.getRow(2).fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFEA783D' } };
      const buffer = await workbook.xlsx.writeBuffer();
      return new NextResponse(new Uint8Array(buffer), { headers: { 'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'Content-Disposition': 'attachment; filename="teachhelper-report.xlsx"', 'Cache-Control': 'no-store' } });
    }
    const body = ['GET', 'HEAD', 'DELETE'].includes(request.method) ? {} : await request.json();
    const result = demoRequest(data, request.method, pathname, request.nextUrl.searchParams, body);
    if (request.method !== 'GET') await saveDemo(id, data);
    return respond(result);
  } catch (e) { return respond({ error: e instanceof Error ? e.message : 'Не удалось выполнить запрос' }, 400); }
}
