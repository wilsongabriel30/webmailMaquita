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

export interface MessageFull extends MessageSummary {
  cc: string;
  text_body: string;
  html_body: string;
  attachments: AttachmentInfo[];
  has_remote_images: boolean;
  blocked_image_count: number;
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
}
