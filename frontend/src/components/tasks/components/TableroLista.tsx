// Modo «Tablero» de Tareas (09/11/2026): las tareas de la lista abierta en columnas. Arrastrar una tarjeta a otra
// columna cambia su estado; se mueve al soltarla y, si el servidor no acepta el cambio, vuelve (el aviso lo da
// useTareas). La tarjeta también se puede soltar en una lista de la barra, como en la vista Lista.
import { useState, type MouseEvent } from 'react';
import type { Task } from '../types';
import { COLORS } from '../types';
import { esTarea, idTarea, marcarTarea } from './arrastreTarea';
import {
  type ColumnaLista, type EstadoLista, columnaDe, columnasVisibles, conEstado, destinoValido, enTablero,
  NOMBRE_COLUMNA, sePuedeArrastrar, DIAS_COMPLETADAS,
} from './columnasLista';
import { TaskItem } from './TaskItem';

interface Props {
  tasks: Task[];
  mostrarLista: boolean;
  seleccionada?: string;
  onToggle: (id: string) => void;
  onToggleImportant: (id: string) => void;
  onOpen: (task: Task) => void;
  onMenu: (task: Task, e: MouseEvent) => void;
  onCambiarEstado: (id: string, estado: EstadoLista) => Promise<void>;
}

const COLOR: Record<ColumnaLista, string> = {
  vencida: '#d13438', espera: '#8a8886', pendiente: COLORS.primary, en_curso: '#c19c00', completada: '#107c10',
};

export function TableroLista({ tasks, mostrarLista, seleccionada, onToggle, onToggleImportant, onOpen, onMenu, onCambiarEstado }: Props) {
  const [arrastrando, setArrastrando] = useState<string | null>(null);
  const [sobre, setSobre] = useState<ColumnaLista | null>(null);
  // Movidas a la espera del servidor: se ven ya en su columna nueva.
  const [movidas, setMovidas] = useState<Record<string, EstadoLista>>({});

  const efectiva = (t: Task) => (t.id in movidas ? conEstado(t, movidas[t.id]) : t);
  const visibles = tasks.map(efectiva).filter(t => enTablero(t));
  const viejas = tasks.filter(t => t.completed && !enTablero(t)).length;
  const tareaArrastrada = arrastrando ? visibles.find(t => t.id === arrastrando) : undefined;

  const soltar = async (t: Task, col: EstadoLista) => {
    setMovidas(m => ({ ...m, [t.id]: col }));
    try { await onCambiarEstado(t.id, col); }
    finally { setMovidas(m => { const n = { ...m }; delete n[t.id]; return n; }); }
  };

  return (
    <div style={{ display: 'flex', gap: 12, padding: '8px 24px 16px', overflowX: 'auto', alignItems: 'flex-start' }}>
      {columnasVisibles(visibles).map(col => {
        const lista = visibles.filter(t => columnaDe(t) === col);
        const valido = destinoValido(tareaArrastrada, col);
        const resaltada = sobre === col && valido;
        return (
          <div key={col} role="list" aria-label={`${NOMBRE_COLUMNA[col]}: ${lista.length} ${lista.length === 1 ? 'tarea' : 'tareas'}`}
            onDragOver={e => { if (esTarea(e) && valido) { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; if (sobre !== col) setSobre(col); } }}
            onDragLeave={e => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setSobre(null); }}
            onDrop={e => {
              e.preventDefault();
              const t = visibles.find(x => x.id === (idTarea(e) || arrastrando));
              setArrastrando(null); setSobre(null);
              if (t && destinoValido(t, col)) void soltar(t, col);
            }}
            style={{
              minWidth: 260, width: 260, flexShrink: 0, background: resaltada ? COLORS.activeBg : '#f3f2f1', borderRadius: 8,
              padding: 6, borderTop: `4px solid ${COLOR[col]}`, outline: resaltada ? `2px dashed ${COLORS.primary}` : 'none',
              outlineOffset: -2, transition: 'background .15s', minHeight: 120,
            }}>
            <div style={{ fontWeight: 700, fontSize: 13, color: COLORS.text, padding: '2px 6px 6px', display: 'flex', gap: 6 }}>
              <span style={{ flex: 1 }}>{NOMBRE_COLUMNA[col]}</span>
              <span style={{ color: COLORS.secondary, fontWeight: 400 }}>{lista.length}</span>
            </div>
            {lista.map(t => {
              const mueve = sePuedeArrastrar(t);
              return (
                <div key={t.id} role="listitem" draggable={mueve}
                  onDragStart={mueve ? e => { marcarTarea(e, t.id); setArrastrando(t.id); } : undefined}
                  onDragEnd={() => { setArrastrando(null); setSobre(null); }}
                  style={{
                    background: '#fff', borderRadius: 6, marginBottom: 6, boxShadow: '0 1px 2px rgba(0,0,0,.12)',
                    opacity: arrastrando === t.id || t.id in movidas ? 0.5 : 1, cursor: mueve ? 'grab' : 'pointer', overflow: 'hidden',
                  }}>
                  <TaskItem task={t} compacta mostrarEstado={col === 'vencida'} onToggle={onToggle} onToggleImportant={onToggleImportant} onClick={onOpen}
                    mostrarLista={mostrarLista} seleccionada={seleccionada === t.id} onMenu={onMenu} />
                </div>
              );
            })}
            {!lista.length && (
              <div style={{ fontSize: 12, color: COLORS.muted, padding: 10, textAlign: 'center' }}>
                {col === 'vencida' ? 'Nada vencido' : col === 'espera' ? '' : 'Arrastra aquí'}
              </div>
            )}
            {col === 'completada' && viejas > 0 && (
              <div style={{ fontSize: 12, color: COLORS.secondary, padding: '4px 6px' }}>
                {viejas === 1 ? 'Otra completada' : `Otras ${viejas} completadas`} hace más de {DIAS_COMPLETADAS} días: se ven en la vista Lista.
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
