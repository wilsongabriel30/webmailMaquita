import { useState } from "react";
import type { CalendarInfo } from "./types/calendar";
import {
  getMonthGrid,
  WEEKDAY_SHORT,
  isToday,
  isSameDay,
  addMonths,
  formatMonthYear,
  getWeekDates,
} from "./utils/dateHelpers";

interface SharedCalendarInfo {
  id: string;
  calendar_id: string;
  calendar_name: string;
  calendar_color: string;
  owner_email: string;
  permission: string;
}

interface Props {
  calendars: CalendarInfo[];
  selectedCalendarIds: Set<string>;
  currentDate: Date;
  onDateSelect: (date: Date) => void;
  onToggleCalendar: (id: string) => void;
  onNewEvent: () => void;
  onAddCalendar: () => void;
  sharedCalendars?: SharedCalendarInfo[];
  onShareCalendar?: (calendarId: string) => void;
}

export function CalendarSidebar({
  calendars,
  selectedCalendarIds,
  currentDate,
  onDateSelect,
  onToggleCalendar,
  onNewEvent: _onNewEvent,
  onAddCalendar,
  sharedCalendars = [],
  onShareCalendar: _onShareCalendar,
}: Props) {
  const [miniDate, setMiniDate] = useState(new Date());
  const [calendarsSectionOpen, setCalendarsSectionOpen] = useState(true);
  const [showAllCalendars, setShowAllCalendars] = useState(false);

  const grid = getMonthGrid(miniDate);
  const miniMonth = miniDate.getMonth();

  /* check if a date is in the same week as currentDate */
  function isCurrentWeek(day: Date): boolean {
    const weekDates = getWeekDates(currentDate);
    return weekDates.some((wd) => isSameDay(wd, day));
  }

  const VISIBLE_CALENDARS = 5;
  const displayedCalendars = showAllCalendars
    ? calendars
    : calendars.slice(0, VISIBLE_CALENDARS);
  const hasMore = calendars.length > VISIBLE_CALENDARS;

  return (
    <div className="w-[220px] bg-[#faf9f8] border-r border-[#e0e0e0] flex flex-col shrink-0 overflow-y-auto select-none">

      {/* ── Mini calendar ───────────────────────────── */}
      <div className="px-3 pt-3 pb-2">
        {/* Month header */}
        <div className="flex items-center justify-between mb-1.5">
          <button
            onClick={() => setMiniDate(addMonths(miniDate, 0))}
            className="text-[12px] font-semibold text-[#323130] flex items-center gap-0.5 hover:underline cursor-pointer"
          >
            <svg className="w-3 h-3 text-[#605e5c]" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
            {formatMonthYear(miniDate)}
          </button>
          <div className="flex flex-col -space-y-0.5">
            <button
              onClick={() => setMiniDate(addMonths(miniDate, -1))}
              className="p-0 text-[#605e5c] hover:text-[#323130] transition-colors"
              aria-label="Mes anterior"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
              </svg>
            </button>
            <button
              onClick={() => setMiniDate(addMonths(miniDate, 1))}
              className="p-0 text-[#605e5c] hover:text-[#323130] transition-colors"
              aria-label="Mes siguiente"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          </div>
        </div>

        {/* Weekday header (single letters) */}
        <div className="grid grid-cols-7 gap-0">
          {WEEKDAY_SHORT.map((d) => (
            <div key={d} className="text-center text-[10px] text-[#a19f9d] font-medium py-0.5">
              {d.charAt(0)}
            </div>
          ))}
        </div>

        {/* Day grid */}
        <div className="grid grid-cols-7 gap-0">
          {grid.flat().map((day, i) => {
            const inMonth = day.getMonth() === miniMonth;
            const today = isToday(day);
            const selected = isSameDay(day, currentDate);
            const inWeek = isCurrentWeek(day) && inMonth;

            return (
              <button
                key={i}
                onClick={() => onDateSelect(day)}
                className={[
                  "text-[11px] w-full aspect-square flex items-center justify-center transition-colors relative",
                  /* current week highlight row */
                  inWeek && !today && !selected ? "bg-[#e8f4fd]" : "",
                  /* outside month */
                  !inMonth ? "text-[#605e5c]" : "text-[#323130]",
                  /* hover */
                  !selected && !today ? "hover:bg-[#edebe9]" : "",
                ].join(" ")}
              >
                <span
                  className={[
                    "w-[22px] h-[22px] flex items-center justify-center rounded-full",
                    /* today = blue circle */
                    today ? "bg-[#0078d4] text-white font-bold" : "",
                    /* selected but not today */
                    selected && !today ? "ring-2 ring-[#0078d4] font-semibold" : "",
                  ].join(" ")}
                >
                  {day.getDate()}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Agregar calendario link ─────────────────── */}
      <div className="px-3 py-2">
        <button
          onClick={onAddCalendar}
          className="flex items-center gap-1.5 text-[12px] text-[#106ebe] hover:underline transition-colors"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path d="M12 4v16m8-8H4" />
          </svg>
          Agregar calendario
        </button>
      </div>

      {/* ── Divider ─────────────────────────────────── */}
      <div className="border-t border-[#e0e0e0] mx-3" />

      {/* ── Mis calendarios section ─────────────────── */}
      <div className="px-3 py-2 flex-1">
        {/* Collapsible header */}
        <button
          onClick={() => setCalendarsSectionOpen(!calendarsSectionOpen)}
          className="flex items-center gap-1 mb-1.5 w-full text-left"
        >
          <svg
            className={"w-3 h-3 text-[#605e5c] transition-transform " + (calendarsSectionOpen ? "" : "-rotate-90")}
            fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
          <span className="text-[12px] font-semibold text-[#323130]">Mis calendarios</span>
        </button>

        {calendarsSectionOpen && (
          <div className="space-y-0.5 ml-1">
            {displayedCalendars.map((cal) => {
              const checked = selectedCalendarIds.has(cal.id);
              return (
                <label
                  key={cal.id}
                  className="flex items-center gap-2 py-1 px-1 rounded cursor-pointer hover:bg-[#edebe9] transition-colors"
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => onToggleCalendar(cal.id)}
                    className="sr-only"
                  />
                  {/* Colored circle / checkbox */}
                  <span
                    className="w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center shrink-0 transition-colors"
                    style={{
                      borderColor: cal.color,
                      backgroundColor: checked ? cal.color : "transparent",
                    }}
                  >
                    {checked && (
                      <svg className="w-2 h-2 text-white" fill="currentColor" viewBox="0 0 20 20">
                        <path
                          fillRule="evenodd"
                          d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                          clipRule="evenodd"
                        />
                      </svg>
                    )}
                  </span>
                  <span className="text-[12px] text-[#323130] truncate">{cal.name}</span>
                </label>
              );
            })}

            {/* Mostrar todo / Mostrar menos */}
            {hasMore && (
              <button
                onClick={() => setShowAllCalendars(!showAllCalendars)}
                className="text-[11px] text-[#106ebe] hover:underline ml-1 mt-1"
              >
                {showAllCalendars ? "Mostrar menos" : "Mostrar todo"}
              </button>
            )}
          </div>
        )}

      {/* Calendarios compartidos conmigo */}
      {sharedCalendars.length > 0 && (
        <>
          <div className="border-t border-[#e0e0e0] mx-3" />
          <div className="px-3 py-2">
            <div className="flex items-center gap-1 mb-1.5">
              <span className="text-[12px] font-semibold text-[#323130]">Compartidos conmigo</span>
            </div>
            <div className="space-y-0.5 ml-1">
              {sharedCalendars.map((sc) => (
                <div
                  key={sc.id}
                  className="flex items-center gap-2 py-1 px-1 rounded hover:bg-[#edebe9] transition-colors"
                  title={`Propietario: ${sc.owner_email} - ${sc.permission === 'read-write' ? 'Lectura y escritura' : 'Solo lectura'}`}
                >
                  <span
                    className="w-3.5 h-3.5 rounded-full shrink-0"
                    style={{ backgroundColor: sc.calendar_color }}
                  />
                  <span className="text-[12px] text-[#323130] truncate flex-1">{sc.calendar_name}</span>
                  <span className="text-[10px] text-[#8a8886]">{sc.owner_email.split('@')[0]}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
      </div>
    </div>
  );
}
