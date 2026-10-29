// Una lista propia o compartida en la barra de Tareas: emoji o ícono con su color, nombre y pendientes.
// Se arrastra para ordenarla o meterla en un grupo; «⋯» o clic derecho abre sus opciones.
import type { DragEvent, MouseEvent } from 'react';
import type { TaskList } from '../types';
import { COLORS } from '../types';
import { SidebarIcon } from './IconoBarra';
import { NombreEditable } from './NombreEditable';
import { colorDeLista, separarEmoji } from './nombreLista';

interface Props {
  lista: TaskList;
  activa: boolean;
  enGrupo: boolean;
  editando: boolean;
  resaltada: boolean;
  /** Se está arrastrando una tarea encima: soltarla la mueve a esta lista. */
  recibeTarea?: boolean;
  onAbrir: () => void;
  onMenu: (e: MouseEvent) => void;
  onRenombrar: (nombre: string) => void;
  onCancelarEdicion: () => void;
  /** Doble clic: cambiar el nombre ahí mismo (solo la propietaria). */
  onEditar?: () => void;
  arrastre: {
    onDragStart: (e: DragEvent) => void;
    onDragOver: (e: DragEvent) => void;
    onDragLeave: () => void;
    onDrop: (e: DragEvent) => void;
    onDragEnd: () => void;
  };
}

export function FilaLista({ lista, activa, enGrupo, editando, resaltada, recibeTarea, onAbrir, onMenu, onRenombrar, onCancelarEdicion, onEditar, arrastre }: Props) {
  const { emoji, texto } = separarEmoji(lista.name);
  const color = colorDeLista(lista.color);
  const compartida = (lista.miembros ?? 1) > 1;
  return (
    <div
      data-lista={lista.id}
      draggable={!editando}
      {...arrastre}
      onClick={onAbrir}
      onDoubleClick={onEditar}
      onContextMenu={onMenu}
      className="fila-lista-tareas"
      style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: `9px 8px 9px ${enGrupo ? 36 : 16}px`, cursor: 'pointer',
        background: activa ? COLORS.activeBg : 'transparent',
        borderLeft: activa ? `3px solid ${color || COLORS.primary}` : '3px solid transparent',
        borderTop: resaltada ? `2px solid ${COLORS.primary}` : '2px solid transparent',
        outline: recibeTarea ? `2px dashed ${COLORS.primary}` : 'none', outlineOffset: -2,
        fontWeight: activa ? 600 : 400, fontSize: 14, color: COLORS.text,
      }}
    >
      <span aria-hidden="true" style={{ width: 18, display: 'flex', justifyContent: 'center', color: color || COLORS.secondary, fontSize: 16 }}>
        {emoji || <SidebarIcon icon="list" />}
      </span>
      {editando ? (
        <NombreEditable valor={lista.name} etiqueta="Nombre de la lista" onGuardar={onRenombrar} onCancelar={onCancelarEdicion} />
      ) : (
        <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{texto}</span>
      )}
      {compartida && (
        <span title={`Compartida (${lista.miembros} personas)`} aria-label="Lista compartida" style={{ display: 'flex', color: COLORS.secondary }}>
          <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
            <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" />
          </svg>
        </span>
      )}
      {lista.task_count > 0 && (
        <span aria-label={`${lista.task_count} pendientes`} style={{ fontSize: 13, minWidth: 18, textAlign: 'right' }}>{lista.task_count}</span>
      )}
      <button type="button" aria-label={`Opciones de la lista ${lista.name}`} title="Opciones de la lista"
        className="opciones-lista-tareas" onClick={e => { e.stopPropagation(); onMenu(e); }}
        style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '0 4px', color: COLORS.secondary, fontSize: 16, lineHeight: 1 }}>
        ⋯
      </button>
    </div>
  );
}
