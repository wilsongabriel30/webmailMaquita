import { useMemo, useEffect, useRef, useState, useCallback } from "react";
import type { CalendarEvent } from "./types/calendar";
import { EventCard } from "./EventCard";
import {
  getWeekDates,
  getHourSlots,
  isToday,
  getEventPosition,
  getOverlappingGroups,
} from "./utils/dateHelpers";
import { parseISO, format } from "date-fns";
import { es } from "date-fns/locale";

interface Props {
  currentDate: Date;
  events: CalendarEvent[];
  onEventClick: (event: CalendarEvent) => void;
  onSlotClick: (date: Date, hour: number) => void;
  onRangeSelect?: (date: Date, startHour: number, endHour: number) => void;
  onEventMove?: (eventId: string, dtstart: string, dtend: string) => void;
  daysToShow?: 5 | 7;
}

const HOUR_HEIGHT = 64;
const GUTTER_WIDTH = 45;
const WEEKDAY_FULL = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];

export function WeekView({
  currentDate,
  events,
  onEventClick,
  onSlotClick,
  onRangeSelect,
  onEventMove,
  daysToShow = 7,
}: Props) {
  const allWeekDates = useMemo(() => getWeekDates(currentDate), [currentDate]);
  const weekDates = useMemo(
    () => (daysToShow === 5 ? allWeekDates.slice(0, 5) : allWeekDates),
    [allWeekDates, daysToShow]
  );
  const hours = useMemo(() => getHourSlots(), []);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [nowLine, setNowLine] = useState(0);

  // Drag state
  const [dragging, setDragging] = useState<{
    eventId: string;
    origDtstart: string;
    origDtend: string;
    startY: number;
    startX: number;
    colWidth: number;
    dayIdx: number;
    origTop: number;
    currentDeltaY: number;
    currentDeltaX: number;
    mode: "move" | "resize";
  } | null>(null);
  const [selecting, setSelecting] = useState<{ dayIdx: number; y0: number; y1: number } | null>(null);
  const selectingRef = useRef<{ dayIdx: number; y0: number; y1: number; day: Date; colTop: number } | null>(null);
  const draggingRef = useRef(dragging);
  draggingRef.current = dragging;
  const suppressClickRef = useRef(false);

  // Auto-scroll to current hour
  useEffect(() => {
    if (scrollRef.current) {
      const now = new Date();
      scrollRef.current.scrollTop = Math.max(0, (now.getHours() - 1) * HOUR_HEIGHT);
    }
  }, []);

  // Current time line
  useEffect(() => {
    function update() {
      const now = new Date();
      setNowLine(((now.getHours() * 60 + now.getMinutes()) / 60) * HOUR_HEIGHT);
    }
    update();
    const timer = setInterval(update, 60000);
    return () => clearInterval(timer);
  }, []);

  // Group events by day
  const eventsByDay = useMemo(() => {
    const map = new Map<string, CalendarEvent[]>();
    for (const ev of events) {
      if (ev.all_day) continue;
      const key = parseISO(ev.dtstart).toDateString();
      const arr = map.get(key) || [];
      arr.push(ev);
      map.set(key, arr);
    }
    return map;
  }, [events]);

  // All-day events
  const allDayEvents = useMemo(() => events.filter((ev) => ev.all_day), [events]);
  const allDayByDay = useMemo(() => {
    const map = new Map<string, CalendarEvent[]>();
    for (const ev of allDayEvents) {
      const key = parseISO(ev.dtstart).toDateString();
      const arr = map.get(key) || [];
      arr.push(ev);
      map.set(key, arr);
    }
    return map;
  }, [allDayEvents]);

  // Mouse drag for vertical movement within WeekView
  const handleMouseDown = useCallback(
    (e: React.MouseEvent, eventId: string, top: number, dtstart: string, dtend: string, dayIdx: number, mode: "move" | "resize" = "move") => {
      e.preventDefault();
      e.stopPropagation();
      const col = (e.currentTarget as HTMLElement).closest("[data-daycol]") as HTMLElement | null;
      const colWidth = col ? col.getBoundingClientRect().width : 0;
      setDragging({ eventId, origDtstart: dtstart, origDtend: dtend, startY: e.clientY, startX: e.clientX, colWidth, dayIdx, origTop: top, currentDeltaY: 0, currentDeltaX: 0, mode });
    },
    []
  );

  // Selección de rango sobre área vacía (crear evento arrastrando)
  useEffect(() => {
    if (!selecting) return;
    function onMove(e: MouseEvent) {
      const sel = selectingRef.current;
      if (!sel) return;
      const y1 = Math.min(24 * HOUR_HEIGHT, Math.max(0, e.clientY - sel.colTop));
      selectingRef.current = { ...sel, y1 };
      setSelecting({ dayIdx: sel.dayIdx, y0: sel.y0, y1 });
    }
    function onUp() {
      const sel = selectingRef.current;
      selectingRef.current = null;
      setSelecting(null);
      if (!sel) return;
      const dist = Math.abs(sel.y1 - sel.y0);
      if (dist < 12) {
        const hour = Math.floor(sel.y0 / HOUR_HEIGHT);
        onSlotClick(sel.day, Math.min(23, Math.max(0, hour)));
        return;
      }
      if (!onRangeSelect) return;
      const snap = (y: number) => Math.round((y / HOUR_HEIGHT) * 4) / 4; // 15 min
      const a = snap(Math.min(sel.y0, sel.y1));
      const b = Math.max(snap(Math.max(sel.y0, sel.y1)), a + 0.25);
      onRangeSelect(sel.day, a, Math.min(24, b));
    }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [selecting !== null, onRangeSelect, onSlotClick]);

  useEffect(() => {
    if (!dragging) return;

    function handleMouseMove(e: MouseEvent) {
      if (!draggingRef.current) return;
      const deltaY = e.clientY - draggingRef.current.startY;
      const deltaX = e.clientX - draggingRef.current.startX;
      setDragging((prev) => prev ? { ...prev, currentDeltaY: deltaY, currentDeltaX: deltaX } : null);
    }

    function handleMouseUp(e: MouseEvent) {
      const d = draggingRef.current;
      if (!d || !onEventMove) {
        setDragging(null);
        return;
      }

      const deltaY = e.clientY - d.startY;
      const deltaX = e.clientX - d.startX;
      // Snap to 15-minute intervals
      const deltaMinutes = Math.round((deltaY / HOUR_HEIGHT) * 60 / 15) * 15;
      const fmtDate = (dt: Date) => format(dt, "yyyy-MM-dd'T'HH:mm:ss");

      if (d.mode === "resize") {
        if (deltaMinutes !== 0) {
          suppressClickRef.current = true;
          setTimeout(() => { suppressClickRef.current = false; }, 300);
          const origStart = parseISO(d.origDtstart);
          const origEnd = parseISO(d.origDtend);
          let newEnd = new Date(origEnd.getTime() + deltaMinutes * 60000);
          if (newEnd.getTime() - origStart.getTime() < 15 * 60000) {
            newEnd = new Date(origStart.getTime() + 15 * 60000);
          }
          onEventMove(d.eventId, fmtDate(origStart), fmtDate(newEnd));
        }
        setDragging(null);
        return;
      }

      // Cambio de dia arrastrando horizontalmente
      let dayDelta = d.colWidth > 0 ? Math.round(deltaX / d.colWidth) : 0;
      const maxIdx = (daysToShow === 5 ? 5 : 7) - 1;
      const newIdx = Math.min(maxIdx, Math.max(0, d.dayIdx + dayDelta));
      dayDelta = newIdx - d.dayIdx;

      if (deltaMinutes !== 0 || dayDelta !== 0) {
        suppressClickRef.current = true;
        setTimeout(() => { suppressClickRef.current = false; }, 300);
        const origStart = parseISO(d.origDtstart);
        const origEnd = parseISO(d.origDtend);
        const offsetMs = deltaMinutes * 60000 + dayDelta * 86400000;
        const newStart = new Date(origStart.getTime() + offsetMs);
        const newEnd = new Date(origEnd.getTime() + offsetMs);
        onEventMove(d.eventId, fmtDate(newStart), fmtDate(newEnd));
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

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden", background: "#fff", fontFamily: "'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif" }}>
      {/* HEADER ROW */}
      <div style={{ display: "flex", borderBottom: "1px solid #e0e0e0", flexShrink: 0, background: "#f5f5f5" }}>
        <div style={{ width: GUTTER_WIDTH, flexShrink: 0 }} />
        {weekDates.map((day, i) => {
          const today = isToday(day);
          return (
            <div
              key={i}
              style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                padding: "8px 0 6px 0",
                borderLeft: "1px solid #e0e0e0",
                borderTop: today ? "3px solid #0078d4" : "3px solid transparent",
                boxSizing: "border-box",
              }}
            >
              <span style={{ fontSize: "26px", fontWeight: 700, lineHeight: 1.1, color: today ? "#0078d4" : "#323130" }}>
                {day.getDate()}
              </span>
              <span style={{ fontSize: "12px", marginTop: "2px", color: today ? "#0078d4" : "#616161", fontWeight: today ? 600 : 400 }}>
                {WEEKDAY_FULL[allWeekDates.indexOf(day)] ?? format(day, "EEEE", { locale: es })}
              </span>
            </div>
          );
        })}
      </div>

      {/* ALL-DAY ROW */}
      {allDayEvents.length > 0 && (
        <div style={{ display: "flex", borderBottom: "1px solid #e0e0e0", flexShrink: 0, minHeight: "32px" }}>
          <div style={{ width: GUTTER_WIDTH, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "flex-end", paddingRight: "6px" }}>
            <span style={{ fontSize: "10px", color: "#a19f9d" }}>todo el dia</span>
          </div>
          {weekDates.map((day, i) => {
            const dayAllDay = allDayByDay.get(day.toDateString()) || [];
            return (
              <div key={i} style={{ flex: 1, borderLeft: "1px solid #e0e0e0", padding: "2px 2px", display: "flex", flexDirection: "column", gap: "2px" }}>
                {dayAllDay.map((ev) => (
                  <div
                    key={ev.id}
                    onClick={() => onEventClick(ev)}
                    style={{
                      fontSize: "11px",
                      padding: "1px 6px",
                      borderRadius: "4px",
                      cursor: "pointer",
                      color: "#fff",
                      backgroundColor: ev.color || "#0078d4",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      display: "flex",
                      alignItems: "center",
                      gap: "3px",
                    }}
                  >
                    {ev.rrule && (
                      <svg width="9" height="9" viewBox="0 0 16 16" fill="rgba(255,255,255,0.85)" style={{ flexShrink: 0 }}>
                        <path d="M11.534 7h3.932a.25.25 0 01.192.41l-1.966 2.36a.25.25 0 01-.384 0l-1.966-2.36a.25.25 0 01.192-.41zm-11 2H4.466a.25.25 0 00.192-.41L2.692 6.23a.25.25 0 00-.384 0L.342 8.59A.25.25 0 00.534 9z"/>
                        <path d="M8 3c-1.552 0-2.94.707-3.857 1.818a.5.5 0 11-.771-.636A5.501 5.501 0 0113.5 8a.5.5 0 01-1 0 4.5 4.5 0 00-4.5-4.5zM2.5 8a.5.5 0 01.5.5 4.5 4.5 0 007.857 2.682.5.5 0 11.771.636A5.501 5.501 0 012 8.5a.5.5 0 01.5-.5z"/>
                      </svg>
                    )}
                    {ev.summary}
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      )}

      {/* TIME GRID */}
      <div ref={scrollRef} style={{ flex: 1, overflowY: "auto", overflowX: "hidden", position: "relative" }}>
        <div style={{ display: "flex", height: 24 * HOUR_HEIGHT, position: "relative" }}>
          {/* Time gutter */}
          <div style={{ width: GUTTER_WIDTH, flexShrink: 0, position: "relative" }}>
            {hours.map((h) =>
              h.hour > 0 ? (
                <div
                  key={h.hour}
                  style={{
                    position: "absolute",
                    top: h.hour * HOUR_HEIGHT,
                    right: 8,
                    transform: "translateY(-50%)",
                    fontSize: "12px",
                    color: "#a19f9d",
                    userSelect: "none",
                    lineHeight: 1,
                  }}
                >
                  {h.hour}
                </div>
              ) : null
            )}
          </div>

          {/* Day columns */}
          {weekDates.map((day, dayIdx) => {
            const dayEvents = eventsByDay.get(day.toDateString()) || [];
            const groups = getOverlappingGroups(dayEvents);
            const today = isToday(day);

            return (
              <div
                key={dayIdx}
                data-daycol
                style={{ flex: 1, position: "relative", borderLeft: "1px solid #e0e0e0" }}
                onMouseDown={(e) => {
                  if (dragging || e.button !== 0) return;
                  const rect = e.currentTarget.getBoundingClientRect();
                  const y0 = e.clientY - rect.top;
                  selectingRef.current = { dayIdx, y0, y1: y0, day, colTop: rect.top };
                  setSelecting({ dayIdx, y0, y1: y0 });
                }}
              >
                {selecting && selecting.dayIdx === dayIdx && Math.abs(selecting.y1 - selecting.y0) >= 12 && (
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
                    <div style={{ position: "absolute", top: h.hour * HOUR_HEIGHT, left: 0, right: 0, borderTop: "1px solid #e0e0e0" }} />
                    <div style={{ position: "absolute", top: h.hour * HOUR_HEIGHT + HOUR_HEIGHT / 2, left: 0, right: 0, borderTop: "1px dashed #f0f0f0" }} />
                  </div>
                ))}

                {/* Current time indicator */}
                {today && (
                  <div style={{ position: "absolute", top: nowLine, left: 0, right: 0, zIndex: 20, pointerEvents: "none", display: "flex", alignItems: "center" }}>
                    <div style={{ width: "8px", height: "8px", borderRadius: "50%", backgroundColor: "#0078d4", marginLeft: "-4px", flexShrink: 0 }} />
                    <div style={{ flex: 1, height: "2px", backgroundColor: "#0078d4" }} />
                  </div>
                )}

                {/* Events */}
                {groups.map((group) =>
                  group.events.map((ev) => {
                    const pos = getEventPosition(ev, day);
                    const colWidth = 100 / ev.totalColumns;
                    const width = `calc(${colWidth}% - 4px)`;
                    const left = `calc(${ev.column * colWidth}% + 2px)`;

                    const isDragging = dragging?.eventId === ev.id;
                    const isResizing = isDragging && dragging!.mode === "resize";
                    const dragOffset = isDragging && !isResizing ? dragging!.currentDeltaY : 0;
                    const dragOffsetX = isDragging && !isResizing ? dragging!.currentDeltaX : 0;
                    const resizeDelta = isResizing ? dragging!.currentDeltaY : 0;

                    return (
                      <div
                        key={ev.id}
                        style={{
                          position: "absolute",
                          top: pos.top + dragOffset,
                          transform: dragOffsetX !== 0 ? `translateX(${dragOffsetX}px)` : undefined,
                          height: Math.max(pos.height + resizeDelta, 20),
                          width,
                          left,
                          zIndex: isDragging ? 30 : 10,
                          opacity: isDragging ? 0.85 : 1,
                          cursor: isDragging ? "grabbing" : "grab",
                          transition: isDragging ? "none" : "top 0.15s ease",
                        }}
                        onMouseDown={(e) =>
                          handleMouseDown(e, ev.id, pos.top, ev.dtstart, ev.dtend, dayIdx)
                        }
                        onClickCapture={(e) => {
                          if (suppressClickRef.current) { e.stopPropagation(); e.preventDefault(); }
                        }}
                      >
                        <EventCard
                          event={ev}
                          onClick={onEventClick}
                          compact={false}
                        />
                        {onEventMove && (
                          <div
                            onMouseDown={(e) => handleMouseDown(e, ev.id, pos.top, ev.dtstart, ev.dtend, dayIdx, "resize")}
                            style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: 7, cursor: "ns-resize", zIndex: 5 }}
                          />
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            );
          })}
        </div>
      </div>

      <style>{`
        .outlook-block-hover:hover { filter: brightness(0.9); }
        .outlook-pill-hover:hover { filter: brightness(0.95); }
      `}</style>
    </div>
  );
}
