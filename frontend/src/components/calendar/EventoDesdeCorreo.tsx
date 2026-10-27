// Evento nuevo que se abre SOBRE el correo al soltar un mensaje en el ícono Calendario (como Outlook):
// no cambia de pantalla; al guardar se crea el evento y se envían las invitaciones.
import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { showToast } from "../common/Toast";
import type { MessageFull } from "../../types";
import type { CalendarInfo, EventFormData } from "./types/calendar";
import { useCalendarApi } from "./hooks/useCalendarApi";
import { EventModal } from "./EventModal";
import { guardarEvento } from "./guardarEvento";
import { EVENTO_DESDE_CORREO, eventoDesdeCorreo, type CorreoArrastrado, type EventoInicial } from "./eventoDesdeCorreo";

export function EventoDesdeCorreo() {
  const calApi = useCalendarApi();
  const { fetchCalendars, createCalendar } = calApi;
  const [calendarios, setCalendarios] = useState<CalendarInfo[]>([]);
  const [inicial, setInicial] = useState<EventoInicial | null>(null);
  // Cada soltado abre un diálogo nuevo, con sus campos de cero
  const [vez, setVez] = useState(0);

  useEffect(() => {
    const alSoltar = async (e: Event) => {
      const meta = (e as CustomEvent<CorreoArrastrado>).detail || {};
      let msg: MessageFull | null = null;
      if (meta.folder && meta.uid) {
        try {
          msg = await api.get<MessageFull>(`/mail/message/${encodeURIComponent(meta.folder)}/${meta.uid}`);
        } catch { /* sin el correo completo el evento sale igual, con el asunto y el remitente */ }
      }
      let cals = (await fetchCalendars()) || [];
      if (!cals.length) {
        // Cuenta sin ningún calendario: se crea el de siempre para poder guardar el evento
        const nuevo = await createCalendar({ name: "Mi calendario", color: "#0078d4" });
        if (nuevo) cals = [nuevo as CalendarInfo];
      }
      setCalendarios(cals);
      setInicial(eventoDesdeCorreo(meta, msg));
      setVez((v) => v + 1);
    };
    window.addEventListener(EVENTO_DESDE_CORREO, alSoltar);
    return () => window.removeEventListener(EVENTO_DESDE_CORREO, alSoltar);
  }, [fetchCalendars, createCalendar]);

  if (!inicial) return null;

  const guardar = async (data: EventFormData) => {
    const guardado = await guardarEvento(calApi, data, null, () => setInicial(null));
    if (guardado) showToast(data.attendees?.length ? "Evento creado y enviada la invitación" : "Evento creado");
  };

  return (
    <EventModal
      key={vez}
      isOpen
      event={null}
      initialDate={inicial.fecha}
      initialHour={inicial.hora}
      initialDurationMinutes={30}
      initialSummary={inicial.titulo}
      initialDescription={inicial.descripcion}
      initialAttendees={inicial.asistentes}
      initialVirtualMeeting
      calendars={calendarios}
      onSave={guardar}
      onDelete={() => setInicial(null)}
      onClose={() => setInicial(null)}
    />
  );
}
