import { useState, useEffect, useCallback } from 'react';
import type { Task, TaskList, ActiveView } from './types';
import { COLORS } from './types';
import { TasksSidebar } from './components/TasksSidebar';
import { TaskListHeader } from './components/TaskListHeader';
import { TaskInput } from './components/TaskInput';
import { TaskItem } from './components/TaskItem';
import { TaskDetailPanel } from './components/TaskDetailPanel';
import { EmptyState } from './components/EmptyState';
import { TaskGrid } from './components/TaskGrid';
import { leerModoVista, guardarModoVista, type ModoVista } from './components/modoVista';
import { useConteosVistas } from './hooks/useConteosVistas';
import { agruparPlaneado } from './components/agruparPlaneado';
import { api } from '../../api/client';
import { SeguimientoVista } from '../tareas/SeguimientoVista';

const _params = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null;
const VISTA_INICIAL: ActiveView | null = _params?.get('vista') === 'seguimiento' || _params?.get('tarea') ? 'seguimiento' : null;
const TAREA_INICIAL = _params?.get('tarea') || null;
// Listas inteligentes: cada una tiene su ruta /tasks/views/<id> («tasks» es la bandeja por defecto).
const VISTAS_INTELIGENTES = ['my-day', 'important', 'planned', 'assigned', 'flagged', 'tasks'];

