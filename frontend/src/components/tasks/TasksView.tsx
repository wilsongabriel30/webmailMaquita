import { useState, useEffect, useCallback, type MouseEvent } from 'react';
import type { Task, TaskList, ActiveView, Orden } from './types';
import { COLORS } from './types';
import { TasksSidebar } from './components/TasksSidebar';
import { TaskListHeader } from './components/TaskListHeader';
import { TaskInput } from './components/TaskInput';
import { TaskDetailPanel } from './components/TaskDetailPanel';
import { EmptyState } from './components/EmptyState';
import { leerModoVista, guardarModoVista, type ModoVista } from './components/modoVista';
import { useConteosVistas } from './hooks/useConteosVistas';
import { MisListas } from './components/MisListas';
import { BotonesCrear } from './components/BotonesCrear';
import { BuscadorTareas } from './components/BuscadorTareas';
import { CuerpoTareas } from './components/CuerpoTareas';
import { MenuTarea } from './components/MenuTarea';
import { DialogoCompartir } from './components/DialogoCompartir';
import { ordenarTareas, leerOrdenVista, guardarOrdenVista } from './components/ordenarTareas';
import { useListas } from './hooks/useListas';
import { useArrastreTareas } from './hooks/useArrastreTareas';
import { useTareas, VISTAS_INTELIGENTES } from './hooks/useTareas';
import { SeguimientoVista } from '../tareas/SeguimientoVista';

const _params = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null;
const VISTA_INICIAL: ActiveView | null = _params?.get('vista') === 'seguimiento' || _params?.get('tarea') ? 'seguimiento' : null;
const TAREA_INICIAL = _params?.get('tarea') || null;

