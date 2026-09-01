// Bandeja de salida + estado del correo sin conexión (T-35). Se abre desde la franja OfflineBanner.
import { useEffect, useState } from 'react';
import { getOutboxEmails, removeFromOutbox, type OutboxEmail } from '../../lib/offlineStore';
import { reintentarEnvio, syncOutbox, TEXTO_ESTADO, causaSinConexion, hayConexion } from '../../lib/syncQueue';
import { estadoDescarga, descargarAhora, configurarDescarga, type EstadoDescarga } from '../../lib/descargaOffline';

export function BandejaSalida({ onCerrar }: { onCerrar: () => void }) {
  const [cola, setCola] = useState<OutboxEmail[]>([]);
  const [desc, setDesc] = useState<EstadoDescarga>(estadoDescarga());
  const [enLinea, setEnLinea] = useState(hayConexion());
  const cargar = () => getOutboxEmails().then(setCola).catch(() => setCola([]));
  useEffect(() => {
    cargar();
    const h = () => cargar(); const d = (e: Event) => setDesc((e as CustomEvent).detail);
    const on = () => setEnLinea(hayConexion()), off = () => setEnLinea(hayConexion());
    window.addEventListener('conexion-cambio', on);
    window.addEventListener('outbox-cambio', h); window.addEventListener('offline-sync-complete', h); window.addEventListener('offline-descarga', d);
    window.addEventListener('online', on); window.addEventListener('offline', off);
    const iv = window.setInterval(cargar, 5000);
    return () => { window.removeEventListener('outbox-cambio', h); window.removeEventListener('offline-sync-complete', h); window.removeEventListener('offline-descarga', d); window.removeEventListener('online', on); window.removeEventListener('offline', off); window.removeEventListener('conexion-cambio', on); window.clearInterval(iv); };
  }, []);
  const fecha = (t: number) => new Date(t).toLocaleString('es-EC', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
  const btn: React.CSSProperties = { border: '1px solid #c8c6c4', background: '#fff', borderRadius: 4, padding: '3px 8px', fontSize: 12, cursor: 'pointer' };
  return (
    <div data-bandeja-salida style={{ position: 'fixed', right: 16, top: 56, width: 'min(440px, 96vw)', maxHeight: '80vh', overflowY: 'auto', background: '#fff', border: '1px solid #e1dfdd', borderRadius: 8, boxShadow: '0 8px 24px rgba(0,0,0,.18)', zIndex: 900, fontFamily: "'Segoe UI', system-ui, sans-serif", fontSize: 13, color: '#323130' }}>
      <div style={{ display: 'flex', alignItems: 'center', padding: '10px 14px', borderBottom: '1px solid #edebe9' }}>
        <b style={{ flex: 1 }}>Bandeja de salida ({cola.length})</b>
        <button onClick={() => syncOutbox()} style={btn} disabled={!enLinea} title={enLinea ? 'Intentar enviar ahora' : causaSinConexion()}>Enviar ahora</button>
        <button onClick={onCerrar} style={{ ...btn, border: 'none', fontSize: 16, marginLeft: 4 }} aria-label="Cerrar">×</button>
      </div>
      {!enLinea && <div style={{ background: '#fff4ce', padding: '8px 14px' }}>Ahora mismo: {causaSinConexion()}. Lo que envíes queda en cola y sale solo al volver la conexión, aunque cierres la app.</div>}
      {cola.length === 0 && <div style={{ padding: 16, color: '#605e5c' }}>No hay correos pendientes de envío.</div>}
      {cola.map(c => (
        <div key={c.id} style={{ padding: '10px 14px', borderBottom: '1px solid #f3f2f1' }}>
          <div style={{ fontWeight: 600 }}>{c.subject || '(sin asunto)'}</div>
          <div style={{ color: '#605e5c' }}>Para: {c.to.join(', ')} · {fecha(c.createdAt)}{c.attachments?.length ? ` · ${c.attachments.length} adjunto(s)` : ''}</div>
          <div style={{ marginTop: 4, color: c.status === 'failed' ? '#a4262c' : c.status === 'sending' ? '#0078d4' : '#8a6d00', fontWeight: 600 }}>
            {TEXTO_ESTADO[c.status]}{c.status !== 'sending' && c.error ? ` (${c.error})` : ''}
          </div>
          <div style={{ marginTop: 6, display: 'flex', gap: 6 }}>
            {c.status === 'failed' && <button style={btn} onClick={() => reintentarEnvio(c.id).then(cargar)}>Reintentar</button>}
            <button style={{ ...btn, color: '#a4262c' }} onClick={() => { if (confirm('¿Descartar este correo? No se enviará.')) removeFromOutbox(c.id).then(cargar); }}>Descartar</button>
          </div>
        </div>
      ))}
      <div style={{ padding: '10px 14px', background: '#faf9f8', borderTop: '1px solid #edebe9' }}>
        <b>Correo sin conexión</b>
        <div style={{ color: '#605e5c', marginTop: 4 }}>
          {desc.activa ? `Descargando ${desc.carpeta === 'Sent' ? 'enviados' : 'recibidos'}: ${desc.hechos}/${desc.total}` :
            desc.error === 'sin sesión' ? 'Inicia sesión para descargar el correo reciente.' :
            desc.ultima ? `Última descarga: ${fecha(desc.ultima)} (adjuntos guardados en esta sesión: ${desc.adjuntos})` : 'Aún no se ha descargado nada.'}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 6, flexWrap: 'wrap' }}>
          <label>Guardar los últimos <select value={desc.dias} onChange={e => configurarDescarga(parseInt(e.target.value, 10), desc.adjMB)}>{[15, 30, 45, 60].map(d => <option key={d} value={d}>{d}</option>)}</select> días</label>
          <label>adjuntos hasta <select value={desc.adjMB} onChange={e => configurarDescarga(desc.dias, parseInt(e.target.value, 10))}>{[0, 2, 5, 10, 25].map(m => <option key={m} value={m}>{m}</option>)}</select> MB</label>
          <button style={btn} onClick={() => descargarAhora()} disabled={desc.activa || !enLinea}>Descargar ahora</button>
        </div>
      </div>
    </div>
  );
}
