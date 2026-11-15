import { useEffect } from 'react';
import { useMailStore } from '../../store/mailStore';
import { showToast } from '../common/Toast';
import {
  anotarRedaccion, latirReserva, pestanasVivas, sostenerSenalDeVida, tomarRedaccionesGuardadas, tomarRedaccionesHuerfanas,
  volcarRedacciones, type RedaccionGuardada,
} from '../../lib/redaccionesRecuperables';
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

// Una sola vez por carga de la página (15/11/2026). Este componente vive dentro de la bandeja y
// se vuelve a montar cada vez que la persona regresa de Calendario, Contactos o Configuración:
// con la marca dentro del componente, cada regreso «recuperaba» los correos que seguían abiertos
// y los duplicaba (1, 2, 4, 7 ventanas iguales, con parpadeo y borradores repetidos).
let recuperadoEnEstaCarga = false;
let latidoEnMarcha = false;

async function reabrir(r: RedaccionGuardada, alFondo = false): Promise<void> {
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
  }, { alFondo });
  // Una ventana que nace minimizada no llega a montarse: se anota ya, para que una recarga no la pierda.
  const ventanas = useMailStore.getState().composeWindows;
  const nueva = ventanas[ventanas.length - 1];
  if (nueva?.minimized) anotarRedaccion({ ...r, id: nueva.id, draftUid: nueva.draftUid });
}

export default function RecuperarRedacciones() {
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
    sostenerSenalDeVida();
    // El latido no se detiene al salir de la bandeja: con un correo minimizado y la persona en el
    // Calendario, la copia de reserva dejaba de latir y otra pestaña podía llevársela.
    if (!latidoEnMarcha) { latidoEnMarcha = true; setInterval(latirReserva, 30_000); }
    if (recuperadoEnEstaCarga) return;
    recuperadoEnEstaCarga = true;
    const avisar = (n: number) => showToast(n === 1
      ? 'Se recuperó el correo que estaba escribiendo.'
      : `Se recuperaron los ${n} correos que estaba escribiendo.`);
    const abiertas: Array<number | null> = [];
    const recuperar = async (lista: RedaccionGuardada[], alFondo = false) => {
      if (!lista.length) return;
      for (const r of lista) { abiertas.push(r.draftUid); await reabrir(r, alFondo); }
      avisar(lista.length);
    };
    // Lo que quedó sin pestaña se abre minimizado si la persona ya está escribiendo otro correo:
    // no se le quita de delante lo que tiene en pantalla.
    const recogerHuerfanas = async () => {
      const vivas = await pestanasVivas();
      await recuperar(tomarRedaccionesHuerfanas(abiertas, vivas), true);
    };
    // Lo de esta pestaña (recarga) y lo que quedó sin pestaña: sesión vencida y reingreso desde
    // otra ventana, pestaña cerrada o ventana nueva de la aplicación de escritorio.
    const propias = tomarRedaccionesGuardadas();
    void recuperar(propias).then(recogerHuerfanas);
    // Segunda pasada: quien vuelve a entrar muy rápido llega antes de que la copia quede libre.
    // No se cancela al salir de la bandeja: es de la carga de la página, no de esta vista.
    setTimeout(() => { void recogerHuerfanas(); }, 25_000);
  }, []);

  return null;
}
