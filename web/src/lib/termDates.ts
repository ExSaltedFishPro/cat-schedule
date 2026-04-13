const DAY_MS = 24 * 60 * 60 * 1000;

function parseDate(input: string | undefined | null): Date | null {
  if (!input) {
    return null;
  }
  const matched = input.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!matched) {
    return null;
  }
  const [, yearText, monthText, dayText] = matched;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const date = new Date(year, month - 1, day, 12, 0, 0, 0);
  return Number.isNaN(date.getTime()) ? null : date;
}

function normalizeDate(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate(), 12, 0, 0, 0);
}

function parseTermStartDates(raw: string | undefined): Record<string, string> {
  if (!raw) {
    return {};
  }

  try {
    const parsed = JSON.parse(raw) as Record<string, string>;
    if (parsed && typeof parsed === "object") {
      return parsed;
    }
  } catch {
    // 继续按逗号分隔格式解析
  }

  return raw
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .reduce<Record<string, string>>((result, item) => {
      const [term, date] = item.split(":").map((value) => value.trim());
      if (term && date) {
        result[term] = date;
      }
      return result;
    }, {});
}

const TERM_START_DATES = parseTermStartDates(import.meta.env.VITE_TERM_START_DATES);
const DEFAULT_TERM_START_DATE = import.meta.env.VITE_DEFAULT_TERM_START_DATE;

export function getTermStartDate(term?: string | null): Date | null {
  return parseDate((term && TERM_START_DATES[term]) || DEFAULT_TERM_START_DATE);
}

export function getCurrentWeekNumber(availableWeeks: number[], term?: string | null): number | null {
  if (!availableWeeks.length) {
    return null;
  }

  const startDate = getTermStartDate(term);
  if (!startDate) {
    return null;
  }

  const today = normalizeDate(new Date());
  const diffDays = Math.floor((today.getTime() - startDate.getTime()) / DAY_MS);
  const rawWeek = Math.floor(diffDays / 7) + 1;
  const minWeek = Math.min(...availableWeeks);
  const maxWeek = Math.max(...availableWeeks);
  if (rawWeek < minWeek) {
    return minWeek;
  }
  if (rawWeek > maxWeek) {
    return maxWeek;
  }
  return availableWeeks.includes(rawWeek) ? rawWeek : minWeek;
}

export function getWeekDateRange(term: string | null | undefined, weekNumber: number): [Date, Date] | null {
  const startDate = getTermStartDate(term);
  if (!startDate) {
    return null;
  }
  const weekStart = new Date(startDate);
  weekStart.setDate(startDate.getDate() + (weekNumber - 1) * 7);
  const weekEnd = new Date(weekStart);
  weekEnd.setDate(weekStart.getDate() + 6);
  return [weekStart, weekEnd];
}

function formatMonthDay(date: Date): string {
  return `${date.getMonth() + 1}/${date.getDate()}`;
}

export function formatWeekLabel(term: string | null | undefined, weekNumber: number): string {
  const range = getWeekDateRange(term, weekNumber);
  if (!range) {
    return `第 ${weekNumber} 周`;
  }
  return `第 ${weekNumber} 周 (${formatMonthDay(range[0])}-${formatMonthDay(range[1])})`;
}
