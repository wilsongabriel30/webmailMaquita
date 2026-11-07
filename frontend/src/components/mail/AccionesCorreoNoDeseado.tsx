import { useState } from 'react';
import { api } from '../../api/client';
import { showToast } from '../common/Toast';
import { useMailStore } from '../../store/mailStore';

// Botones naturales al abrir un correo: marcarlo como No deseado (o No es spam en esa carpeta) y
// bloquear al remitente. Reutilizan endpoints ya probados: /mail/spam/report, /mail/spam/not-spam
// (mueven y enseñan al filtro) y /mail/remitentes-bloqueados (sus próximos correos van a No deseado;
// antes era una regla de /sieve/filters, con tope de 20 y detrás de la respuesta automática).

function extraerCorreo(from: string): string {
  const m = (from || '').match(/<([^>]+)>/);
  return (m ? m[1] : from || '').trim().toLowerCase();
}

function refrescar() {
  try { useMailStore.getState().clearSelection(); } catch { /* noop */ }
  try { useMailStore.getState().setSelectedMessage(null); } catch { /* noop */ }
  window.dispatchEvent(new CustomEvent('refresh-messages'));
}

const IconoNoDeseado = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" style={{ marginRight: 3 }}>
    <circle cx="12" cy="12" r="9" /><path strokeLinecap="round" d="M5.6 5.6l12.8 12.8" />
  </svg>
);
// Icono propio para Bloquear (persona tachada): antes compartía el de No deseado y, en el celular
// o con el panel estrecho, se veían dos botones idénticos uno al lado del otro.
const IconoBloquear = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" style={{ marginRight: 3 }}>
    <circle cx="9" cy="8" r="3.5" /><path strokeLinecap="round" d="M2.5 20c.8-3.6 3.4-5.5 6.5-5.5 1.3 0 2.5.3 3.5 1" />
    <circle cx="17.5" cy="17" r="4" /><path strokeLinecap="round" d="M14.7 19.8l5.6-5.6" />
  </svg>
);
const IconoOk = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" style={{ marginRight: 3 }}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

export function AccionesCorreoNoDeseado(
  { folder, uid, from, estilo }: { folder: string; uid: number; from: string; estilo: React.CSSProperties },
) {
  const [ocupado, setOcupado] = useState(false);
  const enNoDeseado = folder === 'Junk' || folder === 'Spam';
  const correo = extraerCorreo(from);

  const marcarNoDeseado = async () => {
    setOcupado(true);
    try {
      await api.post('/mail/spam/report', { folder, uid });
      showToast('Movido a Correo no deseado. El filtro aprendió que es spam.');
      refrescar();
    } catch { showToast('No se pudo marcar como no deseado'); }
    finally { setOcupado(false); }
  };

  const marcarNoEsSpam = async () => {
    setOcupado(true);
    try {
      await api.post('/mail/spam/not-spam', { folder, uid });
      showToast('Movido a la Bandeja de entrada. El filtro aprendió que no es spam.');
      refrescar();
    } catch { showToast('No se pudo marcar como no spam'); }
    finally { setOcupado(false); }
  };

  const confiar = async () => {
    if (!correo.includes('@')) { showToast('No se pudo leer el remitente'); return; }
    setOcupado(true);
    try {
      await api.post('/mail/remitentes-confiables', { correo });
      if (enNoDeseado) { await api.post('/mail/spam/not-spam', { folder, uid }).catch(() => { }); }
      showToast(`${correo} en confianza: sus correos llegarán siempre a la Bandeja de entrada.`);
      refrescar();
    } catch (e: any) { showToast(e?.message || 'No se pudo confiar en el remitente'); }
    finally { setOcupado(false); }
  };

  const bloquear = async () => {
    if (!correo.includes('@')) { showToast('No se pudo leer el remitente'); return; }
    if (!window.confirm(`¿Bloquear a ${correo}?\n\nSus próximos correos irán directo a Correo no deseado. Puedes deshacerlo en Configuración → Remitentes bloqueados.`)) return;
    setOcupado(true);
    try {
      await api.post('/mail/remitentes-bloqueados', { correo });
      await api.post('/mail/spam/report', { folder, uid }).catch(() => { /* el bloqueo ya se creó */ });
      showToast(`${correo} bloqueado. Sus correos irán a Correo no deseado.`);
      refrescar();
    } catch (e: any) {
      showToast(e?.message || 'No se pudo bloquear el remitente');
    } finally { setOcupado(false); }
  };

  return (
    <>
      {enNoDeseado ? (
        <button style={estilo} onClick={marcarNoEsSpam} disabled={ocupado}
          title="Devolver a la bandeja de entrada y enseñar al filtro que no es spam">
          <IconoOk /><span className="barra-etiqueta barra-etiqueta-sec">No es spam</span>
        </button>
      ) : (
        <button style={estilo} onClick={marcarNoDeseado} disabled={ocupado}
          title="No deseado: mover a Correo no deseado y enseñar al filtro" aria-label="Marcar como correo no deseado">
          <IconoNoDeseado /><span className="barra-etiqueta barra-etiqueta-sec">No deseado</span>
        </button>
      )}
      {enNoDeseado && (
        <button style={estilo} onClick={confiar} disabled={ocupado}
          title="Sus correos llegarán siempre a la Bandeja de entrada, aunque parezcan spam">
          <IconoOk /><span className="barra-etiqueta barra-etiqueta-sec">Confiar en este remitente</span>
        </button>
      )}
      <button style={estilo} onClick={bloquear} disabled={ocupado}
        title="Bloquear remitente: no volver a recibir correos de esta persona" aria-label="Bloquear remitente">
        <IconoBloquear /><span className="barra-etiqueta barra-etiqueta-sec">Bloquear remitente</span>
      </button>
    </>
  );
}
