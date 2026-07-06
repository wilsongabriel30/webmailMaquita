import { useEffect, useState } from 'react';

/* Chat institucional flotante — disponible en TODAS las vistas del correo.
   Es el chat del sistema central de la organización, servido bajo este mismo
   dominio (/chat/) con la identidad de la sesión del correo (puente JWT).
   AUTODETECTA si la instalación tiene chat: si /api/chat no responde (p. ej.
   instalaciones del proyecto sin sistema central), el botón NO aparece. */

export function ChatFlotante() {
  const [disponible, setDisponible] = useState(false);
  const [abierto, setAbierto] = useState(false);
  const [cargado, setCargado] = useState(false);

  useEffect(() => {
    fetch('/api/chat/conversations?limit=1', { credentials: 'include' })
      .then(r => setDisponible(r.ok))
      .catch(() => setDisponible(false));
  }, []);

  if (!disponible) return null;

  return (
    <>
      {/* Panel */}
      <div style={{
        position: 'fixed', bottom: 84, right: 20, width: 400, height: 560,
        maxWidth: 'calc(100vw - 40px)', maxHeight: 'calc(100vh - 120px)',
        borderRadius: 12, boxShadow: '0 8px 32px rgba(0,0,0,.28)',
        overflow: 'hidden', zIndex: 9998, background: '#fff',
        display: abierto ? 'block' : 'none',
      }}>
        {(abierto || cargado) && (
          <iframe src="/chat/?embed=1" title="Chat institucional"
            onLoad={() => setCargado(true)}
            style={{ width: '100%', height: '100%', border: 0 }} />
        )}
      </div>
      {/* Botón flotante */}
      <button onClick={() => setAbierto(v => !v)}
        title={abierto ? 'Cerrar el chat' : 'Chat institucional — habla con tus compañeros'}
        style={{
          position: 'fixed', bottom: 20, right: 20, width: 52, height: 52,
          borderRadius: '50%', border: 0, cursor: 'pointer', zIndex: 9999,
          background: '#0078d4', color: '#fff', fontSize: 22,
          boxShadow: '0 4px 16px rgba(0,120,212,.45)',
        }}>
        {abierto ? '✕' : '💬'}
      </button>
    </>
  );
}
