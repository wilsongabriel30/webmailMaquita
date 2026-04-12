import { useMemo, useEffect, useRef, useState } from "react";
import type { CalendarEvent } from "./types/calendar";
import {
  getHourSlots,
  isToday,
  getEventPosition,
  getOverlappingGroups,
  formatTime,
} from "./utils/dateHelpers";
import { format } from "date-fns";
import { es } from "date-fns/locale";

interface Props {
  currentDate: Date;
  events: CalendarEvent[];
  onEventClick: (event: CalendarEvent) => void;
  onSlotClick: (date: Date, hour: number) => void;
}

const HOUR_HEIGHT = 64;

export function DayView({ currentDate, events, onEventClick, onSlotClick }: Props) {
  const hours = useMemo(() => getHourSlots(), []);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [nowLine, setNowLine] = useState(0);
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
            className={`text-[13px] mt-0.5 capitalize ${
              today ? "text-[#0078d4] font-semibold" : "text-[#616161] dark:text-[#a19f9d]"
            }`}
          >
            {format(currentDate, "EEEE, d 'de' MMMM", { locale: es })}
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
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              const y = e.clientY - rect.top;
              const hour = Math.floor(y / HOUR_HEIGHT);
              onSlotClick(currentDate, Math.min(23, Math.max(0, hour)));
            }}
          >
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

                return (
                  <div
                    key={ev.id}
                    className="absolute rounded cursor-pointer overflow-hidden z-10 hover:z-30 hover:brightness-90 transition-all"
                    style={{
                      top: pos.top,
                      height: Math.max(pos.height, 24),
                      width,
                      left,
                      backgroundColor: ev.color || "#0078d4",
                      borderRadius: "4px",
                    }}
                    onClick={(e) => {
                      e.stopPropagation();
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
