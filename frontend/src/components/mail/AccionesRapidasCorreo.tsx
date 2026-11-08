/**
 * Iconos rápidos arriba a la derecha del correo abierto (07/11/2026, como Outlook):
 * Responder, Responder a todos, Reenviar y «⋯» con el resto de acciones del correo.
 * La barra de abajo sigue igual; esto es el acceso rápido sin bajar hasta el final del correo.
 * Las acciones del menú actúan solo sobre ESTE correo (no sobre la selección de la lista).
 */
import { useEffect, useRef, useState } from 'react';
import { api } from '../../api/client';
import { showToast } from '../common/Toast';
import { useMailStore } from '../../store/mailStore';
import { confirmarBorradoDefinitivo } from '../../lib/confirmarBorrado';
import { abrirMensajeEnVentana } from '../../lib/abrirEnPestana';
import { olvidarLeido, recordarLeido } from './graciaNoLeidos';

function extraerCorreo(from: string): string {
  const m = (from || '').match(/<([^>]+)>/);
  return (m ? m[1] : from || '').trim().toLowerCase();
}

function refrescar(cerrar: boolean) {
  if (cerrar) {
    try { useMailStore.getState().setSelectedMessage(null); } catch { /* noop */ }
    // En la ventana propia del correo no hay lista detrás: se avisa a la bandeja y se cierra (revisión 07/11/2026).
    if (window.location.pathname.endsWith('/mensaje')) {
      try { window.opener?.dispatchEvent(new CustomEvent('refresh-messages')); } catch { /* otro origen */ }
      setTimeout(() => window.close(), 900);
      return;
    }
  }
  window.dispatchEvent(new CustomEvent('refresh-messages'));
}

/** Refleja al instante el cambio de leído/bandera en el correo abierto y en la fila (revisión 07/11/2026). */
function reflejar(uid: number, cambio: { seen?: boolean; flagged?: boolean }) {
  useMailStore.setState(s => ({
    messages: s.messages.map(m => m.uid === uid ? { ...m, ...cambio } : m),
    selectedMessage: s.selectedMessage?.uid === uid ? { ...s.selectedMessage, ...cambio } : s.selectedMessage,
  }));
}

const icono = (d: string) => (
  <svg width="18" height="18" viewBox="0 0 16 16" fill="#0078d4" aria-hidden="true"><path d={d} /></svg>
);
const D_RESPONDER = 'M6.5 3L1 8l5.5 5V10c4.5 0 7 1.5 8.5 5-1-4.5-3.5-8-8.5-8.5V3z';
const D_TODOS = 'M9.5 3L4 8l5.5 5V10c4.5 0 6 1.5 7.5 5-1-4.5-3-8-7.5-8.5V3zM3 8L0 5.5v5L3 8z';
const D_REENVIAR = 'M9.5 3L15 8l-5.5 5V10C5 10 2.5 11.5 1 15c1-4.5 3.5-8 8.5-8.5V3z';

const estiloIcono: React.CSSProperties = {
  border: 'none', borderRadius: 4, width: 32, height: 30, cursor: 'pointer',
  color: '#0078d4', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
};
// Con texto, como Outlook: icono azul y texto oscuro. En pantallas estrechas queda solo el icono (index.css).
const estiloConTexto: React.CSSProperties = {
  ...estiloIcono, width: 'auto', padding: '0 8px', gap: 6, fontSize: 14, whiteSpace: 'nowrap',
};
const estiloOpcion: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 10, width: '100%', textAlign: 'left', padding: '8px 14px',
  border: 'none', fontSize: 13, cursor: 'pointer', whiteSpace: 'nowrap',
};

