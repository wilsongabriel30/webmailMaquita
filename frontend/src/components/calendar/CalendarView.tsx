import { api } from "../../api/client";
import { SchedulingAssistant } from './SchedulingAssistant';
import { useState, useEffect, useCallback, useMemo } from "react";
import type { ViewMode, CalendarInfo, CalendarEvent, EventFormData } from "./types/calendar";
import { useCalendarApi } from "./hooks/useCalendarApi";
import { CalendarHeader, type CalendarFilters } from "./CalendarHeader";
import { CalendarSidebar } from "./CalendarSidebar";
import { MonthView } from "./MonthView";
import { WeekView } from "./WeekView";
import { DayView } from "./DayView";
import { AgendaView } from "./AgendaView";
import { EventModal } from "./EventModal";
import {
  startOfMonth,
  endOfMonth,
  startOfWeek,
  endOfWeek,
  addDays,
  format,
} from "date-fns";

/* Colores del submenú "Categorías" del filtro (CalendarHeader) */
const CATEGORY_COLORS: Record<string, string> = {
  "#e74c3c": "Categoría roja",
  "#e67e22": "Categoría naranja",
  "#f1c40f": "Categoría amarilla",
  "#2ecc71": "Categoría verde",
  "#3498db": "Categoría azul",
  "#9b59b6": "Categoría púrpura",
};

/** Aplica los filtros del menú Filtrar. Todo marcado (estado por defecto) = se muestra todo. */
function eventPassesFilters(ev: CalendarEvent, f: CalendarFilters | null): boolean {
  if (!f) return true;
  const sub = (cat: string, label: string) => f.subs[`${cat}:${label}`] !== false;
  const isMeeting = (ev.attendees?.length || 0) > 0;

  // Citas = sin asistentes; Reuniones = con asistentes
  if (!isMeeting) {
    if (!f.cats.citas) return false;
  } else {
    if (!f.cats.reuniones) return false;
    const st = (ev.status || "").toUpperCase();
    if (st === "CANCELLED" && !sub("reuniones", "Cancelado")) return false;
    if (st === "TENTATIVE" && !sub("reuniones", "Provisional")) return false;
    if (st === "CONFIRMED" && !sub("reuniones", "Aceptado")) return false;
    // Estado vacío o no estándar: tratar como "Sin respuesta" para que el
    // filtro de reuniones también aplique a estos eventos.
    if (!["CANCELLED", "TENTATIVE", "CONFIRMED"].includes(st) && !sub("reuniones", "Sin respuesta")) return false;
  }

  // Periodicidad: Simples (sin rrule) / Serie (con rrule)
  if (ev.rrule) {
    if (!f.cats.periodicidad || !sub("periodicidad", "Serie")) return false;
  } else if (!f.cats.periodicidad || !sub("periodicidad", "Simples")) {
    return false;
  }

  // Categorías por color del evento
  const catLabel = CATEGORY_COLORS[(ev.color || "").toLowerCase()] || "Sin categoría";
  if (!f.cats.categorias || !sub("categorias", catLabel)) return false;

  return true;
}

function getDateRange(date: Date, view: ViewMode): { start: string; end: string } {
  let s: Date;
  let e: Date;
  switch (view) {
    case "month":
      s = startOfWeek(startOfMonth(date), { weekStartsOn: 1 });
      e = endOfWeek(endOfMonth(date), { weekStartsOn: 1 });
      break;
    case "week":
      s = startOfWeek(date, { weekStartsOn: 1 });
      e = endOfWeek(date, { weekStartsOn: 1 });
      break;
    case "workweek":
      s = startOfWeek(date, { weekStartsOn: 1 });
      e = addDays(s, 4);
      e.setHours(23, 59, 59, 999);
      break;
    case "day":
      s = new Date(date);
      s.setHours(0, 0, 0, 0);
      e = new Date(date);
      e.setHours(23, 59, 59, 999);
      break;
    case "agenda":
      s = new Date(date);
      s.setHours(0, 0, 0, 0);
      e = addDays(s, 30);
      break;
  }
  return {
    start: format(s, "yyyy-MM-dd'T'HH:mm:ss"),
    end: format(e, "yyyy-MM-dd'T'HH:mm:ss"),
  };
}

