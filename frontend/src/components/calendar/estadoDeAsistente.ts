/** Respuesta de un asistente a la cita (ACCEPTED, DECLINED, TENTATIVE o vacía), para EstadoAsistente.tsx. */
import type { CalendarEvent, EventAttendee } from "./types/calendar";

export function estadoDeAsistente(event: CalendarEvent | null | undefined, email: string): string {
  const lista = (event?.attendees || []) as (EventAttendee | string)[];
  for (const a of lista) {
    if (typeof a === "string") continue;
    if ((a.email || "").toLowerCase() === email.toLowerCase()) return (a.status || "").toUpperCase();
  }
  return "";
}
