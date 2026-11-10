/**
 * Selector «Correo como adjunto» (09/11/2026).
 *
 * Reclamo: al responder un correo no había forma de adjuntarle otro correo (antiguo o de otra
 * persona); solo se podía arrastrar desde la lista. Este cuadro lista los correos recientes de una
 * carpeta (la actual por defecto), permite buscar por asunto o remitente (el servidor busca con el
 * parámetro `search` de /api/mail/messages/{carpeta}), marcar uno o varios y adjuntarlos. Entran
 * al redactor como .eml por lib/correosComoAdjunto.ts, igual que al arrastrar.
 */
import { useEffect, useMemo, useState } from 'react';
import { api } from '../../api/client';
import { useMailStore } from '../../store/mailStore';
import type { MessageSummary, MessagesResponse } from '../../types';
import type { CorreoAAdjuntar } from '../../lib/correosComoAdjunto';
import { nombreRemitente } from '../../lib/textoAvisoCorreo';
import { fechaCortaLista } from '../../lib/fechaLegible';

interface Props {
  onCerrar: () => void;
  onElegir: (correos: CorreoAAdjuntar[]) => void;
}

const POR_PAGINA = 30;
const NOMBRES: Record<string, string> = {
  INBOX: 'Bandeja de entrada', Sent: 'Enviados', Drafts: 'Borradores', Trash: 'Papelera', Junk: 'Correo no deseado', Archive: 'Archivo',
};

function nombreCarpeta(nombre: string): string {
  if (NOMBRES[nombre]) return NOMBRES[nombre];
  const partes = nombre.split(/[./]/);
  return partes[partes.length - 1] || nombre;
}

function fecha(m: MessageSummary): string {
  const d = new Date(m.received_date || m.date || '');
  return isNaN(d.getTime()) ? '' : fechaCortaLista(d);
}

