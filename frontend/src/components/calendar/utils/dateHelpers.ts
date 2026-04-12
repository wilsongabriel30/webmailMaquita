import {
  startOfMonth,
  endOfMonth,
  startOfWeek,
  endOfWeek,
  addDays as dfAddDays,
  addWeeks as dfAddWeeks,
  addMonths as dfAddMonths,
  format,
  isSameDay as dfIsSameDay,
  isToday as dfIsToday,
  parseISO,
  differenceInMinutes,
  eachDayOfInterval,
} from "date-fns";
import { es } from "date-fns/locale";

export function getMonthGrid(date: Date): Date[][] {
  const monthStart = startOfMonth(date);
  const monthEnd = endOfMonth(date);
  const gridStart = startOfWeek(monthStart, { weekStartsOn: 1 });
  const gridEnd = endOfWeek(monthEnd, { weekStartsOn: 1 });

  const days = eachDayOfInterval({ start: gridStart, end: gridEnd });

  // Ensure exactly 6 rows
  while (days.length < 42) {
    days.push(dfAddDays(days[days.length - 1], 1));
  }

  const grid: Date[][] = [];
  for (let i = 0; i < 6; i++) {
    grid.push(days.slice(i * 7, i * 7 + 7));
  }
  return grid;
}

export function getWeekDates(date: Date): Date[] {
  const weekStart = startOfWeek(date, { weekStartsOn: 1 });
  return Array.from({ length: 7 }, (_, i) => dfAddDays(weekStart, i));
}

export interface HourSlot {
  hour: number;
  label: string;
}

export function getHourSlots(): HourSlot[] {
  return Array.from({ length: 24 }, (_, i) => ({
    hour: i,
    label: `${i.toString().padStart(2, "0")}:00`,
  }));
}

export function formatTime(date: Date | string): string {
  const d = typeof date === "string" ? parseISO(date) : date;
  return format(d, "HH:mm");
}

export function formatDate(date: Date | string): string {
  const d = typeof date === "string" ? parseISO(date) : date;
  return format(d, "d MMM yyyy", { locale: es });
}

export function formatDateFull(date: Date | string): string {
  const d = typeof date === "string" ? parseISO(date) : date;
  return format(d, "EEEE, d de MMMM de yyyy", { locale: es });
}

export function formatMonthYear(date: Date): string {
  return format(date, "MMMM yyyy", { locale: es });
}

export function formatDayHeader(date: Date): string {
  return format(date, "EEE d", { locale: es });
}

export function isSameDay(a: Date | string, b: Date | string): boolean {
  const da = typeof a === "string" ? parseISO(a) : a;
  const db = typeof b === "string" ? parseISO(b) : b;
  return dfIsSameDay(da, db);
}

export function isToday(date: Date | string): boolean {
  const d = typeof date === "string" ? parseISO(date) : date;
  return dfIsToday(d);
}

export function addDays(date: Date, n: number): Date {
  return dfAddDays(date, n);
}

export function addWeeks(date: Date, n: number): Date {
  return dfAddWeeks(date, n);
}

export function addMonths(date: Date, n: number): Date {
  return dfAddMonths(date, n);
}

export function toDateInputValue(date: Date): string {
  return format(date, "yyyy-MM-dd");
}

export function toTimeInputValue(date: Date): string {
  return format(date, "HH:mm");
}

export function toISOString(dateStr: string, timeStr: string): string {
  return `${dateStr}T${timeStr}:00`;
}

const HOUR_HEIGHT = 64;

export function getEventPosition(
  event: { dtstart: string; dtend: string },
  dayStart: Date
): { top: number; height: number } {
  const start = parseISO(event.dtstart);
  const end = parseISO(event.dtend);
  const dayBegin = new Date(dayStart);
  dayBegin.setHours(0, 0, 0, 0);

  const startMinutes = Math.max(0, differenceInMinutes(start, dayBegin));
  const endMinutes = Math.min(24 * 60, differenceInMinutes(end, dayBegin));
  const duration = Math.max(15, endMinutes - startMinutes);

  return {
    top: (startMinutes / 60) * HOUR_HEIGHT,
    height: (duration / 60) * HOUR_HEIGHT,
  };
}

interface EventWithTimes {
  dtstart: string;
  dtend: string;
}

export interface OverlapGroup<T extends EventWithTimes> {
  events: (T & { column: number; totalColumns: number })[];
}

export function getOverlappingGroups<T extends EventWithTimes>(events: T[]): OverlapGroup<T>[] {
  if (events.length === 0) return [];

  const sorted = [...events].sort(
    (a, b) => parseISO(a.dtstart).getTime() - parseISO(b.dtstart).getTime()
  );

  const groups: OverlapGroup<T>[] = [];
  let currentGroup: T[] = [sorted[0]];
  let groupEnd = parseISO(sorted[0].dtend).getTime();

  for (let i = 1; i < sorted.length; i++) {
    const evStart = parseISO(sorted[i].dtstart).getTime();
    if (evStart < groupEnd) {
      currentGroup.push(sorted[i]);
      groupEnd = Math.max(groupEnd, parseISO(sorted[i].dtend).getTime());
    } else {
      groups.push(assignColumns(currentGroup));
      currentGroup = [sorted[i]];
      groupEnd = parseISO(sorted[i].dtend).getTime();
    }
  }
  groups.push(assignColumns(currentGroup));

  return groups;
}

function assignColumns<T extends EventWithTimes>(events: T[]): OverlapGroup<T> {
  const columns: (T & { column: number; totalColumns: number })[] = [];
  const endTimes: number[] = [];

  for (const ev of events) {
    const start = parseISO(ev.dtstart).getTime();
    let col = 0;
    while (col < endTimes.length && endTimes[col] > start) {
      col++;
    }
    endTimes[col] = parseISO(ev.dtend).getTime();
    columns.push({ ...ev, column: col, totalColumns: 0 });
  }

  const totalCols = endTimes.length;
  for (const c of columns) {
    c.totalColumns = totalCols;
  }

  return { events: columns };
}

export const WEEKDAY_SHORT = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

export const MONTH_NAMES = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];
