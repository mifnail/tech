/*  src/api.ts — fetch helpers for same-origin /api/* endpoints.

    Grade mapping (UI ↔ DB):
      UI "—" (ungraded) → DB "" (empty string triggers DELETE in mark_attendance)
      UI "0" (present)  → DB "0"
      UI "Н" (absent)   → DB "Н"
      UI "2"–"5"        → DB same string
    On read: DB empty/missing → UI "—", everything else 1:1.
*/

// ─────────────────────── Grade mapping ───────────────────────

/** Convert UI grade string to DB representation. */
export function gradeToDb(grade: string): string {
  return grade === '—' ? '' : grade;
}

/** Convert DB grade string to UI representation. */
export function gradeFromDb(grade: string | undefined | null): string {
  return grade || '—';
}

// ─────────────────────── Time-slot map ───────────────────────

export const TIME_SLOTS: Record<number, { start: string; end: string }> = {
  1: { start: '08:30', end: '10:00' },
  2: { start: '10:10', end: '11:40' },
  3: { start: '12:10', end: '13:40' },
  4: { start: '13:50', end: '15:20' },
  5: { start: '15:30', end: '17:00' },
  6: { start: '17:10', end: '18:40' },
};

// ─────────────────────── Fetch helpers ───────────────────────

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json() as Promise<T>;
}

// ─────────────────────── Groups ───────────────────────

export interface ApiGroup {
  id: number;
  name: string;
}

export async function fetchGroups(): Promise<ApiGroup[]> {
  return apiFetch('/api/groups');
}

export async function createGroupApi(name: string): Promise<{ id: number }> {
  return apiFetch('/api/groups', {
    method: 'POST',
    body: JSON.stringify({ name }),
  });
}

// ─────────────────────── Students ───────────────────────

export interface ApiStudent {
  id: number;
  group_id: number;
  last_name: string;
  first_name: string;
  middle_name: string;
  group_name?: string;
}

export async function fetchStudents(groupId?: number): Promise<ApiStudent[]> {
  const url = groupId != null ? `/api/students?group_id=${groupId}` : '/api/students';
  return apiFetch(url);
}

// ─────────────────────── Subjects ───────────────────────

export interface ApiSubject {
  id: number;
  name: string;
  total_hours: number;
  group_id: number;
  group_name: string;
  held_lessons: number;
  remaining: number;
}

export async function fetchSubjects(groupId?: number): Promise<ApiSubject[]> {
  const url = groupId != null ? `/api/subjects?group_id=${groupId}` : '/api/subjects';
  return apiFetch(url);
}

// ─────────────────────── Schedule ───────────────────────

export interface ApiScheduleEntry {
  id: number;
  day_of_week: number;
  lesson_number: number;
  subject_id: number;
  week_type: number;
  subject_name: string;
  group_name: string;
  group_id: number;
}

export interface ApiTodayLesson {
  id: number;
  subject_id: number;
  actual_subject_name: string;
  planned_subject: string;
  group_name: string;
  group_id: number;
  date: string;
  status: string;
  lesson_number: number | null;
  needs_attention: boolean;
}

export async function fetchTodaySchedule(): Promise<{
  date: string;
  formatted_date: string;
  day_of_week: number;
  schedule: ApiScheduleEntry[];
  lessons: ApiTodayLesson[];
}> {
  return apiFetch('/api/schedule/today');
}

export async function fetchSchedule(): Promise<ApiScheduleEntry[]> {
  return apiFetch('/api/schedule');
}

// ─────────────────────── Lessons ───────────────────────

export async function createLessonApi(
  subjectId: number,
  date?: string,
  lessonNumber?: number,
): Promise<{ id: number; deduped?: boolean }> {
  const body: Record<string, unknown> = { subject_id: subjectId };
  if (date) body.date = date;
  if (lessonNumber != null) body.lesson_number = lessonNumber;
  return apiFetch('/api/lessons', { method: 'POST', body: JSON.stringify(body) });
}

export async function fetchLessonsByDate(dateStr: string): Promise<ApiTodayLesson[]> {
  return apiFetch(`/api/lessons/date/${dateStr}`);
}

// ─────────────────────── Attendance ───────────────────────

export interface ApiAttendanceRecord {
  student_id: number;
  grade: string;
  last_name: string;
  first_name: string;
  middle_name: string;
}

export interface ApiGroupStudent {
  id: number;
  group_id: number;
  last_name: string;
  first_name: string;
  middle_name: string;
}

export async function fetchAttendance(lessonId: number): Promise<{
  lesson: ApiTodayLesson | null;
  attendance: ApiAttendanceRecord[];
  students: ApiGroupStudent[];
}> {
  return apiFetch(`/api/lessons/${lessonId}/attendance`);
}

export async function postAttendanceBulk(
  lessonId: number,
  records: { student_id: number; grade: string }[],
): Promise<{ ok: boolean }> {
  const payload = records.map((r) => ({
    student_id: r.student_id,
    grade: gradeToDb(r.grade),
  }));
  return apiFetch(`/api/lessons/${lessonId}/attendance`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function postAttendanceSingle(
  lessonId: number,
  studentId: number,
  grade: string,
): Promise<{ ok: boolean }> {
  return apiFetch(`/api/lessons/${lessonId}/attendance`, {
    method: 'POST',
    body: JSON.stringify({ student_id: studentId, grade: gradeToDb(grade) }),
  });
}

// ─────────────────────── Export / Backup ───────────────────────

export async function downloadServerXlsx(subjectId: number): Promise<Blob> {
  const res = await fetch(`/api/export/grades/${subjectId}.xlsx`);
  if (!res.ok) throw new Error(`Export ${res.status}`);
  return res.blob();
}

export async function shareGradesApi(subjectId: number): Promise<{ ok: boolean; path?: string; shared?: boolean }> {
  return apiFetch(`/api/export/grades/${subjectId}/share`, { method: 'POST' });
}

export async function postBackup(): Promise<{ ok: boolean; path?: string }> {
  return apiFetch('/api/backup', { method: 'POST' });
}