export function SelectorCorreoAdjunto({ onCerrar, onElegir }: Props) {
  const carpetas = useMailStore(s => s.folders);
  const carpetaActual = useMailStore(s => s.currentFolder);
  const [carpeta, setCarpeta] = useState(carpetaActual || 'INBOX');
  const [texto, setTexto] = useState('');
  const [busqueda, setBusqueda] = useState('');
  const [pagina, setPagina] = useState(1);
  // Lo que respondió el servidor y para qué consulta (carpeta, búsqueda, página): si la clave no
  // coincide con la consulta actual, es que todavía se está cargando.
  const [datos, setDatos] = useState<{ clave: string; correos: MessageSummary[]; total: number; error: boolean } | null>(null);
  const [sel, setSel] = useState<Map<string, MessageSummary>>(new Map());

  // La búsqueda espera medio segundo a que la persona termine de escribir.
  useEffect(() => {
    const t = setTimeout(() => { setBusqueda(texto.trim()); setPagina(1); }, 500);
    return () => clearTimeout(t);
  }, [texto]);

  const clave = `${carpeta}|${busqueda}|${pagina}`;
  useEffect(() => {
    let vigente = true;
    const p = new URLSearchParams({ page: String(pagina), per_page: String(POR_PAGINA) });
    if (busqueda) p.set('search', busqueda);
    api.get<MessagesResponse>(`/mail/messages/${encodeURIComponent(carpeta)}?${p}`)
      .then(r => {
        if (!vigente) return;
        setDatos(prev => {
          const previos = pagina > 1 && prev ? prev.correos : [];
          const nuevos = r.messages.filter(m => !previos.some(x => x.uid === m.uid));
          return { clave, correos: [...previos, ...nuevos], total: r.total || 0, error: false };
        });
      })
      .catch(() => { if (vigente) setDatos({ clave, correos: [], total: 0, error: true }); });
    return () => { vigente = false; };
  }, [carpeta, busqueda, pagina, clave]);

  const cargando = datos?.clave !== clave;
  const correos = datos?.correos ?? [];
  const total = datos?.total ?? 0;
  const error = !!datos?.error && !cargando;

  useEffect(() => {
    const tecla = (e: KeyboardEvent) => { if (e.key === 'Escape') onCerrar(); };
    window.addEventListener('keydown', tecla);
    return () => window.removeEventListener('keydown', tecla);
  }, [onCerrar]);

  const claveDe = (m: MessageSummary) => `${m.folder || carpeta}:${m.uid}`;
  const alternar = (m: MessageSummary) => {
    setSel(prev => {
      const n = new Map(prev);
      const k = claveDe(m);
      if (n.has(k)) n.delete(k); else n.set(k, m);
      return n;
    });
  };

  const adjuntar = () => {
    const elegidos: CorreoAAdjuntar[] = Array.from(sel.values()).map(m => ({
      folder: m.folder || carpeta, uid: m.uid, subject: m.subject || '', from: m.from, date: m.date,
    }));
    if (!elegidos.length) return;
    onElegir(elegidos);
    onCerrar();
  };

  const opcionesCarpeta = useMemo(() => {
    const nombres = carpetas.map(c => c.name);
    if (!nombres.includes(carpeta)) nombres.unshift(carpeta);
    return nombres;
  }, [carpetas, carpeta]);

  const hayMas = correos.length < total;
  const nSel = sel.size;

  return (
    <div className="fixed inset-0 z-[60] bg-black/40 flex items-center justify-center p-4" onClick={onCerrar} role="dialog" aria-modal="true" aria-label="Adjuntar un correo">
      <div className="bg-white dark:bg-[#252423] rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="px-4 py-3 border-b border-[#edebe9] dark:border-[#3b3a39]">
          <div className="font-semibold text-[#323130] dark:text-[#e0e0e0]">Adjuntar un correo</div>
          <p className="text-[12px] text-[#605e5c] dark:text-[#a19f9d]">El correo elegido viaja completo como archivo .eml, con sus propios adjuntos. Marque uno o varios.</p>
        </div>

        <div className="px-4 py-2 flex flex-wrap gap-2 items-center border-b border-[#f3f2f1] dark:border-[#3b3a39]">
          <label className="text-[12px] text-[#605e5c] dark:text-[#a19f9d] flex items-center gap-1">
            Carpeta
            <select value={carpeta} onChange={e => { setCarpeta(e.target.value); setPagina(1); }}
              className="h-[28px] px-1 text-[12px] border border-[#c8c6c4] rounded bg-white dark:bg-[#1b1a19] dark:text-[#e0e0e0] max-w-[220px]">
              {opcionesCarpeta.map(n => <option key={n} value={n}>{nombreCarpeta(n)}</option>)}
            </select>
          </label>
          <input type="search" value={texto} onChange={e => setTexto(e.target.value)} autoFocus
            placeholder="Buscar por asunto o remitente…" aria-label="Buscar por asunto o remitente"
            className="flex-1 min-w-[180px] h-[28px] px-2 text-[13px] border border-[#c8c6c4] rounded bg-white dark:bg-[#1b1a19] dark:text-[#e0e0e0] outline-none focus:border-[#0078d4]" />
        </div>

        <div className="flex-1 overflow-y-auto min-h-[240px]">
          {error && <p className="p-6 text-center text-[13px] text-[#a4262c]">No se pudo cargar la carpeta. Intente de nuevo.</p>}
          {!error && !cargando && correos.length === 0 && (
            <p className="p-6 text-center text-[13px] text-[#605e5c] dark:text-[#a19f9d]">{busqueda ? 'Ningún correo coincide con la búsqueda.' : 'La carpeta está vacía.'}</p>
          )}
          {correos.map(m => {
            const marcado = sel.has(claveDe(m));
            return (
              <label key={claveDe(m)} className={`flex items-center gap-3 px-4 py-2 cursor-pointer text-[13px] border-b border-[#f3f2f1] dark:border-[#3b3a39] ${marcado ? 'bg-[#deecf9] dark:bg-[#004578]' : 'hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39]'}`}>
                <input type="checkbox" checked={marcado} onChange={() => alternar(m)} className="shrink-0" />
                <span className="w-[150px] shrink-0 truncate text-[#323130] dark:text-[#e0e0e0]" title={m.from}>{nombreRemitente(m.from) || '(sin remitente)'}</span>
                <span className="flex-1 min-w-0 truncate text-[#323130] dark:text-[#e0e0e0]" title={m.subject}>
                  {m.subject || '(sin asunto)'}
                  {m.has_attachments && <span className="ml-1 text-[#605e5c]" title="Con adjuntos">📎</span>}
                </span>
                <span className="w-[80px] shrink-0 text-right text-[12px] text-[#605e5c] dark:text-[#a19f9d]">{fecha(m)}</span>
              </label>
            );
          })}
          {cargando && <p className="p-3 text-center text-[12px] text-[#605e5c] dark:text-[#a19f9d]">Cargando…</p>}
          {!cargando && hayMas && (
            <button type="button" onClick={() => setPagina(p => p + 1)}
              className="w-full py-2 text-[12px] text-[#106ebe] hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39]">
              Cargar más ({correos.length} de {total})
            </button>
          )}
        </div>

        <div className="px-4 py-2 border-t border-[#edebe9] dark:border-[#3b3a39] flex justify-between items-center">
          <span className="text-xs text-[#605e5c] dark:text-[#a19f9d]">{nSel > 0 ? `${nSel} correo${nSel > 1 ? 's' : ''} marcado${nSel > 1 ? 's' : ''}` : 'Marque los correos que quiere adjuntar'}</span>
          <div className="flex gap-2">
            <button type="button" onClick={onCerrar} className="px-3 py-1.5 rounded text-sm text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39]">Cancelar</button>
            <button type="button" onClick={adjuntar} disabled={nSel === 0}
              className="px-3 py-1.5 rounded text-sm font-semibold bg-[#0078d4] text-white hover:bg-[#106ebe] disabled:opacity-50">
              Adjuntar{nSel > 0 ? ` (${nSel})` : ''}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
