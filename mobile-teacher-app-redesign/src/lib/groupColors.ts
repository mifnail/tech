/* Автоматические цвета групп — без выбора пользователем.
 *
 * Правило:
 *  1. Специальность = буквенный префикс до дефиса («АДТ» из «АДТ-31»).
 *     Специальности получают максимально разнесённые оттенки (hue) —
 *     равномерно по кругу, поэтому разные специальности сильно различаются.
 *  2. Курс = первая цифра после дефиса («АДТ-31» → 3). Внутри одной
 *     специальности курс задаёт тон (lightness/saturation): соседние курсы
 *     заметно контрастны, но остаются в одном цветовом семействе.
 *  3. Цвет текста выбирается по контрасту (WCAG) к фону плитки, поэтому
 *     читается на любом оттенке — и в светлой, и в тёмной теме.
 *
 * Реестр названий групп обновляется из App (registerGroupNames) — от него
 * зависит, сколько специальностей в журнале и как раскладываются hue.
 */

const HUE_START = 205; // синий — «домашний» оттенок интерфейса

/** Тон курса в светлой теме: от светлого (1 курс) к тёмному (4 курс). */
const TONES_LIGHT = [
  { s: 58, l: 90 },
  { s: 70, l: 78 },
  { s: 76, l: 63 },
  { s: 60, l: 42 },
];

/** Тон курса в тёмной теме: от приглушённого к светлому. */
const TONES_DARK = [
  { s: 40, l: 24 },
  { s: 52, l: 32 },
  { s: 62, l: 42 },
  { s: 54, l: 56 },
];

let registry: string[] = [];

/** Специальность: «АДТ-31» → «АДТ», «ИС21» → «ИС», «АДТ 31» → «АДТ». */
export function specialtyOf(name: string): string {
  const trimmed = (name || "").trim();
  const head = trimmed.split(/[-\s/.]/)[0] || trimmed;
  return head.replace(/[^A-Za-zА-Яа-яЁё]/g, "").toUpperCase() || trimmed.toUpperCase();
}

/** Курс: первая цифра после дефиса, иначе первая цифра в названии. */
function courseOf(name: string): number {
  const dash = name.indexOf("-");
  const tail = dash >= 0 ? name.slice(dash + 1) : name;
  const digit = tail.match(/\d/);
  return digit ? Math.max(Number(digit[0]), 1) : 1;
}

function hashHue(text: string): number {
  let h = 0;
  for (let i = 0; i < text.length; i++) h = (h * 31 + text.charCodeAt(i)) | 0;
  return Math.abs(h) % 360;
}

/**
 * Обновить реестр групп. Вызывается из App при каждом рендере —
 * пересчёт дешёвый, а список специальностей меняется только при
 * добавлении/удалении групп.
 */
export function registerGroupNames(names: string[]): void {
  const uniq = [...new Set(names.map(specialtyOf).filter(Boolean))].sort((a, b) =>
    a.localeCompare(b, "ru"),
  );
  if (uniq.join("|") !== registry.join("|")) registry = uniq;
}

function isDarkTheme(): boolean {
  return typeof document !== "undefined" &&
    document.documentElement.getAttribute("data-theme") === "dark";
}

/* ── HSL → RGB и контраст (WCAG) ────────────────────────────── */
function hslToRgb(h: number, s: number, l: number): [number, number, number] {
  const sn = s / 100;
  const ln = l / 100;
  const c = (1 - Math.abs(2 * ln - 1)) * sn;
  const hp = ((h % 360) + 360) % 360 / 60;
  const x = c * (1 - Math.abs((hp % 2) - 1));
  let rgb: [number, number, number];
  if (hp < 1) rgb = [c, x, 0];
  else if (hp < 2) rgb = [x, c, 0];
  else if (hp < 3) rgb = [0, c, x];
  else if (hp < 4) rgb = [0, x, c];
  else if (hp < 5) rgb = [x, 0, c];
  else rgb = [c, 0, x];
  const m = ln - c / 2;
  return rgb.map((v) => Math.round((v + m) * 255)) as [number, number, number];
}

function luminance([r, g, b]: [number, number, number]): number {
  const f = (v: number) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}

function contrast(a: number, b: number): number {
  const [hi, lo] = a > b ? [a, b] : [b, a];
  return (hi + 0.05) / (lo + 0.05);
}

const DARK_TEXT: [number, number, number] = [17, 23, 32];
const LIGHT_TEXT: [number, number, number] = [255, 255, 255];

/** Читаемый цвет текста для фона: максимум контраста из тёмного/белого. */
function textOn(rgb: [number, number, number]): string {
  const bg = luminance(rgb);
  const dark = contrast(bg, luminance(DARK_TEXT));
  const light = contrast(bg, luminance(LIGHT_TEXT));
  return dark >= light ? "rgb(17,23,32)" : "rgb(255,255,255)";
}

/**
 * Цвет группы: { bg, fg } как CSS-строки.
 * Одна специальность — одно семейство hue, курс — контрастный тон внутри.
 */
export function colorForGroup(name: string): { bg: string; fg: string } {
  const prefix = specialtyOf(name);
  const n = registry.length;
  const idx = registry.indexOf(prefix);
  // Разные специальности — равномерно по кругу (сильно различаются).
  // Если реестр ещё пуст — детерминированный хеш (стабильный одиночный цвет).
  const hue = n > 0 && idx >= 0
    ? (HUE_START + Math.round((idx * 360) / n)) % 360
    : hashHue(prefix);

  const tones = isDarkTheme() ? TONES_DARK : TONES_LIGHT;
  const v = (courseOf(name) - 1) % tones.length;
  const { s, l } = tones[v];
  const rgb = hslToRgb(hue, s, l);
  return {
    bg: `hsl(${hue}, ${s}%, ${l}%)`,
    fg: textOn(rgb),
  };
}
