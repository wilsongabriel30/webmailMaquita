// Listas propias y grupos de la barra lateral de Tareas: carga, cambios y orden (F2, To Do).
import { useCallback, useEffect, useState } from 'react';
import { api } from '../../../api/client';
import type { Orden, TaskGroup, TaskList } from '../types';
import type { Elemento } from '../components/barraOrden';

export function useListas(alCambiar: () => void) {
  const [listas, setListas] = useState<TaskList[]>([]);
  const [grupos, setGrupos] = useState<TaskGroup[]>([]);
  const [error, setError] = useState('');

  const recargar = useCallback(async () => {
    try {
      const [l, g] = await Promise.all([api.get<TaskList[]>('/tasks/lists'), api.get<TaskGroup[]>('/tasks/groups')]);
      setListas(l);
      setGrupos(g);
    } catch {
      // sin listas: la barra sigue funcionando con las listas inteligentes
    }
    alCambiar();
  }, [alCambiar]);

  useEffect(() => { void recargar(); }, [recargar]);

  const intentar = useCallback(async (accion: () => Promise<unknown>, falla: string) => {
    try {
      await accion();
      setError('');
    } catch {
      setError(falla);
    }
    await recargar();
  }, [recargar]);

  return {
    listas,
    grupos,
    error,
    limpiarError: () => setError(''),
    recargar,
    crearLista: async (name: string) => {
      let nueva: TaskList | null = null;
      await intentar(async () => { nueva = await api.post<TaskList>('/tasks/lists', { name }); }, 'No se pudo crear la lista');
      return nueva as TaskList | null;
    },
    cambiarLista: (id: string, cambios: { name?: string; color?: string; sort_by?: Orden }) =>
      intentar(() => api.patch(`/tasks/lists/${id}`, cambios), 'No se pudo cambiar la lista'),
    eliminarLista: (id: string) => intentar(() => api.del(`/tasks/lists/${id}`), 'No se pudo eliminar la lista'),
    crearGrupo: (name: string) => intentar(() => api.post('/tasks/groups', { name }), 'No se pudo crear el grupo'),
    renombrarGrupo: (id: string, name: string) =>
      intentar(() => api.patch(`/tasks/groups/${id}`, { name }), 'No se pudo cambiar el nombre del grupo'),
    eliminarGrupo: (id: string) => intentar(() => api.del(`/tasks/groups/${id}`), 'No se pudo eliminar el grupo'),
    guardarBarra: (elementos: Elemento[]) =>
      intentar(() => api.put('/tasks/sidebar/orden', { elementos }), 'No se pudo guardar el orden de las listas'),
  };
}
