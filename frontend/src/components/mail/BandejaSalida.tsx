/**
 * «Bandeja de salida» (T-117, 13/11/2026) — SOLO dentro de la app (modo Teams).
 *
 * El motor de cola de envío ya existía (lib/syncQueue.ts + lib/offlineStore.ts): un correo escrito sin
 * conexión se guarda y se reintenta al reconectar. Lo que faltaba era un LUGAR VISIBLE, como en Outlook,
 * para que la persona vea sus correos en cola y pueda actuar. En la web normal no se muestra (allí basta
 * el aviso); dentro de la app sí, fija y visible aunque esté vacía.
 *
 * `EntradaBandejaSalida` es la fila del panel de carpetas (con el número en cola); `PanelBandejaSalida`
 * es la ventana con la lista y las acciones Reintentar / Enviar ahora / Descartar. Se comunican por
 * eventos de ventana, sin tocar el estado global. Al enviarse (al reconectar o con «Enviar ahora») el
 * correo sale de la cola y la bandeja se vacía sola.
 */
import { useEffect, useState } from 'react';
import { getOutboxEmails, removeFromOutbox, type OutboxEmail } from '../../lib/offlineStore';
import { reintentarEnvio, syncOutbox, hayConexion, causaSinConexion, TEXTO_ESTADO } from '../../lib/syncQueue';
import { esDeLaSesion } from '../../lib/sesionActual';
import { esClienteEscritorio } from '../../lib/clienteEscritorio';
import { showToast } from '../common/Toast';

const ABRIR = 'abrir-bandeja-salida';
const CAMBIO = 'outbox-cambio';   // lo emite syncQueue al cambiar la cola

function useBandeja(activo: boolean) {
  const [lista, setLista] = useState<OutboxEmail[]>([]);
  const [cargando, setCargando] = useState(true);
  useEffect(() => {
    if (!activo) return;
    let vivo = true;
    const cargar = () => {
      getOutboxEmails()
        .then((todos) => { if (vivo) setLista((todos || []).filter((e) => esDeLaSesion(e))); })
        .catch(() => { /* se queda con lo que había */ })
        .finally(() => { if (vivo) setCargando(false); });
    };
    cargar();
    window.addEventListener(CAMBIO, cargar);
    return () => { vivo = false; window.removeEventListener(CAMBIO, cargar); };
  }, [activo]);
  return { lista, cargando };
}

/** Fila «Bandeja de salida» del panel de carpetas (solo en la app). */
export function EntradaBandejaSalida() {
  const enApp = esClienteEscritorio();
  const { lista } = useBandeja(enApp);
  if (!enApp) return null;
  const fallidos = lista.filter((e) => e.status === 'failed').length;
  const enCola = lista.length - fallidos;
  return (
    <button type="button" onClick={() => window.dispatchEvent(new CustomEvent(ABRIR))}
      title="Correos escritos sin conexión que saldrán al volver la red"
      className="w-full flex items-center gap-1.5 px-2 py-[4px] rounded text-[13px] text-[#323130] hover:bg-[#edebe9] dark:text-[#e0e0e0] dark:hover:bg-[#333]">
      <span className="w-[12px] shrink-0" />
      <svg className="w-[15px] h-[15px] shrink-0 text-[#605e5c]" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 10l18-7-7 18-2.5-7.5L3 10z" />
      </svg>
      <span className="truncate flex-1 text-left">Bandeja de salida</span>
      {fallidos > 0 && <span className="text-[11px] font-bold text-[#a4262c]" title="Envíos que fallaron">!</span>}
      {enCola > 0 && <span className="text-[11px] font-bold text-[#005a9e] tabular-nums">{enCola}</span>}
    </button>
  );
}

