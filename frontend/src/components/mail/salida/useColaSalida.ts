/**
 * useColaSalida.ts — Lee la cola de salida del equipo (IndexedDB) y la mantiene al día (24/11/2026).
 *
 * Devuelve solo los correos de la sesión abierta (T-73) y se vuelve a cargar sola cuando la cola
 * cambia (evento `outbox-cambio`, que emite syncQueue al enviar, reintentar o descartar).
 * La usan la fila del riel, la lista y el panel de lectura de la bandeja de salida.
 */
import { useEffect, useState } from 'react';
import { getOutboxEmails, type OutboxEmail } from '../../../lib/offlineStore';
import { esDeLaSesion } from '../../../lib/sesionActual';

const CAMBIO = 'outbox-cambio';

export function useColaSalida(activo: boolean = true) {
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
