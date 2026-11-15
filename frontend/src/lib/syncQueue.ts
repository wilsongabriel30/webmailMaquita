// Cola PERSISTENTE de envío (IndexedDB, sobrevive cierres de la app) y sincronización de acciones offline.
// Reglas (T-35, 28/08/2026): un correo redactado NUNCA se pierde. Sin red o con el servidor caído se queda
// «pendiente» y se reintenta al reconectar, al abrir la app y cada 60 s; solo un rechazo definitivo del servidor
// (4xx distinto de 401/408/429) lo marca «No se pudo entregar» (con la causa), y la persona puede reintentar o borrar.
import { enviarUnaVez, renovarIdentificador } from './envioUnico';
import { getPendingActions, removeActions, getOutboxEmails, updateOutboxStatus, removeFromOutbox, rescatarRetenidos } from "./offlineStore";
import type { OfflineAction } from "./offlineStore";
import { esDeLaSesion } from "./sesionActual";

let isSyncing = false;

const ACTION_MAP: Record<OfflineAction["type"], string> = {
  markRead: "mark_read", markUnread: "mark_unread", flag: "flag", unflag: "unflag", delete: "delete", move: "move",
};

/** Causa legible de por qué no se puede enviar ahora (lo que pide soporte). */
import { textoCausa, estadoConexion } from './conexion';
export function causaSinConexion(): string {
  return textoCausa();
}
export function hayConexion(): boolean {
  return estadoConexion().hayConexion;
}
export const TEXTO_ESTADO = {
  // Solo dura los segundos de «Deshacer»; no debería llegar a verse.
  retenido: 'A punto de enviarse',
  pending: 'En cola: se enviará al volver la conexión',
  sending: 'Enviando…',
  failed: 'No se pudo entregar',
} as const;

export async function syncOfflineActions() {
  const actions = await getPendingActions();
  if (actions.length === 0) return;
  const groups = new Map<string, OfflineAction[]>();
  for (const action of actions) {
    const dest = (action.data?.folder as string | undefined) || "";
    const key = `${action.cuenta || ''}|${action.folder}|${action.type}|${dest}`;
    const list = groups.get(key) || [];
    list.push(action);
    groups.set(key, list);
  }
  for (const [, group] of groups) {
    const first = group[0];
    const dest = (first.data?.folder as string | undefined) || "";
    try {
      const res = await fetch(`/api/mail/bulk-action/${encodeURIComponent(first.folder)}`, {
        // Multicuenta: la acción se aplica en el buzón donde se hizo, no en el abierto ahora.
        method: "POST", headers: { "Content-Type": "application/json", "X-Cuenta-Activa": first.cuenta || "propia" }, credentials: "include",
        body: JSON.stringify({ uids: group.map((a) => a.uid), action: ACTION_MAP[first.type] || first.type, dest_folder: dest || undefined }),
      });
      if (res.ok) await removeActions(group.map((a) => a.id));
      else console.error("[Offline] Sync group failed:", res.status, first.folder, first.type);
    } catch (e) {
      console.error("[Offline] Failed to sync group:", first.folder, first.type, e);
    }
  }
}

export async function syncOutbox(soloId?: string): Promise<{ sent: number; failed: number }> {
  if (isSyncing) return { sent: 0, failed: 0 };
  isSyncing = true;
  let sent = 0, failed = 0;
  try {
    if (!navigator.onLine) return { sent, failed };
    // Un correo que se quedó retenido (la pestaña se cerró durante la cuenta atrás de
    // «Deshacer») pasa aquí a pendiente: se envía en cuanto se vuelve a abrir el correo, en
    // vez de perderse en silencio.
    await rescatarRetenidos();
    const emails = await getOutboxEmails();
    // T-73: solo lo escrito con esta misma sesión; lo de otra persona espera a que ella vuelva.
    const pending = emails.filter(e => esDeLaSesion(e) && (soloId ? e.id === soloId : e.status === 'pending' || e.status === 'sending'));
    for (const email of pending) {
      await updateOutboxStatus(email.id, 'sending');
      window.dispatchEvent(new CustomEvent('outbox-cambio'));
      try {
        // Por la ruta que no repite (ver envioUnico.ts): si el servidor ya lo tenía, no sale dos veces.
        const fin = await enviarUnaVez(email.id, email.cuenta || 'propia', {
          to: email.to, cc: email.cc, bcc: email.bcc, subject: email.subject, html_body: email.html_body, text_body: email.text_body,
          in_reply_to: email.in_reply_to || '', references: email.references || '', attachments: email.attachments || [],
          request_read_receipt: email.request_read_receipt || false, request_delivery_receipt: email.request_delivery_receipt || false,
          importance: email.importance || 'normal',
          // Como el envío directo: sin `draft_uid` el correo salía y su borrador se quedaba en Borradores.
          from_email: email.from_email || undefined, sensitivity: email.sensitivity || undefined,
          draft_uid: email.draft_uid ?? null, dlp_override: email.dlp_override || false, dlp_reason: email.dlp_reason || undefined,
        });
        if (fin.tipo === 'enviado') {
          await removeFromOutbox(email.id); sent++;
        } else if (fin.tipo === 'rechazado') {
          await updateOutboxStatus(email.id, 'failed', fin.mensaje); failed++;
        } else {
          await updateOutboxStatus(email.id, 'pending', fin.mensaje);
        }
      } catch {
        await updateOutboxStatus(email.id, 'pending', causaSinConexion());
      }
      window.dispatchEvent(new CustomEvent('outbox-cambio'));
    }
  } finally {
    isSyncing = false;
  }
  return { sent, failed };
}

/** Reintentar a mano un correo marcado «No se pudo entregar». */
export async function reintentarEnvio(id: string) {
  renovarIdentificador(id);   // lo pidió la persona: es un intento nuevo de verdad
  await updateOutboxStatus(id, 'pending');
  return syncOutbox(id);
}

export async function syncAll(): Promise<{ actions: number; sent: number; failed: number }> {
  const actions = await getPendingActions();
  await syncOfflineActions();
  const { sent, failed } = await syncOutbox();
  if (sent > 0 || actions.length > 0) {
    window.dispatchEvent(new CustomEvent('offline-sync-complete', { detail: { actions: actions.length, sent, failed } }));
    window.dispatchEvent(new CustomEvent('refresh-messages'));
  }
  return { actions: actions.length, sent, failed };
}

if (typeof window !== "undefined") {
  window.addEventListener("online", () => setTimeout(() => { syncAll(); }, 2000));
  // Al abrir la app (la cola vive en IndexedDB) y luego cada 60 s mientras haya algo pendiente
  setTimeout(() => { syncAll(); }, 5000);
  setInterval(async () => {
    if (!navigator.onLine) return;
    const pend = (await getOutboxEmails()).some(e => esDeLaSesion(e) && (e.status === 'pending' || e.status === 'sending'));
    const acc = (await getPendingActions()).length > 0;
    if (pend || acc) syncAll();
  }, 60000);
}
