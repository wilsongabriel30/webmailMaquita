// Vista «Cuadrícula» de Tareas (como en Outlook): una tabla con Título y Fecha de vencimiento.
// El título se edita en la misma celda, ⓘ abre el panel de detalles y la fecha se cambia en su celda.
import { useState, type KeyboardEvent, type MouseEvent } from 'react';
import type { Task } from '../types';
import { COLORS } from '../types';
import { colorVencimiento, fechaCompleta, textoVencimiento } from './fechaVencimiento';

interface Props {
  tasks: Task[];
  seleccionada?: string;
  onToggle: (id: string) => void;
  onToggleImportant: (id: string) => void;
  onOpen: (task: Task) => void;
  onUpdate: (id: string, data: Partial<Task>) => void;
  /** Clic derecho: menú de la tarea. */
  onMenu?: (task: Task, e: MouseEvent) => void;
  /** Para arrastrar la fila a otra lista de la barra (useArrastreTareas). */
  propsFila?: (task: Task) => object;
}

const COLUMNAS = '44px minmax(260px, 1fr) 170px 56px';
const ALTO_FILA = 48;

function Circulo({ task, onToggle }: { task: Task; onToggle: (id: string) => void }) {
  return (
    <button type="button" aria-label={task.completed ? 'Marcar como no completada' : 'Marcar como completada'}
      onClick={e => { e.stopPropagation(); onToggle(task.id); }}
      style={{
        width: 20, height: 20, borderRadius: '50%', padding: 0, flexShrink: 0, cursor: 'pointer',
        border: task.completed ? 'none' : `1.5px solid ${COLORS.primary}`,
        background: task.completed ? COLORS.primary : 'transparent',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
      {task.completed ? (
        <svg width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={3}><polyline points="20 6 9 17 4 12" /></svg>
      ) : null}
    </button>
  );
}

function CeldaTitulo({ task, onOpen, onUpdate }: { task: Task; onOpen: (t: Task) => void; onUpdate: Props['onUpdate'] }) {
  const [editando, setEditando] = useState(false);
  const [texto, setTexto] = useState(task.title);

  const empezar = () => { setTexto(task.title); setEditando(true); };
  const guardar = () => {
    setEditando(false);
    const t = texto.trim();
    if (t && t !== task.title) onUpdate(task.id, { title: t });
  };
  const tecla = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') guardar();
    if (e.key === 'Escape') setEditando(false);
  };

  return (
    <div className={`celda-titulo${editando ? ' editando' : ''}`} onClick={e => { e.stopPropagation(); empezar(); }}
      style={{
        display: 'flex', alignItems: 'center', gap: 8, height: ALTO_FILA - 10, margin: '5px 8px 5px 0', padding: '0 8px 0 12px',
        border: `1px solid ${editando ? COLORS.primary : 'transparent'}`, borderRadius: 2, minWidth: 0,
        cursor: 'text',
      }}>
      {editando ? (
        <input autoFocus aria-label="Título de la tarea" value={texto} onChange={e => setTexto(e.target.value)}
          onBlur={guardar} onKeyDown={tecla}
          style={{ flex: 1, minWidth: 0, border: 'none', outline: 'none', background: 'transparent', fontSize: 14, color: COLORS.text, fontFamily: 'inherit' }} />
      ) : (
        <span title={task.title} style={{
          flex: 1, minWidth: 0, fontSize: 14, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          color: task.completed ? COLORS.muted : COLORS.text, textDecoration: task.completed ? 'line-through' : 'none',
        }}>{task.title}</span>
      )}
      <button type="button" aria-label="Abrir detalles" title="Abrir detalles"
        onMouseDown={e => e.preventDefault()} onClick={e => { e.stopPropagation(); onOpen(task); }}
        style={{ display: 'flex', background: 'none', border: 'none', padding: 2, cursor: 'pointer', color: COLORS.primary, flexShrink: 0 }}>
        <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6}>
          <circle cx="12" cy="12" r="9.5" /><path d="M12 11v6" strokeLinecap="round" /><circle cx="12" cy="7.6" r="0.6" fill="currentColor" />
        </svg>
      </button>
    </div>
  );
}

