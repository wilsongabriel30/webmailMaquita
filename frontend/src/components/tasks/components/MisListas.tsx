// Listas propias, compartidas y grupos de la barra de Tareas (F2, como en To Do).
// Arrastrar una lista sobre otra la coloca antes; sobre un grupo, la mete en él; al final de la barra,
// la saca del grupo. Lo mismo se puede hacer sin arrastrar, desde el menú de la lista (clic derecho o «⋯»), que desde
// la F5 es el de To Do: compartir, mover a un grupo, quitar del grupo, mover arriba/abajo, duplicar, imprimir y
// eliminar. Cambiar el nombre y el color se hace desde «⋯» junto al título de la lista.
import { useState, type DragEvent, type MouseEvent } from 'react';
import type { ActiveView, TaskGroup, TaskList } from '../types';
import { COLORS } from '../types';
import { armarBarra, desplazar, mover, moverAGrupo, puedeDesplazar, type Destino, type Elemento } from './barraOrden';
import { FilaLista } from './FilaLista';
import { SidebarIcon } from './IconoBarra';
import { IconoMenuLista } from './IconoMenuLista';
import { MenuContextual, OpcionMenu, SeparadorMenu, SubmenuOpcion } from './MenuContextual';
import { NombreEditable } from './NombreEditable';
import { esTarea, idTarea } from './arrastreTarea';

interface Props {
  listas: TaskList[];
  grupos: TaskGroup[];
  activeView: ActiveView;
  onViewChange: (v: ActiveView) => void;
  onCambiarLista: (id: string, cambios: { name?: string; color?: string }) => void;
  onEliminarLista: (lista: TaskList) => void;
  onRenombrarGrupo: (id: string, nombre: string) => void;
  onEliminarGrupo: (grupo: TaskGroup) => void;
  onGuardarBarra: (barra: Elemento[]) => void;
  /** Una tarea arrastrada desde la lista se soltó sobre una lista de la barra: se mueve allí. */
  onSoltarTarea?: (listId: string, taskId: string) => void;
  /** Abrir el diálogo de compartir (propietaria) o de personas de la lista (miembro). */
  onCompartir?: (lista: TaskList) => void;
  onDuplicar?: (lista: TaskList) => void;
  onImprimir?: (lista: TaskList) => void;
}

type Arrastrado = { tipo: 'grupo' | 'lista'; id: string };
type Menu = { tipo: 'grupo' | 'lista'; id: string; x: number; y: number };

