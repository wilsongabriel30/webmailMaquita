export type ViewMode = "month" | "week" | "workweek" | "day" | "agenda";

export interface CalendarInfo {
  id: string;
  name: string;
  color: string;
  timezone: string;
  is_default: boolean;
}

export interface CalendarEvent {
  id: string;
  calendar_id: string;
  uid: string;
  summary: string;
  description?: string;
  location?: string;
  dtstart: string;
  dtend: string;
  all_day: boolean;
  rrule?: string;
  status: string;
  color?: string;
  calendar_name: string;
  timezone: string;
  reminders?: EventReminder[];
  attendees?: EventAttendee[];
}

export interface EventReminder {
  type: string;
  minutes: number;
}

export interface EventAttendee {
  email: string;
  name?: string;
  status?: string;
  role?: string;
}

export interface EventFormData {
  calendar_id: string;
  summary: string;
  description: string;
  location: string;
  dtstart: string;
  dtend: string;
  all_day: boolean;
  rrule: string;
  timezone: string;
  reminders: EventReminder[];
  attendees: string[];
  optional_attendees: string[];
  /** Solo UI: archivos a subir tras crear/editar el evento */
  _attachments?: File[];
  /** Solo UI: generar enlace de reunión virtual (Jitsi) al guardar */
  _virtualMeeting?: boolean;
}

export interface FreeBusySlot {
  start: string;
  end: string;
}

export interface FreeBusyResponse {
  user: string;
  slots: FreeBusySlot[];
}
