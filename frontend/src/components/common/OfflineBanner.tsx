import { useState, useEffect } from "react";
import { getPendingActions } from "../../lib/offlineStore";

export function OfflineBanner() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [pendingActions, setPendingActions] = useState(0);

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
    if (!isOnline) {
      getPendingActions().then((actions) => setPendingActions(actions.length));
    }
  }, [isOnline]);

  if (isOnline) return null;

  return (
    <div className="bg-amber-500 text-white text-center py-2 px-4 text-sm font-medium shrink-0">
      Sin conexion — Mostrando correos en cache. Las acciones se sincronizaran al reconectar.
      {pendingActions > 0 && " (" + pendingActions + " acciones pendientes)"}
    </div>
  );
}