function CeldaFecha({ task, onUpdate }: { task: Task; onUpdate: Props['onUpdate'] }) {
  const [editando, setEditando] = useState(false);
  const valor = (task.due_date || '').slice(0, 10);

  if (editando) {
    return (
      <input type="date" autoFocus aria-label="Fecha de vencimiento" defaultValue={valor}
        onClick={e => e.stopPropagation()}
        onBlur={e => { setEditando(false); if (e.target.value !== valor) onUpdate(task.id, { due_date: e.target.value || null } as Partial<Task>); }}
        onKeyDown={e => { if (e.key === 'Enter') e.currentTarget.blur(); if (e.key === 'Escape') setEditando(false); }}
        style={{ width: 150, fontSize: 13, padding: '4px 6px', border: `1px solid ${COLORS.primary}`, borderRadius: 2, fontFamily: 'inherit' }} />
    );
  }
  return (
    <div onClick={e => { e.stopPropagation(); setEditando(true); }}
      title={valor ? `${fechaCompleta(task.due_date)} · Cambiar la fecha de vencimiento` : 'Agregar fecha de vencimiento'}
      style={{
        height: '100%', display: 'flex', alignItems: 'center', fontSize: 14, cursor: 'pointer',
        color: colorVencimiento(task, COLORS.text),
      }}>
      {textoVencimiento(task.due_date)}
    </div>
  );
}

export function TaskGrid({ tasks, seleccionada, onToggle, onToggleImportant, onOpen, onUpdate, onMenu, propsFila }: Props) {
  return (
    <div style={{ margin: '0 24px 16px', background: 'white', borderRadius: 4, boxShadow: '0 1px 2px rgba(0,0,0,0.08)', overflowX: 'auto' }}>
      <div role="table" aria-label="Tareas" style={{ minWidth: 540 }}>
        <div role="row" style={{
          display: 'grid', gridTemplateColumns: COLUMNAS, alignItems: 'center', height: 44,
          borderBottom: `1px solid ${COLORS.border}`, fontSize: 13, color: COLORS.text,
        }}>
          <span role="columnheader" aria-label="Completada" />
          <span role="columnheader" style={{ paddingLeft: 13 }}>Título</span>
          <span role="columnheader" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>Fecha de vencimiento</span>
          <span role="columnheader" aria-label="Importancia" />
        </div>
        {tasks.map(task => (
          <div key={task.id} role="row" className="fila-tarea" onClick={() => onOpen(task)} {...propsFila?.(task)}
            onContextMenu={onMenu ? e => { e.preventDefault(); onMenu(task, e); } : undefined}
            style={{
              display: 'grid', gridTemplateColumns: COLUMNAS, alignItems: 'center', minHeight: ALTO_FILA,
              borderBottom: `1px solid ${COLORS.border}`, cursor: 'pointer',
              background: seleccionada === task.id ? COLORS.activeBg : 'transparent',
            }}>
            <span role="cell" style={{ display: 'flex', justifyContent: 'center' }}><Circulo task={task} onToggle={onToggle} /></span>
            <span role="cell" style={{ minWidth: 0 }}><CeldaTitulo task={task} onOpen={onOpen} onUpdate={onUpdate} /></span>
            <span role="cell" style={{ height: '100%' }}><CeldaFecha task={task} onUpdate={onUpdate} /></span>
            <span role="cell" style={{ display: 'flex', justifyContent: 'center' }}>
              <button type="button" aria-label={task.important ? 'Quitar importancia' : 'Marcar como importante'}
                onClick={e => { e.stopPropagation(); onToggleImportant(task.id); }}
                style={{ display: 'flex', background: 'none', border: 'none', padding: 4, cursor: 'pointer' }}>
                <svg width={16} height={16} viewBox="0 0 24 24" fill={task.important ? COLORS.primary : 'none'}
                  stroke={task.important ? COLORS.primary : COLORS.muted} strokeWidth={1.8}>
                  <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
                </svg>
              </button>
            </span>
          </div>
        ))}
      </div>
      <style>{`.fila-tarea:hover { background: ${COLORS.hoverBg}; } .fila-tarea:hover .celda-titulo:not(.editando) { border-color: ${COLORS.border} !important; }`}</style>
    </div>
  );
}
