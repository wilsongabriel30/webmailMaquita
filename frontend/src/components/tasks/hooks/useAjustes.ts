// Configuración personal de Tareas (la ⚙ de la barra, F6). Vive en el servidor (GET/PUT /tasks/ajustes) para que
// siga a la persona en cualquier equipo; mientras llega, se usan los valores de fábrica.
// Se envía solo lo que cambia y se vuelve a leer al abrir la ⚙: «Avisos por correo» también se cambia desde
// «Compartir lista» (o desde otra pestaña), y reenviar la copia vieja lo desactivaba sin aviso (05/11/2026).
import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../../../api/client';

export interface Ajustes {
  confirmar_eliminar: boolean;
  importantes_arriba: boolean;
  sonido_completar: boolean;
  /** Listas inteligentes ocultas en la barra (Mi día y Tareas siempre se ven). */
  listas_ocultas: string[];
  avisos_correo: boolean;
}

export const AJUSTES_DE_FABRICA: Ajustes = {
  confirmar_eliminar: true, importantes_arriba: false, sonido_completar: true, listas_ocultas: [], avisos_correo: false,
};

export function useAjustes() {
  const [ajustes, setAjustes] = useState<Ajustes>(AJUSTES_DE_FABRICA);
  const [error, setError] = useState('');
  const actuales = useRef(ajustes);
  useEffect(() => { actuales.current = ajustes; }, [ajustes]);

  const recargar = useCallback(async () => {
    try { setAjustes(await api.get<Ajustes>('/tasks/ajustes')); } catch { /* se queda lo que había */ }
  }, []);

  useEffect(() => {
    let vigente = true;
    api.get<Ajustes>('/tasks/ajustes').then(a => { if (vigente) setAjustes(a); }).catch(() => {});
    return () => { vigente = false; };
  }, []);

  const cambiar = useCallback(async (cambios: Partial<Ajustes>) => {
    const antes = actuales.current;
    setAjustes(a => ({ ...a, ...cambios }));
    try {
      setAjustes(await api.put<Ajustes>('/tasks/ajustes', cambios));
      setError('');
    } catch {
      // Se deshace solo lo que se intentó cambiar (otro cambio hecho mientras tanto se respeta).
      const deshacer = Object.fromEntries(Object.keys(cambios).map(k => [k, antes[k as keyof Ajustes]]));
      setAjustes(a => ({ ...a, ...deshacer }));
      setError('No se pudo guardar la configuración');
    }
  }, []);

  return { ajustes, cambiar, error, recargar };
}
