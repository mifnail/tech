# Skill: tech-frontend — React/TypeScript Frontend

**Trigger:** Working on the React/TypeScript frontend in `mobile-teacher-app-redesign/`.

**Frontend root:** `c:/Users/user/WorkBuddy AI/2026-09-13-22-13-51/tech/mobile-teacher-app-redesign/`

## Architecture

React + TypeScript + Vite. Hash-based routing. 480px mobile-first column.
DEV mode: seeded data in localStorage. PROD mode: fetch from Flask API.

## File Structure

```
src/
├── App.tsx              → Hash router + bottom nav + route views
├── lib/
│   ├── types.ts         → Domain models (Group, Student, Subject, Lesson, GradeRec, Settings, DB)
│   ├── store.ts         → Reactive store (useSyncExternalStore), DEV seed, PROD API sync
│   ├── router.ts        → Hash-based routing (useRoute hook)
│   ├── grades.ts        → Grade cycling logic (nextGrade, prevGrade)
│   ├── update.ts        → Auto-update checking
│   └── date.ts          → Date utilities (todayISO, weekdayOf, weekParity, addDaysISO)
├── components/
│   ├── shell.tsx        → BottomNav (Today, Groups, Schedule, Analytics, More)
│   ├── ui.tsx           → ToastProvider, shared UI components
│   ├── UpdateBanner.tsx → Update notification
│   └── NewLessonSheet.tsx → Bottom sheet for starting a lesson
├── screens/
│   ├── Today.tsx        → Today's schedule + lessons
│   ├── Groups.tsx      → Group list
│   ├── GroupDetail.tsx  → Group page (students, subjects, schedule)
│   ├── Statement.tsx   → Gradebook/statement view (group + subject)
│   ├── Schedule.tsx     → Weekly schedule editor
│   ├── LessonRun.tsx   → Lesson screen (attendance, grades, substitutions)
│   ├── Analytics.tsx   → Average grades, attendance stats
│   └── Settings.tsx    → Bot settings, backup/restore, teacher codes
└── vite-env.d.ts
```

## Routing (hash-based)

| Route | Screen |
|-------|--------|
| `#today` | TodayScreen |
| `#groups` | GroupsScreen |
| `#group/<id>` | GroupDetailScreen |
| `#statement/<groupId>/<subjectId>` | StatementScreen |
| `#schedule` | ScheduleScreen |
| `#lesson/<id>` | LessonRunScreen |
| `#analytics` | AnalyticsScreen |
| `#more` | SettingsScreen |

Bottom nav hidden on `#lesson/*` (compact header/footer).

## Store (store.ts)

- Singleton `store` instance of `Store` class
- `useDB()` hook — reactive access to DB (re-renders on mutation)
- `useVersion()` hook — version counter for useMemo dependencies
- **DEV mode:** seeded data (5 weeks of lessons + schedule), persists to localStorage
- **PROD mode:** `loadFromApi()` fetches all data in two parallel batches, maps API shapes to frontend types

### PROD API Mapping

| API endpoint | Store field |
|-------------|-------------|
| GET /api/groups | db.groups |
| GET /api/subjects | db.subjects |
| GET /api/students | db.students |
| GET /api/schedule | db.schedule |
| GET /api/schedule/today | db.lessons (today's) |
| GET /api/subjects/<id>/gradebook | db.lessons + db.grades |
| GET /api/bot/links | student.tg |
| GET /api/maxbot/links | student.max |
| GET /api/groups/<id>/curator | group.curatorCode, curatorBound |
| GET /api/settings/bot | settings.tgEnabled, tgHasToken |
| GET /api/settings/maxbot | settings.maxEnabled, maxHasToken, teacherCode, teacherBound |

### Mutations (OPTIMISTIC in PROD)

All mutations update local state first, then fire API calls. On error, rollback.
- `addGroup`, `removeGroup`, `addStudent`, `removeStudent`, `addSubject`, `assignSubject`
- `addScheduleItem`, `removeScheduleItem`, `createLesson`, `setLessonStatus`, `substituteLesson`
- `cycleGrade(lessonId, studentId, dir)` — marks dirty, 1.5s debounce flush
- `togglePresent`, `updateSettings`, `regenerateTeacherCode`

### Grade Flush (PROD)

- `markGradeDirty(lessonId)` — snapshot grades before first change, start 1.5s timer
- `flushAttendance()` — bulk POST to `/api/lessons/<id>/attendance`, rollback on error
- Auto-bound to `pagehide` and `visibilitychange` events

## Domain Types (types.ts)

```typescript
Group { id, name, curatorCode, curatorBound, subjectIds }
Student { id, groupId, name, tg?, max? }
Subject { id, name, totalHours?, heldLessons? }
ScheduleItem { id, groupId, subjectId, weekday, parity, time, room, lessonNumber }
Lesson { id, groupId, subjectId, date, status, time, room, lessonNumber }
GradeRec { lessonId, studentId, value: number|null, present: boolean }
Settings { theme, teacherName, tgToken, maxToken, teacherCode, tgEnabled, maxEnabled, ... }
DB { groups, students, subjects, schedule, lessons, grades, settings, seq }
```

## Grade Cycling

Cycle: `null → 2 → 3 → 4 → 5 → null` (forward), reverse for backward.
`"0"` means present without a grade. `absent` = not present.

## Build

```bash
cd mobile-teacher-app-redesign/
npm install
npm run build    # outputs to dist/index.html (Vite singlefile)
npm run dev      # dev server
```

The built `dist/index.html` is served by Flask at `/` (inlined CSS/JS, no external assets).
Flask adds `Cache-Control: no-store` and a static version comment.

## Legacy Frontend (static/)

`static/app.js` + `static/style.css` + `templates/index.html` is the old vanilla JS SPA.
It's being replaced by the React frontend. Don't add new features to the legacy frontend.
The React build (`dist/index.html`) is what's served at `/`.

## Theme

Light/dark via `data-theme` attribute on `<html>`. CSS variables for colors.
Theme persisted in localStorage key `th-theme`.
