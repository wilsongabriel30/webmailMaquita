/**
 * Estado del índice del buzón (RAG) y sincronización en segundo plano.
 * Misma lógica que la página /asistente (components/rag/RagAssistant.tsx): /rag/status y
 * /rag/sync, consultando el avance cada 3 s mientras la sincronización corre.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../../api/client';

export interface Sincronizacion {
  estado: 'en_curso' | 'listo' | 'error';
  leidos: number;
  indexed: number;
  errores: number;
  mensaje: string;
  total?: number;
}

export interface EstadoIndice {
  enabled: boolean;
  indexed: number;
  sync?: Sincronizacion | null;
}

export function useEstadoIndice(activo: boolean) {
  const [estado, setEstado] = useState<EstadoIndice | null>(null);
  const [aviso, setAviso] = useState('');
  const [iniciando, setIniciando] = useState(false);
  const sondeo = useRef<number | null>(null);

  const cargar = useCallback(
    () => api.get<EstadoIndice>('/rag/status')
      .then((s) => { setEstado(s); return s; })
      .catch(() => { setEstado({ enabled: false, indexed: 0 }); return null; }),
    [],
  );

  const pararSondeo = () => {
    if (sondeo.current) { window.clearInterval(sondeo.current); sondeo.current = null; }
  };

  const seguir = useCallback(() => {
    pararSondeo();
    sondeo.current = window.setInterval(async () => {
      const s = await cargar();
      const sy = s?.sync;
      if (!sy || sy.estado !== 'en_curso') {
        pararSondeo();
        if (sy?.estado === 'error') setAviso(sy.mensaje || 'La preparación de tu bandeja falló.');
        else if (sy?.estado === 'listo') setAviso('Tu bandeja está lista para preguntas.');
      }
    }, 3000);
  }, [cargar]);

  useEffect(() => {
    if (!activo) return;
    cargar().then((s) => { if (s?.sync?.estado === 'en_curso') seguir(); });
    return () => pararSondeo();
  }, [activo, cargar, seguir]);

  const sincronizar = useCallback(async () => {
    setIniciando(true); setAviso('');
    try {
      const r = await api.post<{ started: boolean; error?: string }>('/rag/sync', {});
      if (r?.error) setAviso(r.error);
      else seguir();
    } catch {
      setAviso('No se pudo empezar a preparar tu bandeja. Inténtalo de nuevo en un momento.');
    }
    setIniciando(false);
  }, [seguir]);

  const sincronizando = iniciando || estado?.sync?.estado === 'en_curso';
  return { estado, aviso, sincronizando, sincronizar };
}
