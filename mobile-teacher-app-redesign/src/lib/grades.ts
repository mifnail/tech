/* Логика оценок: двусторонний перебор тапом, средние, тона. */

export type GradeValue = number | null;

/** Порядок перебора вперёд (правая половина строки): — → 0 → 5 → 4 → 3 → 2 */
export const CYCLE: GradeValue[] = [null, 0, 5, 4, 3, 2];

export function nextGrade(v: GradeValue): GradeValue {
  const i = CYCLE.indexOf(v);
  return CYCLE[(i + 1) % CYCLE.length];
}

export function prevGrade(v: GradeValue): GradeValue {
  const i = CYCLE.indexOf(v);
  return CYCLE[(i - 1 + CYCLE.length) % CYCLE.length];
}

/** Среднее только по числовым оценкам 2–5 (0/absent/пустые не входят).
    Паритет с серверным AVG по строкам: mean всех числовых записей. */
export function avgOf(values: GradeValue[]): number | null {
  const nums = values.filter((v): v is number => v !== null && v >= 2 && v <= 5);
  if (!nums.length) return null;
  return nums.reduce((a, b) => a + b, 0) / nums.length;
}

export function formatAvg(v: number | null): string {
  return v === null ? "—" : v.toFixed(2).replace(/0$/, "").replace(/\.$/, ".0");
}

export type GradeTone = "g5" | "g4" | "g3" | "g2" | "na" | "none";

export function gradeTone(v: GradeValue, present: boolean): GradeTone {
  if (!present) return "na";
  if (v === null) return "none";
  if (v === 5) return "g5";
  if (v === 4) return "g4";
  if (v === 3) return "g3";
  return "g2"; // 2 и 0 — красные
}

export function gradeLabel(v: GradeValue, present: boolean): string {
  if (!present) return "Н";
  return v === null ? "—" : String(v);
}

/** Должник: средний балл ниже 3.5 при наличии хотя бы двух оценок. */
export function isDebtor(values: GradeValue[]): boolean {
  const nums = values.filter((v): v is number => v !== null);
  if (nums.length < 2) return false;
  return nums.reduce((a, b) => a + b, 0) / nums.length < 3.5;
}

/** Лёгкий тактильный отклик (API вибрации есть на Android WebView). */
export function buzz(ms = 8): void {
  try {
    if (typeof navigator !== "undefined" && navigator.vibrate) {
      navigator.vibrate(ms);
    }
  } catch (_) {
    /* нет вибрации — не страшно */
  }
}
