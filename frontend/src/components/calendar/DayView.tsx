import { useMemo, useEffect, useRef, useState, useCallback } from "react";
import type { CalendarEvent } from "./types/calendar";
import {
  getHourSlots,
  isToday,
  getEventPosition,
  getOverlappingGroups,
  formatTime,
} from "./utils/dateHelpers";
import { format, parseISO } from "date-fns";
import { es } from "date-fns/locale";

interface Props {
  currentDate: Date;
  events: CalendarEvent[];
  onEventClick: (event: CalendarEvent) => void;
  onSlotClick: (date: Date, hour: number) => void;
  onRangeSelect?: (date: Date, startHour: number, endHour: number) => void;
  onEventMove?: (eventId: string, dtstart: string, dtend: string) => void;
}

const HOUR_HEIGHT = 64;

export function DayView({ currentDate, events, onEventClick, onSlotClick, onRangeSelect, onEventMove }: Props) {
  const hours = useMemo(() => getHourSlots(), []);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [nowLine, setNowLine] = useState(0);
  interface DragState { eventId: string; origDtstart: string; origDtend: string; startY: number; origTop: number; currentDeltaY: number; mode: "move" | "resize"; }
  const [dragging, setDragging] = useState<DragState | null>(null);
  const draggingRef = useRef<DragState | null>(null);
  const suppressClickRef = useRef(false);
  const [selecting, setSelecting] = useState<{ y0: number; y1: number } | null>(null);
  const selectingRef = useRef<{ y0: number; y1: number; colTop: number } | null>(null);

  useEffect(() => {
    if (!selecting) return;
    function onMove(e: MouseEvent) {
      const sel = selectingRef.current;
      if (!sel) return;
      const y1 = Math.min(24 * HOUR_HEIGHT, Math.max(0, e.clientY - sel.colTop));
      selectingRef.current = { ...sel, y1 };
      setSelecting({ y0: sel.y0, y1 });
    }
    function onUp() {
      const sel = selectingRef.current;
      selectingRef.current = null;
      setSelecting(null);
      if (!sel) return;
      const dist = Math.abs(sel.y1 - sel.y0);
      if (dist < 12) {
        const hour = Math.floor(sel.y0 / HOUR_HEIGHT);
        onSlotClick(currentDate, Math.min(23, Math.max(0, hour)));
        return;
      }
      if (!onRangeSelect) return;
      const snap = (y: number) => Math.round((y / HOUR_HEIGHT) * 4) / 4;
      const a = snap(Math.min(sel.y0, sel.y1));
      const b = Math.max(snap(Math.max(sel.y0, sel.y1)), a + 0.25);
      onRangeSelect(currentDate, a, Math.min(24, b));
    }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [selecting !== null, onRangeSelect, onSlotClick, currentDate]);
  useEffect(() => { draggingRef.current = dragging; }, [dragging]);

  const handleMouseDown = useCallback(
    (e: React.MouseEvent, eventId: string, top: number, dtstart: string, dtend: string, mode: "move" | "resize" = "move") => {
      if (!onEventMove) return;
      e.preventDefault();
      e.stopPropagation();
      setDragging({ eventId, origDtstart: dtstart, origDtend: dtend, startY: e.clientY, origTop: top, currentDeltaY: 0, mode });
    },
    [onEventMove]
  );

  useEffect(() => {
    if (!dragging) return;
    function handleMouseMove(e: MouseEvent) {
      if (!draggingRef.current) return;
      const deltaY = e.clientY - draggingRef.current.startY;
      setDragging((prev) => prev ? { ...prev, currentDeltaY: deltaY } : null);
    }
    function handleMouseUp(e: MouseEvent) {
      const d = draggingRef.current;
      if (!d || !onEventMove) { setDragging(null); return; }
      const deltaY = e.clientY - d.startY;
      const deltaMinutes = Math.round((deltaY / HOUR_HEIGHT) * 60 / 15) * 15;
      const fmtDate = (dt: Date) => format(dt, "yyyy-MM-dd'T'HH:mm:ss");
      if (deltaMinutes !== 0) {
        suppressClickRef.current = true;
        setTimeout(() => { suppressClickRef.current = false; }, 300);
        const origStart = parseISO(d.origDtstart);
        const origEnd = parseISO(d.origDtend);
        if (d.mode === "resize") {
          let newEnd = new Date(origEnd.getTime() + deltaMinutes * 60000);
          if (newEnd.getTime() - origStart.getTime() < 15 * 60000) {
            newEnd = new Date(origStart.getTime() + 15 * 60000);
          }
          onEventMove(d.eventId, fmtDate(origStart), fmtDate(newEnd));
        } else {
          const newStart = new Date(origStart.getTime() + deltaMinutes * 60000);
          const newEnd = new Date(origEnd.getTime() + deltaMinutes * 60000);
          onEventMove(d.eventId, fmtDate(newStart), fmtDate(newEnd));
        }
      }
      setDragging(null);
    }
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [dragging, onEventMove]);
  const today = isToday(currentDate);

  const dayEvents = useMemo(() => events.filter((ev) => !ev.all_day), [events]);
  const allDayEvents = useMemo(() => events.filter((ev) => ev.all_day), [events]);
  const groups = useMemo(() => getOverlappingGroups(dayEvents), [dayEvents]);

  useEffect(() => {
    if (scrollRef.current) {
      const now = new Date();
      scrollRef.current.scrollTop = Math.max(0, (now.getHours() - 1) * HOUR_HEIGHT);
    }
  }, []);

  useEffect(() => {
    function update() {
      const now = new Date();
      setNowLine(((now.getHours() * 60 + now.getMinutes()) / 60) * HOUR_HEIGHT);
    }
    update();
    const timer = setInterval(update, 60000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="flex flex-col flex-1 overflow-hidden bg-white dark:bg-[#1b1a19]">
      {/* Header - Outlook style: big day number + full day name */}
      <div className="flex border-b border-[#e0e0e0] dark:border-[#3b3a39] shrink-0">
        <div className="w-[56px] shrink-0" />
        <div
          className="flex-1 flex flex-col items-center py-3"
          style={today ? { borderTop: "3px solid #0078d4" } : {}}
        >
          <span
            className={`text-[26px] font-bold leading-tight ${
              today ? "text-[#0078d4]" : "text-[#323130] dark:text-[#f3f2f1]"
            }`}
          >
            {currentDate.getDate()}
          </span>
          <span
            className={`text-[13px] mt-0.5 ${
              today ? "text-[#0078d4] font-semibold" : "text-[#616161] dark:text-[#a19f9d]"
            }`}
          >
            {(() => { const t = format(currentDate, "EEEE, d 'de' MMMM", { locale: es }); return t.charAt(0).toUpperCase() + t.slice(1); })()}
          </span>
        </div>
      </div>

      {/* All day events */}
      {allDayEvents.length > 0 && (
        <div className="flex border-b border-[#e0e0e0] dark:border-[#3b3a39] shrink-0 min-h-[32px]">
          <div className="w-[56px] shrink-0 flex items-center justify-end pr-2">
            <span className="text-[10px] text-[#a19f9d]">todo el día</span>
          </div>
          <div className="flex-1 p-1 flex flex-wrap gap-1">
            {allDayEvents.map((ev) => (
              <div
                key={ev.id}
                onClick={() => onEventClick(ev)}
                className="text-[12px] px-2 py-1 rounded cursor-pointer text-white"
                style={{ backgroundColor: ev.color || "#0078d4", borderRadius: "4px" }}
              >
                {ev.summary}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Time grid */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto relative">
        <div className="flex" style={{ height: 24 * HOUR_HEIGHT }}>
          {/* Time gutter */}
          <div className="w-[56px] shrink-0 relative">
            {hours.map((h) => (
              <div
                key={h.hour}
                className="absolute w-full text-right pr-3 text-[12px] text-[#616161] dark:text-[#a19f9d] -translate-y-1/2 select-none"
                style={{ top: h.hour * HOUR_HEIGHT }}
              >
                {h.hour > 0 ? h.hour : ""}
              </div>
            ))}
          </div>

          {/* Single day column */}
          <div
            className="flex-1 relative"
            onMouseDown={(e) => {
              if (dragging || e.button !== 0) return;
              const rect = e.currentTarget.getBoundingClientRect();
              const y0 = e.clientY - rect.top;
              selectingRef.current = { y0, y1: y0, colTop: rect.top };
              setSelecting({ y0, y1: y0 });
            }}
          >
            {selecting && Math.abs(selecting.y1 - selecting.y0) >= 12 && (
              <div style={{
                position: "absolute",
                top: Math.min(selecting.y0, selecting.y1),
                height: Math.abs(selecting.y1 - selecting.y0),
                left: 1, right: 1,
                background: "rgba(0,120,212,0.18)",
                border: "1px solid rgba(0,120,212,0.6)",
                borderRadius: 4, zIndex: 5, pointerEvents: "none",
              }} />
            )}
            {/* Hour lines */}
            {hours.map((h) => (
              <div key={h.hour}>
                <div
                  className="absolute w-full border-t border-[#e0e0e0] dark:border-[#3b3a39]"
                  style={{ top: h.hour * HOUR_HEIGHT }}
                />
                {/* Half-hour dashed line */}
                <div
                  className="absolute w-full border-t border-dashed border-[#f0f0f0] dark:border-[#2d2c2b]"
                  style={{ top: h.hour * HOUR_HEIGHT + HOUR_HEIGHT / 2 }}
                />
              </div>
            ))}

            {/* Current time indicator */}
            {today && (
              <div
                className="absolute w-full z-20 pointer-events-none"
                style={{ top: nowLine }}
              >
                <div className="flex items-center">
                  <div className="w-2 h-2 rounded-full bg-[#0078d4] -ml-1" />
                  <div className="flex-1 h-[2px] bg-[#0078d4]" />
                </div>
              </div>
            )}

            {/* Events - wider since single column */}
            {groups.map((group) =>
              group.events.map((ev) => {
                const pos = getEventPosition(ev, currentDate);
                const colWidth = 100 / ev.totalColumns;
                const width = `calc(${colWidth}% - 8px)`;
                const left = `calc(${ev.column * colWidth}% + 4px)`;

                const isDragging = dragging?.eventId === ev.id;
                const isResizing = isDragging && dragging!.mode === "resize";
                const dragOffset = isDragging && !isResizing ? dragging!.currentDeltaY : 0;
                const resizeDelta = isResizing ? dragging!.currentDeltaY : 0;
                return (
                  <div
                    key={ev.id}
                    className="absolute rounded overflow-hidden hover:z-30 hover:brightness-90"
                    style={{
                      top: pos.top + dragOffset,
                      height: Math.max(pos.height + resizeDelta, 24),
                      width,
                      left,
                      backgroundColor: ev.color || "#0078d4",
                      borderRadius: "4px",
                      zIndex: isDragging ? 30 : 10,
                      opacity: isDragging ? 0.85 : 1,
                      cursor: isDragging ? "grabbing" : "grab",
                      transition: isDragging ? "none" : "top 0.15s ease",
                    }}
                    onMouseDown={(e) => handleMouseDown(e, ev.id, pos.top, ev.dtstart, ev.dtend)}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (suppressClickRef.current) return;
                      onEventClick(ev);
                    }}
                  >
                    <div className="px-3 py-1.5 h-full">
                      <div className="text-[13px] font-semibold text-white truncate leading-tight">
                        {ev.summary}
                      </div>
                      <div className="text-[12px] text-white/90 leading-tight">
                        {formatTime(ev.dtstart)} - {formatTime(ev.dtend)}
                      </div>
                      {ev.location && pos.height > 50 && (
                        <div className="text-[11px] text-white/75 mt-1 flex items-center gap-1 truncate">
                          <svg
                            className="w-3 h-3 shrink-0"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
                            />
                          </svg>
                          {ev.location}
                        </div>
                      )}
                      {ev.description && pos.height > 90 && (
                        <div className="text-[11px] text-white/70 mt-1 line-clamp-2">
                          {ev.description}
                        </div>
                      )}
                    </div>
                    {onEventMove && (
                      <div
                        onMouseDown={(e) => handleMouseDown(e, ev.id, pos.top, ev.dtstart, ev.dtend, "resize")}
                        style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: 7, cursor: "ns-resize", zIndex: 5 }}
                      />
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
