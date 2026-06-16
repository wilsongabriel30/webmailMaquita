import { useEffect, useState, useCallback } from "react";
import { useResponsive } from "../../hooks/useResponsive";
import { Toolbar } from './Toolbar';
import { MessageList } from './MessageList';
import { MessageView } from './MessageView';
import { ComposePanel } from '../compose/ComposePanel';
import { ToastContainer } from '../common/Toast';
import { useSearchParams } from "react-router-dom";
import { useMailStore } from '../../store/mailStore';

function MyDayPanel({ onClose }: { onClose: () => void }) {
  const now = new Date();
  const month = now.toLocaleDateString('es-EC', { month: 'long', year: 'numeric' });
  const today = now.getDate();
  const dayName = now.toLocaleDateString('es-EC', { weekday: 'long' });
  const currentHour = now.getHours();
  const firstDay = new Date(now.getFullYear(), now.getMonth(), 1).getDay();
  const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();

  const [events, setEvents] = useState<any[]>([]);
  const [loadingEvents, setLoadingEvents] = useState(true);
  const [creatingAt, setCreatingAt] = useState<number | null>(null);
  const [newEventTitle, setNewEventTitle] = useState('');
  const [selectedEvent, setSelectedEvent] = useState<any>(null);

  // Build calendar grid
  const weeks: (number | null)[][] = [];
  let week: (number | null)[] = Array(firstDay).fill(null);
  for (let d = 1; d <= daysInMonth; d++) {
    week.push(d);
    if (week.length === 7) { weeks.push(week); week = []; }
  }
  if (week.length > 0) { while (week.length < 7) week.push(null); weeks.push(week); }

  // Load today's events from calendar API
  const loadEvents = useCallback(async () => {
    try {
      const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      const endOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
      const params = new URLSearchParams({
        start: startOfDay.toISOString(),
        end: endOfDay.toISOString(),
      });
      const res = await fetch('/api/calendar/events?' + params.toString(), { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setEvents(Array.isArray(data) ? data : []);
      }
    } catch {}
    setLoadingEvents(false);
  }, []);

  useEffect(() => { loadEvents(); }, [loadEvents]);

  // Work hours: 7:00 to 18:00
  const hours = Array.from({ length: 12 }, (_, i) => i + 7);

  // Get events for a specific hour
  const getEventsForHour = (hour: number) => {
    return events.filter(ev => {
      const start = new Date(ev.start || ev.start_time);
      return start.getHours() === hour;
    });
  };

  // Create quick event
  const handleCreateEvent = async (hour: number) => {
    if (!newEventTitle.trim()) { setCreatingAt(null); return; }
    try {
      const start = new Date(now.getFullYear(), now.getMonth(), now.getDate(), hour, 0);
      const end = new Date(now.getFullYear(), now.getMonth(), now.getDate(), hour + 1, 0);
      // First get or use default calendar
      const calRes = await fetch('/api/calendar/calendars', { credentials: 'include' });
      let calId = '';
      if (calRes.ok) {
        const cals = await calRes.json();
        if (cals.length > 0) calId = cals[0].id;
      }
      if (!calId) {
        // Create default calendar
        const createCal = await fetch('/api/calendar/calendars', {
          method: 'POST', credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: 'Mi calendario', color: '#0078d4' })
        });
        if (createCal.ok) { const c = await createCal.json(); calId = c.id; }
      }
      if (calId) {
        await fetch('/api/calendar/events', {
          method: 'POST', credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            calendar_id: calId,
            title: newEventTitle.trim(),
            start: start.toISOString(),
            end: end.toISOString(),
          })
        });
        await loadEvents();
      }
    } catch {}
    setNewEventTitle('');
    setCreatingAt(null);
  };

  // Delete event
  const handleDeleteEvent = async (eventId: string) => {
    try {
      await fetch(`/api/calendar/events/${eventId}`, { method: 'DELETE', credentials: 'include' });
      setSelectedEvent(null);
      await loadEvents();
    } catch {}
  };

  // Format hour
  const fmtHour = (h: number) => {
    if (h === 0) return '12:00';
    if (h < 12) return h + ':00';
    if (h === 12) return '12:00';
    return (h - 12) + ':00';
  };

  return (
    <div className="w-[300px] shrink-0 border-l border-[#edebe9] bg-white flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#edebe9] shrink-0">
        <span className="text-[15px] font-semibold text-[#323130]">Calendario</span>
        <button onClick={onClose} className="text-[#605e5c] hover:text-[#323130] text-[18px] leading-none">&times;</button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Calendar mini */}
        <div className="px-4 py-3 border-b border-[#edebe9]">
          <div className="text-[13px] font-semibold text-[#323130] mb-2 capitalize">{month}</div>
          <table className="w-full text-center text-[12px]">
            <thead>
              <tr className="text-[#605e5c]">
                {['Do','Lu','Ma','Mi','Ju','Vi','S\u00e1'].map(d => <th key={d} className="py-1 font-normal">{d}</th>)}
              </tr>
            </thead>
            <tbody>
              {weeks.map((w, i) => (
                <tr key={i}>
                  {w.map((d, j) => (
                    <td key={j} className="py-0.5">
                      {d && (
                        <span className={d === today
                          ? 'inline-flex items-center justify-center w-[26px] h-[26px] rounded-full bg-[#0078d4] text-white font-semibold text-[12px]'
                          : 'inline-flex items-center justify-center w-[26px] h-[26px] rounded-full hover:bg-[#f3f2f1] text-[12px] text-[#323130] cursor-pointer'
                        }>{d}</span>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Day header */}
        <div className="px-4 py-2 border-b border-[#edebe9] shrink-0 flex items-center justify-between">
          <div className="text-[13px] font-semibold text-[#323130] capitalize">{dayName}, {today} de {now.toLocaleDateString('es-EC', { month: 'long' })}</div>
          <span className="text-[11px] text-[#605e5c]">{events.length} evento{events.length !== 1 ? 's' : ''}</span>
        </div>

        {/* Event detail popup */}
        {selectedEvent && (
          <div className="mx-3 my-2 bg-[#f0f6ff] border border-[#c7e0f4] rounded p-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[13px] font-semibold text-[#0078d4]">{selectedEvent.title || selectedEvent.summary || 'Evento'}</span>
              <button onClick={() => setSelectedEvent(null)} className="text-[#605e5c] hover:text-[#323130] text-[14px]">&times;</button>
            </div>
            <div className="text-[11px] text-[#605e5c]">
              {new Date(selectedEvent.start || selectedEvent.start_time).toLocaleTimeString('es-EC', { hour: '2-digit', minute: '2-digit' })}
              {' - '}
              {new Date(selectedEvent.end || selectedEvent.end_time).toLocaleTimeString('es-EC', { hour: '2-digit', minute: '2-digit' })}
            </div>
            {selectedEvent.location && <div className="text-[11px] text-[#605e5c] mt-1">&#x1f4cd; {selectedEvent.location}</div>}
            {selectedEvent.description && <div className="text-[11px] text-[#323130] mt-1">{selectedEvent.description}</div>}
            <button onClick={() => handleDeleteEvent(selectedEvent.id)}
              className="mt-2 text-[11px] text-[#d13438] hover:underline">Eliminar evento</button>
          </div>
        )}

        {/* Hourly agenda — 7:00 to 18:00 */}
        <div className="px-1">
          {loadingEvents ? (
            <div className="text-[12px] text-[#605e5c] px-3 py-4">Cargando eventos...</div>
          ) : (
            hours.map(hour => {
              const hourEvents = getEventsForHour(hour);
              const isPast = hour < currentHour;
              const isCurrent = hour === currentHour;
              const isCreating = creatingAt === hour;
              return (
                <div key={hour}
                  className={`flex border-b border-[#f3f2f1] min-h-[40px] group cursor-pointer hover:bg-[#faf9f8] ${isPast ? 'opacity-50' : ''}`}
                  onClick={() => { if (!isCreating && hourEvents.length === 0) { setCreatingAt(hour); setNewEventTitle(''); } }}>
                  <div className={`w-[50px] shrink-0 text-[11px] py-2 px-2 text-right ${isCurrent ? 'text-[#0078d4] font-semibold' : 'text-[#605e5c]'}`}>
                    {fmtHour(hour)}
                  </div>
                  <div className={`flex-1 py-1 px-1 ${isCurrent ? 'border-l-2 border-[#0078d4] bg-[#f0f6ff]' : 'border-l border-[#edebe9]'}`}>
                    {isCreating ? (
                      <input
                        autoFocus
                        value={newEventTitle}
                        onChange={(e) => setNewEventTitle(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') handleCreateEvent(hour); if (e.key === 'Escape') setCreatingAt(null); }}
                        onBlur={() => handleCreateEvent(hour)}
                        placeholder="Nuevo evento..."
                        className="w-full text-[11px] px-2 py-1 border border-[#0078d4] rounded outline-none bg-white"
                        onClick={(e) => e.stopPropagation()}
                      />
                    ) : hourEvents.length > 0 ? hourEvents.map((ev, i) => (
                      <div key={i}
                        onClick={(e) => { e.stopPropagation(); setSelectedEvent(ev); }}
                        className="bg-[#0078d4] text-white text-[11px] px-2 py-1.5 rounded mb-0.5 truncate cursor-pointer hover:bg-[#106ebe] flex items-center gap-1">
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4M8 2v4M3 10h18" /></svg>
                        <span className="truncate">{ev.title || ev.summary || 'Evento'}</span>
                      </div>
                    )) : (
                      <div className="text-[10px] text-transparent group-hover:text-[#a19f9d] py-1 px-1">+ Agregar evento</div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}

// Divisor arrastrable entre la lista de mensajes y el panel de lectura.
// Al arrastrarlo cambia el ancho de la lista; el panel de la derecha (flex-1)
// se ajusta solo, asi el correo abierto se ve mas ancho o mas angosto.
function ListResizeHandle() {
  const setMessageListWidth = useMailStore(s => s.setMessageListWidth);
  const onMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startW = useMailStore.getState().messageListWidth;
    const onMove = (ev: MouseEvent) => setMessageListWidth(startW + (ev.clientX - startX));
    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  };
  return (
    <div
      onMouseDown={onMouseDown}
      title="Arrastra para ajustar el ancho de la lista"
      className="w-[5px] shrink-0 cursor-col-resize bg-transparent hover:bg-[#0078d4]/40 active:bg-[#0078d4]/60 transition-colors max-md:hidden"
    />
  );
}

export function MailView() {
  const composeWindows = useMailStore(s => s.composeWindows);
  const restoreCompose = useMailStore(s => s.restoreCompose);
  const closeCompose = useMailStore(s => s.closeCompose);
  const openCompose = useMailStore(s => s.openCompose);
  const storeReadingPane = useMailStore(s => s.readingPane);
  const selectedMessage = useMailStore(s => s.selectedMessage);
  const setSelectedMessage = useMailStore(s => s.setSelectedMessage);
  const showMyDay = useMailStore(s => s.showMyDay);
  const setShowMyDay = useMailStore(s => s.setShowMyDay);
  const { isMobile } = useResponsive();
  const readingPane = isMobile ? "off" : storeReadingPane;

  // Auto-open compose when navigated with ?compose=new (from calendar)
  const [searchParams, setSearchParams] = useSearchParams();
  useEffect(() => {
    if (searchParams.get('compose') === 'new') {
      openCompose('new');
      searchParams.delete('compose');
      setSearchParams(searchParams, { replace: true });
    }
  }, []);

  const activeCompose = composeWindows.find(w => !w.minimized);
  const minimizedComposes = composeWindows.filter(w => w.minimized);

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Toolbar */}
      <div className="shrink-0 relative z-[50]">
        <Toolbar />
      </div>

      {/* Content area + optional Mi día sidebar */}
      <div className="flex-1 flex overflow-hidden min-h-0">
      <div className="flex-1 flex flex-col overflow-hidden min-h-0">
      {/* Content: layout changes based on readingPane */}
      {readingPane === 'right' && (
        /* ── DERECHA: lista izquierda + lectura/compose derecha (default Outlook) ── */
        <div className="flex-1 flex overflow-hidden min-h-0">
          <MessageList />
          <ListResizeHandle />
          <div className="flex-1 min-w-0 flex flex-col">
            {activeCompose ? (
              <ComposePanel key={activeCompose.id} win={activeCompose} />
            ) : (
              <MessageView />
            )}
          </div>
        </div>
      )}

      {readingPane === 'bottom' && (
        /* ── ABAJO: lista arriba + lectura/compose abajo (split horizontal) ── */
        <div className="flex-1 flex flex-col overflow-hidden min-h-0">
          <div className="h-[45%] min-h-[150px] border-b border-[#edebe9] overflow-hidden flex [&_.message-list-container]:w-full [&_.message-list-container]:h-full [&_.message-list-container]:border-r-0">
            <MessageList />
          </div>
          <div className="flex-1 overflow-hidden">
            {activeCompose ? (
              <ComposePanel key={activeCompose.id} win={activeCompose} />
            ) : (
              <MessageView />
            )}
          </div>
        </div>
      )}

      {readingPane === "off" && (
        /* ── OCULTO (legacy) ── */
        <div className="flex-1 flex flex-col overflow-hidden min-h-0">
          {activeCompose ? (
            <ComposePanel key={activeCompose.id} win={activeCompose} />
          ) : selectedMessage ? (
            <>
              <div className="shrink-0 flex items-center gap-2 px-3 py-1.5 border-b border-[#edebe9] bg-[#faf9f8]">
                <button onClick={() => setSelectedMessage(null)}
                  className="flex items-center gap-1 text-[13px] text-[#0078d4] hover:underline">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M10.5 3L5 8l5.5 5V3z"/></svg>
                  Volver a la bandeja
                </button>
              </div>
              <div className="flex-1 overflow-hidden">
                <MessageView />
              </div>
            </>
          ) : (
            <MessageList />
          )}
        </div>
      )}

      {readingPane === 'fullscreen' && (
        /* ── RELLENAR PANTALLA ── */
        <div className="flex-1 flex overflow-hidden min-h-0">
          {activeCompose ? (
            <ComposePanel key={activeCompose.id} win={activeCompose} />
          ) : selectedMessage ? (
            <>
              <div className="flex-1 flex flex-col min-w-0">
                <div className="shrink-0 flex items-center gap-2 px-3 py-1.5 border-b border-[#edebe9] bg-[#faf9f8]">
                  <button onClick={() => setSelectedMessage(null)}
                    className="flex items-center gap-1 text-[13px] text-[#0078d4] hover:underline">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M10.5 3L5 8l5.5 5V3z"/></svg>
                    Volver a la bandeja
                  </button>
                </div>
                <div className="flex-1 overflow-hidden">
                  <MessageView />
                </div>
              </div>
            </>
          ) : (
            <MessageList />
          )}
        </div>
      )}

      {readingPane === 'popout' && (
        /* ── SOLO ELEMENTOS EMERGENTES: siempre muestra lista, mensaje en popup ── */
        <div className="flex-1 flex overflow-hidden min-h-0">
          <MessageList />
        </div>
      )}

      </div>
      {showMyDay && <MyDayPanel onClose={() => setShowMyDay(false)} />}
      </div>

      {/* (compose se muestra inline dentro del panel de contenido, no flotante) */}

      {/* Minimized compose tabs — barra inferior llamativa */}
      {minimizedComposes.length > 0 && (
        <div className="fixed bottom-0 right-6 z-[99] flex gap-2">
          {minimizedComposes.map(win => (
            <div key={win.id}
              className="bg-[#0078d4] text-white rounded-t-lg text-[12px] font-semibold shadow-lg flex items-center"
              style={{ boxShadow: '0 -2px 12px rgba(0,120,212,0.3)' }}>
              <button onClick={() => restoreCompose(win.id)}
                className="flex items-center gap-2 px-3 py-2.5 hover:bg-[#106ebe] transition-colors max-w-[190px] truncate rounded-tl-lg">
                <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
                <span className="truncate">{(win.data.subject && win.data.subject !== '(No Subject)') ? win.data.subject : 'Nuevo mensaje'}</span>
              </button>
              <button onClick={(e) => { e.stopPropagation(); closeCompose(win.id); }}
                className="px-2 py-2.5 hover:bg-[#c42b1c] transition-colors rounded-tr-lg text-white/80 hover:text-white" title="Cerrar">
                {'\u00D7'}
              </button>
            </div>
          ))}
        </div>
      )}

      <ToastContainer />
    </div>
  );
}
