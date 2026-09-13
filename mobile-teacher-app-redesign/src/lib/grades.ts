/* Логика оценок: двусторонний перебор тапом, средние, тона. */

export type GradeValue = number | null;

/** Порядок перебора вперёд (правая половина строки): . → 5 → 4 → 3 → 2 (Н — отдельно через toggle, 0 не используется) */
export const CYCLE: GradeValue[] = [null, 5, 4, 3, 2];

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
  if (v === null || v === 0) return "none";
  if (v === 5) return "g5";
  if (v === 4) return "g4";
  if (v === 3) return "g3";
  return "g2"; // 2 — красная
}

export function gradeLabel(v: GradeValue, present: boolean): string {
  if (!present) return "Н";
  if (v === null || v === 0) return ".";
  return String(v);
}

/** Должник: вовсе без оценок 2–5, либо средний по 2–5 ниже 3. */
export function isDebtor(values: GradeValue[]): boolean {
  const avg = avgOf(values);
  if (avg === null) return true;
  return avg < 3;
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
