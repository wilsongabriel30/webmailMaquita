import { useState, useCallback, useMemo, useRef } from "react";
import { api } from "../../../api/client";
import type { CalendarInfo, CalendarEvent, EventFormData, FreeBusyResponse } from "../types/calendar";

interface EventsResponse {
  events: CalendarEvent[];
}

interface CalendarsResponse {
  calendars: CalendarInfo[];
}

export function useCalendarApi() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestIdRef = useRef(0);

  const withLoading = useCallback(async <T>(fn: () => Promise<T>): Promise<T | null> => {
    const currentRequestId = ++requestIdRef.current;
    setLoading(true);
    setError(null);
    try {
      const result = await fn();
      if (requestIdRef.current !== currentRequestId) {
        return null;
      }
      return result;
    } catch (err) {
      if (requestIdRef.current !== currentRequestId) {
        return null;
      }
      const msg = err instanceof Error ? err.message : "Error desconocido";
      setError(msg);
      return null;
    } finally {
      if (requestIdRef.current === currentRequestId) {
        setLoading(false);
      }
    }
  }, []);

  // Wrapper sin loading spinner para consultas secundarias
  const withoutLoading = useCallback(async <T>(fn: () => Promise<T>): Promise<T | null> => {
    try {
      return await fn();
    } catch (err) {
      console.error("[CalendarApi]", err);
      return null;
    }
  }, []);

  const fetchCalendars = useCallback(() =>
    withLoading(async () => {
      const res = await api.get<CalendarsResponse>("/calendar/calendars");
      return res.calendars;
    }),
  [withLoading]);

  const createCalendar = useCallback((data: { name: string; color: string; timezone?: string }) =>
    withLoading(() => api.post<CalendarInfo>("/calendar/calendars", data)),
  [withLoading]);

  const updateCalendar = useCallback((id: string, data: { name?: string; color?: string }) =>
    withLoading(() => api.patch<CalendarInfo>("/calendar/calendars/" + id, data)),
  [withLoading]);

  const deleteCalendar = useCallback((id: string) =>
    withLoading(() => api.del<{ ok: boolean }>("/calendar/calendars/" + id)),
  [withLoading]);

  const fetchEvents = useCallback((start: string, end: string, calendarId?: string) =>
    withLoading(async () => {
      let url = "/calendar/events?start=" + encodeURIComponent(start) + "&end=" + encodeURIComponent(end);
      if (calendarId) url += "&calendar_id=" + encodeURIComponent(calendarId);
      const res = await api.get<EventsResponse>(url);
      return res.events;
    }),
  [withLoading]);

  const createEvent = useCallback((data: EventFormData) =>
    withLoading(() => api.post<CalendarEvent>("/calendar/events", data)),
  [withLoading]);

  const updateEvent = useCallback((id: string, data: EventFormData) =>
    withLoading(() => api.put<CalendarEvent>("/calendar/events/" + id, data)),
  [withLoading]);

  const moveEvent = useCallback((id: string, dtstart: string, dtend: string) =>
    withLoading(() => api.patch<CalendarEvent>("/calendar/events/" + id + "/move", { dtstart, dtend })),
  [withLoading]);

  const deleteEvent = useCallback((id: string) =>
    withLoading(() => api.del<{ ok: boolean }>("/calendar/events/" + id)),
  [withLoading]);

  // ── Free/Busy ─────────────────────────────────────────
  const fetchFreeBusy = useCallback((userEmail: string, start: string, end: string) =>
    withoutLoading(async () => {
      const url = "/calendar/freebusy?user=" + encodeURIComponent(userEmail)
        + "&start=" + encodeURIComponent(start)
        + "&end=" + encodeURIComponent(end);
      return api.get<FreeBusyResponse>(url);
    }),
  [withoutLoading]);

  // ── Calendar Sharing ──────────────────────────────────
  const shareCalendar = useCallback((calendarId: string, sharedWith: string, permission: string) =>
    withLoading(() => api.post<object>("/calendar/calendars/" + calendarId + "/share", { shared_with: sharedWith, permission })),
  [withLoading]);

  const listCalendarShares = useCallback((calendarId: string) =>
    withLoading(() => api.get<object[]>("/calendar/calendars/" + calendarId + "/shares")),
  [withLoading]);

  const revokeCalendarShare = useCallback((calendarId: string, sharedWith: string) =>
    withLoading(() => api.del<object>("/calendar/calendars/" + calendarId + "/share/" + encodeURIComponent(sharedWith))),
  [withLoading]);

  const listSharedWithMe = useCallback(() =>
    withLoading(() => api.get<object[]>("/calendar/shared")),
  [withLoading]);

  const listSharedEvents = useCallback((start: string, end: string) =>
    withLoading(async () => {
      const url = "/calendar/shared/events?start=" + encodeURIComponent(start) + "&end=" + encodeURIComponent(end);
      return api.get<object[]>(url);
    }),
  [withLoading]);

  // ── Invitaciones ──────────────────────────────────────
  const sendEventInvitations = useCallback((eventId: string) =>
    withLoading(() => api.post<{ sent: number }>("/calendar/events/" + eventId + "/invite", {})),
  [withLoading]);

  const respondEventInvitation = useCallback((eventId: string, status: "accepted" | "declined" | "tentative") =>
    withLoading(() => api.post<object>("/calendar/events/" + eventId + "/respond", { status })),
  [withLoading]);

  return useMemo(() => ({
    loading,
    error,
    fetchCalendars,
    createCalendar,
    updateCalendar,
    deleteCalendar,
    fetchEvents,
    createEvent,
    updateEvent,
    moveEvent,
    deleteEvent,
    fetchFreeBusy,
    shareCalendar,
    listCalendarShares,
    revokeCalendarShare,
    listSharedWithMe,
    listSharedEvents,
    sendEventInvitations,
    respondEventInvitation,
  }), [loading, error, fetchCalendars, createCalendar, updateCalendar, deleteCalendar, fetchEvents, createEvent, updateEvent, moveEvent, deleteEvent, fetchFreeBusy, shareCalendar, listCalendarShares, revokeCalendarShare, listSharedWithMe, listSharedEvents, sendEventInvitations, respondEventInvitation]);
}
