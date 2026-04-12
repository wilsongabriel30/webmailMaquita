import React, { useState, useEffect, useCallback } from 'react';
import type { Task, TaskList, ActiveView } from './types';
import { COLORS, SMART_LISTS } from './types';
import { TasksSidebar } from './components/TasksSidebar';
import { TaskListHeader } from './components/TaskListHeader';
import { TaskInput } from './components/TaskInput';
import { TaskItem } from './components/TaskItem';
import { TaskDetailPanel } from './components/TaskDetailPanel';
import { EmptyState } from './components/EmptyState';
import { api } from '../../api/client';

export function TasksView() {
  const [activeView, setActiveView] = useState<ActiveView>('my-day');
  const [tasks, setTasks] = useState<Task[]>([]);
  const [customLists, setCustomLists] = useState<TaskList[]>([]);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [sortBy, setSortBy] = useState('date');
  const [smartCounts, setSmartCounts] = useState<Record<string, number>>({});

  // ─── Data fetching ─────────────────────────────────────────────

  const fetchLists = useCallback(async () => {
    try {
      const lists = await api.get<TaskList[]>('/tasks/lists');
      const custom = lists.filter(l => l.list_type === 'custom');
      setCustomLists(custom);
      // Build smart counts from response
      const counts: Record<string, number> = {};
      lists.forEach(l => {
        if (l.list_type === 'smart') counts[l.name] = l.task_count;
      });
      setSmartCounts(counts);
    } catch {
      // API not ready yet, use empty state
      setCustomLists([]);
    }
  }, []);

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      let result: Task[];
      const smartViews = ['my-day', 'important', 'planned', 'assigned', 'flagged'];
      if (smartViews.includes(activeView)) {
        const viewMap: Record<string, string> = {
          'my-day': '/tasks/views/my-day',
          'important': '/tasks/views/important',
          'planned': '/tasks/views/planned',
          'assigned': '/tasks/views/assigned',
          'flagged': '/tasks/views/flagged',
        };
        result = await api.get<Task[]>(viewMap[activeView] || '/tasks/views/my-day');
      } else if (activeView === 'tasks') {
        // Default list - get the "tasks" list
        try {
          const lists = await api.get<TaskList[]>('/tasks/lists');
          const defaultList = lists.find(l => l.list_type === 'default');
          if (defaultList) {
            result = await api.get<Task[]>(`/tasks/lists/${defaultList.id}/tasks`);
          } else {
            result = [];
          }
        } catch {
          result = [];
        }
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

  // ─── Task actions ──────────────────────────────────────────────

  const addTask = async (title: string, dueDate?: string, reminder?: string) => {
    try {
      const listId = (!['my-day', 'important', 'planned', 'assigned', 'flagged', 'tasks'].includes(activeView))
        ? activeView : undefined;
      const payload: Record<string, unknown> = { title };
      if (dueDate) payload.due_date = dueDate;
      if (reminder) payload.reminder = reminder;
      if (activeView === 'my-day') payload.my_day = true;
      if (activeView === 'important') payload.important = true;

      if (listId) {
        await api.post(`/tasks/lists/${listId}/tasks`, payload);
      } else {
        await api.post('/tasks/tasks', payload);
      }
      fetchTasks();
      fetchLists();
    } catch {
      setError('No se pudo agregar la tarea');
    }
  };

  const toggleTask = async (id: string) => {
    if (id.startsWith('mail-')) return;
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
    if (id.startsWith('mail-')) return; // mail tasks are read-only
    setTasks(prev => prev.map(t => t.id === id ? { ...t, ...data } : t));
    if (selectedTask?.id === id) setSelectedTask(prev => prev ? { ...prev, ...data } : null);
    try {
      await api.patch(`/tasks/tasks/${id}`, data);
      if ('my_day' in data) fetchTasks();
      fetchLists();
    } catch {
      fetchTasks();
    }
  };

  const deleteTask = async (id: string) => {
    if (id.startsWith('mail-')) return; // mail tasks are read-only
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

  // ─── Group tasks for planned view ─────────────────────────────

  const groupTasksForPlanned = () => {
    const groups: { label: string; tasks: Task[] }[] = [];
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const tomorrow = new Date(today); tomorrow.setDate(tomorrow.getDate() + 1);
    const nextWeek = new Date(today); nextWeek.setDate(nextWeek.getDate() + 7);

    const buckets: Record<string, Task[]> = { anterior: [], hoy: [], manana: [], semana: [], despues: [], sinFecha: [] };
    sortedTasks.forEach(t => {
      if (!t.due_date) { buckets.sinFecha.push(t); return; }
      const d = new Date((t.due_date || '').slice(0, 10) + 'T00:00:00');
      if (d < today) buckets.anterior.push(t);
      else if (d.getTime() === today.getTime()) buckets.hoy.push(t);
      else if (d.getTime() === tomorrow.getTime()) buckets.manana.push(t);
      else if (d < nextWeek) buckets.semana.push(t);
      else buckets.despues.push(t);
    });

    if (buckets.anterior.length) groups.push({ label: 'Anterior', tasks: buckets.anterior });
    if (buckets.hoy.length) groups.push({ label: 'Hoy', tasks: buckets.hoy });
    if (buckets.manana.length) groups.push({ label: 'Mañana', tasks: buckets.manana });
    if (buckets.semana.length) groups.push({ label: 'Esta semana', tasks: buckets.semana });
    if (buckets.despues.length) groups.push({ label: 'Después', tasks: buckets.despues });
    if (buckets.sinFecha.length) groups.push({ label: 'Sin fecha', tasks: buckets.sinFecha });
    return groups;
  };

  // ─── Get custom list name ─────────────────────────────────────

  const customListName = customLists.find(l => l.id === activeView)?.name;

  // ─── Render ────────────────────────────────────────────────────

  const isPlanned = activeView === 'planned';
  const showInput = activeView !== 'flagged' && activeView !== 'assigned';
  const isFlagged = activeView === 'flagged';

  return (
    <div style={{ display: 'flex', height: '100%', width: '100%', overflow: 'hidden', fontFamily: "'Segoe UI', system-ui, sans-serif" }}>
      {/* Sidebar */}
      <TasksSidebar
        activeView={activeView}
        onViewChange={v => { setActiveView(v); setSelectedTask(null); }}
        customLists={customLists}
        onCreateList={createList}
        onDeleteList={deleteList}
        smartCounts={smartCounts}
      />

      {/* Main content */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: '#faf9f8', overflow: 'hidden' }}>
        <TaskListHeader
          activeView={activeView}
          customListName={customListName}
          sortBy={sortBy}
          onSortChange={setSortBy}
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
        {showInput && <TaskInput onAdd={addTask} />}

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
          ) : isPlanned ? (
            // Grouped view for Planned
            groupTasksForPlanned().map(group => (
              <div key={group.label}>
                <div style={{
                  padding: '8px 24px', fontSize: 14, fontWeight: 600, color: COLORS.text,
                  display: 'flex', alignItems: 'center', gap: 8,
                }}>
                  <svg width={12} height={12} viewBox="0 0 24 24" fill="none" stroke={COLORS.secondary} strokeWidth={2.5}>
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                  {group.label}
                  <span style={{ fontSize: 12, color: COLORS.muted, fontWeight: 400 }}>({group.tasks.length})</span>
                </div>
                {group.tasks.map(task => (
                  <TaskItem key={task.id} task={task} onToggle={toggleTask} onToggleImportant={toggleImportant} onClick={setSelectedTask} />
                ))}
              </div>
            ))
          ) : (
            sortedTasks.map(task => (
              <TaskItem key={task.id} task={task} onToggle={toggleTask} onToggleImportant={toggleImportant} onClick={setSelectedTask} />
            ))
          )}
        </div>
      </div>

      {/* Detail panel */}
      {selectedTask && (
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
