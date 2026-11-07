/**
 * EstadoAsistente.tsx — Respuesta de cada asistente junto a su nombre (05/11/2026).
 * ✓ aceptó · ✗ rechazó · ? provisional · sin marca = no ha respondido.
 */
import type { CalendarEvent, EventAttendee } from "./types/calendar";

const MARCAS: Record<string, { texto: string; titulo: string; color: string }> = {
  ACCEPTED: { texto: "✓", titulo: "Aceptó", color: "#107c10" },
  DECLINED: { texto: "✗", titulo: "Rechazó", color: "#d13438" },
  TENTATIVE: { texto: "?", titulo: "Provisional", color: "#ca5010" },
};

export function estadoDeAsistente(event: CalendarEvent | null | undefined, email: string): string {
  const lista = (event?.attendees || []) as (EventAttendee | string)[];
  for (const a of lista) {
    if (typeof a === "string") continue;
    if ((a.email || "").toLowerCase() === email.toLowerCase()) return (a.status || "").toUpperCase();
  }
  return "";
}

export function EstadoAsistente({ estado }: { estado: string }) {
  const m = MARCAS[estado];
  if (!m) return null;
  return (
    <span title={m.titulo} aria-label={m.titulo}
      style={{ marginLeft: 4, fontSize: 11, fontWeight: 700, color: m.color }}>
      {m.texto}
    </span>
  );
}
