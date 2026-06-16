import { useMemo, useState, useCallback, useRef } from "react";
import type { CalendarEvent } from "./types/calendar";
import {
  getMonthGrid,
  isToday,
  formatTime,
} from "./utils/dateHelpers";
import { parseISO, format, differenceInMilliseconds } from "date-fns";

interface Props {
  currentDate: Date;
  events: CalendarEvent[];
  onEventClick: (event: CalendarEvent) => void;
  onDateClick: (date: Date) => void;
  onShowMore?: (date: Date) => void;
  onEventMove?: (eventId: string, dtstart: string, dtend: string) => void;
}

const MAX_VISIBLE = 3;
const DAY_HEADERS = ["L", "M", "X", "J", "V", "S", "D"];

export function MonthView({ currentDate, events, onEventClick, onDateClick, onEventMove, onShowMore }: Props) {
  const grid = useMemo(() => getMonthGrid(currentDate), [currentDate]);
  const currentMonth = currentDate.getMonth();

  // Drag state
  const [dragEventId, setDragEventId] = useState<string | null>(null);
  const [dragOverDate, setDragOverDate] = useState<string | null>(null);
  const dragDataRef = useRef<{ eventId: string; origDtstart: string; origDtend: string } | null>(null);

  const eventsByDay = useMemo(() => {
    const map = new Map<string, CalendarEvent[]>();
    for (const ev of events) {
      const key = parseISO(ev.dtstart).toDateString();
      const arr = map.get(key) || [];
      arr.push(ev);
      map.set(key, arr);
    }
    return map;
  }, [events]);

  const handleDragStart = useCallback((e: React.DragEvent, ev: CalendarEvent) => {
    e.stopPropagation();
    setDragEventId(ev.id);
    dragDataRef.current = { eventId: ev.id, origDtstart: ev.dtstart, origDtend: ev.dtend };
    e.dataTransfer.effectAllowed = "move";
    // Needed for Firefox
    e.dataTransfer.setData("text/plain", ev.id);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent, day: Date) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDragOverDate(day.toDateString());
  }, []);

  const handleDragLeave = useCallback(() => {
    setDragOverDate(null);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent, targetDay: Date) => {
    e.preventDefault();
    setDragOverDate(null);
    setDragEventId(null);

    if (!dragDataRef.current || !onEventMove) return;
    const { eventId, origDtstart, origDtend } = dragDataRef.current;
    dragDataRef.current = null;

    const origStart = parseISO(origDtstart);
    const origEnd = parseISO(origDtend);
    const duration = differenceInMilliseconds(origEnd, origStart);

    const newStart = new Date(targetDay);
    newStart.setHours(origStart.getHours(), origStart.getMinutes(), origStart.getSeconds());
    const newEnd = new Date(newStart.getTime() + duration);

    const fmtDate = (d: Date) => format(d, "yyyy-MM-dd'T'HH:mm:ss");
    onEventMove(eventId, fmtDate(newStart), fmtDate(newEnd));
  }, [onEventMove]);

  const handleDragEnd = useCallback(() => {
    setDragEventId(null);
    setDragOverDate(null);
    dragDataRef.current = null;
  }, []);

  return (
    <div className="flex flex-col flex-1 overflow-hidden bg-white dark:bg-[#1b1a19]">
      {/* Day headers */}
      <div className="grid grid-cols-7 border-b border-[#e0e0e0] dark:border-[#3b3a39]">
        {DAY_HEADERS.map((d) => (
          <div
            key={d}
            className="text-center text-[12px] font-bold text-[#616161] dark:text-[#a19f9d] py-2 select-none"
          >
            {d}
          </div>
        ))}
      </div>

      {/* Month grid */}
      <div className="flex-1 grid grid-rows-6 overflow-hidden">
        {grid.map((week, wi) => (
          <div
            key={wi}
            className="grid grid-cols-7 border-b border-[#e0e0e0] dark:border-[#3b3a39] min-h-0"
          >
            {week.map((day, di) => {
              const inMonth = day.getMonth() === currentMonth;
              const todayFlag = isToday(day);
              const dayEvents = eventsByDay.get(day.toDateString()) || [];
              const visible = dayEvents.slice(0, MAX_VISIBLE);
              const remaining = dayEvents.length - MAX_VISIBLE;
              const isDragOver = dragOverDate === day.toDateString();

              return (
                <div
                  key={di}
                  onClick={() => onDateClick(day)}
                  onDragOver={(e) => handleDragOver(e, day)}
                  onDragLeave={handleDragLeave}
                  onDrop={(e) => handleDrop(e, day)}
                  className={`border-r border-[#e0e0e0] dark:border-[#3b3a39] last:border-r-0 p-1.5 cursor-pointer overflow-hidden flex flex-col
                    ${!inMonth ? "bg-[#fafafa] dark:bg-[#141414]" : "bg-white dark:bg-[#1b1a19]"}
                    ${isDragOver ? "!bg-[#deecf9] dark:!bg-[#1a3a5c]" : ""}
                    hover:bg-[#f5f5f5] dark:hover:bg-[#252423] transition-colors`}
                >
                  {/* Day number */}
                  <div className="flex items-start mb-1">
                    <span
                      className={`text-[13px] leading-none flex items-center justify-center
                        ${todayFlag ? "bg-[#0078d4] text-white font-bold w-[24px] h-[24px] rounded-full" : "w-[24px] h-[24px]"}
                        ${!inMonth && !todayFlag ? "text-[#605e5c] dark:text-[#484644]" : ""}
                        ${inMonth && !todayFlag ? "text-[#323130] dark:text-[#d2d0ce] font-medium" : ""}
                      `}
                    >
                      {day.getDate()}
                    </span>
                  </div>

                  {/* Event pills */}
                  <div className="flex-1 space-y-[2px] overflow-hidden min-h-0">
                    {visible.map((ev) => (
                      <div
                        key={ev.id}
                        draggable
                        onDragStart={(e) => handleDragStart(e, ev)}
                        onDragEnd={handleDragEnd}
                        onClick={(e) => {
                          e.stopPropagation();
                          onEventClick(ev);
                        }}
                        className={`flex items-center rounded text-[11px] leading-tight cursor-grab active:cursor-grabbing truncate hover:brightness-95 transition-colors overflow-hidden
                          ${dragEventId === ev.id ? "opacity-40" : ""}`}
                        style={{
                          backgroundColor: `${ev.color || "#0078d4"}15`,
                          borderLeft: `3px solid ${ev.color || "#0078d4"}`,
                        }}
                      >
                        <span className="px-1.5 py-[2px] truncate dark:text-[#d2d0ce] flex items-center gap-1">
                          {ev.rrule && (
                            <svg width="9" height="9" viewBox="0 0 16 16" fill={ev.color || "#0078d4"} className="shrink-0">
                              <path d="M11.534 7h3.932a.25.25 0 01.192.41l-1.966 2.36a.25.25 0 01-.384 0l-1.966-2.36a.25.25 0 01.192-.41zm-11 2H4.466a.25.25 0 00.192-.41L2.692 6.23a.25.25 0 00-.384 0L.342 8.59A.25.25 0 00.534 9z"/>
                              <path d="M8 3c-1.552 0-2.94.707-3.857 1.818a.5.5 0 11-.771-.636A5.501 5.501 0 0113.5 8a.5.5 0 01-1 0 4.5 4.5 0 00-4.5-4.5zM2.5 8a.5.5 0 01.5.5 4.5 4.5 0 007.857 2.682.5.5 0 11.771.636A5.501 5.501 0 012 8.5a.5.5 0 01.5-.5z"/>
                            </svg>
                          )}
                          {!ev.all_day && (
                            <span
                              className="font-semibold mr-0.5 shrink-0"
                              style={{ color: ev.color || "#0078d4" }}
                            >
                              {formatTime(ev.dtstart)}
                            </span>
                          )}
                          <span className="text-[#323130] dark:text-[#d2d0ce] truncate">{ev.summary}</span>
                        </span>
                      </div>
                    ))}
                    {remaining > 0 && (
                      <div
                        onClick={(e) => { e.stopPropagation(); (onShowMore || onDateClick)(day); }}
                        className="text-[10px] text-[#0078d4] pl-1 font-medium cursor-pointer hover:underline"
                      >
                        +{remaining} mas
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
