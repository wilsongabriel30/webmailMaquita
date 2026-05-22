import { useState, useEffect } from "react";
import { getPendingActions, getOutboxCount } from "../../lib/offlineStore";

export function OfflineBanner() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [pendingActions, setPendingActions] = useState(0);
  const [outboxCount, setOutboxCount] = useState(0);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  useEffect(() => {
    const updateCounts = () => {
      getPendingActions().then((actions) => setPendingActions(actions.length));
      getOutboxCount().then((count) => setOutboxCount(count));
    };
    updateCounts();
    // Refresh counts periodically when offline
    if (!isOnline) {
      const interval = setInterval(updateCounts, 5000);
      return () => clearInterval(interval);
    }
  }, [isOnline]);

  // Show sync success notification briefly
  const [syncResult, setSyncResult] = useState<string | null>(null);
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      const parts: string[] = [];
      if (detail.sent > 0) parts.push(`${detail.sent} correo(s) enviado(s)`);
      if (detail.actions > 0) parts.push(`${detail.actions} accion(es) sincronizada(s)`);
      if (parts.length > 0) {
        setSyncResult(parts.join(', '));
        setTimeout(() => setSyncResult(null), 5000);
      }
    };
    window.addEventListener('offline-sync-complete', handler);
    return () => window.removeEventListener('offline-sync-complete', handler);
  }, []);

  // Show sync success banner
  if (syncResult && isOnline) {
    return (
      <div className="bg-green-600 text-white text-center py-2 px-4 text-sm font-medium shrink-0 flex items-center justify-center gap-2">
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
        Sincronizado: {syncResult}
      </div>
    );
  }

  if (isOnline) return null;

  const details: string[] = [];
  if (pendingActions > 0) details.push(`${pendingActions} accion(es) pendiente(s)`);
  if (outboxCount > 0) details.push(`${outboxCount} correo(s) en bandeja de salida`);

  return (
    <div className="bg-amber-500 text-white text-center py-2 px-4 text-sm font-medium shrink-0 flex items-center justify-center gap-2">
      <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M18.364 5.636a9 9 0 010 12.728M15.536 8.464a5 5 0 010 7.072M12 12h.01" />
      </svg>
      <span>
        Sin conexion — Mostrando correos en cache.
        {details.length > 0 && ` (${details.join(', ')})`}
        {' '}Se sincronizara al reconectar.
      </span>
    </div>
  );
}
