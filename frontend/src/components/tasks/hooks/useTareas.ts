// Tareas de la vista abierta (lista inteligente, lista propia o búsqueda) y lo que se hace con ellas.
// Salió de TasksView (F3): los cambios se ven al instante y, si el servidor falla, se vuelve a pedir la lista.
import { useCallback, useEffect, useState } from 'react';
import { api } from '../../../api/client';
import type { ActiveView, Task } from '../types';

// Listas inteligentes: cada una tiene su ruta /tasks/views/<id> («tasks» es la bandeja por defecto).
export const VISTAS_INTELIGENTES = ['my-day', 'important', 'planned', 'assigned', 'flagged', 'tasks'];

// El cliente API deja en el mensaje del error lo que explicó el servidor.
function mensaje(e: unknown, defecto: string): string {
  return e instanceof Error && e.message ? e.message : defecto;
}

export function useTareas(activeView: ActiveView, busqueda: string, alCambiar: () => void) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  // Cargando = todavía no llegó la respuesta para la vista (o búsqueda) que se está mirando.
  const clave = `${activeView}|${busqueda.trim()}`;
  const [cargada, setCargada] = useState('');
  const loading = cargada !== clave;
  const [error, setError] = useState('');

  const pedir = useCallback((): Promise<Task[]> => {
    const texto = busqueda.trim();
    if (texto) return api.get<Task[]>(`/tasks/buscar?q=${encodeURIComponent(texto)}`);
    // «seguimiento» es una vista (SeguimientoVista carga sus datos), no una lista: pedirla como lista daba 400
    if (activeView === 'seguimiento') return Promise.resolve([]);
    if (VISTAS_INTELIGENTES.includes(activeView)) return api.get<Task[]>(`/tasks/views/${activeView}`);
    return api.get<Task[]>(`/tasks/lists/${activeView}/tasks`);
  }, [activeView, busqueda]);

  const fetchTasks = useCallback(async () => {
    try {
      const r = await pedir();
      setTasks(r);
      // El panel abierto se pone al día (otra persona pudo cambiar la tarea).
      setSelectedTask(prev => (prev ? r.find(t => t.id === prev.id) ?? prev : prev));
    } catch {
      setTasks([]);
    }
  }, [pedir]);

  useEffect(() => {
    let vigente = true;
    pedir()
      .catch(() => [] as Task[])
      .then(r => { if (vigente) { setTasks(r); setCargada(clave); } });
    return () => { vigente = false; };
  }, [pedir, clave]);

  // Mantiene el panel de detalle al día con lo que se cambió en la lista.
  const cambiarLocal = (id: string, cambio: (t: Task) => Task) => {
    setTasks(prev => prev.map(t => (t.id === id ? cambio(t) : t)));
    setSelectedTask(prev => (prev?.id === id ? cambio(prev) : prev));
  };

  const addTask = async (title: string, dueDate?: string, reminder?: string, recurrence?: string) => {
    try {
      const listId = (!['my-day', 'important', 'planned', 'assigned', 'flagged', 'tasks', 'seguimiento'].includes(activeView))
        ? activeView : undefined;
      const payload: Record<string, unknown> = { title };
      if (dueDate) payload.due_date = dueDate;
      if (reminder) payload.reminder = reminder;
      if (recurrence) payload.recurrence = recurrence;
      if (activeView === 'my-day') payload.my_day = true;
      if (activeView === 'important') payload.important = true;
      if (activeView === 'planned' && !dueDate) payload.due_date = new Date().toISOString().slice(0, 10);

      if (listId) {
        await api.post(`/tasks/lists/${listId}/tasks`, payload);
      } else {
        await api.post('/tasks/tasks', payload);
      }
      fetchTasks();
      alCambiar();
    } catch (e) {
      setError('Error al agregar tarea: ' + mensaje(e, 'desconocido'));
    }
  };

  const toggleTask = async (id: string) => {
    const tarea = tasks.find(t => t.id === id);
    cambiarLocal(id, t => ({ ...t, completed: !t.completed }));
    try {
      await api.patch(`/tasks/tasks/${id}/toggle`);
      // Al completar una tarea que se repite, el servidor crea la siguiente: hay que traerla.
      if (tarea?.recurrence && !tarea.completed) fetchTasks();
      alCambiar();
    } catch {
      fetchTasks();
    }
  };

  const toggleImportant = async (id: string) => {
    cambiarLocal(id, t => ({ ...t, important: !t.important }));
    try {
      await api.patch(`/tasks/tasks/${id}/important`);
      alCambiar();
    } catch {
      fetchTasks();
    }
  };

  const updateTask = async (id: string, data: Partial<Task>) => {
    cambiarLocal(id, t => ({ ...t, ...data }));
    const payload = Object.fromEntries(Object.entries(data).filter(([, v]) => v !== undefined));
    if (Object.keys(payload).length === 0) return; // nada que actualizar -> no PATCH vacio
    try {
      await api.patch(`/tasks/tasks/${id}`, payload);
      if ('my_day' in data || 'completed' in data) fetchTasks();
      alCambiar();
    } catch (e) {
      setError('No se pudo guardar el cambio: ' + mensaje(e, 'desconocido'));
      fetchTasks();
    }
  };

  const deleteTask = async (id: string) => {
    setSelectedTask(null);
    setTasks(prev => prev.filter(t => t.id !== id));
    try {
      await api.del(`/tasks/tasks/${id}`);
      alCambiar();
    } catch {
      fetchTasks();
    }
  };

  /** Mover a otra lista (arrastrando a la barra o con «Mover a…»). */
  const moverTarea = async (id: string, listId: string) => {
    const tarea = tasks.find(t => t.id === id);
    if (!tarea || tarea.list_id === listId) return;
    // En una lista propia la tarea se va de la vista; en las inteligentes se queda con su nueva lista.
    if (!VISTAS_INTELIGENTES.includes(activeView) && !busqueda.trim()) {
      setTasks(prev => prev.filter(t => t.id !== id));
      setSelectedTask(prev => (prev?.id === id ? null : prev));
    }
    try {
      const movida = await api.patch<Task>(`/tasks/tasks/${id}/lista`, { list_id: listId });
      cambiarLocal(id, () => movida);
      alCambiar();
    } catch (e) {
      setError('No se pudo mover la tarea: ' + mensaje(e, 'desconocido'));
      fetchTasks();
    }
  };

  /** La tarea volvió del servidor (p. ej. tras asignarla): se reemplaza tal cual. */
  const reemplazarTarea = (t: Task) => cambiarLocal(t.id, () => t);

  return {
    tasks, setTasks, selectedTask, setSelectedTask, loading, error, setError,
    fetchTasks, addTask, toggleTask, toggleImportant, updateTask, deleteTask, moverTarea, reemplazarTarea,
  };
}