export function MisListas({ listas, grupos, activeView, onViewChange, onCambiarLista, onEliminarLista, onRenombrarGrupo, onEliminarGrupo, onGuardarBarra, onSoltarTarea, onCompartir, onDuplicar, onImprimir }: Props) {
  const [arrastrado, setArrastrado] = useState<Arrastrado | null>(null);
  const [sobre, setSobre] = useState<string | null>(null);
  const [recibe, setRecibe] = useState<string | null>(null);
  const [menu, setMenu] = useState<Menu | null>(null);
  const [editando, setEditando] = useState<string | null>(null);
  const [plegados, setPlegados] = useState<Set<string>>(new Set());

  const barra = armarBarra(listas, grupos);
  const porId = new Map(listas.map(l => [l.id, l]));

  const soltar = (destino: Destino) => (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (arrastrado) onGuardarBarra(mover(barra, arrastrado, destino));
    setArrastrado(null);
    setSobre(null);
  };
  // Sobre una lista también se puede soltar una tarea (la mueve a esa lista).
  const tomaTarea = (yo: Arrastrado, e: DragEvent) => yo.tipo === 'lista' && !!onSoltarTarea && esTarea(e);
  const arrastreDe = (yo: Arrastrado, destino: Destino) => ({
    onDragStart: (e: DragEvent) => { e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', yo.id); setArrastrado(yo); },
    onDragOver: (e: DragEvent) => {
      if (tomaTarea(yo, e)) { e.preventDefault(); setRecibe(yo.id); return; }
      if (arrastrado) { e.preventDefault(); setSobre(yo.id); }
    },
    onDragLeave: () => { setSobre(s => (s === yo.id ? null : s)); setRecibe(r => (r === yo.id ? null : r)); },
    onDrop: (e: DragEvent) => {
      if (tomaTarea(yo, e)) { e.preventDefault(); e.stopPropagation(); setRecibe(null); onSoltarTarea!(yo.id, idTarea(e)); return; }
      soltar(destino)(e);
    },
    onDragEnd: () => { setArrastrado(null); setSobre(null); },
  });
  const abrirMenu = (tipo: Menu['tipo'], id: string) => (e: MouseEvent) => {
    e.preventDefault();
    setMenu({ tipo, id, x: e.clientX, y: e.clientY });
  };

  const fila = (id: string, enGrupo: boolean) => {
    const l = porId.get(id);
    if (!l) return null;
    return (
      <FilaLista key={id} lista={l} activa={activeView === id} enGrupo={enGrupo}
        editando={editando === id} resaltada={sobre === id && arrastrado?.id !== id} recibeTarea={recibe === id}
        onAbrir={() => onViewChange(id)} onMenu={abrirMenu('lista', id)}
        onRenombrar={n => { setEditando(null); onCambiarLista(id, { name: n }); }}
        onCancelarEdicion={() => setEditando(null)}
        onEditar={l.role !== 'member' ? () => setEditando(id) : undefined}
        arrastre={arrastreDe({ tipo: 'lista', id }, { tipo: 'antesDeLista', id })} />
    );
  };

  const lista = menu?.tipo === 'lista' ? porId.get(menu.id) : undefined;
  const grupo = menu?.tipo === 'grupo' ? grupos.find(g => g.id === menu.id) : undefined;
  const esDueña = lista?.role !== 'member';
  const cerrar = () => setMenu(null);

  return (
    <div role="list" aria-label="Mis listas">
      {barra.map(el => {
        if (el.tipo === 'lista') return fila(el.id, false);
        const g = grupos.find(x => x.id === el.id);
        if (!g) return null;
        const plegado = plegados.has(g.id);
        const arr = arrastreDe({ tipo: 'grupo', id: g.id }, { tipo: 'enGrupo', id: g.id });
        return (
          <div key={g.id} role="group" aria-label={`Grupo ${g.name}`}>
            <div draggable={editando !== g.id} {...arr} onContextMenu={abrirMenu('grupo', g.id)}
              onClick={() => setPlegados(p => { const n = new Set(p); if (n.has(g.id)) n.delete(g.id); else n.add(g.id); return n; })}
              aria-expanded={!plegado}
              style={{
                display: 'flex', alignItems: 'center', gap: 10, padding: '9px 8px 9px 16px', cursor: 'pointer', fontSize: 14,
                color: COLORS.text, background: sobre === g.id && arrastrado?.id !== g.id ? COLORS.activeBg : 'transparent',
                borderLeft: '3px solid transparent',
              }}>
              <span aria-hidden="true" style={{ display: 'flex', color: COLORS.secondary }}><SidebarIcon icon="folder" /></span>
              {editando === g.id ? (
                <NombreEditable valor={g.name} etiqueta="Nombre del grupo"
                  onGuardar={n => { setEditando(null); onRenombrarGrupo(g.id, n); }} onCancelar={() => setEditando(null)} />
              ) : (
                <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{g.name}</span>
              )}
              <svg aria-hidden="true" width={12} height={12} viewBox="0 0 24 24" fill="none" stroke={COLORS.secondary} strokeWidth={2.5}
                style={{ transform: plegado ? 'rotate(-90deg)' : 'none', transition: 'transform 0.15s' }}>
                <polyline points="6 9 12 15 18 9" />
              </svg>
              <button type="button" aria-label={`Opciones del grupo ${g.name}`} title="Opciones del grupo"
                onClick={e => { e.stopPropagation(); abrirMenu('grupo', g.id)(e); }}
                style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '0 4px', color: COLORS.secondary, fontSize: 16, lineHeight: 1 }}>
                ⋯
              </button>
            </div>
            {!plegado && el.listas.map(id => fila(id, true))}
            {!plegado && el.listas.length === 0 && (
              <div style={{ padding: '4px 16px 8px 46px', fontSize: 12, color: COLORS.muted }}>
                Arrastra listas aquí
              </div>
            )}
          </div>
        );
      })}

      {arrastrado && (
        <div onDragOver={e => { e.preventDefault(); setSobre('__final'); }} onDragLeave={() => setSobre(null)}
          onDrop={soltar({ tipo: 'alFinal' })}
          style={{
            margin: '4px 16px', padding: '10px 8px', fontSize: 12, textAlign: 'center', borderRadius: 4,
            color: COLORS.secondary, border: `1px dashed ${sobre === '__final' ? COLORS.primary : COLORS.border}`,
            background: sobre === '__final' ? COLORS.activeBg : 'transparent',
          }}>
          {arrastrado.tipo === 'lista' ? 'Suelta aquí para dejarla fuera de los grupos' : 'Suelta aquí para llevar el grupo al final'}
        </div>
      )}

      {menu && lista && (
        <MenuContextual x={menu.x} y={menu.y} etiqueta={`Opciones de la lista ${lista.name}`} onCerrar={cerrar}>
          {onCompartir && (
            <OpcionMenu onClick={() => { cerrar(); onCompartir(lista); }}>
              <IconoMenuLista nombre="compartir" /> {esDueña ? 'Compartir la lista' : 'Personas de la lista'}
            </OpcionMenu>
          )}
          {grupos.some(g => g.id !== lista.group_id) && (
            <SubmenuOpcion etiqueta="Mover la lista a…" icono={<IconoMenuLista nombre="moverA" />}>
              {grupos.filter(g => g.id !== lista.group_id).map(g => (
                <OpcionMenu key={g.id} onClick={() => { cerrar(); onGuardarBarra(moverAGrupo(barra, lista.id, g.id)); }}>
                  <SidebarIcon icon="folder" size={16} /> {g.name}
                </OpcionMenu>
              ))}
            </SubmenuOpcion>
          )}
          {lista.group_id && (
            <OpcionMenu onClick={() => { cerrar(); onGuardarBarra(moverAGrupo(barra, lista.id, null)); }}>
              <IconoMenuLista nombre="quitarGrupo" /> Quitar del grupo
            </OpcionMenu>
          )}
          {puedeDesplazar(barra, lista.id, -1) && (
            <OpcionMenu onClick={() => { cerrar(); onGuardarBarra(desplazar(barra, lista.id, -1)); }}>
              <IconoMenuLista nombre="arriba" /> Mover arriba
            </OpcionMenu>
          )}
          {puedeDesplazar(barra, lista.id, 1) && (
            <OpcionMenu onClick={() => { cerrar(); onGuardarBarra(desplazar(barra, lista.id, 1)); }}>
              <IconoMenuLista nombre="abajo" /> Mover abajo
            </OpcionMenu>
          )}
          {onDuplicar && (
            <OpcionMenu onClick={() => { cerrar(); onDuplicar(lista); }}>
              <IconoMenuLista nombre="duplicar" /> Duplicar lista
            </OpcionMenu>
          )}
          {onImprimir && (
            <OpcionMenu onClick={() => { cerrar(); onImprimir(lista); }}>
              <IconoMenuLista nombre="imprimir" /> Imprimir esta lista
            </OpcionMenu>
          )}
          <SeparadorMenu />
          {esDueña ? (
            <OpcionMenu peligro onClick={() => { cerrar(); onEliminarLista(lista); }}>
              <IconoMenuLista nombre="eliminar" /> Eliminar lista
            </OpcionMenu>
          ) : onCompartir && (
            <OpcionMenu peligro titulo="Dejarás de ver la lista; sus tareas siguen para las demás personas"
              onClick={() => { cerrar(); onCompartir(lista); }}>
              <IconoMenuLista nombre="salir" /> Salir de la lista…
            </OpcionMenu>
          )}
        </MenuContextual>
      )}

      {menu && grupo && (
        <MenuContextual x={menu.x} y={menu.y} etiqueta={`Opciones del grupo ${grupo.name}`} onCerrar={cerrar}>
          <OpcionMenu onClick={() => { cerrar(); setEditando(grupo.id); }}>Cambiar nombre</OpcionMenu>
          <SeparadorMenu />
          <OpcionMenu peligro titulo="Sus listas no se borran: quedan fuera del grupo"
            onClick={() => { cerrar(); onEliminarGrupo(grupo); }}>Eliminar grupo</OpcionMenu>
        </MenuContextual>
      )}
    </div>
  );
}