export function AccionesRapidasCorreo({
  folder, uid, from, seen, flagged, enVentana,
  onResponder, onResponderTodos, onReenviar, onReenviarAdjunto, onImprimir, onDescargarEml, onTraducir, onVerOrigen,
}: {
  folder: string; uid: number; from: string; seen?: boolean; flagged?: boolean;
  /** Ya abierto en su propia ventana: no se ofrece «Abrir en otra ventana». */
  enVentana?: boolean;
  onResponder: () => void; onResponderTodos: () => void; onReenviar: () => void;
  onImprimir: () => void; onDescargarEml: () => void;
  /** «Reenviar como adjunto» (.eml), que antes estaba en la barra de abajo. */
  onReenviarAdjunto?: () => void;
  /** «Traducir» y «Ver origen del mensaje», como en el «⋯» de Outlook (07/11/2026). */
  onTraducir?: () => void; onVerOrigen?: () => void;
}) {
  const [abierto, setAbierto] = useState(false);
  const caja = useRef<HTMLDivElement>(null);
  const enNoDeseado = folder === 'Junk' || folder === 'Spam';

  useEffect(() => {
    if (!abierto) return;
    const fuera = (e: MouseEvent) => { if (caja.current && !caja.current.contains(e.target as Node)) setAbierto(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setAbierto(false); };
    document.addEventListener('mousedown', fuera);
    document.addEventListener('keydown', esc);
    return () => { document.removeEventListener('mousedown', fuera); document.removeEventListener('keydown', esc); };
  }, [abierto]);

  const accion = (fn: () => void | Promise<void>) => () => { setAbierto(false); void fn(); };

  const lote = async (action: string, dest = '') =>
    api.post(`/mail/bulk-action/${encodeURIComponent(folder)}`, { uids: [uid], action, dest_folder: dest });

  const eliminar = async () => {
    try {
      if (folder === 'Trash') {
        if (!confirmarBorradoDefinitivo(1)) return;
        await lote('delete');
        showToast('Eliminado permanentemente');
      } else {
        await lote('move', 'Trash');
        showToast('Movido a Papelera');
      }
      refrescar(true);
    } catch { showToast('No se pudo eliminar'); }
  };

  const leido = async () => {
    try {
      await lote(seen ? 'mark_unread' : 'mark_read');
      if (seen) olvidarLeido(folder, uid); else recordarLeido(folder, uid);
      reflejar(uid, { seen: !seen });
      showToast(seen ? 'Marcado como no leído' : 'Marcado como leído');
      refrescar(false);
    } catch { showToast('No se pudo cambiar'); }
  };

  const bandera = async () => {
    try {
      await lote(flagged ? 'unflag' : 'flag');
      reflejar(uid, { flagged: !flagged });
      showToast(flagged ? 'Bandera quitada' : 'Marcado con bandera');
      refrescar(false);
    } catch { showToast('No se pudo cambiar'); }
  };

  const noDeseado = async () => {
    try {
      await api.post(enNoDeseado ? '/mail/spam/not-spam' : '/mail/spam/report', { folder, uid });
      showToast(enNoDeseado ? 'Movido a la Bandeja de entrada.' : 'Movido a Correo no deseado.');
      refrescar(true);
    } catch { showToast('No se pudo mover'); }
  };

  const bloquear = async () => {
    const correo = extraerCorreo(from);
    if (!correo.includes('@')) { showToast('No se pudo leer el remitente'); return; }
    if (!window.confirm(`¿Bloquear a ${correo}?\n\nSus próximos correos irán directo a Correo no deseado. Puede deshacerlo en Configuración → Remitentes bloqueados.`)) return;
    try {
      await api.post('/mail/remitentes-bloqueados', { correo });
      await api.post('/mail/spam/report', { folder, uid }).catch(() => { /* el bloqueo ya se creó */ });
      showToast(`${correo} bloqueado.`);
      refrescar(true);
    } catch (e) { showToast((e as { message?: string } | null)?.message || 'No se pudo bloquear el remitente'); }
  };

  const phishing = async () => {
    if (!window.confirm('¿Informar este correo como phishing (suplantación o estafa)?\n\nSe moverá a Correo no deseado. No abra sus enlaces ni sus adjuntos.')) return;
    try {
      await api.post('/mail/spam/report', { folder, uid });
      showToast('Informado como phishing y movido a Correo no deseado.');
      refrescar(true);
    } catch { showToast('No se pudo informar'); }
  };

  return (
    <div ref={caja} style={{ display: 'inline-flex', alignItems: 'center', gap: 2, position: 'relative' }}>
      <button type="button" className="bg-transparent hover:bg-[#f3f2f1] text-[#323130]" style={estiloConTexto} onClick={onResponder} title="Responder">{icono(D_RESPONDER)}<span className="accion-rapida-texto">Responder</span></button>
      <button type="button" className="bg-transparent hover:bg-[#f3f2f1] text-[#323130]" style={estiloConTexto} onClick={onResponderTodos} title="Responder a todos">{icono(D_TODOS)}<span className="accion-rapida-texto">Responder a todos</span></button>
      <button type="button" className="bg-transparent hover:bg-[#f3f2f1] text-[#323130]" style={estiloConTexto} onClick={onReenviar} title="Reenviar">{icono(D_REENVIAR)}<span className="accion-rapida-texto">Reenviar</span></button>
      <span className="bg-[#e1dfdd]" style={{ width: 1, height: 20, margin: '0 4px' }} />
      <button type="button" className="bg-transparent hover:bg-[#f3f2f1] text-[#323130]" style={estiloIcono} onClick={() => setAbierto(v => !v)}
        title="Más acciones" aria-label="Más acciones" aria-haspopup="menu" aria-expanded={abierto}>
        <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
          <circle cx="3" cy="8" r="1.4" /><circle cx="8" cy="8" r="1.4" /><circle cx="13" cy="8" r="1.4" />
        </svg>
      </button>
      {abierto && (
        <div role="menu" className="bg-white border border-[#e1dfdd]" style={{
          position: 'absolute', top: '100%', right: 0, zIndex: 50, marginTop: 4, minWidth: 230,
          borderRadius: 6, boxShadow: '0 6px 20px rgba(0,0,0,0.14)', padding: '4px 0',
        }}>
          <button type="button" role="menuitem" className="bg-transparent hover:bg-[#f3f2f1] text-[#323130]" style={estiloOpcion} onClick={accion(eliminar)}><svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#605e5c" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M3 4.5h10M6.5 4.5V3h3v1.5M4.5 4.5l.6 8.5h5.8l.6-8.5" /></svg>Eliminar</button>
          <button type="button" role="menuitem" className="bg-transparent hover:bg-[#f3f2f1] text-[#323130]" style={estiloOpcion} onClick={accion(leido)}><svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#605e5c" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M2 4h12v8H2zM2 4l6 4.5L14 4" /></svg>{seen ? 'Marcar como no leído' : 'Marcar como leído'}</button>
          <button type="button" role="menuitem" className="bg-transparent hover:bg-[#f3f2f1] text-[#323130]" style={estiloOpcion} onClick={accion(bandera)}><svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#605e5c" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M3.5 14V2.5M3.5 3h8l-1.8 2.8L11.5 8.5h-8" /></svg>{flagged ? 'Quitar la bandera' : 'Marcar con bandera'}</button>
          {onReenviarAdjunto && (<>
            <div className="bg-[#edebe9]" style={{ height: 1, margin: '4px 0' }} />
            <div className="text-[#605e5c]" style={{ padding: '4px 14px 2px', fontSize: 11, fontWeight: 600 }}>Otras acciones de respuesta</div>
            <button type="button" role="menuitem" className="bg-transparent hover:bg-[#f3f2f1] text-[#323130]" style={estiloOpcion} onClick={accion(onReenviarAdjunto)}><svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#605e5c" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M13.5 7.5l-5 5a3 3 0 01-4.2-4.2l5.6-5.6a2 2 0 012.8 2.8l-5.6 5.6a1 1 0 01-1.4-1.4l5-5" /></svg>Reenviar como adjunto</button>
          </>)}
          <div className="bg-[#edebe9]" style={{ height: 1, margin: '4px 0' }} />
          <button type="button" role="menuitem" className="bg-transparent hover:bg-[#f3f2f1] text-[#323130]" style={estiloOpcion} onClick={accion(noDeseado)}><svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#605e5c" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M8 2a6 6 0 100 12A6 6 0 008 2zM3.8 3.8l8.4 8.4" /></svg>{enNoDeseado ? 'No es correo no deseado' : 'Informar de correo no deseado'}</button>
          {!enNoDeseado && <button type="button" role="menuitem" className="bg-transparent hover:bg-[#f3f2f1] text-[#323130]" style={estiloOpcion} onClick={accion(phishing)}><svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#605e5c" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M8 1.8l5.5 2.2v3.6c0 3.2-2.3 5.7-5.5 6.6-3.2-.9-5.5-3.4-5.5-6.6V4zM8 5.2v3.3M8 10.6v.2" /></svg>Informar sobre phishing</button>}
          <button type="button" role="menuitem" className="bg-transparent hover:bg-[#f3f2f1] text-[#323130]" style={estiloOpcion} onClick={accion(bloquear)}><svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#605e5c" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M6 6.5a2.3 2.3 0 100-4.6 2.3 2.3 0 000 4.6zM1.8 13.5c.5-2.4 2.2-3.7 4.2-3.7M11.5 14.5a2.7 2.7 0 100-5.4 2.7 2.7 0 000 5.4zM9.6 13.6l3.8-3.6" /></svg>Bloquear remitente</button>
          <div className="bg-[#edebe9]" style={{ height: 1, margin: '4px 0' }} />
          <button type="button" role="menuitem" className="bg-transparent hover:bg-[#f3f2f1] text-[#323130]" style={estiloOpcion} onClick={accion(onImprimir)}><svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#605e5c" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M4.5 6V2h7v4M4.5 11.5H2.5V6h11v5.5h-2M4.5 9.5h7V14h-7z" /></svg>Imprimir</button>
          {onTraducir && <button type="button" role="menuitem" className="bg-transparent hover:bg-[#f3f2f1] text-[#323130]" style={estiloOpcion} onClick={accion(onTraducir)}><svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#605e5c" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M2 3.5h6M5 2v1.5M3.2 3.5c.6 2.4 2.2 4.2 4.3 5M6.8 3.5c-.6 2.4-2.2 4.2-4.6 5.2M8.5 14l2.8-7 2.8 7M9.5 11.8h3.6" /></svg>Traducir</button>}
          {onVerOrigen && <button type="button" role="menuitem" className="bg-transparent hover:bg-[#f3f2f1] text-[#323130]" style={estiloOpcion} onClick={accion(onVerOrigen)}><svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#605e5c" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5.5 4.5L2 8l3.5 3.5M10.5 4.5L14 8l-3.5 3.5" /></svg>Ver origen del mensaje</button>}
          {!enVentana && (
            <button type="button" role="menuitem" className="bg-transparent hover:bg-[#f3f2f1] text-[#323130]" style={estiloOpcion} onClick={accion(() => abrirMensajeEnVentana(folder, uid))}><svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#605e5c" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5 2.5h8.5V11M2.5 5h8.5v8.5H2.5z" /></svg>Abrir en otra ventana</button>
          )}
          <button type="button" role="menuitem" className="bg-transparent hover:bg-[#f3f2f1] text-[#323130]" style={estiloOpcion} onClick={accion(onDescargarEml)}><svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#605e5c" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M2.5 2.5h9l2 2v9h-11zM5 2.5v3.5h5V2.5M5 13.5V9.5h6v4" /></svg>Guardar como (.eml)</button>
        </div>
      )}
    </div>
  );
}
