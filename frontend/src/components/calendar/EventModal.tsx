import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import type { CalendarInfo, CalendarEvent, EventFormData, EventReminder, FreeBusySlot } from "./types/calendar";
import { toDateInputValue, toTimeInputValue, formatTime } from "./utils/dateHelpers";
import { parseISO, addMinutes, format } from "date-fns";
import { useCalendarApi } from "./hooks/useCalendarApi";
import { api } from "../../api/client";
import { es } from "date-fns/locale";

interface Props {
  isOpen: boolean;
  event: CalendarEvent | null;
  initialDate?: Date;
  initialHour?: number;
  calendars: CalendarInfo[];
  onSave: (data: EventFormData) => void;
  onDelete: (id: string) => void;
  onClose: () => void;
}

const RECURRENCE_OPTIONS = [
  { value: "", label: "No se repite" },
  { value: "FREQ=DAILY", label: "Cada dia" },
  { value: "FREQ=WEEKLY", label: "Cada semana" },
  { value: "FREQ=MONTHLY", label: "Cada mes" },
  { value: "FREQ=YEARLY", label: "Cada ano" },
  { value: "custom", label: "Personalizado..." },
];

const WEEKDAYS_RRULE = [
  { value: "MO", label: "L" },
  { value: "TU", label: "M" },
  { value: "WE", label: "X" },
  { value: "TH", label: "J" },
  { value: "FR", label: "V" },
  { value: "SA", label: "S" },
  { value: "SU", label: "D" },
];

const REMINDER_OPTIONS = [
  { minutes: 0, label: "Al momento" },
  { minutes: 5, label: "5 minutos antes" },
  { minutes: 15, label: "15 minutos antes" },
  { minutes: 30, label: "30 minutos antes" },
  { minutes: 60, label: "1 hora antes" },
  { minutes: 1440, label: "1 día antes" },
];

const STATUS_OPTIONS = [
  { value: "busy", label: "Ocupado", icon: "■" },
  { value: "free", label: "Disponible", icon: "□" },
  { value: "workingElsewhere", label: "Trabajando en otro sitio", icon: "◫" },
  { value: "tentative", label: "Provisional", icon: "◧" },
  { value: "oof", label: "Fuera de oficina", icon: "▨" },
];

