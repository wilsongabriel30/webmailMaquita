/**
 * eventosCompartidos.ts — Calendarios que otras personas comparten conmigo (05/11/2026).
 * Hasta hoy el panel lateral los listaba pero sus eventos no se cargaban en la vista. Aquí se unen
 * a los propios y se preparan para el diálogo de evento (con «solo lectura» si el permiso no es
 * de escritura).
 */
import type { SharedCalendarInfo } from "./CalendarSidebar";
import type { CalendarEvent, CalendarInfo } from "./types/calendar";

export function unirEventosCompartidos(propios: CalendarEvent[], compartidos: object[] | null | undefined): CalendarEvent[] {
  if (!compartidos || compartidos.length === 0) return propios;
  const vistos = new Set(propios.map((e) => e.id));
  const extra = (compartidos as CalendarEvent[]).filter((e) => e && e.id && !vistos.has(e.id));
  return extra.length ? [...propios, ...extra] : propios;
}

export function calendariosParaDialogo(propios: CalendarInfo[], compartidos: SharedCalendarInfo[]): CalendarInfo[] {
  if (!compartidos.length) return propios;
  const ids = new Set(propios.map((c) => c.id));
  const ajenos: CalendarInfo[] = compartidos
    .filter((sc) => !ids.has(sc.calendar_id))
    .map((sc) => ({
      id: sc.calendar_id,
      name: `${sc.calendar_name} (${sc.owner_email.split("@")[0]})`,
      color: sc.calendar_color,
      timezone: "America/Guayaquil",
      is_default: false,
      solo_lectura: sc.permission !== "read-write",
    }));
  return [...propios, ...ajenos];
}
