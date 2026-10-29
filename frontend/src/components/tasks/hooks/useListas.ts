// Listas propias y grupos de la barra lateral de Tareas: carga, cambios y orden (F2, To Do).
import { useCallback, useEffect, useState } from 'react';
import { api } from '../../../api/client';
import type { Orden, TaskGroup, TaskList } from '../types';
import type { Elemento } from '../components/barraOrden';

export function useListas(alCambiar: () => void) {
  const [listas, setListas] = useState<TaskList[]>([]);
  const [grupos, setGrupos] = useState<TaskGroup[]>([]);
  const [error, setError] = useState('');

  // Sin listas (falla de red): la barra sigue funcionando con las listas inteligentes.
  const pedir = () => Promise.all([api.get<TaskList[]>('/tasks/lists'), api.get<TaskGroup[]>('/tasks/groups')]);

  const recargar = useCallback(async () => {
    try {
      const [l, g] = await pedir();
      setListas(l);
      setGrupos(g);
    } catch { /* se conserva lo que había */ }
    alCambiar();
  }, [alCambiar]);

  useEffect(() => {
    let vigente = true;
    pedir().then(([l, g]) => { if (vigente) { setListas(l); setGrupos(g); } }).catch(() => {});
    return () => { vigente = false; };
  }, []);

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
    duplicarLista: async (id: string) => {
      let copia: TaskList | null = null;
      await intentar(async () => { copia = await api.post<TaskList>(`/tasks/lists/${id}/duplicar`); }, 'No se pudo duplicar la lista');
      return copia as TaskList | null;
    },
    eliminarLista: (id: string) => intentar(() => api.del(`/tasks/lists/${id}`), 'No se pudo eliminar la lista'),
    crearGrupo: (name: string) => intentar(() => api.post('/tasks/groups', { name }), 'No se pudo crear el grupo'),
    renombrarGrupo: (id: string, name: string) =>
      intentar(() => api.patch(`/tasks/groups/${id}`, { name }), 'No se pudo cambiar el nombre del grupo'),
    eliminarGrupo: (id: string) => intentar(() => api.del(`/tasks/groups/${id}`), 'No se pudo eliminar el grupo'),
    guardarBarra: (elementos: Elemento[]) =>
      intentar(() => api.put('/tasks/sidebar/orden', { elementos }), 'No se pudo guardar el orden de las listas'),
  };
}
