// «⋯» junto al título de una lista (como en To Do): cambiar el nombre, el color e imprimirla. El resto de opciones
// (compartir, mover, duplicar, eliminar) va en el menú de la lista en la barra.
import { useState } from 'react';
import type { TaskList } from '../types';
import { BOARD_COLORS, COLORS } from '../types';
import { IconoMenuLista } from './IconoMenuLista';
import { MenuContextual, OpcionMenu, SeparadorMenu, TituloMenu } from './MenuContextual';

const SIN_COLOR = '#e0e0e0';

interface Props {
  lista: TaskList;
  onEditarNombre: () => void;
  onColor: (color: string) => void;
  onImprimir: () => void;
}

export function OpcionesLista({ lista, onEditarNombre, onColor, onImprimir }: Props) {
  const [menu, setMenu] = useState<{ x: number; y: number } | null>(null);
  const esDueña = lista.role !== 'member';
  const cerrar = () => setMenu(null);
  return (
    <>
      <button type="button" aria-label="Opciones de la lista" title="Opciones de la lista"
        onClick={e => setMenu({ x: e.clientX, y: e.clientY + 12 })}
        style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '0 6px', color: COLORS.secondary, fontSize: 18, lineHeight: 1 }}>
        ⋯
      </button>
      {menu && (
        <MenuContextual x={menu.x} y={menu.y} etiqueta={`Opciones de la lista ${lista.name}`} onCerrar={cerrar}>
          {lista.list_type === 'custom' && (
            <OpcionMenu deshabilitada={!esDueña} titulo={esDueña ? undefined : 'Solo la propietaria puede cambiarle el nombre'}
              onClick={() => { cerrar(); onEditarNombre(); }}>
              <IconoMenuLista nombre="renombrar" /> Cambiar nombre de la lista
            </OpcionMenu>
          )}
          <OpcionMenu onClick={() => { cerrar(); onImprimir(); }}>
            <IconoMenuLista nombre="imprimir" /> Imprimir esta lista
          </OpcionMenu>
          {lista.list_type === 'custom' && esDueña && <>
            <SeparadorMenu />
            <TituloMenu>Color</TituloMenu>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, padding: '4px 16px 8px' }}>
              {[SIN_COLOR, ...BOARD_COLORS].map(c => (
                <button key={c} type="button"
                  aria-label={c === SIN_COLOR ? 'Sin color' : `Color ${c}`} title={c === SIN_COLOR ? 'Sin color' : c}
                  onClick={() => { cerrar(); onColor(c); }}
                  style={{
                    width: 22, height: 22, borderRadius: '50%', cursor: 'pointer', padding: 0,
                    background: c === SIN_COLOR ? 'white' : c,
                    border: (lista.color || SIN_COLOR).toLowerCase() === c.toLowerCase() ? `2px solid ${COLORS.text}` : `1px solid ${COLORS.border}`,
                  }} />
              ))}
            </div>
          </>}
        </MenuContextual>
      )}
    </>
  );
}
