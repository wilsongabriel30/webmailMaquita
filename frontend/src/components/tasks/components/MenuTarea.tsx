// Menú de una tarea (clic derecho, como en To Do): Mi día, importancia, completar, vencimiento, «Mover a…» y eliminar.
import type { Task, TaskList } from '../types';
import { COLORS } from '../types';
import { SidebarIcon } from './IconoBarra';
import { MenuContextual, OpcionMenu, SeparadorMenu, TituloMenu } from './MenuContextual';
import { hoyTexto } from './repeticion';
import { separarEmoji } from './nombreLista';

interface Props {
  task: Task;
  x: number;
  y: number;
  listas: TaskList[];
  onCerrar: () => void;
  onUpdate: (id: string, data: Partial<Task>) => void;
  onToggle: (id: string) => void;
  onToggleImportant: (id: string) => void;
  onMover: (id: string, listId: string) => void;
  onDelete: (id: string) => void;
}

function manana(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function MenuTarea({ task, x, y, listas, onCerrar, onUpdate, onToggle, onToggleImportant, onMover, onDelete }: Props) {
  const hacer = (accion: () => void) => () => { onCerrar(); accion(); };
  // A dónde se puede mover: listas propias, compartidas y «Tareas» (no la del correo marcado).
  const destinos = listas.filter(l => (l.list_type === 'custom' || l.list_type === 'default') && l.id !== task.list_id);
  const fija = !!task.correo;
  return (
    <MenuContextual x={x} y={y} etiqueta={`Opciones de la tarea ${task.title}`} onCerrar={onCerrar}>
      <OpcionMenu onClick={hacer(() => onUpdate(task.id, { my_day: !task.my_day }))}>
        <SidebarIcon icon="sun" size={14} /> {task.my_day ? 'Quitar de Mi día' : 'Agregar a Mi día'}
      </OpcionMenu>
      <OpcionMenu onClick={hacer(() => onToggleImportant(task.id))}>
        <SidebarIcon icon="star" size={14} /> {task.important ? 'Quitar importancia' : 'Marcar como importante'}
      </OpcionMenu>
      <OpcionMenu onClick={hacer(() => onToggle(task.id))}>
        <svg aria-hidden="true" width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><circle cx="12" cy="12" r="9" />{!task.completed && <polyline points="8 12 11 15 16 9" />}</svg>
        {task.completed ? 'Marcar como no completada' : 'Marcar como completada'}
      </OpcionMenu>
      <SeparadorMenu />
      <OpcionMenu onClick={hacer(() => onUpdate(task.id, { due_date: hoyTexto() }))}>
        <SidebarIcon icon="calendar" size={14} /> Vence hoy
      </OpcionMenu>
      <OpcionMenu onClick={hacer(() => onUpdate(task.id, { due_date: manana() }))}>
        <SidebarIcon icon="calendar" size={14} /> Vence mañana
      </OpcionMenu>
      {task.due_date && (
        <OpcionMenu onClick={hacer(() => onUpdate(task.id, { due_date: null }))}>
          <SidebarIcon icon="calendar" size={14} /> Quitar fecha de vencimiento
        </OpcionMenu>
      )}
      <SeparadorMenu />
      <TituloMenu>Mover a…</TituloMenu>
      {fija ? (
        <OpcionMenu deshabilitada onClick={() => {}} titulo="Las tareas de un correo marcado se quedan en su lista">
          No se puede mover
        </OpcionMenu>
      ) : destinos.length === 0 ? (
        <OpcionMenu deshabilitada onClick={() => {}}>No hay otras listas</OpcionMenu>
      ) : (
        <div style={{ maxHeight: 200, overflowY: 'auto' }}>
          {destinos.map(l => {
            const { emoji, texto } = separarEmoji(l.list_type === 'default' ? 'Tareas' : l.name);
            return (
              <OpcionMenu key={l.id} onClick={hacer(() => onMover(task.id, l.id))}>
                <span aria-hidden="true" style={{ width: 14, display: 'inline-flex', justifyContent: 'center', color: COLORS.secondary }}>
                  {emoji || <SidebarIcon icon={l.list_type === 'default' ? 'home' : 'list'} size={14} />}
                </span>
                {texto}
              </OpcionMenu>
            );
          })}
        </div>
      )}
      <SeparadorMenu />
      <OpcionMenu peligro onClick={hacer(() => { if (confirm(`¿Eliminar la tarea «${task.title}»?`)) onDelete(task.id); })}>
        Eliminar tarea
      </OpcionMenu>
    </MenuContextual>
  );
}
