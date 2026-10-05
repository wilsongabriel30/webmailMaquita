/**
 * Adelanto de resultados mientras termina la búsqueda en todas las carpetas.
 *
 * Buscar en el buzón virtual (todas las carpetas) tarda uno o varios segundos en buzones con
 * cientos de carpetas; buscar en una sola carpeta es inmediato. Mientras llega la búsqueda
 * completa se muestran ya las coincidencias de la carpeta en la que estaba la persona, que es
 * donde suele estar lo que busca. Al llegar los resultados completos, la lista los sustituye.
 */
import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { useMailStore } from '../../store/mailStore';
import { getFolderDisplayName } from '../../folders';
import { carpetaAnterior } from '../../lib/busquedaGlobal';
import type { MessagesResponse, MessageSummary, MessageFull } from '../../types';

const MAXIMO = 15;

interface Props { consulta: string; }

function fechaCorta(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const hoy = new Date();
  return d.toDateString() === hoy.toDateString()
    ? d.toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString('es', { day: '2-digit', month: 'short', year: d.getFullYear() === hoy.getFullYear() ? undefined : 'numeric' });
}

function soloNombre(remitente: string): string {
  return remitente.replace(/<[^>]*>/g, '').replace(/"/g, '').trim() || remitente;
}

/** Pasa a la carpeta del adelanto con la misma búsqueda y abre el mensaje elegido. */
function abrir(carpeta: string, consulta: string, uid: number) {
  useMailStore.getState().setCarpetaYBusqueda(carpeta, consulta);
  api.get<MessageFull>(`/mail/message/${encodeURIComponent(carpeta)}/${uid}`)
    .then(msg => {
      const st = useMailStore.getState();
      if (msg && msg.uid && st.currentFolder === carpeta) st.setSelectedMessage(msg);
    })
    .catch(() => { /* la lista de la carpeta ya está a la vista; se abre desde ahí */ });
}

export function AdelantoCarpetaActual({ consulta }: Props) {
  const carpeta = carpetaAnterior();
  const [resultado, setResultado] = useState<{ clave: string; mensajes: MessageSummary[]; total: number } | null>(null);
  const clave = `${carpeta}\n${consulta}`;

  useEffect(() => {
    let vigente = true;
    const p = new URLSearchParams({ page: '1', per_page: String(MAXIMO), search: consulta });
    api.get<MessagesResponse>(`/mail/messages/${encodeURIComponent(carpeta)}?${p}`)
      .then(r => { if (vigente) setResultado({ clave, mensajes: r.messages, total: r.total }); })
      .catch(() => { /* sin adelanto: la búsqueda completa sigue su curso */ });
    return () => { vigente = false; };
  }, [carpeta, consulta, clave]);

  if (!resultado || resultado.clave !== clave || resultado.mensajes.length === 0) return null;
  const nombre = getFolderDisplayName(carpeta);
  return (
    <div className="border-t border-[#edebe9] text-left" data-testid="adelanto-carpeta">
      <p className="px-4 py-2 text-[12px] text-[#605e5c] bg-[#faf9f8]">
        Mientras tanto, en <span className="font-semibold text-[#323130]">{nombre}</span>
        {resultado.total > resultado.mensajes.length ? ` (${resultado.mensajes.length} de ${resultado.total})` : ''}:
      </p>
      {resultado.mensajes.map(m => (
        <button key={m.uid} type="button" onClick={() => abrir(carpeta, consulta, m.uid)}
          className="w-full text-left px-4 py-[6px] border-b border-[#f3f2f1] hover:bg-[#f3f2f1] focus:bg-[#f3f2f1] outline-none">
          <span className="flex items-baseline gap-2">
            <span className={`flex-1 truncate text-[13px] ${m.seen ? 'text-[#323130]' : 'font-semibold text-[#201f1e]'}`}>{soloNombre(m.from)}</span>
            <span className="text-[11px] text-[#605e5c] shrink-0">{fechaCorta(m.date)}</span>
          </span>
          <span className={`block truncate text-[12px] ${m.seen ? 'text-[#605e5c]' : 'text-[#0078d4] font-semibold'}`}>{m.subject || '(sin asunto)'}</span>
        </button>
      ))}
    </div>
  );
}
