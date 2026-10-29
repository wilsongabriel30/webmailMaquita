import { useState, useEffect, useCallback } from 'react';
import type { Task, TaskList, ActiveView, Orden } from './types';
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
import { MisListas } from './components/MisListas';
import { BotonesCrear } from './components/BotonesCrear';
import { ordenarTareas, leerOrdenVista, guardarOrdenVista } from './components/ordenarTareas';
import { useListas } from './hooks/useListas';
import { useArrastreTareas } from './hooks/useArrastreTareas';
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
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { conteos, recargarConteos } = useConteosVistas(activeView);
  const listas = useListas(recargarConteos);
  const fetchLists = listas.recargar;
  // «Tareas» es una vista inteligente, pero también una lista de verdad (la por defecto).
  const listaActiva: TaskList | undefined = activeView === 'tasks'
    ? listas.listas.find(l => l.list_type === 'default')
    : listas.listas.find(l => l.id === activeView);
  const [ordenVistas, setOrdenVistas] = useState<Record<string, Orden>>({});
  const orden: Orden = listaActiva ? (listaActiva.sort_by || 'manual') : (ordenVistas[activeView] ?? leerOrdenVista(activeView));
  const cambiarOrden = (o: Orden) => {
    if (listaActiva) void listas.cambiarLista(listaActiva.id, { sort_by: o });
    else { guardarOrdenVista(activeView, o); setOrdenVistas(v => ({ ...v, [activeView]: o })); }
  };
  const [modo, setModo] = useState<ModoVista>(leerModoVista);
  const cambiarModo = (m: ModoVista) => { setModo(m); guardarModoVista(m); };

  // ─── Data fetching ─────────────────────────────────────────────

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

  // ─── Orden ──────────────────────────────────────────────────────

  const sortedTasks = ordenarTareas(tasks, orden);
  const arrastre = useArrastreTareas(
    listaActiva && orden === 'manual' && modo === 'lista' ? listaActiva.id : null,
    sortedTasks, setTasks, () => { void fetchTasks(); },
  );

  const eliminarLista = (l: TaskList) => {
    if (!confirm(`¿Eliminar la lista «${l.name}» y todas sus tareas?`)) return;
    if (activeView === l.id) setActiveView('tasks');
    void listas.eliminarLista(l.id);
  };

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
        smartCounts={conteos}
        pie={<BotonesCrear
          onCrearLista={async n => { const nueva = await listas.crearLista(n); if (nueva) setActiveView(nueva.id); }}
          onCrearGrupo={n => { void listas.crearGrupo(n); }} />}
      >
        <MisListas listas={listas.listas} grupos={listas.grupos} activeView={activeView}
          onViewChange={v => { setActiveView(v); setSelectedTask(null); }}
          onCambiarLista={(id, c) => { void listas.cambiarLista(id, c); }}
          onEliminarLista={eliminarLista}
          onRenombrarGrupo={(id, n) => { void listas.renombrarGrupo(id, n); }}
          onEliminarGrupo={g => { if (confirm(`¿Eliminar el grupo «${g.name}»? Sus listas no se borran: quedan fuera del grupo.`)) void listas.eliminarGrupo(g.id); }}
          onGuardarBarra={b => { void listas.guardarBarra(b); }} />
      </TasksSidebar>}

      {/* Seguimiento de tareas asignadas (T-34) */}
      {activeView === 'seguimiento' ? <SeguimientoVista yo={yo} tareaInicial={TAREA_INICIAL} /> : (
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: '#faf9f8', overflow: 'hidden' }}>
        <TaskListHeader
          activeView={activeView}
          lista={activeView === 'tasks' ? undefined : listaActiva}
          orden={orden}
          onOrdenChange={cambiarOrden}
          modo={modo}
          onModoChange={cambiarModo}
        />

        {/* Error banner */}
        {(error || listas.error) && (
          <div style={{
            margin: '0 24px 8px', padding: '8px 12px', background: '#fde7e9',
            color: '#d13438', borderRadius: 4, fontSize: 13, display: 'flex',
            justifyContent: 'space-between', alignItems: 'center',
          }}>
            <span>{error || listas.error}</span>
            <button aria-label="Cerrar aviso" onClick={() => { setError(''); listas.limpiarError(); }} style={{ background: 'none', border: 'none', cursor: 'pointer', fontWeight: 'bold', color: '#d13438' }}>&times;</button>
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
                <div key={task.id} {...arrastre.props(task)}
                  style={{ borderTop: arrastre.sobre === task.id ? `2px solid ${COLORS.primary}` : '2px solid transparent' }}>
                  <TaskItem task={task} onToggle={toggleTask} onToggleImportant={toggleImportant}
                    onClick={setSelectedTask} mostrarLista={mostrarLista} />
                </div>
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