export function TasksView() {
  const [activeView, setActiveView] = useState<ActiveView>(VISTA_INICIAL || 'my-day');
  const [yo] = useState<string>(() => { try { return localStorage.getItem('user_email') || (JSON.parse(localStorage.getItem('user') || '{}').email) || ''; } catch { return ''; } });
  const [sidebarVisible, setSidebarVisible] = useState(() => typeof window === 'undefined' || window.innerWidth >= 768);
  useEffect(() => {
    const h = () => setSidebarVisible(v => !v);
    window.addEventListener('toggle-tasks-sidebar', h);
    return () => window.removeEventListener('toggle-tasks-sidebar', h);
  }, []);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [customLists, setCustomLists] = useState<TaskList[]>([]);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [sortBy, setSortBy] = useState('date');
  const { conteos, recargarConteos } = useConteosVistas(activeView);
  const [modo, setModo] = useState<ModoVista>(leerModoVista);
  const cambiarModo = (m: ModoVista) => { setModo(m); guardarModoVista(m); };

  // ─── Data fetching ─────────────────────────────────────────────

  const fetchLists = useCallback(async () => {
    try {
      const lists = await api.get<TaskList[]>('/tasks/lists');
      const custom = lists.filter(l => l.list_type === 'custom');
      setCustomLists(custom);
    } catch {
      // API not ready yet, use empty state
      setCustomLists([]);
    }
    void recargarConteos();
  }, [recargarConteos]);

  const fetchTasks = useCallback(async () => {
    // «seguimiento» es una vista (SeguimientoVista carga sus datos), no una lista: pedirla como lista daba 400
    if (activeView === 'seguimiento') { setTasks([]); setLoading(false); return; }
    setLoading(true);
    setError('');
    try {
      let result: Task[];
      if (VISTAS_INTELIGENTES.includes(activeView)) {
        result = await api.get<Task[]>(`/tasks/views/${activeView}`);
      } else {
        // Custom list
        result = await api.get<Task[]>(`/tasks/lists/${activeView}/tasks`);
      }
      setTasks(result);
    } catch {
      setTasks([]);
      // Don't show error if API is not ready
    } finally {
      setLoading(false);
    }
  }, [activeView]);

  useEffect(() => { fetchLists(); }, [fetchLists]);
  useEffect(() => { fetchTasks(); }, [fetchTasks]);

  // Escuchar evento de refresh desde WebSocket (tarea asignada/actualizada)
  useEffect(() => {
    const handler = () => { fetchTasks(); fetchLists(); };
    window.addEventListener('refresh-tasks', handler);
    return () => window.removeEventListener('refresh-tasks', handler);
  }, [fetchTasks, fetchLists]);

  // ─── Task actions ──────────────────────────────────────────────

  const addTask = async (title: string, dueDate?: string, reminder?: string) => {
    try {
      const listId = (!['my-day', 'important', 'planned', 'assigned', 'flagged', 'tasks', 'seguimiento'].includes(activeView))
        ? activeView : undefined;
      const payload: Record<string, unknown> = { title };
      if (dueDate) payload.due_date = dueDate;
      if (reminder) payload.reminder = reminder;
      if (activeView === 'my-day') payload.my_day = true;
      if (activeView === 'important') payload.important = true;
      if (activeView === 'planned' && !dueDate) payload.due_date = new Date().toISOString().slice(0, 10);

      if (listId) {
        await api.post(`/tasks/lists/${listId}/tasks`, payload);
      } else {
        await api.post('/tasks/tasks', payload);
      }
      fetchTasks();
      fetchLists();
    } catch (e) {
      setError('Error al agregar tarea: ' + (e instanceof Error ? e.message : 'desconocido'));
    }
  };

  const toggleTask = async (id: string) => {
    // Optimistic update
    setTasks(prev => prev.map(t => t.id === id ? { ...t, completed: !t.completed } : t));
    if (selectedTask?.id === id) setSelectedTask(prev => prev ? { ...prev, completed: !prev.completed } : null);
    try {
      await api.patch(`/tasks/tasks/${id}/toggle`);
      fetchLists();
    } catch {
      fetchTasks(); // revert
    }
  };

  const toggleImportant = async (id: string) => {
    setTasks(prev => prev.map(t => t.id === id ? { ...t, important: !t.important } : t));
    if (selectedTask?.id === id) setSelectedTask(prev => prev ? { ...prev, important: !prev.important } : null);
    try {
      await api.patch(`/tasks/tasks/${id}/important`);
      fetchLists();
    } catch {
      fetchTasks();
    }
  };

  const updateTask = async (id: string, data: Partial<Task>) => {
    setTasks(prev => prev.map(t => t.id === id ? { ...t, ...data } : t));
    if (selectedTask?.id === id) setSelectedTask(prev => prev ? { ...prev, ...data } : null);
    const payload = Object.fromEntries(Object.entries(data).filter(([, v]) => v !== undefined));
    if (Object.keys(payload).length === 0) return; // nada que actualizar -> no PATCH vacio
    try {
      await api.patch(`/tasks/tasks/${id}`, payload);
      if ('my_day' in data) fetchTasks();
      fetchLists();
    } catch {
      fetchTasks();
    }
  };

  const deleteTask = async (id: string) => {
    setSelectedTask(null);
    setTasks(prev => prev.filter(t => t.id !== id));
    try {
      await api.del(`/tasks/tasks/${id}`);
      fetchLists();
    } catch {
      fetchTasks();
    }
  };

  const createList = async (name: string) => {
    try {
      await api.post('/tasks/lists', { name });
      fetchLists();
    } catch {
      setError('No se pudo crear la lista');
    }
  };

  const deleteList = async (id: string) => {
    if (!confirm('¿Eliminar esta lista y todas sus tareas?')) return;
    try {
      await api.del(`/tasks/lists/${id}`);
      if (activeView === id) setActiveView('tasks');
      fetchLists();
    } catch {
      setError('No se pudo eliminar la lista');
    }
  };

  // ─── Sort tasks ────────────────────────────────────────────────

  const sortedTasks = [...tasks].sort((a, b) => {
    // Completed at bottom
    if (a.completed !== b.completed) return a.completed ? 1 : -1;
    if (sortBy === 'alpha') return a.title.localeCompare(b.title);
    if (sortBy === 'important') return (b.important ? 1 : 0) - (a.important ? 1 : 0);
    if (sortBy === 'created') {
      const ca = a.created_at || '';
      const cb = b.created_at || '';
      return cb.localeCompare(ca);
    }
    // date
    if (a.due_date && b.due_date) return a.due_date.localeCompare(b.due_date);
    if (a.due_date) return -1;
    if (b.due_date) return 1;
    return 0;
  });

  // ─── Get custom list name ─────────────────────────────────────

  const customListName = customLists.find(l => l.id === activeView)?.name;

  // ─── Render ────────────────────────────────────────────────────

  const isPlanned = activeView === 'planned';
  const mostrarLista = VISTAS_INTELIGENTES.includes(activeView) && activeView !== 'tasks';
  const grupos = isPlanned ? agruparPlaneado(sortedTasks) : [{ clave: 'todas', label: '', tasks: sortedTasks }];
  const showInput = activeView !== 'flagged' && activeView !== 'assigned';

  return (
    <div className="tasks-view" style={{ display: 'flex', height: '100%', width: '100%', overflow: 'hidden', fontFamily: "'Segoe UI', system-ui, sans-serif" }}>
      {/* Sidebar */}
      {sidebarVisible && <TasksSidebar
        activeView={activeView}
        onViewChange={v => { setActiveView(v); setSelectedTask(null); }}
        customLists={customLists}
        onCreateList={createList}
        onDeleteList={deleteList}
        smartCounts={conteos}
      />}

      {/* Seguimiento de tareas asignadas (T-34) */}
      {activeView === 'seguimiento' ? <SeguimientoVista yo={yo} tareaInicial={TAREA_INICIAL} /> : (
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: '#faf9f8', overflow: 'hidden' }}>
        <TaskListHeader
          activeView={activeView}
          customListName={customListName}
          sortBy={sortBy}
          onSortChange={setSortBy}
          modo={modo}
          onModoChange={cambiarModo}
        />

        {/* Error banner */}
        {error && (
          <div style={{
            margin: '0 24px 8px', padding: '8px 12px', background: '#fde7e9',
            color: '#d13438', borderRadius: 4, fontSize: 13, display: 'flex',
            justifyContent: 'space-between', alignItems: 'center',
          }}>
            <span>{error}</span>
            <button onClick={() => setError('')} style={{ background: 'none', border: 'none', cursor: 'pointer', fontWeight: 'bold', color: '#d13438' }}>&times;</button>
          </div>
        )}

        {/* Task input */}
        {showInput && <TaskInput onAdd={addTask} activeView={activeView} />}

        {/* Task list */}
        <div style={{ flex: 1, overflowY: 'auto', marginTop: 8 }}>
          {loading ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
              <div style={{
                width: 32, height: 32, border: `2px solid ${COLORS.border}`,
                borderTopColor: COLORS.primary, borderRadius: '50%',
                animation: 'spin 0.8s linear infinite',
              }} />
              <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
            </div>
          ) : sortedTasks.length === 0 ? (
            <EmptyState view={activeView} />
          ) : grupos.map(grupo => (
            <div key={grupo.clave}>
              {grupo.label && (
                <div style={{
                  padding: '8px 24px', fontSize: 14, fontWeight: 600, color: COLORS.text,
                  display: 'flex', alignItems: 'center', gap: 8,
                }}>
                  <svg width={12} height={12} viewBox="0 0 24 24" fill="none" stroke={COLORS.secondary} strokeWidth={2.5}>
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                  {grupo.label}
                  <span style={{ fontSize: 12, color: COLORS.muted, fontWeight: 400 }}>({grupo.tasks.length})</span>
                </div>
              )}
              {modo === 'cuadricula' ? (
                <TaskGrid tasks={grupo.tasks} seleccionada={selectedTask?.id} onToggle={toggleTask}
                  onToggleImportant={toggleImportant} onOpen={setSelectedTask} onUpdate={updateTask} />
              ) : grupo.tasks.map(task => (
                <TaskItem key={task.id} task={task} onToggle={toggleTask} onToggleImportant={toggleImportant}
                  onClick={setSelectedTask} mostrarLista={mostrarLista} />
              ))}
            </div>
          ))}
        </div>
      </div>)}

      {/* Detail panel */}
      {selectedTask && activeView !== 'seguimiento' && (
        <TaskDetailPanel
          task={selectedTask}
          onUpdate={updateTask}
          onDelete={deleteTask}
          onClose={() => setSelectedTask(null)}
        />
      )}
    </div>
  );
}
