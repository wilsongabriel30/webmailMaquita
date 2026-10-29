// Configuración personal de Tareas (la ⚙ de la barra, F6). Vive en el servidor (GET/PUT /tasks/ajustes) para que
// siga a la persona en cualquier equipo; mientras llega, se usan los valores de fábrica.
import { useCallback, useEffect, useState } from 'react';
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

  useEffect(() => {
    let vigente = true;
    api.get<Ajustes>('/tasks/ajustes').then(a => { if (vigente) setAjustes(a); }).catch(() => {});
    return () => { vigente = false; };
  }, []);

  const cambiar = useCallback(async (cambios: Partial<Ajustes>) => {
    const antes = ajustes;
    const nuevos = { ...ajustes, ...cambios };
    setAjustes(nuevos);
    try {
      setAjustes(await api.put<Ajustes>('/tasks/ajustes', nuevos));
      setError('');
    } catch {
      setAjustes(antes);
      setError('No se pudo guardar la configuración');
    }
  }, [ajustes]);

  return { ajustes, cambiar, error };
}