export function TasksView() {
  const [activeView, setActiveView] = useState<ActiveView>(VISTA_INICIAL || 'my-day');
  const [busqueda, setBusqueda] = useState('');
  const [yo] = useState<string>(() => { try { return localStorage.getItem('user_email') || (JSON.parse(localStorage.getItem('user') || '{}').email) || ''; } catch { return ''; } });
  const [sidebarVisible, setSidebarVisible] = useState(() => typeof window === 'undefined' || window.innerWidth >= 768);
  useEffect(() => {
    const h = () => setSidebarVisible(v => !v);
    window.addEventListener('toggle-tasks-sidebar', h);
    return () => window.removeEventListener('toggle-tasks-sidebar', h);
  }, []);
  const { conteos, recargarConteos } = useConteosVistas(activeView);
  const listas = useListas(recargarConteos);
  const fetchLists = listas.recargar;
  const {
    tasks, setTasks, selectedTask, setSelectedTask, loading, error, setError,
    fetchTasks, addTask, toggleTask, toggleImportant, updateTask, deleteTask, moverTarea, reemplazarTarea,
  } = useTareas(activeView, busqueda, fetchLists);
  const [compartiendo, setCompartiendo] = useState<string | null>(null);
  const cerrarCompartir = useCallback(() => setCompartiendo(null), []);
  const listaCompartida = listas.listas.find(l => l.id === compartiendo);
  const buscando = busqueda.trim() !== '';
  const [menu, setMenu] = useState<{ task: Task; x: number; y: number } | null>(null);

  // «Tareas» es una vista inteligente, pero también una lista de verdad (la por defecto).
  const listaPorDefecto = listas.listas.find(l => l.list_type === 'default');
  const listaActiva: TaskList | undefined = buscando ? undefined : activeView === 'tasks'
    ? listaPorDefecto
    : listas.listas.find(l => l.id === activeView);
  const claveOrden = buscando ? 'buscar' : activeView;
  const [ordenVistas, setOrdenVistas] = useState<Record<string, Orden>>({});
  const orden: Orden = listaActiva ? (listaActiva.sort_by || 'manual') : (ordenVistas[claveOrden] ?? leerOrdenVista(claveOrden));
  const cambiarOrden = (o: Orden) => {
    if (listaActiva) void listas.cambiarLista(listaActiva.id, { sort_by: o });
    else { guardarOrdenVista(claveOrden, o); setOrdenVistas(v => ({ ...v, [claveOrden]: o })); }
  };
  const [modo, setModo] = useState<ModoVista>(leerModoVista);
  const cambiarModo = (m: ModoVista) => { setModo(m); guardarModoVista(m); };

  // Escuchar evento de refresh desde WebSocket (tarea asignada/actualizada)
  useEffect(() => {
    const handler = () => { fetchTasks(); fetchLists(); };
    window.addEventListener('refresh-tasks', handler);
    return () => window.removeEventListener('refresh-tasks', handler);
  }, [fetchTasks, fetchLists]);

  const abrirVista = (v: ActiveView) => { setActiveView(v); setSelectedTask(null); setBusqueda(''); };
  const buscar = useCallback((texto: string) => { setBusqueda(texto); setSelectedTask(null); }, [setSelectedTask]);

  // Soltar una tarea en la barra: en una lista la mueve; en «Mi día» o «Importante» la agrega.
  const soltarTarea = (destino: ActiveView, id: string) => {
    if (destino === 'my-day') void updateTask(id, { my_day: true });
    else if (destino === 'important') void updateTask(id, { important: true });
    else if (destino === 'tasks') { if (listaPorDefecto) void moverTarea(id, listaPorDefecto.id); }
    else void moverTarea(id, destino);
  };

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

  const mostrarLista = buscando || (VISTAS_INTELIGENTES.includes(activeView) && activeView !== 'tasks');
  const showInput = !buscando && activeView !== 'flagged' && activeView !== 'assigned';
  const vacio = buscando
    ? <div style={{ padding: 40, textAlign: 'center', fontSize: 14, color: COLORS.secondary }}>No hay tareas que contengan «{busqueda.trim()}».</div>
    : <EmptyState view={activeView} />;

  return (
    <div className="tasks-view" style={{ display: 'flex', height: '100%', width: '100%', overflow: 'hidden', fontFamily: "'Segoe UI', system-ui, sans-serif" }}>
      {/* Sidebar */}
      {sidebarVisible && <TasksSidebar
        activeView={buscando ? '' : activeView}
        onViewChange={abrirVista}
        smartCounts={conteos}
        buscador={<BuscadorTareas valor={busqueda} onBuscar={buscar} />}
        onSoltarTarea={soltarTarea}
        pie={<BotonesCrear
          onCrearLista={async n => { const nueva = await listas.crearLista(n); if (nueva) abrirVista(nueva.id); }}
          onCrearGrupo={n => { void listas.crearGrupo(n); }} />}
      >
        <MisListas listas={listas.listas} grupos={listas.grupos} activeView={buscando ? '' : activeView}
          onViewChange={abrirVista}
          onCambiarLista={(id, c) => { void listas.cambiarLista(id, c); }}
          onEliminarLista={eliminarLista}
          onRenombrarGrupo={(id, n) => { void listas.renombrarGrupo(id, n); }}
          onEliminarGrupo={g => { if (confirm(`¿Eliminar el grupo «${g.name}»? Sus listas no se borran: quedan fuera del grupo.`)) void listas.eliminarGrupo(g.id); }}
          onGuardarBarra={b => { void listas.guardarBarra(b); }}
          onSoltarTarea={(listId, id) => void moverTarea(id, listId)}
          onCompartir={l => setCompartiendo(l.id)} />
      </TasksSidebar>}

      {/* Seguimiento de tareas asignadas (T-34) */}
      {activeView === 'seguimiento' && !buscando ? <SeguimientoVista yo={yo} tareaInicial={TAREA_INICIAL} /> : (
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: '#faf9f8', overflow: 'hidden' }}>
        <TaskListHeader
          activeView={buscando ? '' : activeView}
          lista={activeView === 'tasks' ? undefined : listaActiva}
          orden={orden}
          onOrdenChange={cambiarOrden}
          modo={modo}
          onModoChange={cambiarModo}
          busqueda={buscando ? busqueda.trim() : undefined}
          onCompartir={listaActiva?.list_type === 'custom' ? () => setCompartiendo(listaActiva.id) : undefined}
        />

        {/* Error banner */}
        {(error || listas.error) && (
          <div role="alert" style={{
            margin: '0 24px 8px', padding: '8px 12px', background: '#fde7e9',
            color: '#d13438', borderRadius: 4, fontSize: 13, display: 'flex',
            justifyContent: 'space-between', alignItems: 'center',
          }}>
            <span>{error || listas.error}</span>
            <button aria-label="Cerrar aviso" onClick={() => { setError(''); listas.limpiarError(); }} style={{ background: 'none', border: 'none', cursor: 'pointer', fontWeight: 'bold', color: '#d13438' }}>&times;</button>
          </div>
        )}

        {showInput && <TaskInput onAdd={addTask} activeView={activeView} />}

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
          ) : (
            <CuerpoTareas tasks={sortedTasks} modo={modo} porFecha={!buscando && activeView === 'planned'}
              mostrarLista={mostrarLista} seleccionada={selectedTask?.id} vacio={vacio}
              onToggle={toggleTask} onToggleImportant={toggleImportant} onOpen={setSelectedTask} onUpdate={updateTask}
              onMenu={(task: Task, e: MouseEvent) => setMenu({ task, x: e.clientX, y: e.clientY })}
              arrastre={arrastre} />
          )}
        </div>
      </div>)}

      {listaCompartida && (
        <DialogoCompartir lista={listaCompartida} yo={yo} onCerrar={cerrarCompartir}
          onCambio={() => { void fetchLists(); }}
          onSalir={() => { setCompartiendo(null); abrirVista('tasks'); }} />
      )}

      {menu && (
        <MenuTarea task={menu.task} x={menu.x} y={menu.y} listas={listas.listas} onCerrar={() => setMenu(null)}
          onUpdate={updateTask} onToggle={toggleTask} onToggleImportant={toggleImportant}
          onMover={moverTarea} onDelete={deleteTask} />
      )}

      {/* Detail panel */}
      {selectedTask && (activeView !== 'seguimiento' || buscando) && (
        <TaskDetailPanel
          key={selectedTask.id}
          task={selectedTask}
          onUpdate={updateTask}
          onToggle={toggleTask}
          onToggleImportant={toggleImportant}
          onDelete={deleteTask}
          onClose={() => setSelectedTask(null)}
          onRefrescar={() => { void fetchTasks(); }}
          onAsignada={reemplazarTarea}
        />
      )}
    </div>
  );
}