/** Ventana con la lista de la bandeja de salida. Se abre con el evento «abrir-bandeja-salida». */
export function PanelBandejaSalida() {
  const [abierto, setAbierto] = useState(false);
  const { lista, cargando } = useBandeja(abierto);

  useEffect(() => {
    const abrir = () => setAbierto(true);
    window.addEventListener(ABRIR, abrir);
    return () => window.removeEventListener(ABRIR, abrir);
  }, []);
  useEffect(() => {
    if (!abierto) return;
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setAbierto(false); };
    document.addEventListener('keydown', esc);
    return () => document.removeEventListener('keydown', esc);
  }, [abierto]);

  const enviarAhora = async (e: OutboxEmail) => {
    if (!hayConexion()) { showToast('Sin conexión: ' + causaSinConexion()); return; }
    showToast('Enviando…');
    await syncOutbox(e.id);
  };
  const reintentar = async (e: OutboxEmail) => {
    if (!hayConexion()) { showToast('Sin conexión: ' + causaSinConexion()); return; }
    showToast('Reintentando…');
    await reintentarEnvio(e.id);
  };
  const descartar = async (e: OutboxEmail) => {
    if (!window.confirm(`¿Descartar «${e.subject || '(sin asunto)'}»? No se enviará y se borrará de la cola.`)) return;
    await removeFromOutbox(e.id);
    window.dispatchEvent(new CustomEvent(CAMBIO));
    showToast('Correo descartado de la bandeja de salida');
  };

  if (!abierto) return null;
  const boton = 'px-2.5 py-1 rounded border border-[#d2d0ce] bg-white text-[12px] text-[#323130] hover:bg-[#f3f2f1] dark:bg-[#2b2b2b] dark:text-[#e0e0e0] dark:border-[#444]';
  return (
    <div className="fixed inset-0 z-[9000] flex items-start justify-center bg-black/30 pt-[8vh] px-3" onMouseDown={(e) => { if (e.target === e.currentTarget) setAbierto(false); }}>
      <div role="dialog" aria-modal="true" aria-label="Bandeja de salida"
        className="w-full max-w-[720px] max-h-[78vh] flex flex-col bg-white rounded-lg shadow-xl border border-[#e1dfdd] dark:bg-[#1f1f1f] dark:border-[#3a3a3a]">
        <div className="flex items-center gap-2 px-5 py-3 border-b border-[#edebe9] dark:border-[#3a3a3a]">
          <h2 className="text-[16px] font-semibold text-[#323130] dark:text-[#e0e0e0]">Bandeja de salida</h2>
          <span className="text-[12px] text-[#605e5c]">{cargando ? 'cargando…' : `${lista.length} ${lista.length === 1 ? 'correo' : 'correos'}`}</span>
          <button type="button" onClick={() => setAbierto(false)} aria-label="Cerrar" className="ml-auto text-[#605e5c] hover:text-[#201f1e] text-[18px] leading-none px-2">×</button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {lista.length === 0 && !cargando && (
            <p className="px-5 py-8 text-[13px] text-[#605e5c] text-center">
              No hay correos en cola. Lo que escriba sin conexión aparecerá aquí y saldrá solo al volver la red.
            </p>
          )}
          {lista.map((e) => (
            <div key={e.id} className="px-5 py-3 border-b border-[#f3f2f1] dark:border-[#333]">
              <div className="flex items-baseline gap-2">
                <span className="text-[14px] font-semibold text-[#323130] truncate dark:text-[#e0e0e0]">{e.subject || '(sin asunto)'}</span>
                {e.status === 'failed' && <span className="shrink-0 text-[11px] font-bold text-[#a4262c]">{TEXTO_ESTADO.failed.toUpperCase()}</span>}
                {e.status === 'sending' && <span className="shrink-0 text-[11px] text-[#605e5c]">{TEXTO_ESTADO.sending}</span>}
                {(e.status === 'pending' || e.status === 'retenido') && <span className="shrink-0 text-[11px] text-[#005a9e]">{TEXTO_ESTADO[e.status]}</span>}
              </div>
              <div className="text-[12px] text-[#605e5c] truncate">Para: {(e.to || []).join(', ') || '—'}</div>
              {e.status === 'failed' && e.error && <div className="text-[12px] text-[#a4262c] mt-0.5">{e.error}</div>}
              <div className="mt-1.5 flex flex-wrap items-center gap-2">
                <span className="text-[11px] text-[#605e5c]">{new Date(e.createdAt).toLocaleString('es-EC', { dateStyle: 'medium', timeStyle: 'short' })}</span>
                <span className="flex gap-2 ml-auto">
                  {e.status === 'failed' && <button type="button" className={boton} onClick={() => reintentar(e)}>Reintentar</button>}
                  {(e.status === 'pending' || e.status === 'retenido') && <button type="button" className={boton} onClick={() => enviarAhora(e)}>Enviar ahora</button>}
                  {e.status !== 'sending' && <button type="button" className={`${boton} !text-[#a4262c]`} onClick={() => descartar(e)}>Descartar</button>}
                </span>
              </div>
            </div>
          ))}
        </div>
        <p className="px-5 py-2.5 text-[11px] text-[#605e5c] border-t border-[#edebe9] dark:border-[#3a3a3a]">
          Los correos en cola salen solos al volver la conexión. «Enviar ahora» lo intenta de inmediato; «Descartar» lo borra sin enviarlo.
        </p>
      </div>
    </div>
  );
}
