/**
 * «Programados» (11/11/2026): lo que la persona dejó para enviar más tarde.
 *
 * Programar ya existía, pero no había dónde verlo ni cómo cambiarlo. Aquí se listan los envíos pendientes
 * (y los que fallaron en los últimos días) con tres acciones: cambiar la fecha, editar (vuelve a la
 * redacción y cancela la programación) y cancelar. A la hora indicada el servidor lo envía solo y lo deja
 * en «Enviados»; hace falta que la cuenta tenga alguna sesión iniciada.
 *
 * `EntradaProgramados` es la fila del panel de carpetas (con el número de pendientes); `PanelProgramados`
 * es la ventana con la lista. Se comunican por eventos de ventana para no tocar el estado global.
 */
import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { useMailStore } from '../../store/mailStore';
import { showToast } from '../common/Toast';

interface Programado { id: number; to: string[]; cc: string[]; bcc: string[]; subject: string; scheduled_at: string; status: string }
interface Detalle extends Programado { html_body: string; text_body: string; in_reply_to: string; references: string }

const ABRIR = 'abrir-programados';
export const CAMBIO_PROGRAMADOS = 'programados-cambio';

function paraCampoFecha(iso: string): string {
  const d = new Date(iso);
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

function useProgramados(activo: boolean) {
  const [lista, setLista] = useState<Programado[]>([]);
  const [cargando, setCargando] = useState(true);
  useEffect(() => {
    if (!activo) return;
    let vivo = true;
    const cargar = () => {
      api.get<{ programados: Programado[] }>('/mail/programados')
        .then((r) => { if (vivo) setLista(r.programados || []); })
        .catch(() => { /* se queda con lo que había */ })
        .finally(() => { if (vivo) setCargando(false); });
    };
    cargar();
    window.addEventListener(CAMBIO_PROGRAMADOS, cargar);
    return () => { vivo = false; window.removeEventListener(CAMBIO_PROGRAMADOS, cargar); };
  }, [activo]);
  return { lista, cargando };
}

/** Fila «Programados» del panel de carpetas. */
export function EntradaProgramados() {
  const { lista } = useProgramados(true);
  const pendientes = lista.filter((p) => p.status !== 'failed').length;
  const fallidos = lista.length - pendientes;
  return (
    <button type="button" onClick={() => window.dispatchEvent(new CustomEvent(ABRIR))}
      title="Correos que dejó programados para enviar más tarde"
      className="w-full flex items-center gap-1.5 px-2 py-[4px] rounded text-[13px] text-[#323130] hover:bg-[#edebe9] dark:text-[#e0e0e0] dark:hover:bg-[#333]">
      <span className="w-[12px] shrink-0" />
      <svg className="w-[15px] h-[15px] shrink-0 text-[#605e5c]" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="9" /><path strokeLinecap="round" strokeLinejoin="round" d="M12 7v5l3 2" />
      </svg>
      <span className="truncate flex-1 text-left">Programados</span>
      {fallidos > 0 && <span className="text-[11px] font-bold text-[#a4262c]" title="Envíos que fallaron">!</span>}
      {pendientes > 0 && <span className="text-[11px] font-bold text-[#005a9e] tabular-nums">{pendientes}</span>}
    </button>
  );
}

/** Ventana con la lista de envíos programados. Se abre con el evento «abrir-programados». */
export function PanelProgramados() {
  const [abierto, setAbierto] = useState(false);
  const { lista, cargando } = useProgramados(abierto);
  const [editando, setEditando] = useState<{ id: number; fecha: string; minimo: string } | null>(null);

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

  const avisarCambio = () => window.dispatchEvent(new CustomEvent(CAMBIO_PROGRAMADOS));

  const cancelar = async (p: Programado) => {
    if (!window.confirm(`¿Cancelar el envío programado «${p.subject || '(sin asunto)'}»? No se enviará.`)) return;
    try { await api.del(`/mail/programados/${p.id}`); showToast('Envío programado cancelado'); avisarCambio(); }
    catch { showToast('No se pudo cancelar: es posible que ya se haya enviado'); avisarCambio(); }
  };

  const guardarFecha = async () => {
    if (!editando) return;
    const fecha = new Date(editando.fecha);
    if (Number.isNaN(fecha.getTime()) || fecha.getTime() < Date.now() + 60000) { showToast('Elija una fecha y hora futuras'); return; }
    try {
      await api.patch(`/mail/programados/${editando.id}`, { scheduled_at: fecha.toISOString() });
      showToast(`Se enviará el ${fecha.toLocaleString('es-EC')}`);
      setEditando(null); avisarCambio();
    } catch { showToast('No se pudo cambiar la fecha: es posible que ya se haya enviado'); avisarCambio(); }
  };

  const editar = async (p: Programado) => {
    try {
      const d = await api.get<Detalle>(`/mail/programados/${p.id}`);
      await api.del(`/mail/programados/${p.id}`);
      useMailStore.getState().openCompose('new', {
        to: d.to, cc: d.cc, bcc: d.bcc, subject: d.subject, html_body: d.html_body, text_body: d.text_body,
        in_reply_to: d.in_reply_to || undefined, references: d.references || undefined,
      });
      setAbierto(false); avisarCambio();
      showToast('Se abrió para editar y se quitó de Programados: al terminar, envíelo o vuelva a programarlo', undefined, { fijo: true });
    } catch { showToast('No se pudo abrir: es posible que ya se haya enviado'); avisarCambio(); }
  };

  if (!abierto) return null;
  const boton = 'px-2.5 py-1 rounded border border-[#d2d0ce] bg-white text-[12px] text-[#323130] hover:bg-[#f3f2f1] dark:bg-[#2b2b2b] dark:text-[#e0e0e0] dark:border-[#444]';
  return (
    <div className="fixed inset-0 z-[9000] flex items-start justify-center bg-black/30 pt-[8vh] px-3" onMouseDown={(e) => { if (e.target === e.currentTarget) setAbierto(false); }}>
      <div role="dialog" aria-modal="true" aria-label="Envíos programados"
        className="w-full max-w-[720px] max-h-[78vh] flex flex-col bg-white rounded-lg shadow-xl border border-[#e1dfdd] dark:bg-[#1f1f1f] dark:border-[#3a3a3a]">
        <div className="flex items-center gap-2 px-5 py-3 border-b border-[#edebe9] dark:border-[#3a3a3a]">
          <h2 className="text-[16px] font-semibold text-[#323130] dark:text-[#e0e0e0]">Programados</h2>
          <span className="text-[12px] text-[#605e5c]">{cargando ? 'cargando…' : `${lista.length} ${lista.length === 1 ? 'correo' : 'correos'}`}</span>
          <button type="button" onClick={() => setAbierto(false)} aria-label="Cerrar" className="ml-auto text-[#605e5c] hover:text-[#201f1e] text-[18px] leading-none px-2">×</button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {lista.length === 0 && !cargando && (
            <p className="px-5 py-8 text-[13px] text-[#605e5c] text-center">
              No tiene correos programados. Para programar uno: en el correo nuevo, la flecha junto a «Enviar» → «Programar envío».
            </p>
          )}
          {lista.map((p) => (
            <div key={p.id} className="px-5 py-3 border-b border-[#f3f2f1] dark:border-[#333]">
              <div className="flex items-baseline gap-2">
                <span className="text-[14px] font-semibold text-[#323130] truncate dark:text-[#e0e0e0]">{p.subject || '(sin asunto)'}</span>
                {p.status === 'failed' && <span className="shrink-0 text-[11px] font-bold text-[#a4262c]">NO SE PUDO ENVIAR</span>}
                {p.status === 'sending' && <span className="shrink-0 text-[11px] text-[#605e5c]">enviándose…</span>}
              </div>
              <div className="text-[12px] text-[#605e5c] truncate">Para: {[...p.to, ...p.cc].join(', ') || '—'}</div>
              <div className="mt-1.5 flex flex-wrap items-center gap-2">
                {editando?.id === p.id ? (
                  <>
                    <input type="datetime-local" value={editando.fecha} min={editando.minimo}
                      onChange={(e) => setEditando({ ...editando, fecha: e.target.value })} aria-label="Nueva fecha y hora de envío"
                      className="px-2 py-1 border border-[#0078d4] rounded text-[12px] bg-white dark:bg-[#2b2b2b] dark:text-[#e0e0e0]" />
                    <button type="button" className={`${boton} !bg-[#0078d4] !text-white !border-[#0078d4]`} onClick={guardarFecha}>Guardar fecha</button>
                    <button type="button" className={boton} onClick={() => setEditando(null)}>No cambiar</button>
                  </>
                ) : (
                  <>
                    <span className="text-[12px] text-[#323130] dark:text-[#e0e0e0]">
                      {p.status === 'failed' ? 'Estaba para el ' : 'Se enviará el '}<b>{new Date(p.scheduled_at).toLocaleString('es-EC', { dateStyle: 'full', timeStyle: 'short' })}</b>
                    </span>
                    <span className="flex gap-2 ml-auto">
                      {p.status !== 'sending' && <button type="button" className={boton} onClick={() => setEditando({ id: p.id, minimo: paraCampoFecha(new Date(Date.now() + 120000).toISOString()), fecha: paraCampoFecha(p.status === 'failed' ? new Date(Date.now() + 600000).toISOString() : p.scheduled_at) })}>{p.status === 'failed' ? 'Reintentar…' : 'Cambiar fecha'}</button>}
                      {p.status !== 'sending' && <button type="button" className={boton} onClick={() => editar(p)}>Editar</button>}
                      {p.status !== 'sending' && <button type="button" className={`${boton} !text-[#a4262c]`} onClick={() => cancelar(p)}>Cancelar envío</button>}
                    </span>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
        <p className="px-5 py-2.5 text-[11px] text-[#605e5c] border-t border-[#edebe9] dark:border-[#3a3a3a]">
          A la hora indicada el correo sale solo y queda en «Enviados», aunque su equipo esté apagado o no tenga la sesión iniciada.
        </p>
      </div>
    </div>
  );
}
