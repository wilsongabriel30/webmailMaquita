/**
 * Recuperar un correo enviado (botón, comprobación previa y resultado por destinatario).
 *
 * Decisión de la dirección (09/11/2026): la recuperación quita el correo del buzón del destinatario
 * aunque ya lo haya leído; aquí la lectura solo se informa («Recuperable (ya lo leyó)»), nunca
 * se presenta como impedimento. Si a todos los destinatarios locales les salió bien, el servidor
 * pasa el correo de Enviados a Borradores y se avisa aquí para corregirlo y volverlo a enviar.
 *
 * Vive fuera de MessageView para que ese archivo no siga creciendo.
 */
import React from 'react';
import { api } from '../../api/client';
import { useMailStore } from '../../store/mailStore';
import { showToast } from '../common/Toast';
import type { MessageFull } from '../../types';

/** Resultado de comprobar o ejecutar la recuperación de un correo enviado. */
interface EstadoRecuperacion {
  recipient: string;
  can_recall: boolean;
  /** Externo: no se retira aquí, pero se puede pedir al otro servidor o enviar el aviso. */
  can_request?: boolean;
  was_read: boolean | null;
  reason?: string;
  status?: string;
  detail?: string;
  /** Pasó el plazo máximo de recuperación (lo decide el servidor). */
  fuera_de_plazo?: boolean;
}

interface RespuestaRecuperar {
  results: EstadoRecuperacion[];
  message: string;
  movido_a_borradores?: boolean;
}

/** Palabra clave IMAP con la que el servidor marca el borrador que nació de una recuperación. */
export const KEYWORD_RECUPERADO = '$Recuperado';

function destinatariosDe(msg: MessageFull): string[] {
  const lista = (msg.to || '').split(',').map((s) => s.trim()).filter(Boolean);
  if (msg.cc) lista.push(...msg.cc.split(',').map((s) => s.trim()).filter(Boolean));
  return lista;
}

/** Texto por destinatario en la comprobación previa. */
function textoComprobacion(r: EstadoRecuperacion): string {
  if (r.can_recall) return r.was_read ? 'Recuperable (ya lo leyó)' : 'Recuperable';
  return r.reason || 'No disponible';
}

/** Texto por destinatario tras ejecutar la recuperación. */
function textoResultado(r: EstadoRecuperacion): string {
  switch (r.status) {
    case 'recalled': return r.detail || (r.was_read ? 'Recuperado (ya lo había leído)' : 'Recuperado');
    case 'external_request_sent': return 'Externo: se le envió el aviso de «enviado por error» (copia para usted)';
    case 'external': return 'Externo: no se pudo enviar el aviso de envío por error';
    case 'not_found': return 'No encontrado';
    case 'fuera_de_plazo': return r.detail || 'Fuera de plazo';
    default: return r.detail || 'Error al recuperar';
  }
}

const estiloBoton: React.CSSProperties = {
  padding: '5px 14px', color: 'white', border: 'none', borderRadius: 4, fontSize: 12, cursor: 'pointer', fontWeight: 600,
};

interface Props {
  msg: MessageFull;
  folder: string;
}

export function PanelRecuperarCorreo({ msg, folder }: Props) {
  const [estado, setEstado] = React.useState<'idle' | 'checking' | 'recalling' | 'done' | 'error'>('idle');
  const [info, setInfo] = React.useState<EstadoRecuperacion[]>([]);
  const [movido, setMovido] = React.useState(false);

  // Al cambiar de correo, el panel vuelve a su estado inicial.
  React.useEffect(() => { setEstado('idle'); setInfo([]); setMovido(false); }, [msg.uid, folder]);

  const comprobar = React.useCallback(async () => {
    setEstado('checking');
    try {
      const res = await api.post<{ checks: EstadoRecuperacion[]; aviso?: string | null }>('/mail/recall/check', {
        message_id: msg.message_id, recipients: destinatariosDe(msg), action: 'delete',
      });
      setInfo(res.checks || []);
      setEstado('idle');
      // Plazo vencido: aviso visible, no solo la letra pequeña junto al botón.
      if (res.aviso) showToast(res.aviso, undefined, { fijo: true });
    } catch { setEstado('error'); }
  }, [msg]);

  const recuperar = React.useCallback(async () => {
    setEstado('recalling');
    try {
      const res = await api.post<RespuestaRecuperar>('/mail/recall', {
        message_id: msg.message_id, recipients: destinatariosDe(msg), action: 'delete',
      });
      setInfo((res.results || []).map((r) => ({ ...r, can_recall: r.status === 'recalled' })));
      setEstado('done');
      if ((res.results || []).length > 0 && (res.results || []).every((r) => r.status === 'fuera_de_plazo')) {
        showToast(res.message, undefined, { fijo: true });
      }
      if (res.movido_a_borradores) {
        setMovido(true);
        showToast('Mensaje recuperado. Lo encontrará en Borradores para corregirlo y volverlo a enviar.');
        // El correo ya no está en Enviados: se cierra y se refresca la lista.
        useMailStore.getState().setSelectedMessage(null);
        window.dispatchEvent(new CustomEvent('refresh-messages'));
      }
    } catch { setEstado('error'); }
  }, [msg]);

  // Borrador nacido de una recuperación: se señala al abrirlo.
  if (folder === 'Drafts') {
    if (!(msg.flags || []).includes(KEYWORD_RECUPERADO)) return null;
    return (
      <span style={{ marginLeft: 'auto', fontSize: 12, color: '#8a5a00', fontWeight: 600 }} title="Este borrador es el correo que recuperó de sus destinatarios">
        Mensaje recuperado: corríjalo y vuelva a enviarlo
      </span>
    );
  }

  if (folder !== 'Sent') return null;

  return (
    <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
      {estado === 'done' ? (
        <div style={{ fontSize: 11, color: '#605e5c' }}>
          <div style={{ color: '#107c10', fontWeight: 600, fontSize: 12 }}>
            {movido ? 'Mensaje recuperado (ahora en Borradores)' : 'Recuperación terminada'}
          </div>
          {info.map((r, i) => <div key={i}>{r.recipient}: {textoResultado(r)}</div>)}
        </div>
      ) : estado === 'error' ? (
        <span style={{ fontSize: 12, color: '#d13438' }}>Error al recuperar</span>
      ) : info.length > 0 ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ fontSize: 11, color: '#605e5c' }}>
            {info.map((r, i) => <div key={i}>{r.recipient}: {textoComprobacion(r)}</div>)}
          </div>
          {info.some((r) => r.can_recall || r.can_request) && (
            <button type="button" onClick={recuperar} disabled={estado === 'recalling'}
              style={{ ...estiloBoton, background: '#d13438' }}>
              {estado === 'recalling' ? 'Recuperando...' : 'Confirmar recuperación'}
            </button>
          )}
        </div>
      ) : (
        <button type="button" onClick={comprobar} disabled={estado === 'checking'}
          style={{ ...estiloBoton, background: '#ca5010', display: 'flex', alignItems: 'center', gap: 4 }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
          </svg>
          {estado === 'checking' ? 'Verificando...' : 'Recuperar mensaje'}
        </button>
      )}
    </div>
  );
}
