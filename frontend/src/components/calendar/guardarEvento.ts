// Guardar un evento del calendario con todo lo que lo acompaña: la videollamada de Maquita Meet,
// los adjuntos, el vínculo con la reunión y las invitaciones a los asistentes.
// Vive aparte para que lo usen tanto el Calendario como el evento creado al arrastrar un correo.
import { api } from "../../api/client";
import type { CalendarEvent, EventFormData } from "./types/calendar";
import type { useCalendarApi } from "./hooks/useCalendarApi";
import { avisarFalloGeneralInvitaciones, avisarResultadoInvitaciones } from "./avisoInvitaciones";

type ApiCalendario = ReturnType<typeof useCalendarApi>;

/** Guarda el evento (nuevo o editado). Devuelve el evento guardado, o null si el servidor falló.
 *  `alGuardar` se llama en cuanto el evento existe, antes de subir adjuntos: así el diálogo se cierra sin esperar. */
export async function guardarEvento(
  calApi: ApiCalendario,
  data: EventFormData,
  editEvent: CalendarEvent | null,
  alGuardar?: () => void,
): Promise<object | null> {
  const { _attachments, _virtualMeeting, ...payload } = data;

  // Videollamada Maquita Meet (T-30): la reunión es UN registro del servicio de reuniones (mismo id en Raíces, en el
  // calendario y en la app). Se crea aquí y el evento lleva el enlace + la marca X-MAQUITA-REUNION:<id>.
  let reunionNueva: number | null = null;
  if (_virtualMeeting && !/(REUNION-ID|X-MAQUITA-REUNION):/.test(payload.description || "") && !/https?:\/\//.test(payload.location || "")) {
    try {
      const horas = Math.max(1, Math.ceil((new Date(payload.dtend).getTime() - new Date(payload.dtstart).getTime()) / 3600000));
      const m = await api.post<{ success: boolean; reunion: { id: number; url_sala: string; url_acceso: string } }>("/chat/reuniones", {
        asunto: payload.summary,
        inicio: payload.dtstart,
        duracion_horas: horas,
        participantes: [...(payload.attendees || []), ...(payload.optional_attendees || [])],
        calendario: false,
      });
      if (m?.reunion?.url_sala) {
        reunionNueva = m.reunion.id;
        if (!payload.location) payload.location = m.reunion.url_sala;
        payload.description = (payload.description ? payload.description + "\n\n" : "") +
          `Videollamada: ${m.reunion.url_sala}\nEntrar con tu usuario: ${m.reunion.url_acceso}?redirigir=1\nREUNION-ID: ${m.reunion.id}`;
      }
    } catch {
      console.error("[Calendar] No se pudo crear la videollamada de la reunión");
    }
  }
  // Evento ya vinculado a una reunión: al editarlo se actualiza la reunión (hora, asistentes, asunto)
  const reunionVinculada = /(?:REUNION-ID|X-MAQUITA-REUNION):\s*(\d+)/.exec((editEvent?.description || "") + " " + (payload.description || ""));

  const savedEvent = editEvent
    ? await calApi.updateEvent(editEvent.id, payload)
    : await calApi.createEvent(payload);
  if (!savedEvent) {
    console.error("[Calendar] Error guardando evento");
    return null;
  }
  alGuardar?.();

  // Subir adjuntos del evento (el endpoint requiere el id ya creado)
  const evId = (savedEvent as { id?: string }).id || editEvent?.id;
  if (_attachments && _attachments.length > 0 && evId) {
    for (const file of _attachments) {
      const fd = new FormData();
      fd.append("file", file);
      try {
        await fetch(`/api/calendar/events/${evId}/attachments`, {
          method: "POST", body: fd, credentials: "include",
        });
      } catch {
        console.error("[Calendar] Error subiendo adjunto", file.name);
      }
    }
  }

  // T-30: vínculo evento ⇄ reunión (mismo id) y sincronía al editar
  try {
    if (reunionNueva && evId) {
      await api.post(`/chat/reuniones/${reunionNueva}/vincular-evento`, { evento_id: evId, calendar_id: payload.calendar_id });
    } else if (editEvent && reunionVinculada) {
      const horas = Math.max(1, Math.ceil((new Date(payload.dtend).getTime() - new Date(payload.dtstart).getTime()) / 3600000));
      await api.put(`/chat/reuniones/${reunionVinculada[1]}`, {
        asunto: payload.summary, inicio: payload.dtstart, duracion_horas: horas,
        participantes: [...(payload.attendees || []), ...(payload.optional_attendees || [])], sin_calendario: true,
      });
    }
  } catch {
    console.error("[Calendar] No se pudo sincronizar la videollamada de la reunión");
  }

  // Si hay asistentes, enviar invitaciones automáticamente
  if ((data.attendees && data.attendees.length > 0) || (data.optional_attendees && data.optional_attendees.length > 0)) {
    const eventId = (savedEvent as { id: string }).id;
    if (eventId) {
      calApi.sendEventInvitations(eventId).then((res) => {
        if (res) avisarResultadoInvitaciones(res);
        else avisarFalloGeneralInvitaciones();
      }).catch(() => avisarFalloGeneralInvitaciones());
    }
  }
  return savedEvent;
}