export default function CalendarView() {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [viewMode, setViewMode] = useState<ViewMode>("month");
  const [calendars, setCalendars] = useState<CalendarInfo[]>([]);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [selectedCalendarIds, setSelectedCalendarIds] = useState<Set<string>>(new Set());
  const [sidebarVisible, setSidebarVisible] = useState(() => typeof window === 'undefined' || window.innerWidth >= 768);
  const [splitView, setSplitView] = useState(false);
  const [calFilters, setCalFilters] = useState<CalendarFilters | null>(null);

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [editEvent, setEditEvent] = useState<CalendarEvent | null>(null);
  const [modalInitialDate, setModalInitialDate] = useState<Date | undefined>();
  const [modalInitialHour, setModalInitialHour] = useState<number | undefined>();
  const [modalInitialDuration, setModalInitialDuration] = useState<number | undefined>();
  const [modalInitialSummary, setModalInitialSummary] = useState<string | undefined>();
  const [modalInitialDescription, setModalInitialDescription] = useState<string | undefined>();

  useEffect(() => {
    let raw: string | null = null;
    try { raw = sessionStorage.getItem('pending-event-from-mail'); } catch {}
    if (!raw) return;
    try { sessionStorage.removeItem('pending-event-from-mail'); } catch {}
    try {
      const m = JSON.parse(raw);
      setEditEvent(null);
      setModalInitialDate(new Date());
      setModalInitialHour(undefined);
      setModalInitialDuration(undefined);
      setModalInitialSummary(m.subject || 'Evento desde correo');
      setModalInitialDescription(`Creado desde el correo de ${m.from || 'remitente desconocido'}:\n"${m.subject || ''}"`);
      setModalOpen(true);
    } catch {}
  }, []);

  const calApi = useCalendarApi();
  const { fetchCalendars, fetchEvents, createEvent, updateEvent, deleteEvent, moveEvent, createCalendar, deleteCalendar,
          shareCalendar, listSharedWithMe,
          loading, error } = calApi;

  // Compartición de calendarios
  const [sharedCalendars, setSharedCalendars] = useState<object[]>([]);
  const [shareModalOpen, setShareModalOpen] = useState(false);
  const [shareCalendarId, setShareCalendarId] = useState<string>('');
  const [shareWithEmail, setShareWithEmail] = useState('');
  const [sharePermission, setSharePermission] = useState<'read' | 'read-write'>('read');
const [showScheduling, setShowScheduling] = useState(false);

  // Load calendars on mount + calendarios compartidos conmigo
  useEffect(() => {
    fetchCalendars().then((cals) => {
      if (cals) {
        setCalendars(cals);
        setSelectedCalendarIds(new Set(cals.map((c) => c.id)));
      }
    });
    listSharedWithMe().then((shared) => {
      if (shared) setSharedCalendars(shared as object[]);
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchCalendars]);

  // Load events when date/view changes
  const loadEvents = useCallback(async () => {
    const { start, end } = getDateRange(currentDate, viewMode);
    const evts = await fetchEvents(start, end);
    if (evts) {
      setEvents(evts);
    }
  }, [currentDate, viewMode, fetchEvents]);

  useEffect(() => {
    if (calendars.length > 0) {
      loadEvents();
    }
  }, [loadEvents, calendars]);

  // Filter events by selected calendars + filtros del menú Filtrar
  const filteredEvents = useMemo(
    () =>
      events.filter(
        (ev) => selectedCalendarIds.has(ev.calendar_id) && eventPassesFilters(ev, calFilters)
      ),
    [events, selectedCalendarIds, calFilters]
  );

  function toggleCalendar(id: string) {
    setSelectedCalendarIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function openNewEvent(date?: Date, hour?: number, durationMinutes?: number) {
    setEditEvent(null);
    setModalInitialDate(date);
    setModalInitialHour(hour);
    setModalInitialDuration(durationMinutes);
    setModalInitialSummary(undefined);
    setModalInitialDescription(undefined);
    setModalOpen(true);
  }

  function handleRangeSelect(date: Date, startHour: number, endHour: number) {
    openNewEvent(date, startHour, Math.round((endHour - startHour) * 60));
  }

  function openEditEvent(ev: CalendarEvent) {
    setEditEvent(ev);
    setModalInitialDate(undefined);
    setModalInitialHour(undefined);
    setModalOpen(true);
  }

  async function handleSaveEvent(data: EventFormData) {
    const { _attachments, _virtualMeeting, ...payload } = data;

    // Reunión virtual: generar sala Jitsi y dejar el enlace en ubicación/descripción
    if (_virtualMeeting && !/https?:\/\//.test(payload.location || "")) {
      try {
        // Sin attendees aquí: pasarlos hacía que /meetings/create enviara su propio
        // correo simple por SMTP síncrono (guardado lento + invitación duplicada sin
        // formato). La única invitación (formateada, con el enlace en ubicación/
        // descripción) la envía sendEventInvitations() al final.
        const m = await api.post<{ meeting_url: string }>("/meetings/create", {
          title: payload.summary,
          start_time: payload.dtstart,
          attendees: [],
        });
        if (m?.meeting_url) {
          if (!payload.location) payload.location = m.meeting_url;
          payload.description = (payload.description ? payload.description + "\n\n" : "") +
            `Reunión virtual: ${m.meeting_url}`;
        }
      } catch {
        console.error("[Calendar] No se pudo crear la sala de reunión virtual");
      }
    }

    let savedEvent: object | null = null;
    if (editEvent) {
      savedEvent = await updateEvent(editEvent.id, payload);
    } else {
      savedEvent = await createEvent(payload);
    }
    if (!savedEvent) {
      // No cerrar modal si hubo error — el usuario debe ver que falló
      console.error("[Calendar] Error guardando evento");
      return;
    }
    setModalOpen(false);

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

    loadEvents();
    // Si hay asistentes, enviar invitaciones automáticamente
    if ((data.attendees && data.attendees.length > 0) || (data.optional_attendees && data.optional_attendees.length > 0)) {
      const eventId = (savedEvent as { id: string }).id;
      if (eventId) {
        calApi.sendEventInvitations(eventId).then((res) => {
          if (res && (res as { sent: number }).sent > 0) {
            console.info(`Invitaciones enviadas: ${(res as { sent: number }).sent}`);
          }
        }).catch(() => {/* silencioso */});
      }
    }
  }

  async function handleDeleteCalendar(id: string, name: string) {
    if (!window.confirm(`¿Eliminar el calendario "${name}" y todos sus eventos? Esta acción no se puede deshacer.`)) return;
    const ok = await deleteCalendar(id);
    if (ok) {
      setCalendars((prev) => prev.filter((c) => c.id !== id));
      setSelectedCalendarIds((prev) => { const n = new Set(prev); n.delete(id); return n; });
      loadEvents();
    } else {
      window.alert("No se pudo eliminar el calendario.");
    }
  }

  async function handleDeleteEvent(id: string) {
    await deleteEvent(id);
    setModalOpen(false);
    loadEvents();
  }

  async function handleMoveEvent(eventId: string, dtstart: string, dtend: string) {
    await moveEvent(eventId, dtstart, dtend);
    loadEvents();
  }

  function handleDateClick(date: Date) {
    openNewEvent(date);
  }

  function handleSlotClick(date: Date, hour: number) {
    openNewEvent(date, hour);
  }

  function handleOpenShareModal(calendarId: string) {
    setShareCalendarId(calendarId);
    setShareWithEmail('');
    setSharePermission('read');
    setShareModalOpen(true);
  }

  async function handleShareCalendar() {
    if (!shareWithEmail.trim()) return;
    await shareCalendar(shareCalendarId, shareWithEmail.trim(), sharePermission);
    setShareModalOpen(false);
    // Recargar compartidos
    listSharedWithMe().then((shared) => {
      if (shared) setSharedCalendars(shared as object[]);
    });
  }

  function handleAddCalendar() {
    const name = prompt("Nombre del nuevo calendario:");
    if (!name) return;
    const color = "#0078d4";
    createCalendar({ name, color }).then((cal) => {
      if (cal) {
        setCalendars((prev) => [...prev, cal]);
        setSelectedCalendarIds((prev) => new Set([...prev, cal.id]));
      }
    });
  }

  // Listen for sidebar toggle
  useEffect(() => {
    const handler = () => setSidebarVisible((v) => !v);
    window.addEventListener("toggle-sidebar", handler);
    return () => window.removeEventListener("toggle-sidebar", handler);
  }, []);

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* Sidebar */}
      {sidebarVisible && (
        <CalendarSidebar
          calendars={calendars}
          selectedCalendarIds={selectedCalendarIds}
          currentDate={currentDate}
          onDateSelect={(d) => {
            setCurrentDate(d);
            setViewMode("day");
          }}
          onToggleCalendar={toggleCalendar}
          onNewEvent={() => openNewEvent()}
          onAddCalendar={handleAddCalendar}
          onDeleteCalendar={handleDeleteCalendar}
          sharedCalendars={sharedCalendars as any[]}
          onShareCalendar={handleOpenShareModal}
        />
      )}

      {/* Main */}
      <div className="flex-1 flex flex-col bg-white dark:bg-[#292827]" style={{ minWidth: 0 }}>
        <CalendarHeader
          currentDate={currentDate}
          viewMode={viewMode}
          onDateChange={setCurrentDate}
          onViewChange={setViewMode}
          onNewEvent={() => openNewEvent()}
          onToday={() => setCurrentDate(new Date())}
          onScheduling={() => setShowScheduling(true)}
          splitView={splitView}
          onSplitViewChange={setSplitView}
          onFiltersChange={setCalFilters}
        />

        <div className="flex-1 flex flex-col overflow-hidden">
        {/* Loading indicator */}
        {loading && (
          <div className="h-0.5 bg-[#0078d4]/20 overflow-hidden">
            <div className="h-full w-1/3 bg-[#0078d4] animate-[loading_1s_ease-in-out_infinite]" />
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="px-4 py-2 bg-[#fde7e9] dark:bg-[#442726] text-[#a4262c] dark:text-[#f1707b] text-[12px] flex items-center gap-2">
            <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {error}
          </div>
        )}

        {/* Views (+ panel de agenda cuando "Vista en dos paneles" está activa) */}
        <div className="flex-1 flex overflow-hidden">
        <div className="flex-1 flex flex-col overflow-hidden" style={{ minWidth: 0 }}>
        {viewMode === "month" && (
          <MonthView
            currentDate={currentDate}
            events={filteredEvents}
            onEventClick={openEditEvent}
            onDateClick={handleDateClick}
            onEventMove={handleMoveEvent}
            onShowMore={(d) => { setCurrentDate(d); setViewMode("day"); }}
          />
        )}
        {viewMode === "week" && (
          <WeekView
            currentDate={currentDate}
            events={filteredEvents}
            onEventClick={openEditEvent}
            onSlotClick={handleSlotClick}
            onRangeSelect={handleRangeSelect}
            onEventMove={handleMoveEvent}
          />
        )}
        {viewMode === "workweek" && (
          <WeekView
            currentDate={currentDate}
            events={filteredEvents}
            onEventClick={openEditEvent}
            onSlotClick={handleSlotClick}
            onRangeSelect={handleRangeSelect}
            onEventMove={handleMoveEvent}
          />
        )}
        {viewMode === "day" && (
          <DayView
            currentDate={currentDate}
            events={filteredEvents}
            onEventClick={openEditEvent}
            onSlotClick={handleSlotClick}
            onRangeSelect={handleRangeSelect}
            onEventMove={handleMoveEvent}
          />
        )}
        {viewMode === "agenda" && (
          <AgendaView
            currentDate={currentDate}
            events={filteredEvents}
            onEventClick={openEditEvent}
          />
        )}
        </div>{/* end vista principal */}

        {/* Panel derecho: agenda de próximos eventos (Vista en dos paneles) */}
        {splitView && viewMode !== "agenda" && (
          <div className="w-[340px] shrink-0 border-l border-[#edebe9] dark:border-[#3b3a39] flex flex-col overflow-y-auto bg-white dark:bg-[#292827]">
            <div className="px-4 py-[10px] text-[13px] font-semibold text-[#323130] dark:text-[#f3f2f1] border-b border-[#edebe9] dark:border-[#3b3a39] shrink-0">
              Próximos eventos
            </div>
            <AgendaView
              currentDate={new Date(currentDate.getFullYear(), currentDate.getMonth(), currentDate.getDate())}
              events={filteredEvents}
              onEventClick={openEditEvent}
            />
          </div>
        )}
        </div>{/* end split container */}
        </div>{/* end overflow content area */}
      </div>

      {/* Modal de compartición */}
      {shareModalOpen && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ background: '#fff', borderRadius: 8, padding: 24, minWidth: 340, boxShadow: '0 8px 32px rgba(0,0,0,0.18)' }}>
            <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16, color: '#323130' }}>Compartir calendario</h3>
            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 12, color: '#605e5c', display: 'block', marginBottom: 4 }}>Compartir con (email)</label>
              <input
                type="email"
                value={shareWithEmail}
                onChange={(e) => setShareWithEmail(e.target.value)}
                placeholder="usuario@ejemplo.com"
                style={{ width: '100%', border: '1px solid #c8c6c4', borderRadius: 4, padding: '6px 8px', fontSize: 13 }}
              />
            </div>
            <div style={{ marginBottom: 20 }}>
              <label style={{ fontSize: 12, color: '#605e5c', display: 'block', marginBottom: 4 }}>Permiso</label>
              <select
                value={sharePermission}
                onChange={(e) => setSharePermission(e.target.value as 'read' | 'read-write')}
                style={{ width: '100%', border: '1px solid #c8c6c4', borderRadius: 4, padding: '6px 8px', fontSize: 13 }}
              >
                <option value="read">Solo lectura</option>
                <option value="read-write">Lectura y escritura</option>
              </select>
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button onClick={() => setShareModalOpen(false)} style={{ padding: '6px 16px', fontSize: 13, border: '1px solid #c8c6c4', borderRadius: 4, background: '#fff', cursor: 'pointer' }}>Cancelar</button>
              <button onClick={handleShareCalendar} style={{ padding: '6px 16px', fontSize: 13, border: 'none', borderRadius: 4, background: '#0078d4', color: '#fff', cursor: 'pointer' }}>Compartir</button>
            </div>
          </div>
        </div>
      )}

      {/* Event Modal */}
{showScheduling && <SchedulingAssistant onClose={() => setShowScheduling(false)} onSelectSlot={(start) => { setModalInitialDate(new Date(start)); setModalOpen(true); setShowScheduling(false); }} />}
      <EventModal
        isOpen={modalOpen}
        event={editEvent}
        initialDate={modalInitialDate}
        initialHour={modalInitialHour}
        initialDurationMinutes={modalInitialDuration}
        initialSummary={modalInitialSummary}
        initialDescription={modalInitialDescription}
        calendars={calendars}
        onSave={handleSaveEvent}
        onDelete={handleDeleteEvent}
        onClose={() => setModalOpen(false)}
      />

      <style>{`
        @keyframes loading {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(400%); }
        }
      `}</style>
    </div>
  );
}
