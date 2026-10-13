import { useEffect, useRef } from 'react';
import { useMailStore } from '../../store/mailStore';
import { showToast } from '../common/Toast';
import { tomarRedaccionesGuardadas, volcarRedacciones, type RedaccionGuardada } from '../../lib/redaccionesRecuperables';
import type { AttachmentInfo } from '../../types';

/**
 * Al cargar el webmail, vuelve a abrir los correos que estaban a medio escribir en esta pestaña
 * antes de una recarga (13/10/2026). Se abren como «Editar borrador»: el texto, los destinatarios
 * y el asunto salen de la copia de la pestaña (lo más reciente) y los adjuntos del borrador del
 * servidor. Antes de salir de la página se anota lo que hay en pantalla.
 */

const lista = (s: string) => s.split(',').map(x => x.trim()).filter(Boolean);

async function adjuntosDelBorrador(uid: number): Promise<AttachmentInfo[] | null> {
  try {
    const res = await fetch(`/api/mail/message/Drafts/${uid}?marcar_leido=false`, { credentials: 'include' });
    if (!res.ok) return null;
    return ((await res.json()) as { attachments?: AttachmentInfo[] }).attachments || [];
  } catch {
    return null;
  }
}

async function reabrir(r: RedaccionGuardada): Promise<void> {
  // Si el borrador del servidor ya no está (se envió o se borró desde otro equipo), se reabre
  // igual con el texto, como borrador nuevo: mejor de más que perder lo escrito.
  const adjuntos = r.draftUid ? await adjuntosDelBorrador(r.draftUid) : [];
  useMailStore.getState().openCompose('new', {
    to: lista(r.to),
    cc: lista(r.cc),
    bcc: lista(r.bcc),
    subject: r.subject,
    text_body: '',
    html_body: r.html || '<p></p>',
    in_reply_to: r.inReplyTo,
    references: r.references,
    draft_uid: adjuntos === null ? null : r.draftUid,
    adjuntos_borrador: adjuntos || [],
  });
}

export default function RecuperarRedacciones() {
  const hecho = useRef(false);

  useEffect(() => {
    const alSalir = () => volcarRedacciones();
    window.addEventListener('pagehide', alSalir);
    window.addEventListener('beforeunload', alSalir);
    return () => {
      window.removeEventListener('pagehide', alSalir);
      window.removeEventListener('beforeunload', alSalir);
    };
  }, []);

  useEffect(() => {
    if (hecho.current) return;
    hecho.current = true;
    const pendientes = tomarRedaccionesGuardadas();
    if (!pendientes.length) return;
    (async () => {
      for (const r of pendientes) await reabrir(r);
      showToast(pendientes.length === 1
        ? 'Se recuperó el correo que estabas escribiendo.'
        : `Se recuperaron los ${pendientes.length} correos que estabas escribiendo.`);
    })();
  }, []);

  return null;
}