export function EventModal({
  isOpen,
  event,
  initialDate,
  initialHour,
  calendars,
  onSave,
  onDelete,
  onClose,
}: Props) {
  const summaryRef = useRef<HTMLInputElement>(null);
  const isEdit = !!event;

  const getDefaultStart = useCallback(() => {
    if (event) return parseISO(event.dtstart);
    if (initialDate) {
      const d = new Date(initialDate);
      d.setHours(initialHour ?? 9, 0, 0, 0);
      return d;
    }
    const now = new Date();
    now.setMinutes(0, 0, 0);
    now.setHours(now.getHours() + 1);
    return now;
  }, [event, initialDate, initialHour]);

  const getDefaultEnd = useCallback(() => {
    if (event) return parseISO(event.dtend);
    return addMinutes(getDefaultStart(), 30);
  }, [event, getDefaultStart]);

  const defaultCalId = event?.calendar_id || calendars.find((c) => c.is_default)?.id || calendars[0]?.id || "";

  const [summary, setSummary] = useState(event?.summary || "");
  const [description, setDescription] = useState(event?.description || "");
  const [location, setLocation] = useState(event?.location || "");
  const [calendarId, setCalendarId] = useState(defaultCalId);
  const [startDate, setStartDate] = useState(toDateInputValue(getDefaultStart()));
  const [startTime, setStartTime] = useState(toTimeInputValue(getDefaultStart()));
  const [endDate, setEndDate] = useState(toDateInputValue(getDefaultEnd()));
  const [endTime, setEndTime] = useState(toTimeInputValue(getDefaultEnd()));
  const [allDay, setAllDay] = useState(event?.all_day || false);
  const [rrule, setRrule] = useState(event?.rrule || "");
  const [reminders, setReminders] = useState<EventReminder[]>(event?.reminders || []);
  const [attendees, setAttendees] = useState<string[]>(event?.attendees?.filter((a) => a.role !== "OPT-PARTICIPANT").map((a) => a.email).filter(Boolean) as string[] || []);
  const [optionalAttendees, setOptionalAttendees] = useState<string[]>(event?.attendees?.filter((a) => a.role === "OPT-PARTICIPANT").map((a) => a.email).filter(Boolean) as string[] || []);
  const [newAttendee, setNewAttendee] = useState("");
  const [newOptionalAttendee, setNewOptionalAttendee] = useState("");
  const [optionalSuggestions, setOptionalSuggestions] = useState<{email:string;display_name?:string}[]>([]);
  const [showOptionalSuggestions, setShowOptionalSuggestions] = useState(false);
  const [attendeeSuggestions, setAttendeeSuggestions] = useState<{email:string;display_name?:string}[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const suggestionsRef = useRef<HTMLDivElement>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [status, setStatus] = useState("busy");
  const [activeTab, setActiveTab] = useState<"event" | "series">("event");
  const [showDatePickers, setShowDatePickers] = useState(false);
  const [showStatusDropdown, setShowStatusDropdown] = useState(false);
  const [virtualMeeting, setVirtualMeeting] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const descRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [attachments, setAttachments] = useState<{file: File; preview?: string}[]>([]);

  // Custom recurrence state
  const [customFreq, setCustomFreq] = useState<"DAILY" | "WEEKLY" | "MONTHLY" | "YEARLY">("WEEKLY");
  const [customInterval, setCustomInterval] = useState(1);
  const [customDays, setCustomDays] = useState<string[]>([]);
  const [customCount, setCustomCount] = useState<number | null>(null);
  const [showCustomRecurrence, setShowCustomRecurrence] = useState(false);

  // Free/Busy state
  const { fetchFreeBusy } = useCalendarApi();
  const [freeBusyData, setFreeBusyData] = useState<Map<string, FreeBusySlot[]>>(new Map());
  const [loadingFreeBusy, setLoadingFreeBusy] = useState(false);

  // Reset on open
  useEffect(() => {
    if (isOpen) {
      const start = getDefaultStart();
      const end = getDefaultEnd();
      setSummary(event?.summary || "");
      setDescription(event?.description || "");
      setLocation(event?.location || "");
      setCalendarId(event?.calendar_id || calendars.find((c) => c.is_default)?.id || calendars[0]?.id || "");
      setStartDate(toDateInputValue(start));
      setStartTime(toTimeInputValue(start));
      setEndDate(toDateInputValue(end));
      setEndTime(toTimeInputValue(end));
      setAllDay(event?.all_day || false);
      setRrule(event?.rrule || "");
      setReminders(event?.reminders || []);
      setAttendees(event?.attendees?.filter((a) => a.role !== "OPT-PARTICIPANT").map((a) => a.email).filter(Boolean) as string[] || []);
      setOptionalAttendees(event?.attendees?.filter((a) => a.role === "OPT-PARTICIPANT").map((a) => a.email).filter(Boolean) as string[] || []);
      setNewAttendee("");
      setNewOptionalAttendee("");
      setAttachments([]);
      setConfirmDelete(false);
      setStatus(event?.status || "busy");
      setActiveTab("event");
      setShowDatePickers(false);
      setShowStatusDropdown(false);
      setVirtualMeeting(false);
      setIsExpanded(false);
      setTimeout(() => summaryRef.current?.focus(), 100);
    }
  }, [isOpen, event, calendars, getDefaultStart, getDefaultEnd]);

  // Fetch Free/Busy when attendees change
  useEffect(() => {
    if (!isOpen || (attendees.length === 0 && optionalAttendees.length === 0)) {
      setFreeBusyData(new Map());
      return;
    }
    const abortController = new AbortController();
    const fetchAll = async () => {
      setLoadingFreeBusy(true);
      const dayStart = startDate + "T00:00:00";
      const dayEnd = startDate + "T23:59:59";
      const results = new Map<string, FreeBusySlot[]>();
      for (const email of [...attendees, ...optionalAttendees]) {
        try {
          const res = await fetchFreeBusy(email, dayStart, dayEnd);
          if (res && !abortController.signal.aborted) {
            results.set(email, res.slots);
          }
        } catch { /* silencioso */ }
      }
      if (!abortController.signal.aborted) {
        setFreeBusyData(results);
        setLoadingFreeBusy(false);
      }
    };
    fetchAll();
    return () => { abortController.abort(); };
  }, [isOpen, attendees, startDate, fetchFreeBusy]);

  const selectedCalendar = useMemo(
    () => calendars.find((c) => c.id === calendarId),
    [calendars, calendarId]
  );

  // Format date/time display like Outlook: "Lun 6/4/2026, de 13:00 a 13:30"
  const dateTimeDisplay = useMemo(() => {
    try {
      const start = new Date(`${startDate}T${startTime}:00`);
      const dayName = format(start, "EEE", { locale: es });
      const capDay = dayName.charAt(0).toUpperCase() + dayName.slice(1);
      const day = start.getDate();
      const month = start.getMonth() + 1;
      const year = start.getFullYear();
      if (allDay) {
        return `${capDay} ${day}/${month}/${year}, todo el día`;
      }
      return `${capDay} ${day}/${month}/${year}, de ${startTime} a ${endTime}`;
    } catch {
      return "";
    }
  }, [startDate, startTime, endTime, allDay]);

  // Mini day view hours for right panel
  const miniDayHours = useMemo(() => {
    const startH = parseInt(startTime.split(":")[0]) || 8;
    const rangeStart = Math.max(0, startH - 2);
    const rangeEnd = Math.min(24, startH + 6);
    return Array.from({ length: rangeEnd - rangeStart }, (_, i) => rangeStart + i);
  }, [startTime]);

  // Mini day date display
  const miniDayDateDisplay = useMemo(() => {
    try {
      const d = new Date(`${startDate}T00:00:00`);
      const dayName = format(d, "EEE", { locale: es });
      const capDay = dayName.charAt(0).toUpperCase() + dayName.slice(1);
      const dayNum = d.getDate();
      const monthName = format(d, "MMM", { locale: es });
      const capMonth = monthName.charAt(0).toUpperCase() + monthName.slice(1) + ".";
      const year = d.getFullYear();
      return `${capDay}, ${dayNum} ${capMonth} ${year}`;
    } catch {
      return "";
    }
  }, [startDate]);

  const currentStatusLabel = useMemo(() => {
    return STATUS_OPTIONS.find((s) => s.value === status)?.label || "Ocupado";
  }, [status]);

  function handleFileAttach(files: FileList | null) {
    if (!files) return;
    const newAtts = Array.from(files).map(file => {
      const item: {file: File; preview?: string} = { file };
      if (file.type.startsWith("image/")) item.preview = URL.createObjectURL(file);
      return item;
    });
    setAttachments(prev => [...prev, ...newAtts]);
  }

  function removeAttachment(idx: number) {
    setAttachments(prev => {
      if (prev[idx].preview) URL.revokeObjectURL(prev[idx].preview!);
      return prev.filter((_, i) => i !== idx);
    });
  }

  function fmtSize(b: number) {
    if (b < 1024) return b + " B";
    if (b < 1048576) return (b / 1024).toFixed(1) + " KB";
    return (b / 1048576).toFixed(1) + " MB";
  }

  function handleSave() {
    if (!summary.trim()) return;
    if (!calendarId) { alert("Selecciona un calendario"); return; }
    const dtstart = allDay ? `${startDate}T00:00:00` : `${startDate}T${startTime}:00`;
    const dtend = allDay ? `${endDate}T23:59:59` : `${endDate}T${endTime}:00`;
    onSave({
      calendar_id: calendarId,
      summary: summary.trim(),
      description,
      location,
      dtstart,
      dtend,
      all_day: allDay,
      rrule,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      reminders,
      attendees,
      optional_attendees: optionalAttendees,
    });
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    }
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleSave();
    }
  }

  function addReminder() {
    setReminders([...reminders, { type: "notification", minutes: 15 }]);
  }

  function removeReminder(idx: number) {
    setReminders(reminders.filter((_, i) => i !== idx));
  }

  function addAttendee(emailOverride?: string) {
    const email = (emailOverride || newAttendee).trim();
    if (email && !attendees.includes(email)) {
      setAttendees([...attendees, email]);
    }
    setNewAttendee("");
    setAttendeeSuggestions([]);
    setShowSuggestions(false);
  }

  function addOptionalAttendee(emailOverride?: string) {
    const email = (emailOverride || newOptionalAttendee).trim();
    if (email && !optionalAttendees.includes(email) && !attendees.includes(email)) {
      setOptionalAttendees([...optionalAttendees, email]);
    }
    setNewOptionalAttendee("");
    setOptionalSuggestions([]);
    setShowOptionalSuggestions(false);
  }

  async function searchOptionalContacts(q: string) {
    if (q.length < 2) { setOptionalSuggestions([]); setShowOptionalSuggestions(false); return; }
    try {
      const data = await api.get<{contacts:{email:string;display_name?:string}[]}>("/contacts/search?q=" + encodeURIComponent(q) + "&limit=8");
      const list = Array.isArray(data) ? data : (data as any)?.contacts || [];
      setOptionalSuggestions(list.filter((c: any) => c.email && !attendees.includes(c.email) && !optionalAttendees.includes(c.email)).map((c: any) => ({ email: c.email, display_name: c.display_name || c.name || "" })));
      setShowOptionalSuggestions(true);
    } catch { setOptionalSuggestions([]); }
  }

  async function searchContacts(q: string) {
    if (q.length < 2) { setAttendeeSuggestions([]); setShowSuggestions(false); return; }
    try {
      const data = await api.get<{contacts:{email:string;display_name?:string}[]}>("/contacts/search?q=" + encodeURIComponent(q) + "&limit=8");
      const list = Array.isArray(data) ? data : (data as any)?.contacts || [];
      setAttendeeSuggestions(list.filter((c: any) => c.email && !attendees.includes(c.email)).map((c: any) => ({ email: c.email, display_name: c.display_name || c.name || "" })));
      setShowSuggestions(true);
    } catch { setAttendeeSuggestions([]); }
  }

  if (!isOpen) return null;

  const calColor = selectedCalendar?.color || "#0078d4";

  return (
    <div className="olkm-root" onKeyDown={handleKeyDown}>
      {/* Overlay */}
      <div className="olkm-overlay" onClick={onClose} />

      {/* Modal Panel */}
      <div className={`olkm-panel${isExpanded ? " olkm-dialog-expanded" : ""}`}>
        {/* Title Bar */}
        <div className="olkm-titlebar">
          <div className="olkm-titlebar-left">
            <span className="olkm-titlebar-text">
              {isEdit ? "Editar evento" : "Nuevo evento"}: {selectedCalendar?.name || "Calendario"}
            </span>
          </div>
          <div className="olkm-titlebar-actions">
            <button className="olkm-titlebar-btn" title={isExpanded ? "Restaurar" : "Expandir"} onClick={() => setIsExpanded(!isExpanded)}>
              <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
                {isExpanded
                  ? <path d="M5 1v3H1v1h4a1 1 0 001-1V1H5zm5 14v-3h4v-1h-4a1 1 0 00-1 1v3h1z"/>
                  : <path d="M3 3v4h1V4.707l3.646 3.647.708-.708L4.707 4H7V3H3zm10 10V9h-1v2.293l-3.646-3.647-.708.708L11.293 12H9v1h4z"/>
                }
              </svg>
            </button>
            <button className="olkm-titlebar-btn olkm-close-btn" onClick={onClose} title="Cerrar">
              <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
                <path d="M2.146 2.854a.5.5 0 11.708-.708L8 7.293l5.146-5.147a.5.5 0 01.708.708L8.707 8l5.147 5.146a.5.5 0 01-.708.708L8 8.707l-5.146 5.147a.5.5 0 01-.708-.708L7.293 8 2.146 2.854z"/>
              </svg>
            </button>
          </div>
        </div>

        {/* Toolbar */}
        <div className="olkm-toolbar">
          <div className="olkm-toolbar-left">
            <button
              className="olkm-save-btn"
              onClick={handleSave}
              disabled={!summary.trim()}
            >
              <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
                <path d="M2 2a2 2 0 012-2h7.586a1 1 0 01.707.293l3.414 3.414a1 1 0 01.293.707V14a2 2 0 01-2 2H4a2 2 0 01-2-2V2zm6 1a1 1 0 00-1 1v2a1 1 0 002 0V4a1 1 0 00-1-1zm-3 9a3 3 0 106 0 3 3 0 00-6 0z"/>
              </svg>
              <span>Guardar</span>
            </button>

            <div className="olkm-toolbar-sep" />

            <button
              className={`olkm-tab-btn ${activeTab === "event" ? "active" : ""}`}
              onClick={() => setActiveTab("event")}
            >
              <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
                <path d="M4.5 0a.5.5 0 01.5.5V1h6V.5a.5.5 0 011 0V1h1.5A1.5 1.5 0 0115 2.5v11a1.5 1.5 0 01-1.5 1.5h-11A1.5 1.5 0 011 13.5v-11A1.5 1.5 0 012.5 1H4V.5a.5.5 0 01.5-.5zM2 5v8.5a.5.5 0 00.5.5h11a.5.5 0 00.5-.5V5H2z"/>
              </svg>
              <span>Evento</span>
            </button>

            <button
              className={`olkm-tab-btn ${activeTab === "series" ? "active" : ""}`}
              onClick={() => setActiveTab("series")}
            >
              <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
                <path d="M11.534 7h3.932a.25.25 0 01.192.41l-1.966 2.36a.25.25 0 01-.384 0l-1.966-2.36a.25.25 0 01.192-.41zm-11 2H4.466a.25.25 0 00.192-.41L2.692 6.23a.25.25 0 00-.384 0L.342 8.59A.25.25 0 00.534 9z"/>
                <path d="M8 3c-1.552 0-2.94.707-3.857 1.818a.5.5 0 11-.771-.636A5.501 5.501 0 0113.5 8a.5.5 0 01-1 0 4.5 4.5 0 00-4.5-4.5zM2.5 8a.5.5 0 01.5.5 4.5 4.5 0 007.857 2.682.5.5 0 11.771.636A5.501 5.501 0 012 8.5a.5.5 0 01.5-.5z"/>
              </svg>
              <span>Serie</span>
            </button>

            <div className="olkm-toolbar-sep" />

            {/* Status dropdown */}
            <div className="olkm-status-wrapper">
              <button
                className="olkm-tab-btn"
                onClick={() => setShowStatusDropdown(!showStatusDropdown)}
              >
                <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
                  <rect x="3" y="3" width="10" height="10" rx="1" />
                </svg>
                <span>{currentStatusLabel}</span>
                <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor" style={{ marginLeft: 2 }}>
                  <path d="M4.427 7.427l3.396 3.396a.25.25 0 00.354 0l3.396-3.396A.25.25 0 0011.396 7H4.604a.25.25 0 00-.177.427z"/>
                </svg>
              </button>
              {showStatusDropdown && (
                <div className="olkm-status-dropdown">
                  {STATUS_OPTIONS.map((s) => (
                    <button
                      key={s.value}
                      className={`olkm-status-option ${status === s.value ? "selected" : ""}`}
                      onClick={() => { setStatus(s.value); setShowStatusDropdown(false); }}
                    >
                      <span className="olkm-status-icon">{s.icon}</span>
                      <span>{s.label}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {isEdit && (
              <>
                <div className="olkm-toolbar-sep" />
                {confirmDelete ? (
                  <div className="olkm-delete-confirm">
                    <span className="olkm-delete-question">¿Eliminar este evento?</span>
                    <button
                      className="olkm-delete-yes"
                      onClick={() => onDelete(event!.id)}
                    >
                      Eliminar
                    </button>
                    <button
                      className="olkm-delete-cancel"
                      onClick={() => setConfirmDelete(false)}
                    >
                      Cancelar
                    </button>
                  </div>
                ) : (
                  <button
                    className="olkm-tab-btn delete"
                    onClick={() => setConfirmDelete(true)}
                  >
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
                      <path d="M5.5 5.5A.5.5 0 016 6v6a.5.5 0 01-1 0V6a.5.5 0 01.5-.5zm2.5 0a.5.5 0 01.5.5v6a.5.5 0 01-1 0V6a.5.5 0 01.5-.5zm3 .5a.5.5 0 00-1 0v6a.5.5 0 001 0V6z"/>
                      <path d="M14.5 3a1 1 0 01-1 1H13v9a2 2 0 01-2 2H5a2 2 0 01-2-2V4h-.5a1 1 0 010-2H6a1 1 0 011-1h2a1 1 0 011 1h3.5a1 1 0 011 1zM4.118 4L4 4.059V13a1 1 0 001 1h6a1 1 0 001-1V4.059L11.882 4H4.118zM2.5 3h11a.5.5 0 000-1h-11a.5.5 0 000 1z"/>
                    </svg>
                    <span>Eliminar</span>
                  </button>
                )}
              </>
            )}
          </div>
        </div>

        {/* Content area */}
        <div className="olkm-content">
          {/* Left: Form fields */}
          <div className="olkm-form">
            {activeTab === "event" ? (
              <>
                {/* Title field */}
                <div className="olkm-field">
                  <div className="olkm-field-icon">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                      <path d="M4.5 0a.5.5 0 01.5.5V1h6V.5a.5.5 0 011 0V1h1.5A1.5 1.5 0 0115 2.5v11a1.5 1.5 0 01-1.5 1.5h-11A1.5 1.5 0 011 13.5v-11A1.5 1.5 0 012.5 1H4V.5a.5.5 0 01.5-.5zM2 5v8.5a.5.5 0 00.5.5h11a.5.5 0 00.5-.5V5H2z"/>
                    </svg>
                  </div>
                  <input
                    ref={summaryRef}
                    type="text"
                    value={summary}
                    onChange={(e) => setSummary(e.target.value)}
                    placeholder="Agregar título"
                    className="olkm-title-input"
                  />
                </div>
                <div className="olkm-separator" />

                {/* Attendees field */}
                <div className="olkm-field">
                  <div className="olkm-field-icon">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                      <path d="M7 14s-1 0-1-1 1-4 5-4 5 3 5 4-1 1-1 1H7zm4-6a3 3 0 100-6 3 3 0 000 6z"/>
                      <path fillRule="evenodd" d="M5.216 14A2.238 2.238 0 015 13c0-1.355.68-2.75 1.936-3.72A6.325 6.325 0 005 9c-4 0-5 3-5 4s1 1 1 1h4.216z"/>
                      <path d="M4.5 8a2.5 2.5 0 100-5 2.5 2.5 0 000 5z"/>
                    </svg>
                  </div>
                  <div className="olkm-attendees-area">
                    {attendees.map((email, idx) => (
                      <span key={idx} className="olkm-attendee-chip">
                        <span className="olkm-attendee-avatar">
                          {(email || "?").charAt(0).toUpperCase()}
                        </span>
                        {email}
                        <button
                          className="olkm-attendee-remove"
                          onClick={() => setAttendees(attendees.filter((_, i) => i !== idx))}
                        >
                          ×
                        </button>
                      </span>
                    ))}
                    <div style={{ position: "relative", flex: 1 }}>
                      <input
                        type="text"
                        value={newAttendee}
                        onChange={(e) => { setNewAttendee(e.target.value); searchContacts(e.target.value); }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === "Tab" || e.key === ",") {
                            if (newAttendee.trim()) {
                              e.preventDefault();
                              e.stopPropagation();
                              addAttendee();
                            }
                          }
                          if (e.key === "Escape") { setShowSuggestions(false); }
                        }}
                        onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
                        placeholder="Requeridos: buscar contacto o escribir email..."
                        className="olkm-inline-input"
                      />
                      {showSuggestions && attendeeSuggestions.length > 0 && (
                        <div ref={suggestionsRef} style={{
                          position: "absolute", top: "100%", left: 0, right: 0, zIndex: 1000,
                          background: "#fff", border: "1px solid #e1dfdd", borderRadius: 4,
                          boxShadow: "0 4px 12px rgba(0,0,0,0.15)", maxHeight: 200, overflowY: "auto",
                        }}>
                          {attendeeSuggestions.map((s, i) => (
                            <div key={i}
                              onMouseDown={(e) => { e.preventDefault(); addAttendee(s.email); }}
                              style={{
                                padding: "8px 12px", cursor: "pointer", fontSize: 13,
                                borderBottom: "1px solid #f3f2f1",
                              }}
                              onMouseEnter={(e) => { (e.target as HTMLElement).style.background = "#f3f2f1"; }}
                              onMouseLeave={(e) => { (e.target as HTMLElement).style.background = "#fff"; }}
                            >
                              <div style={{ fontWeight: 600 }}>{s.display_name || s.email}</div>
                              {s.display_name && <div style={{ fontSize: 11, color: "#605e5c" }}>{s.email}</div>}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Optional Attendees field */}
                <div className="olkm-field">
                  <div className="olkm-field-icon">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" opacity="0.6">
                      <path d="M7 14s-1 0-1-1 1-4 5-4 5 3 5 4-1 1-1 1H7zm4-6a3 3 0 100-6 3 3 0 000 6z"/>
                      <path fillRule="evenodd" d="M5.216 14A2.238 2.238 0 015 13c0-1.355.68-2.75 1.936-3.72A6.325 6.325 0 005 9c-4 0-5 3-5 4s1 1 1 1h4.216z"/>
                      <path d="M4.5 8a2.5 2.5 0 100-5 2.5 2.5 0 000 5z"/>
                    </svg>
                  </div>
                  <div className="olkm-attendees-area">
                    {optionalAttendees.map((email, idx) => (
                      <span key={idx} className="olkm-attendee-chip" style={{ background: "#f3f2f1", borderColor: "#d2d0ce" }}>
                        <span className="olkm-attendee-avatar" style={{ background: "#a19f9d" }}>
                          {(email || "?").charAt(0).toUpperCase()}
                        </span>
                        {email}
                        <button
                          className="olkm-attendee-remove"
                          onClick={() => setOptionalAttendees(optionalAttendees.filter((_, i) => i !== idx))}
                        >
                          ×
                        </button>
                      </span>
                    ))}
                    <div style={{ position: "relative", flex: 1 }}>
                      <input
                        type="text"
                        value={newOptionalAttendee}
                        onChange={(e) => { setNewOptionalAttendee(e.target.value); searchOptionalContacts(e.target.value); }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === "Tab" || e.key === ",") {
                            if (newOptionalAttendee.trim()) {
                              e.preventDefault();
                              e.stopPropagation();
                              addOptionalAttendee();
                            }
                          }
                          if (e.key === "Escape") { setShowOptionalSuggestions(false); }
                        }}
                        onBlur={() => setTimeout(() => setShowOptionalSuggestions(false), 200)}
                        placeholder="Opcional: buscar contacto o escribir email..."
                        className="olkm-inline-input"
                      />
                      {showOptionalSuggestions && optionalSuggestions.length > 0 && (
                        <div style={{
                          position: "absolute", top: "100%", left: 0, right: 0, zIndex: 1000,
                          background: "#fff", border: "1px solid #e1dfdd", borderRadius: 4,
                          boxShadow: "0 4px 12px rgba(0,0,0,0.15)", maxHeight: 200, overflowY: "auto",
                        }}>
                          {optionalSuggestions.map((s, i) => (
                            <div key={i}
                              onMouseDown={(e) => { e.preventDefault(); addOptionalAttendee(s.email); }}
                              style={{
                                padding: "8px 12px", cursor: "pointer", fontSize: 13,
                                borderBottom: "1px solid #f3f2f1",
                              }}
                              onMouseEnter={(e) => { (e.target as HTMLElement).style.background = "#f3f2f1"; }}
                              onMouseLeave={(e) => { (e.target as HTMLElement).style.background = "#fff"; }}
                            >
                              <div style={{ fontWeight: 600 }}>{s.display_name || s.email}</div>
                              {s.display_name && <div style={{ fontSize: 11, color: "#605e5c" }}>{s.email}</div>}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
                <div className="olkm-separator" />

                {/* Date/Time field */}
                <div className="olkm-field">
                  <div className="olkm-field-icon">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                      <path d="M8 3.5a.5.5 0 00-1 0V8a.5.5 0 00.252.434l3.5 2a.5.5 0 00.496-.868L8 7.71V3.5z"/>
                      <path d="M8 16A8 8 0 108 0a8 8 0 000 16zm7-8A7 7 0 111 8a7 7 0 0114 0z"/>
                    </svg>
                  </div>
                  <div className="olkm-datetime-area">
                    <div
                      className="olkm-datetime-display"
                      onClick={() => setShowDatePickers(!showDatePickers)}
                    >
                      {dateTimeDisplay}
                      <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor" style={{ marginLeft: 6, opacity: 0.5 }}>
                        <path d="M4.427 7.427l3.396 3.396a.25.25 0 00.354 0l3.396-3.396A.25.25 0 0011.396 7H4.604a.25.25 0 00-.177.427z"/>
                      </svg>
                    </div>
                    {showDatePickers && (
                      <div className="olkm-datetime-pickers">
                        <div className="olkm-picker-row">
                          <label className="olkm-picker-label">Inicio</label>
                          <input
                            type="date"
                            value={startDate}
                            onChange={(e) => {
                              setStartDate(e.target.value);
                              if (e.target.value > endDate) setEndDate(e.target.value);
                            }}
                            className="olkm-date-input"
                          />
                          {!allDay && (
                            <input
                              type="time"
                              value={startTime}
                              onChange={(e) => setStartTime(e.target.value)}
                              className="olkm-time-input"
                            />
                          )}
                        </div>
                        <div className="olkm-picker-row">
                          <label className="olkm-picker-label">Fin</label>
                          <input
                            type="date"
                            value={endDate}
                            onChange={(e) => setEndDate(e.target.value)}
                            className="olkm-date-input"
                          />
                          {!allDay && (
                            <input
                              type="time"
                              value={endTime}
                              onChange={(e) => setEndTime(e.target.value)}
                              className="olkm-time-input"
                            />
                          )}
                        </div>
                        <label className="olkm-allday-toggle">
                          <div className={`olkm-toggle-switch ${allDay ? "on" : ""}`}>
                            <div className="olkm-toggle-thumb" />
                          </div>
                          <span>Todo el día</span>
                          <input
                            type="checkbox"
                            checked={allDay}
                            onChange={(e) => setAllDay(e.target.checked)}
                            style={{ display: "none" }}
                          />
                        </label>
                      </div>
                    )}
                  </div>
                </div>
                <div className="olkm-separator" />

                {/* Location field */}
                <div className="olkm-field">
                  <div className="olkm-field-icon">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                      <path d="M8 16s6-5.686 6-10A6 6 0 002 6c0 4.314 6 10 6 10zm0-7a3 3 0 110-6 3 3 0 010 6z"/>
                    </svg>
                  </div>
                  <input
                    type="text"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    placeholder="Buscar una ubicación"
                    className="olkm-inline-input"
                  />
                  <button className="olkm-field-action-btn" title="Configuración de sala" onClick={() => setVirtualMeeting(!virtualMeeting)}>
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
                      <path d="M9.405 1.05c-.413-1.4-2.397-1.4-2.81 0l-.1.34a1.464 1.464 0 01-2.105.872l-.31-.17c-1.283-.698-2.686.705-1.987 1.987l.169.311c.446.82.023 1.841-.872 2.105l-.34.1c-1.4.413-1.4 2.397 0 2.81l.34.1a1.464 1.464 0 01.872 2.105l-.17.31c-.698 1.283.705 2.686 1.987 1.987l.311-.169a1.464 1.464 0 012.105.872l.1.34c.413 1.4 2.397 1.4 2.81 0l.1-.34a1.464 1.464 0 012.105-.872l.31.17c1.283.698 2.686-.705 1.987-1.987l-.169-.311a1.464 1.464 0 01.872-2.105l.34-.1c1.4-.413 1.4-2.397 0-2.81l-.34-.1a1.464 1.464 0 01-.872-2.105l.17-.31c.698-1.283-.705-2.686-1.987-1.987l-.311.169a1.464 1.464 0 01-2.105-.872l-.1-.34zM8 10.93a2.929 2.929 0 110-5.858 2.929 2.929 0 010 5.858z"/>
                    </svg>
                  </button>
                </div>
                <div className="olkm-separator" />

                {/* Virtual meeting toggle */}
                <div className="olkm-field">
                  <div className="olkm-field-icon">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                      <path d="M0 5a2 2 0 012-2h7.5a2 2 0 011.983 1.738l3.11-1.382A1 1 0 0116 4.269v7.462a1 1 0 01-1.406.913l-3.111-1.382A2 2 0 019.5 13H2a2 2 0 01-2-2V5z"/>
                    </svg>
                  </div>
                  <div className="olkm-virtual-row">
                    <span className="olkm-virtual-label">Reunión virtual</span>
                    <label className="olkm-toggle-container">
                      <input
                        type="checkbox"
                        checked={virtualMeeting}
                        onChange={(e) => setVirtualMeeting(e.target.checked)}
                        style={{ display: "none" }}
                      />
                      <div className={`olkm-toggle-switch ${virtualMeeting ? "on" : ""}`}>
                        <div className="olkm-toggle-thumb" />
                      </div>
                    </label>
                  </div>
                </div>
                <div className="olkm-separator" />

                {/* Calendar selector */}
                <div className="olkm-field">
                  <div className="olkm-field-icon">
                    <span className="olkm-cal-dot" style={{ backgroundColor: calColor }} />
                  </div>
                  <select
                    value={calendarId}
                    onChange={(e) => setCalendarId(e.target.value)}
                    className="olkm-select"
                  >
                    {calendars.map((cal) => (
                      <option key={cal.id} value={cal.id}>
                        {cal.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="olkm-separator" />

                {/* Reminders */}
                <div className="olkm-field">
                  <div className="olkm-field-icon">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                      <path d="M8 16a2 2 0 001.985-1.75H6.015A2 2 0 008 16zm.104-14.5A5.502 5.502 0 0113.5 7c0 .898.168 1.56.467 2.1.29.527.616.862.86 1.065.249.21.356.338.356.535 0 .3-.262.5-.504.5h-12.36C2.058 11.2 1.796 11 1.796 10.7c0-.197.107-.326.356-.535.244-.203.57-.538.86-1.065.3-.54.467-1.202.467-2.1a5.502 5.502 0 015.521-5.5h.104z"/>
                    </svg>
                  </div>
                  <div className="olkm-reminders">
                    {reminders.map((r, idx) => (
                      <div key={idx} className="olkm-reminder-row">
                        <select
                          value={r.minutes}
                          onChange={(e) => {
                            const updated = [...reminders];
                            updated[idx] = { ...r, minutes: parseInt(e.target.value) };
                            setReminders(updated);
                          }}
                          className="olkm-select small"
                        >
                          {REMINDER_OPTIONS.map((opt) => (
                            <option key={opt.minutes} value={opt.minutes}>
                              {opt.label}
                            </option>
                          ))}
                        </select>
                        <button onClick={() => removeReminder(idx)} className="olkm-reminder-remove">
                          ×
                        </button>
                      </div>
                    ))}
                    <button onClick={addReminder} className="olkm-add-link">
                      + Agregar recordatorio
                    </button>
                  </div>
                </div>
                <div className="olkm-separator" />

                {/* Description field */}
                <div className="olkm-field olkm-field-grow">
                  <div className="olkm-field-icon" style={{ paddingTop: 6 }}>
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                      <path d="M2.5 3a.5.5 0 000 1h11a.5.5 0 000-1h-11zm0 3a.5.5 0 000 1h11a.5.5 0 000-1h-11zm0 3a.5.5 0 000 1h11a.5.5 0 000-1h-11zm0 3a.5.5 0 000 1h7a.5.5 0 000-1h-7z"/>
                    </svg>
                  </div>
                  <div className="olkm-desc-wrapper">
                    <div className="olkm-desc-toolbar">
                      <button className="olkm-desc-btn" title="Negrita" onClick={() => { if(descRef.current) { const ta = descRef.current; const s = ta.selectionStart; const e = ta.selectionEnd; const sel = ta.value.substring(s,e); setDescription(ta.value.substring(0,s) + "**" + sel + "**" + ta.value.substring(e)); setTimeout(() => { ta.focus(); ta.setSelectionRange(s+2, e+2); }, 0); } }}><strong>B</strong></button>
                      <button className="olkm-desc-btn" title="Cursiva" onClick={() => { if(descRef.current) { const ta = descRef.current; const s = ta.selectionStart; const e = ta.selectionEnd; const sel = ta.value.substring(s,e); setDescription(ta.value.substring(0,s) + "_" + sel + "_" + ta.value.substring(e)); setTimeout(() => { ta.focus(); ta.setSelectionRange(s+1, e+1); }, 0); } }}><em>I</em></button>
                      <button className="olkm-desc-btn" title="Subrayado" onClick={() => { if(descRef.current) { const ta = descRef.current; const s = ta.selectionStart; const e = ta.selectionEnd; const sel = ta.value.substring(s,e); setDescription(ta.value.substring(0,s) + "<u>" + sel + "</u>" + ta.value.substring(e)); setTimeout(() => { ta.focus(); ta.setSelectionRange(s+3, e+3); }, 0); } }}><span style={{ textDecoration: "underline" }}>U</span></button>
                    </div>
                    <textarea
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      placeholder="Agregar detalles del evento..."
                      className="olkm-textarea"
                      rows={5}
                    />
                  </div>
                </div>
              </>
            ) : (
              /* Series tab - Recurrencia avanzada */
              <>
              <div style={{ padding: "16px 0" }}>
                <div className="olkm-field" style={{ marginBottom: "16px" }}>
                  <div className="olkm-field-icon">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                      <path d="M11.534 7h3.932a.25.25 0 01.192.41l-1.966 2.36a.25.25 0 01-.384 0l-1.966-2.36a.25.25 0 01.192-.41zm-11 2H4.466a.25.25 0 00.192-.41L2.692 6.23a.25.25 0 00-.384 0L.342 8.59A.25.25 0 00.534 9z"/>
                      <path d="M8 3c-1.552 0-2.94.707-3.857 1.818a.5.5 0 11-.771-.636A5.501 5.501 0 0113.5 8a.5.5 0 01-1 0 4.5 4.5 0 00-4.5-4.5zM2.5 8a.5.5 0 01.5.5 4.5 4.5 0 007.857 2.682.5.5 0 11.771.636A5.501 5.501 0 012 8.5a.5.5 0 01.5-.5z"/>
                    </svg>
                  </div>
                  <div style={{ flex: 1 }}>
                    <label className="olkm-series-label">Repeticion</label>
                    <select
                      value={showCustomRecurrence ? "custom" : rrule}
                      onChange={(e) => {
                        if (e.target.value === "custom") {
                          setShowCustomRecurrence(true);
                        } else {
                          setShowCustomRecurrence(false);
                          setRrule(e.target.value);
                        }
                      }}
                      className="olkm-select"
                    >
                      {RECURRENCE_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Custom recurrence builder */}
                {showCustomRecurrence && (
                  <div style={{ marginLeft: "32px", padding: "16px", background: "#f9f9f8", borderRadius: "8px", border: "1px solid #edebe9" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                      <span style={{ fontSize: "13px", color: "#323130" }}>Repetir cada</span>
                      <input
                        type="number"
                        min={1}
                        max={99}
                        value={customInterval}
                        onChange={(e) => setCustomInterval(Math.max(1, parseInt(e.target.value) || 1))}
                        style={{ width: "60px", border: "1px solid #c8c6c4", borderRadius: "4px", padding: "4px 8px", fontSize: "13px", textAlign: "center" }}
                      />
                      <select
                        value={customFreq}
                        onChange={(e) => setCustomFreq(e.target.value as any)}
                        style={{ border: "1px solid #c8c6c4", borderRadius: "4px", padding: "4px 8px", fontSize: "13px" }}
                      >
                        <option value="DAILY">dia(s)</option>
                        <option value="WEEKLY">semana(s)</option>
                        <option value="MONTHLY">mes(es)</option>
                        <option value="YEARLY">ano(s)</option>
                      </select>
                    </div>

                    {/* Day selector for WEEKLY */}
                    {customFreq === "WEEKLY" && (
                      <div style={{ marginBottom: "12px" }}>
                        <span style={{ fontSize: "12px", color: "#605e5c", display: "block", marginBottom: "6px" }}>Repetir en:</span>
                        <div style={{ display: "flex", gap: "4px" }}>
                          {WEEKDAYS_RRULE.map((wd) => (
                            <button
                              key={wd.value}
                              onClick={() => {
                                setCustomDays((prev) =>
                                  prev.includes(wd.value)
                                    ? prev.filter((d) => d !== wd.value)
                                    : [...prev, wd.value]
                                );
                              }}
                              style={{
                                width: "32px",
                                height: "32px",
                                borderRadius: "50%",
                                border: customDays.includes(wd.value) ? "2px solid #0078d4" : "1px solid #c8c6c4",
                                background: customDays.includes(wd.value) ? "#0078d4" : "#fff",
                                color: customDays.includes(wd.value) ? "#fff" : "#323130",
                                fontSize: "12px",
                                fontWeight: 600,
                                cursor: "pointer",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                              }}
                            >
                              {wd.label}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Count / end */}
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                      <span style={{ fontSize: "13px", color: "#323130" }}>Terminar después de</span>
                      <input
                        type="number"
                        min={1}
                        max={365}
                        value={customCount || ""}
                        onChange={(e) => {
                          const v = parseInt(e.target.value);
                          setCustomCount(v > 0 ? v : null);
                        }}
                        placeholder="sin limite"
                        style={{ width: "80px", border: "1px solid #c8c6c4", borderRadius: "4px", padding: "4px 8px", fontSize: "13px", textAlign: "center" }}
                      />
                      <span style={{ fontSize: "13px", color: "#605e5c" }}>ocurrencia(s)</span>
                    </div>

                    {/* Apply button */}
                    <button
                      onClick={() => {
                        let rule = "FREQ=" + customFreq;
                        if (customInterval > 1) rule += ";INTERVAL=" + customInterval;
                        if (customFreq === "WEEKLY" && customDays.length > 0) {
                          rule += ";BYDAY=" + customDays.join(",");
                        }
                        if (customCount) rule += ";COUNT=" + customCount;
                        setRrule(rule);
                        setShowCustomRecurrence(false);
                      }}
                      style={{
                        padding: "6px 20px",
                        fontSize: "13px",
                        border: "none",
                        borderRadius: "4px",
                        background: "#0078d4",
                        color: "#fff",
                        cursor: "pointer",
                        fontWeight: 600,
                      }}
                    >
                      Aplicar
                    </button>
                    {rrule && (
                      <span style={{ marginLeft: "12px", fontSize: "12px", color: "#0078d4", fontFamily: "monospace" }}>
                        {rrule}
                      </span>
                    )}
                  </div>
                )}

                {/* Current rrule display */}
                {rrule && !showCustomRecurrence && (
                  <div style={{ marginLeft: "32px", padding: "8px 12px", background: "#deecf9", borderRadius: "6px", display: "flex", alignItems: "center", gap: "8px" }}>
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="#0078d4">
                      <path d="M11.534 7h3.932a.25.25 0 01.192.41l-1.966 2.36a.25.25 0 01-.384 0l-1.966-2.36a.25.25 0 01.192-.41zm-11 2H4.466a.25.25 0 00.192-.41L2.692 6.23a.25.25 0 00-.384 0L.342 8.59A.25.25 0 00.534 9z"/>
                      <path d="M8 3c-1.552 0-2.94.707-3.857 1.818a.5.5 0 11-.771-.636A5.501 5.501 0 0113.5 8a.5.5 0 01-1 0 4.5 4.5 0 00-4.5-4.5zM2.5 8a.5.5 0 01.5.5 4.5 4.5 0 007.857 2.682.5.5 0 11.771.636A5.501 5.501 0 012 8.5a.5.5 0 01.5-.5z"/>
                    </svg>
                    <span style={{ fontSize: "12px", color: "#0078d4", fontFamily: "monospace" }}>{rrule}</span>
                    <button
                      onClick={() => setRrule("")}
                      style={{ marginLeft: "auto", background: "none", border: "none", color: "#a4262c", cursor: "pointer", fontSize: "14px", fontWeight: 600 }}
                    >
                      Quitar
                    </button>
                  </div>
                )}
              </div>

              {/* Free/Busy timeline when attendees exist */}
              {attendees.length > 0 && (
                <div style={{ marginTop: "16px", padding: "0 0 0 32px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="#605e5c">
                      <path d="M8 3.5a.5.5 0 00-1 0V8a.5.5 0 00.252.434l3.5 2a.5.5 0 00.496-.868L8 7.71V3.5z"/>
                      <path d="M8 16A8 8 0 108 0a8 8 0 000 16zm7-8A7 7 0 111 8a7 7 0 0114 0z"/>
                    </svg>
                    <span style={{ fontSize: "13px", fontWeight: 600, color: "#323130" }}>Disponibilidad</span>
                    {loadingFreeBusy && (
                      <span style={{ fontSize: "11px", color: "#a19f9d" }}>Cargando...</span>
                    )}
                  </div>

                  {/* Timeline 8:00 - 20:00 */}
                  <div style={{ overflowX: "auto" }}>
                    {/* Hours header */}
                    <div style={{ display: "flex", marginLeft: "100px", marginBottom: "2px" }}>
                      {Array.from({ length: 13 }, (_, i) => i + 8).map((h) => (
                        <div key={h} style={{ width: "40px", flexShrink: 0, fontSize: "10px", color: "#a19f9d", textAlign: "left" }}>
                          {h + ":00"}
                        </div>
                      ))}
                    </div>

                    {/* Per-attendee row */}
                    {attendees.map((email) => {
                      const slots = freeBusyData.get(email) || [];
                      return (
                        <div key={email} style={{ display: "flex", alignItems: "center", marginBottom: "4px" }}>
                          <div style={{ width: "100px", flexShrink: 0, fontSize: "11px", color: "#605e5c", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", paddingRight: "4px" }} title={email}>
                            {email.split("@")[0]}
                          </div>
                          <div style={{ position: "relative", height: "20px", width: "520px", background: "#e8f5e9", borderRadius: "3px", flexShrink: 0 }}>
                            {slots.map((slot, idx) => {
                              const slotStart = parseISO(slot.start);
                              const slotEnd = parseISO(slot.end);
                              const dayStart = 8 * 60;
                              const dayEnd = 21 * 60;
                              const totalMinutes = dayEnd - dayStart;
                              const startMin = Math.max(0, slotStart.getHours() * 60 + slotStart.getMinutes() - dayStart);
                              const endMin = Math.min(totalMinutes, slotEnd.getHours() * 60 + slotEnd.getMinutes() - dayStart);
                              if (endMin <= 0 || startMin >= totalMinutes) return null;
                              const leftPct = (startMin / totalMinutes) * 100;
                              const widthPct = ((endMin - startMin) / totalMinutes) * 100;
                              return (
                                <div
                                  key={idx}
                                  style={{
                                    position: "absolute",
                                    left: leftPct + "%",
                                    width: widthPct + "%",
                                    top: 0,
                                    bottom: 0,
                                    background: "#c62828",
                                    opacity: 0.6,
                                    borderRadius: "2px",
                                  }}
                                  title={formatTime(slot.start) + " - " + formatTime(slot.end) + " (ocupado)"}
                                />
                              );
                            })}
                            {/* Current event indicator */}
                            {(() => {
                              const dayStartMin = 8 * 60;
                              const dayEndMin = 21 * 60;
                              const totalMin = dayEndMin - dayStartMin;
                              const evStartH = parseInt(startTime.split(":")[0]);
                              const evStartM = parseInt(startTime.split(":")[1]) || 0;
                              const evEndH = parseInt(endTime.split(":")[0]);
                              const evEndM = parseInt(endTime.split(":")[1]) || 0;
                              const evStart = Math.max(0, evStartH * 60 + evStartM - dayStartMin);
                              const evEnd = Math.min(totalMin, evEndH * 60 + evEndM - dayStartMin);
                              if (evEnd <= 0 || evStart >= totalMin) return null;
                              return (
                                <div
                                  style={{
                                    position: "absolute",
                                    left: (evStart / totalMin) * 100 + "%",
                                    width: ((evEnd - evStart) / totalMin) * 100 + "%",
                                    top: 0,
                                    bottom: 0,
                                    border: "2px solid #0078d4",
                                    borderRadius: "2px",
                                    pointerEvents: "none",
                                  }}
                                />
                              );
                            })()}
                          </div>
                        </div>
                      );
                    })}

                    {/* Legend */}
                    <div style={{ display: "flex", gap: "16px", marginTop: "8px", marginLeft: "100px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "11px", color: "#605e5c" }}>
                        <div style={{ width: "12px", height: "12px", background: "#e8f5e9", borderRadius: "2px" }} />
                        Libre
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "11px", color: "#605e5c" }}>
                        <div style={{ width: "12px", height: "12px", background: "#c62828", opacity: 0.6, borderRadius: "2px" }} />
                        Ocupado
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "11px", color: "#605e5c" }}>
                        <div style={{ width: "12px", height: "12px", border: "2px solid #0078d4", borderRadius: "2px", boxSizing: "border-box" }} />
                        Este evento
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </>
            )}
          </div>

          {/* Right: Mini day view */}
          {!allDay && (
            <div className="olkm-miniday">
              <div className="olkm-miniday-header">
                <button className="olkm-miniday-nav" title="Día anterior" onClick={() => { const d = new Date(startDate + "T00:00:00"); d.setDate(d.getDate() - 1); const v = d.toISOString().split("T")[0]; setStartDate(v); setEndDate(v); }}>
                  <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M11.354 1.646a.5.5 0 010 .708L5.707 8l5.647 5.646a.5.5 0 01-.708.708l-6-6a.5.5 0 010-.708l6-6a.5.5 0 01.708 0z"/>
                  </svg>
                </button>
                <span className="olkm-miniday-title">
                  <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor" style={{ marginRight: 4 }}>
                    <path d="M4.5 0a.5.5 0 01.5.5V1h6V.5a.5.5 0 011 0V1h1.5A1.5 1.5 0 0115 2.5v11a1.5 1.5 0 01-1.5 1.5h-11A1.5 1.5 0 011 13.5v-11A1.5 1.5 0 012.5 1H4V.5a.5.5 0 01.5-.5zM2 5v8.5a.5.5 0 00.5.5h11a.5.5 0 00.5-.5V5H2z"/>
                  </svg>
                  {miniDayDateDisplay}
                </span>
                <button className="olkm-miniday-nav" title="Día siguiente" onClick={() => { const d = new Date(startDate + "T00:00:00"); d.setDate(d.getDate() + 1); const v = d.toISOString().split("T")[0]; setStartDate(v); setEndDate(v); }}>
                  <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M4.646 1.646a.5.5 0 01.708 0l6 6a.5.5 0 010 .708l-6 6a.5.5 0 01-.708-.708L10.293 8 4.646 2.354a.5.5 0 010-.708z"/>
                  </svg>
                </button>
              </div>
              <div className="olkm-miniday-grid">
                {miniDayHours.map((h) => {
                  const startH = parseInt(startTime.split(":")[0]);
                  const startM = parseInt(startTime.split(":")[1]) || 0;
                  const endH = parseInt(endTime.split(":")[0]);
                  const endM = parseInt(endTime.split(":")[1]) || 0;
                  const isInEvent = h >= startH && h < endH;
                  const isStartHour = h === startH;
                  const isPartialEnd = h === endH && endM > 0;
                  return (
                    <div key={h} className="olkm-miniday-row">
                      <span className="olkm-miniday-hour">{h}</span>
                      <div className="olkm-miniday-cell">
                        {isInEvent && (
                          <div
                            className="olkm-miniday-event"
                            style={{
                              backgroundColor: calColor,
                              top: isStartHour ? `${(startM / 60) * 100}%` : "0",
                              height: isStartHour
                                ? h === endH - 1
                                  ? `${((endM > 0 ? endM : 60) - startM) / 60 * 100}%`
                                  : `${((60 - startM) / 60) * 100}%`
                                : h === endH - 1 && endM > 0
                                  ? `${(endM / 60) * 100}%`
                                  : "100%",
                            }}
                          >
                            {isStartHour && (
                              <span className="olkm-miniday-event-label">
                                {startTime} - {endTime}
                              </span>
                            )}
                          </div>
                        )}
                        {isPartialEnd && !isInEvent && (
                          <div
                            className="olkm-miniday-event"
                            style={{
                              backgroundColor: calColor,
                              top: "0",
                              height: `${(endM / 60) * 100}%`,
                            }}
                          />
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Attachments preview */}
        {attachments.length > 0 && (
          <div style={{ padding: "8px 24px", borderTop: "1px solid #edebe9", background: "#faf9f8", maxHeight: 120, overflowY: "auto" }}>
            <div style={{ fontSize: 11, color: "#605e5c", marginBottom: 4, fontWeight: 600 }}>Adjuntos ({attachments.length})</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {attachments.map((att, idx) => (
                <div key={idx} style={{ display: "flex", alignItems: "center", gap: 6, padding: "4px 8px", background: "#fff", border: "1px solid #e1dfdd", borderRadius: 4, fontSize: 12 }}>
                  {att.preview ? (
                    <img src={att.preview} alt={att.file.name} style={{ width: 32, height: 32, objectFit: "cover", borderRadius: 3 }} />
                  ) : (
                    <svg width="20" height="20" viewBox="0 0 16 16" fill="#605e5c"><path d="M4 0a2 2 0 00-2 2v12a2 2 0 002 2h8a2 2 0 002-2V4.414A2 2 0 0013.414 3L11 .586A2 2 0 009.586 0H4zm5.586 1H10v3a1 1 0 001 1h3v9a1 1 0 01-1 1H4a1 1 0 01-1-1V2a1 1 0 011-1h5.586z"/></svg>
                  )}
                  <div style={{ maxWidth: 120, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    <div style={{ fontWeight: 500 }}>{att.file.name}</div>
                    <div style={{ fontSize: 10, color: "#a19f9d" }}>{fmtSize(att.file.size)}</div>
                  </div>
                  <button onClick={() => removeAttachment(idx)} style={{ background: "none", border: "none", cursor: "pointer", color: "#a19f9d", fontSize: 14, padding: "0 2px" }}>\u00d7</button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Bottom bar */}
        <div className="olkm-bottom">
          <div className="olkm-bottom-icons">
            <button className="olkm-bottom-btn" title="Adjuntar archivo" onClick={() => fileInputRef.current?.click()}>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                <path d="M4.5 3a2.5 2.5 0 015 0v9a1.5 1.5 0 01-3 0V5a.5.5 0 011 0v7a.5.5 0 001 0V3a1.5 1.5 0 00-3 0v9a2.5 2.5 0 005 0V5a.5.5 0 011 0v7a3.5 3.5 0 01-7 0V3z"/>
              </svg>
            </button>
            <input ref={fileInputRef} type="file" multiple className="hidden" onChange={(e) => handleFileAttach(e.target.files)} />
            <button className="olkm-bottom-btn" title="Insertar imagen" onClick={() => { const inp = document.createElement("input"); inp.type = "file"; inp.accept = "image/*"; inp.multiple = true; inp.onchange = (e) => handleFileAttach((e.target as HTMLInputElement).files); inp.click(); }}>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                <path d="M6.002 5.5a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0z"/>
                <path d="M2.002 1a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V3a2 2 0 00-2-2h-12zm12 1a1 1 0 011 1v6.5l-3.777-1.947a.5.5 0 00-.577.093l-3.71 3.71-2.66-1.772a.5.5 0 00-.63.062L1.002 12V3a1 1 0 011-1h12z"/>
              </svg>
            </button>
            <button className="olkm-bottom-btn" title="Emoji" onClick={() => { if(descRef.current) { const ta = descRef.current; const pos = ta.selectionStart; const emojis = ["😀","📅","✅","❌","⏰","📌","🔔","⭐","💼","📞"]; const emoji = emojis[Math.floor(Math.random() * emojis.length)]; setDescription(ta.value.substring(0,pos) + emoji + ta.value.substring(pos)); setTimeout(() => { ta.focus(); ta.setSelectionRange(pos+2, pos+2); }, 0); } }}>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                <path d="M8 15A7 7 0 118 1a7 7 0 010 14zm0 1A8 8 0 108 0a8 8 0 000 16z"/>
                <path d="M4.285 9.567a.5.5 0 01.683.183A3.498 3.498 0 008 11.5a3.498 3.498 0 003.032-1.75.5.5 0 11.866.5A4.498 4.498 0 018 12.5a4.498 4.498 0 01-3.898-2.25.5.5 0 01.183-.683zM7 6.5C7 7.328 6.552 8 6 8s-1-.672-1-1.5S5.448 5 6 5s1 .672 1 1.5zm4 0c0 .828-.448 1.5-1 1.5s-1-.672-1-1.5S9.448 5 10 5s1 .672 1 1.5z"/>
              </svg>
            </button>
          </div>
          <span className="olkm-shortcut-hint">Ctrl+Enter para guardar</span>
        </div>
      </div>

      <style>{`
        /* ============= ROOT & OVERLAY ============= */
        .olkm-root {
          position: fixed; inset: 0; z-index: 1000;
          display: flex; align-items: center; justify-content: center;
          font-family: 'Segoe UI Variable', 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
          font-size: 14px; color: #323130;
        }
        .olkm-dialog-expanded {
          width: 95vw !important;
          max-width: 95vw !important;
          height: 92vh !important;
          max-height: 92vh !important;
        }
        .olkm-overlay {
          position: absolute; inset: 0;
          background: rgba(0,0,0,0.4);
          animation: olkmFadeIn 120ms ease;
        }

        /* ============= PANEL ============= */
        .olkm-panel {
          position: relative;
          background: #fff;
          border-radius: 8px;
          box-shadow: 0 25.6px 57.6px rgba(0,0,0,0.22), 0 4.8px 14.4px rgba(0,0,0,0.18);
          width: 920px; max-width: calc(100vw - 32px);
          max-height: 80vh;
          display: flex; flex-direction: column;
          animation: olkmSlideUp 180ms cubic-bezier(0.1, 0.9, 0.2, 1);
          overflow: hidden;
        }

        /* ============= TITLE BAR ============= */
        .olkm-titlebar {
          display: flex; align-items: center; justify-content: space-between;
          padding: 0 8px 0 16px;
          background: #f5f5f5;
          border-bottom: 1px solid #edebe9;
          height: 36px; min-height: 36px;
          flex-shrink: 0;
        }
        .olkm-titlebar-text {
          font-size: 12px; font-weight: 600;
          color: #323130;
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .olkm-titlebar-actions { display: flex; gap: 0; }
        .olkm-titlebar-btn {
          background: none; border: none;
          width: 36px; height: 36px;
          display: flex; align-items: center; justify-content: center;
          color: #605e5c; cursor: pointer; border-radius: 0;
          transition: background 80ms;
        }
        .olkm-titlebar-btn:hover { background: #e1dfdd; }
        .olkm-close-btn:hover { background: #e81123; color: #fff; }

        /* ============= TOOLBAR ============= */
        .olkm-toolbar {
          display: flex; align-items: center;
          padding: 4px 12px;
          border-bottom: 1px solid #edebe9;
          background: #fff;
          flex-shrink: 0;
          min-height: 40px;
        }
        .olkm-toolbar-left {
          display: flex; align-items: center; gap: 2px;
          flex-wrap: wrap;
        }
        .olkm-save-btn {
          display: inline-flex; align-items: center; gap: 6px;
          background: #0078d4; color: #fff;
          border: none; border-radius: 4px;
          padding: 5px 16px; font-size: 13px; font-weight: 600;
          cursor: pointer; height: 32px;
          transition: background 80ms;
          font-family: inherit;
        }
        .olkm-save-btn:hover:not(:disabled) { background: #106ebe; }
        .olkm-save-btn:active:not(:disabled) { background: #005a9e; }
        .olkm-save-btn:disabled { opacity: 0.4; cursor: not-allowed; }
        .olkm-toolbar-sep {
          width: 1px; height: 24px; background: #edebe9; margin: 0 6px;
          flex-shrink: 0;
        }
        .olkm-tab-btn {
          display: inline-flex; align-items: center; gap: 5px;
          background: none; border: none;
          padding: 5px 10px; font-size: 13px;
          color: #323130; cursor: pointer;
          border-radius: 4px; height: 32px;
          border-bottom: 2px solid transparent;
          font-family: inherit;
          transition: background 80ms;
        }
        .olkm-tab-btn:hover { background: #f3f2f1; }
        .olkm-tab-btn.active {
          font-weight: 600;
          border-bottom-color: #0078d4;
          border-radius: 4px 4px 0 0;
        }
        .olkm-tab-btn.delete { color: #d13438; }
        .olkm-tab-btn.delete:hover { background: #fde7e9; }

        /* Status dropdown */
        .olkm-status-wrapper { position: relative; }
        .olkm-status-dropdown {
          position: absolute; top: 100%; left: 0;
          background: #fff;
          border: 1px solid #edebe9;
          border-radius: 4px;
          box-shadow: 0 8px 16px rgba(0,0,0,0.14);
          z-index: 10; min-width: 220px;
          padding: 4px 0;
          margin-top: 2px;
        }
        .olkm-status-option {
          display: flex; align-items: center; gap: 8px;
          width: 100%; border: none; background: none;
          padding: 8px 12px; font-size: 13px; color: #323130;
          cursor: pointer; text-align: left;
          font-family: inherit;
        }
        .olkm-status-option:hover { background: #f3f2f1; }
        .olkm-status-option.selected { background: #e1dfdd; font-weight: 600; }
        .olkm-status-icon { font-size: 12px; color: #605e5c; width: 16px; text-align: center; }

        /* Delete confirm */
        .olkm-delete-confirm {
          display: flex; gap: 8px; align-items: center;
        }
        .olkm-delete-question {
          font-size: 12px; color: #605e5c; white-space: nowrap;
        }
        .olkm-delete-yes {
          background: #d13438; color: #fff; border: none;
          border-radius: 4px; padding: 4px 14px; font-size: 12px;
          cursor: pointer; font-weight: 600; font-family: inherit;
          transition: background 80ms;
        }
        .olkm-delete-yes:hover { background: #a4262c; }
        .olkm-delete-cancel {
          background: none; border: 1px solid #8a8886;
          border-radius: 4px; padding: 4px 14px; font-size: 12px;
          color: #323130; cursor: pointer; font-family: inherit;
        }
        .olkm-delete-cancel:hover { background: #f3f2f1; }

        /* ============= CONTENT ============= */
        .olkm-content {
          display: flex; flex: 1;
          overflow: hidden; min-height: 0;
        }
        .olkm-form {
          flex: 3; padding: 0 20px 16px;
          overflow-y: auto;
        }

        /* ============= FIELDS ============= */
        .olkm-field {
          display: flex; align-items: flex-start; gap: 14px;
          padding: 12px 0;
          min-height: 44px;
        }
        .olkm-field-grow { flex: 1; }
        .olkm-field-icon {
          width: 20px; min-width: 20px;
          padding-top: 2px;
          color: #605e5c;
          display: flex; justify-content: center;
          flex-shrink: 0;
        }
        .olkm-separator {
          height: 1px; background: #edebe9; margin-left: 34px;
        }

        /* Title input */
        .olkm-title-input {
          flex: 1; border: none; outline: none;
          font-size: 20px; font-weight: 600;
          color: #323130; background: transparent;
          padding: 0;
          border-bottom: 2px solid transparent;
          font-family: inherit;
          transition: border-color 100ms;
        }
        .olkm-title-input:focus { border-bottom-color: #0078d4; }
        .olkm-title-input::placeholder { color: #a19f9d; font-weight: 400; }

        /* Inline input */
        .olkm-inline-input {
          flex: 1; border: none; outline: none;
          font-size: 14px; color: #323130; background: transparent;
          padding: 2px 0;
          border-bottom: 1px solid transparent;
          font-family: inherit;
          transition: border-color 100ms;
        }
        .olkm-inline-input:focus { border-bottom-color: #0078d4; }
        .olkm-inline-input::placeholder { color: #a19f9d; }

        /* Select */
        .olkm-select {
          flex: 1; border: none; outline: none;
          font-size: 14px; color: #323130; background: transparent;
          padding: 2px 0; cursor: pointer;
          font-family: inherit;
        }
        .olkm-select.small { flex: none; width: auto; }

        /* Field action button (gear on location) */
        .olkm-field-action-btn {
          background: none; border: none; cursor: pointer;
          color: #a19f9d; padding: 4px; border-radius: 4px;
          display: flex; align-items: center;
          transition: color 80ms;
        }
        .olkm-field-action-btn:hover { color: #605e5c; background: #f3f2f1; }

        /* ============= ATTENDEES ============= */
        .olkm-attendees-area {
          flex: 1; display: flex; flex-wrap: wrap; gap: 6px;
          align-items: center;
        }
        .olkm-attendee-chip {
          display: inline-flex; align-items: center; gap: 4px;
          background: #f0f0f0; border-radius: 16px;
          padding: 2px 8px 2px 2px;
          font-size: 13px; color: #323130;
        }
        .olkm-attendee-avatar {
          width: 22px; height: 22px; border-radius: 50%;
          background: #0078d4; color: #fff;
          display: flex; align-items: center; justify-content: center;
          font-size: 11px; font-weight: 600;
        }
        .olkm-attendee-remove {
          background: none; border: none; cursor: pointer;
          color: #a19f9d; font-size: 16px; padding: 0 2px;
          line-height: 1;
        }
        .olkm-attendee-remove:hover { color: #d13438; }

        /* ============= DATE/TIME ============= */
        .olkm-datetime-area { flex: 1; }
        .olkm-datetime-display {
          font-size: 14px; color: #323130; font-weight: 500;
          cursor: pointer; display: inline-flex; align-items: center;
          padding: 2px 0;
          border-bottom: 1px dashed #c8c6c4;
        }
        .olkm-datetime-display:hover { border-bottom-color: #0078d4; }
        .olkm-datetime-pickers {
          margin-top: 10px;
          display: flex; flex-direction: column; gap: 8px;
          padding: 12px;
          background: #faf9f8;
          border-radius: 4px;
          border: 1px solid #edebe9;
        }
        .olkm-picker-row {
          display: flex; align-items: center; gap: 8px;
        }
        .olkm-picker-label {
          font-size: 12px; color: #605e5c; width: 40px;
          font-weight: 600;
        }
        .olkm-date-input, .olkm-time-input {
          border: 1px solid #c8c6c4; border-radius: 4px;
          padding: 5px 10px; font-size: 13px;
          color: #323130; background: #fff;
          font-family: inherit;
          transition: border-color 100ms;
        }
        .olkm-date-input:focus, .olkm-time-input:focus {
          border-color: #0078d4; outline: none;
        }

        /* Toggle switch */
        .olkm-allday-toggle {
          display: flex; align-items: center; gap: 8px;
          margin-top: 4px; font-size: 13px; color: #605e5c;
          cursor: pointer;
        }
        .olkm-toggle-container { cursor: pointer; }
        .olkm-toggle-switch {
          width: 40px; height: 20px;
          background: #8a8886; border-radius: 10px;
          position: relative;
          transition: background 150ms;
        }
        .olkm-toggle-switch.on { background: #0078d4; }
        .olkm-toggle-thumb {
          width: 14px; height: 14px;
          background: #fff; border-radius: 50%;
          position: absolute; top: 3px; left: 3px;
          transition: transform 150ms;
          box-shadow: 0 1px 2px rgba(0,0,0,0.2);
        }
        .olkm-toggle-switch.on .olkm-toggle-thumb {
          transform: translateX(20px);
        }

        /* Virtual meeting row */
        .olkm-virtual-row {
          flex: 1; display: flex; align-items: center;
          justify-content: space-between;
        }
        .olkm-virtual-label {
          font-size: 14px; color: #323130;
        }

        /* Calendar dot */
        .olkm-cal-dot {
          width: 12px; height: 12px; border-radius: 50%;
          display: inline-block;
        }

        /* ============= REMINDERS ============= */
        .olkm-reminders { flex: 1; }
        .olkm-reminder-row {
          display: flex; align-items: center; gap: 8px;
          margin-bottom: 6px;
        }
        .olkm-reminder-remove {
          background: none; border: none; cursor: pointer;
          color: #a19f9d; font-size: 18px; padding: 0 4px;
          line-height: 1;
        }
        .olkm-reminder-remove:hover { color: #d13438; }
        .olkm-add-link {
          background: none; border: none; cursor: pointer;
          color: #0078d4; font-size: 13px; padding: 2px 0;
          font-family: inherit;
        }
        .olkm-add-link:hover { text-decoration: underline; }

        /* ============= DESCRIPTION ============= */
        .olkm-desc-wrapper { flex: 1; }
        .olkm-desc-toolbar {
          display: flex; gap: 0; margin-bottom: 4px;
          border-bottom: 1px solid #edebe9; padding-bottom: 4px;
        }
        .olkm-desc-btn {
          background: none; border: none; cursor: pointer;
          width: 32px; height: 28px; border-radius: 4px;
          color: #605e5c; font-size: 13px;
          display: flex; align-items: center; justify-content: center;
          font-family: inherit;
        }
        .olkm-desc-btn:hover { background: #f3f2f1; }
        .olkm-textarea {
          width: 100%; border: none; outline: none;
          font-size: 14px; color: #323130; background: transparent;
          padding: 8px 0; resize: vertical;
          font-family: inherit;
          line-height: 1.6;
        }
        .olkm-textarea::placeholder { color: #a19f9d; }

        /* Series tab */
        .olkm-series-label {
          display: block; font-size: 12px; font-weight: 600;
          color: #605e5c; margin-bottom: 8px;
          text-transform: uppercase; letter-spacing: 0.5px;
        }

        /* ============= MINI DAY VIEW ============= */
        .olkm-miniday {
          width: 280px; min-width: 280px;
          border-left: 1px solid #edebe9;
          flex-shrink: 0;
          display: flex; flex-direction: column;
          overflow: hidden;
          background: #faf9f8;
        }
        .olkm-miniday-header {
          display: flex; align-items: center; justify-content: space-between;
          padding: 10px 12px;
          font-size: 13px; font-weight: 600;
          color: #323130;
          border-bottom: 1px solid #edebe9;
          background: #fff;
        }
        .olkm-miniday-nav {
          background: none; border: none; cursor: pointer;
          color: #605e5c; padding: 4px;
          border-radius: 4px;
          display: flex; align-items: center;
        }
        .olkm-miniday-nav:hover { background: #e1dfdd; }
        .olkm-miniday-title {
          display: flex; align-items: center;
          font-size: 13px;
        }
        .olkm-miniday-grid {
          flex: 1; overflow-y: auto;
        }
        .olkm-miniday-row {
          display: flex; height: 44px;
          border-bottom: 1px solid #edebe9;
        }
        .olkm-miniday-hour {
          width: 44px; font-size: 12px; color: #a19f9d;
          padding: 4px 8px 0 0; text-align: right;
          flex-shrink: 0;
          font-weight: 400;
        }
        .olkm-miniday-cell {
          flex: 1; position: relative;
          border-left: 1px solid #edebe9;
          background: #fff;
        }
        .olkm-miniday-event {
          position: absolute; left: 0; right: 0;
          border-radius: 3px;
          overflow: hidden;
          margin: 0 2px;
        }
        .olkm-miniday-event-label {
          font-size: 11px; color: #fff; padding: 2px 6px;
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
          display: block; font-weight: 600;
        }

        /* ============= BOTTOM BAR ============= */
        .olkm-bottom {
          display: flex; align-items: center; justify-content: space-between;
          padding: 6px 16px;
          border-top: 1px solid #edebe9;
          background: #fff;
          flex-shrink: 0;
          min-height: 36px;
        }
        .olkm-bottom-icons { display: flex; gap: 2px; }
        .olkm-bottom-btn {
          background: none; border: none; cursor: pointer;
          padding: 6px 8px; border-radius: 4px; color: #605e5c;
          display: flex; align-items: center;
          transition: background 80ms;
        }
        .olkm-bottom-btn:hover { background: #f3f2f1; color: #323130; }
        .olkm-shortcut-hint {
          font-size: 11px; color: #a19f9d;
        }

        /* ============= RESPONSIVE ============= */
        @media (max-width: 768px) {
          .olkm-miniday { display: none; }
          .olkm-panel { width: 100%; max-width: 100%; border-radius: 0; max-height: 100vh; }
        }

        /* ============= ANIMATIONS ============= */
        @keyframes olkmFadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes olkmSlideUp {
          from { opacity: 0; transform: translateY(24px) scale(0.98); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }

        /* ============= DARK MODE ============= */
        @media (prefers-color-scheme: dark) {
          .olkm-root { color: #d2d0ce; }
          .olkm-panel { background: #292827; }
          .olkm-titlebar { background: #1b1a19; border-color: #484644; }
          .olkm-titlebar-text { color: #d2d0ce; }
          .olkm-titlebar-btn { color: #a19f9d; }
          .olkm-titlebar-btn:hover { background: #3b3a39; }
          .olkm-close-btn:hover { background: #e81123; color: #fff; }
          .olkm-toolbar { background: #292827; border-color: #484644; }
          .olkm-toolbar-sep { background: #484644; }
          .olkm-tab-btn { color: #d2d0ce; }
          .olkm-tab-btn:hover { background: #3b3a39; }
          .olkm-tab-btn.active { background: transparent; }
          .olkm-tab-btn.delete { color: #f1707b; }
          .olkm-tab-btn.delete:hover { background: #442726; }
          .olkm-field-icon { color: #a19f9d; }
          .olkm-separator { background: #3b3a39; }
          .olkm-title-input { color: #f3f2f1; }
          .olkm-title-input::placeholder { color: #605e5c; }
          .olkm-inline-input { color: #d2d0ce; }
          .olkm-inline-input::placeholder { color: #605e5c; }
          .olkm-select { color: #d2d0ce; }
          .olkm-attendee-chip { background: #3b3a39; color: #d2d0ce; }
          .olkm-datetime-display { color: #d2d0ce; border-bottom-color: #605e5c; }
          .olkm-datetime-pickers { background: #1b1a19; border-color: #484644; }
          .olkm-picker-label { color: #a19f9d; }
          .olkm-date-input, .olkm-time-input { background: #292827; color: #d2d0ce; border-color: #484644; }
          .olkm-virtual-label { color: #d2d0ce; }
          .olkm-textarea { color: #d2d0ce; }
          .olkm-textarea::placeholder { color: #605e5c; }
          .olkm-desc-toolbar { border-color: #3b3a39; }
          .olkm-desc-btn { color: #a19f9d; }
          .olkm-desc-btn:hover { background: #3b3a39; }
          .olkm-series-label { color: #a19f9d; }
          .olkm-miniday { background: #1b1a19; border-color: #484644; }
          .olkm-miniday-header { background: #292827; border-color: #484644; color: #d2d0ce; }
          .olkm-miniday-nav { color: #a19f9d; }
          .olkm-miniday-nav:hover { background: #3b3a39; }
          .olkm-miniday-row { border-color: #3b3a39; }
          .olkm-miniday-cell { border-color: #3b3a39; background: #292827; }
          .olkm-bottom { background: #292827; border-color: #484644; }
          .olkm-bottom-btn { color: #a19f9d; }
          .olkm-bottom-btn:hover { background: #3b3a39; color: #d2d0ce; }
          .olkm-status-dropdown { background: #292827; border-color: #484644; }
          .olkm-status-option { color: #d2d0ce; }
          .olkm-status-option:hover { background: #3b3a39; }
          .olkm-status-option.selected { background: #484644; }
          .olkm-delete-question { color: #a19f9d; }
          .olkm-delete-cancel { color: #d2d0ce; border-color: #605e5c; }
          .olkm-delete-cancel:hover { background: #3b3a39; }
          .olkm-allday-toggle { color: #a19f9d; }
          .olkm-field-action-btn { color: #605e5c; }
          .olkm-field-action-btn:hover { color: #a19f9d; background: #3b3a39; }
        }
      `}</style>
    </div>
  );
}
