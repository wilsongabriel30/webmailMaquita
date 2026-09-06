export interface Folder {
  name: string;
  delimiter: string;
  flags: string[];
  type: 'inbox' | 'sent' | 'drafts' | 'trash' | 'junk' | 'archive' | 'folder';
  unseen: number;
}

export interface MessageSummary {
  uid: number;
  folder: string;
  message_id: string | null;
  thread_id: string;
  from: string;
  to: string;
  subject: string;
  date: string | null;
  size: number;
  flags: string[];
  seen: boolean;
  flagged: boolean;
  snippet: string;
  has_attachments: boolean;
  importance: 'normal' | 'high' | 'low';
}

export interface AttachmentInfo {
  filename: string;
  content_type: string;
  size: number;
  part_number: string;
  is_inline: boolean;
}

/** Invitación de calendario que el backend detecta dentro de un correo. */
export interface CalendarInvite {
  summary?: string;
  organizer?: string;
  location?: string;
  starts_at?: string;
  ends_at?: string;
  attendees?: { name?: string; email?: string; status?: string; role?: string }[];
  description?: string;
  method?: string;
  /**
   * El backend envía la invitación tal como viene del calendario del remitente,
   * con campos que varían según quién la genere (dtstart, organizer_name, y los
   * que traiga cada cliente). Se declaran arriba los que esta vista usa siempre
   * y se deja el resto abierto: enumerarlos todos sería perseguir un contrato
   * que no controlamos.
   */
  [clave: string]: unknown;
}

export interface MessageFull extends MessageSummary {
  cc: string;
  text_body: string;
  html_body: string;
  attachments: AttachmentInfo[];
  has_remote_images: boolean;
  /** Dirección del remitente cuando el backend la separa del nombre visible. */
  from_addr?: string;
  /** Invitación de calendario, si el correo la lleva. */
  calendar_invite?: CalendarInvite;
  blocked_image_count: number;
  /** Enlaces desenvueltos por el backend (rastreadores retirados). */
  unwrapped_link_count?: number;
  /** Aviso de rastreadores que NO se pudieron retirar. Ver TrackingNotice.tsx */
  tracking_notice?: {
    hay_rastreo: boolean;
    es_publicidad: boolean;
    servicios: string[];
    mensaje: string;
  } | null;
  references: string;
  in_reply_to: string;
}

export interface UserInfo {
  username: string;
  is_admin: boolean;
}

export interface MessagesResponse {
  messages: MessageSummary[];
  total: number;
  page: number;
  per_page: number;
}

export interface ComposeData {
  to: string[];
  cc?: string[];
  bcc?: string[];
  subject: string;
  text_body: string;
  html_body: string;
  in_reply_to?: string;
  references?: string;
  draft_uid?: number | null;
  // Archivos del Almacén a adjuntar al abrir el redactor (accion "Enviar por correo")
  adjuntos_almacen?: { nombre: string; ruta: string }[];
  /** Cuerpo sugerido por el asistente de respuesta rápida. */
  prefill_body?: string;
}
