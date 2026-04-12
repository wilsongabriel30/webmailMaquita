import { useMemo } from "react";
import type { CalendarEvent } from "./types/calendar";
import { formatTime, formatDateFull, isToday, addDays } from "./utils/dateHelpers";
import { parseISO } from "date-fns";

interface Props {
  currentDate: Date;
  events: CalendarEvent[];
  onEventClick: (event: CalendarEvent) => void;
}

export function AgendaView({ currentDate, events, onEventClick }: Props) {
  const grouped = useMemo(() => {
    const endDate = addDays(currentDate, 30);
    const filtered = events
      .filter((ev) => {
        const d = parseISO(ev.dtstart);
        return d >= currentDate && d <= endDate;
      })
      .sort((a, b) => parseISO(a.dtstart).getTime() - parseISO(b.dtstart).getTime());

    const groups = new Map<string, CalendarEvent[]>();
    for (const ev of filtered) {
      const key = parseISO(ev.dtstart).toDateString();
      const arr = groups.get(key) || [];
      arr.push(ev);
      groups.set(key, arr);
    }
    return Array.from(groups.entries()).map(([dateStr, evts]) => ({
      date: new Date(dateStr),
      events: evts,
    }));
  }, [currentDate, events]);

  if (grouped.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-[#a19f9d] dark:text-[#605e5c]">
        <div className="text-center">
          <svg className="w-12 h-12 mx-auto mb-3 text-[#c8c6c4]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          <p className="text-[14px]">No hay eventos en los proximos 30 dias</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4">
      {grouped.map(({ date, events: dayEvents }) => {
        const today = isToday(date);
        return (
          <div key={date.toISOString()} className="mb-4">
            {/* Date header */}
            <div
              className={`sticky top-0 z-10 py-2 px-3 rounded-md mb-1 ${
                today
                  ? "bg-[#0078d4]/10 border-l-[3px] border-[#0078d4]"
                  : "bg-[#f3f2f1] dark:bg-[#3b3a39]"
              }`}
            >
              <span
                className={`text-[13px] font-semibold capitalize ${
                  today ? "text-[#0078d4]" : "text-[#323130] dark:text-[#f3f2f1]"
                }`}
              >
                {today ? "Hoy - " : ""}
                {formatDateFull(date)}
              </span>
            </div>

            {/* Events */}
            <div className="space-y-1 pl-2">
              {dayEvents.map((ev) => (
                <div
                  key={ev.id}
                  onClick={() => onEventClick(ev)}
                  className="flex items-start gap-3 p-2.5 rounded-md cursor-pointer hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39] transition-colors group"
                >
                  <div className="w-1 self-stretch rounded-full shrink-0" style={{ backgroundColor: ev.color || "#0078d4" }} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      {ev.rrule && (
                        <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 16 16" fill={ev.color || "#0078d4"}>
                          <path d="M11.534 7h3.932a.25.25 0 01.192.41l-1.966 2.36a.25.25 0 01-.384 0l-1.966-2.36a.25.25 0 01.192-.41zm-11 2H4.466a.25.25 0 00.192-.41L2.692 6.23a.25.25 0 00-.384 0L.342 8.59A.25.25 0 00.534 9z"/>
                          <path d="M8 3c-1.552 0-2.94.707-3.857 1.818a.5.5 0 11-.771-.636A5.501 5.501 0 0113.5 8a.5.5 0 01-1 0 4.5 4.5 0 00-4.5-4.5zM2.5 8a.5.5 0 01.5.5 4.5 4.5 0 007.857 2.682.5.5 0 11.771.636A5.501 5.501 0 012 8.5a.5.5 0 01.5-.5z"/>
                        </svg>
                      )}
                      <span className="text-[13px] font-semibold text-[#323130] dark:text-[#f3f2f1] truncate">
                        {ev.summary}
                      </span>
                    </div>
                    <div className="text-[12px] text-[#605e5c] dark:text-[#a19f9d] mt-0.5">
                      {ev.all_day ? "Todo el dia" : `${formatTime(ev.dtstart)} - ${formatTime(ev.dtend)}`}
                    </div>
                    {ev.location && (
                      <div className="text-[12px] text-[#a19f9d] mt-0.5 flex items-center gap-1">
                        <svg className="w-3 h-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                        </svg>
                        {ev.location}
                      </div>
                    )}
                  </div>
                  <span className="text-[11px] text-[#a19f9d] shrink-0">{ev.calendar_name}</span>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
