// Franja de estado de conexión y cola de envío (T-35). Sin red: causa clara y acceso a la bandeja de salida;
// con red pero con correos en cola o fallidos: también se muestra para que nada quede olvidado.
import { useState, useEffect } from "react";
import { getPendingActions, getOutboxEmails } from "../../lib/offlineStore";
import { BandejaSalida } from "./BandejaSalida";
import { estadoConexion, textoCausa } from "../../lib/conexion";

export function OfflineBanner() {
  const [isOnline, setIsOnline] = useState(estadoConexion().hayConexion);
  const [causa, setCausa] = useState(textoCausa());
  const [pendingActions, setPendingActions] = useState(0);
  const [cola, setCola] = useState({ pendientes: 0, fallidos: 0 });
  const [abierta, setAbierta] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);

  useEffect(() => {
    const act = () => { setIsOnline(estadoConexion().hayConexion); setCausa(textoCausa()); };
    window.addEventListener("online", act); window.addEventListener("offline", act); window.addEventListener("conexion-cambio", act);
    return () => { window.removeEventListener("online", act); window.removeEventListener("offline", act); window.removeEventListener("conexion-cambio", act); };
  }, []);
  useEffect(() => {
    const actualizar = () => {
      getPendingActions().then(a => setPendingActions(a.length)).catch(() => {});
      getOutboxEmails().then(e => setCola({ pendientes: e.filter(x => x.status !== 'failed').length, fallidos: e.filter(x => x.status === 'failed').length })).catch(() => {});
    };
    actualizar();
    window.addEventListener('outbox-cambio', actualizar); window.addEventListener('offline-sync-complete', actualizar);
    const iv = setInterval(actualizar, 5000);
    return () => { clearInterval(iv); window.removeEventListener('outbox-cambio', actualizar); window.removeEventListener('offline-sync-complete', actualizar); };
  }, [isOnline]);
  useEffect(() => {
    const handler = (e: Event) => {
      const d = (e as CustomEvent).detail; const partes: string[] = [];
      if (d.sent > 0) partes.push(`${d.sent} correo(s) enviado(s) desde la bandeja de salida`);
      if (d.actions > 0) partes.push(`${d.actions} acción(es) sincronizada(s)`);
      if (partes.length) { setSyncResult(partes.join(', ')); setTimeout(() => setSyncResult(null), 6000); }
    };
    window.addEventListener('offline-sync-complete', handler);
    return () => window.removeEventListener('offline-sync-complete', handler);
  }, []);
  useEffect(() => {
    const h = () => setAbierta(v => !v);
    window.addEventListener('abrir-bandeja-salida', h);
    return () => window.removeEventListener('abrir-bandeja-salida', h);
  }, []);

  const panel = abierta ? <BandejaSalida onCerrar={() => setAbierta(false)} /> : null;
  const enlace = <button data-ver-bandeja onClick={() => setAbierta(v => !v)} style={{ background: 'rgba(255,255,255,.25)', border: '1px solid rgba(255,255,255,.6)', color: '#fff', borderRadius: 4, padding: '1px 8px', cursor: 'pointer', fontSize: 12, marginLeft: 8 }}>Ver bandeja de salida</button>;

  if (syncResult && isOnline) {
    return (<>
      <div className="bg-green-600 text-white text-center py-2 px-4 text-sm font-medium shrink-0 flex items-center justify-center gap-2">Sincronizado: {syncResult}</div>{panel}
    </>);
  }
  if (isOnline) {
    if (cola.pendientes === 0 && cola.fallidos === 0) return panel;
    return (<>
      <div className="text-white text-center py-2 px-4 text-sm font-medium shrink-0 flex items-center justify-center gap-2" style={{ background: cola.fallidos ? '#a4262c' : '#8a6d00' }}>
        {cola.fallidos ? `${cola.fallidos} correo(s) no se pudieron entregar` : `${cola.pendientes} correo(s) en cola: se enviarán en cuanto el servidor responda`}{enlace}
      </div>{panel}
    </>);
  }
  const detalles: string[] = [];
  if (pendingActions > 0) detalles.push(`${pendingActions} acción(es) pendiente(s)`);
  if (cola.pendientes > 0) detalles.push(`${cola.pendientes} correo(s) en cola`);
  return (<>
    <div data-sin-conexion className="bg-amber-500 text-white text-center py-2 px-4 text-sm font-medium shrink-0 flex items-center justify-center gap-2">
      <span>{causa === 'sin internet en este equipo' ? 'Sin internet en este equipo' : 'El servidor de correo no responde'}: viendo el correo descargado; lo nuevo llegará al reconectar.{detalles.length ? ` (${detalles.join(', ')})` : ''}</span>{enlace}
    </div>{panel}
  </>);
}
