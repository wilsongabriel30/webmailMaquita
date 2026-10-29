// Cuerpo de la vista de Tareas: las pendientes (en «Planeado», agrupadas por fecha) y, al final y plegadas, las
// completadas. Igual en vista Lista y en Cuadrícula.
import type { DragEvent, MouseEvent, ReactNode } from 'react';
import type { Task } from '../types';
import { COLORS } from '../types';
import { agruparPlaneado } from './agruparPlaneado';
import type { ModoVista } from './modoVista';
import { SeccionCompletadas } from './SeccionCompletadas';
import { TaskGrid } from './TaskGrid';
import { TaskItem } from './TaskItem';

interface Props {
  tasks: Task[];
  modo: ModoVista;
  /** «Planeado»: las pendientes van en grupos (Vencidas, Hoy, Mañana…). */
  porFecha: boolean;
  mostrarLista: boolean;
  seleccionada?: string;
  vacio: ReactNode;
  onToggle: (id: string) => void;
  onToggleImportant: (id: string) => void;
  onOpen: (task: Task) => void;
  onUpdate: (id: string, data: Partial<Task>) => void;
  onMenu: (task: Task, e: MouseEvent) => void;
  arrastre: { sobre: string | null; props: (t: Task) => { draggable?: boolean; onDragStart?: (e: DragEvent) => void } };
}

export function CuerpoTareas({ tasks, modo, porFecha, mostrarLista, seleccionada, vacio, onToggle, onToggleImportant, onOpen, onUpdate, onMenu, arrastre }: Props) {
  if (tasks.length === 0) return <>{vacio}</>;
  const pendientes = tasks.filter(t => !t.completed);
  const completadas = tasks.filter(t => t.completed);
  const grupos = porFecha ? agruparPlaneado(pendientes) : [{ clave: 'todas', label: '', tasks: pendientes }];

  const pintar = (lista: Task[]) => modo === 'cuadricula' ? (
    <TaskGrid tasks={lista} seleccionada={seleccionada} onToggle={onToggle} onToggleImportant={onToggleImportant}
      onOpen={onOpen} onUpdate={onUpdate} onMenu={onMenu} propsFila={arrastre.props} />
  ) : lista.map(task => (
    <div key={task.id} {...arrastre.props(task)}
      style={{ borderTop: arrastre.sobre === task.id ? `2px solid ${COLORS.primary}` : '2px solid transparent' }}>
      <TaskItem task={task} onToggle={onToggle} onToggleImportant={onToggleImportant} onClick={onOpen}
        mostrarLista={mostrarLista} seleccionada={seleccionada === task.id} onMenu={onMenu} />
    </div>
  ));

  return (
    <>
      {grupos.filter(g => g.tasks.length > 0 || !porFecha).map(grupo => (
        <div key={grupo.clave}>
          {grupo.label && (
            <div style={{ padding: '8px 24px', fontSize: 14, fontWeight: 600, color: COLORS.text, display: 'flex', alignItems: 'center', gap: 8 }}>
              <svg width={12} height={12} viewBox="0 0 24 24" fill="none" stroke={COLORS.secondary} strokeWidth={2.5}>
                <polyline points="6 9 12 15 18 9" />
              </svg>
              {grupo.label}
              <span style={{ fontSize: 12, color: COLORS.muted, fontWeight: 400 }}>({grupo.tasks.length})</span>
            </div>
          )}
          {pintar(grupo.tasks)}
        </div>
      ))}
      <SeccionCompletadas cantidad={completadas.length}>{pintar(completadas)}</SeccionCompletadas>
    </>
  );
}
