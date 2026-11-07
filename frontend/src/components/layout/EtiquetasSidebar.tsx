/**
 * EtiquetasSidebar.tsx — sección «Etiquetas» de la barra lateral del correo (05/11/2026).
 * Lista las etiquetas del usuario (color y nº de correos), filtra la lista al pulsar una,
 * crea nuevas y, con clic derecho o el botón «⋯», renombra, cambia el color o elimina.
 */
import { useEffect, useState } from 'react';
import { useMailStore } from '../../store/mailStore';
import { useLabels, type Label } from '../../hooks/useLabels';
import { ContextMenu } from '../common/ContextMenu';
import { showToast } from '../common/Toast';
import { DialogoEtiqueta } from '../labels/DialogoEtiqueta';
import { olvidarCorreosDeEtiqueta } from '../../lib/correosPorEtiqueta';

const ICONO_LAPIZ = 'M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z';
const ICONO_COLOR = 'M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485';
const ICONO_BORRAR = 'M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16';

export function EtiquetasSidebar() {
  const { labels, fetchLabels, createLabel, updateLabel, deleteLabel, supported } = useLabels();
  const etiquetaFiltro = useMailStore((s) => s.etiquetaFiltro);
  const setEtiquetaFiltro = useMailStore((s) => s.setEtiquetaFiltro);
  const [plegado, setPlegado] = useState(() => { try { return localStorage.getItem('sidebar.etiquetas.plegado') === '1'; } catch { return false; } });
  const [menu, setMenu] = useState<{ x: number; y: number; label: Label } | null>(null);
  const [dialogo, setDialogo] = useState<{ modo: 'nueva' } | { modo: 'editar'; label: Label } | null>(null);

  useEffect(() => { fetchLabels(); }, [fetchLabels]);
  useEffect(() => { try { localStorage.setItem('sidebar.etiquetas.plegado', plegado ? '1' : '0'); } catch { /* sin almacenamiento */ } }, [plegado]);

  if (!supported) return null;

  const elegir = (l: Label) => {
    olvidarCorreosDeEtiqueta();
    setEtiquetaFiltro(etiquetaFiltro?.id === l.id ? null : { id: l.id, name: l.name, color: l.color });
  };

  const eliminar = async (l: Label) => {
    if (!window.confirm(`¿Eliminar la etiqueta «${l.name}»?\n\nLos correos no se borran; solo pierden esta etiqueta.`)) return;
    try {
      await deleteLabel(l.id);
      if (etiquetaFiltro?.id === l.id) setEtiquetaFiltro(null);
      window.dispatchEvent(new CustomEvent('refresh-message-labels'));
      showToast(`Etiqueta «${l.name}» eliminada`);
    } catch { showToast('No se pudo eliminar la etiqueta'); }
  };

  const guardarDialogo = async (nombre: string, color: string) => {
    if (dialogo?.modo === 'editar') {
      await updateLabel(dialogo.label.id, { name: nombre, color });
      if (etiquetaFiltro?.id === dialogo.label.id) setEtiquetaFiltro({ id: dialogo.label.id, name: nombre, color });
      window.dispatchEvent(new CustomEvent('refresh-message-labels'));
      showToast('Etiqueta actualizada');
    } else {
      await createLabel(nombre, color);
      showToast(`Etiqueta «${nombre}» creada`);
    }
  };

  return (
    <div className="px-1">
      <button onClick={() => setPlegado(!plegado)}
        className="flex items-center gap-1 px-1.5 py-[3px] w-full text-[11px] font-semibold text-[#605e5c] uppercase tracking-wider hover:bg-[#e1dfdd] rounded transition-colors mt-1.5">
        <svg className={`w-[10px] h-[10px] transition-transform ${plegado ? '' : 'rotate-90'}`} fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
        </svg>
        Etiquetas
      </button>
      {!plegado && (
        <>
          {labels.map((l) => {
            const activa = etiquetaFiltro?.id === l.id;
            return (
              <div key={l.id} role="button" tabIndex={0} onClick={() => elegir(l)}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); elegir(l); } }}
                onContextMenu={(e) => { e.preventDefault(); setMenu({ x: e.clientX, y: e.clientY, label: l }); }}
                title={`${l.name}: ${l.count ?? 0} correos`}
                className={`group flex items-center gap-2 px-2 py-[3px] ml-1 rounded cursor-pointer text-[13px] ${activa ? 'bg-[#e1dfdd] dark:bg-[#333] font-semibold' : 'hover:bg-[#f3f2f1] dark:hover:bg-[#2a2a2a]'} text-[#323130] dark:text-[#e0e0e0]`}>
                <span className="w-3 h-3 rounded-sm shrink-0" style={{ backgroundColor: l.color }} />
                <span className="truncate flex-1">{l.name}</span>
                {typeof l.count === 'number' && l.count > 0 && <span className="text-[11px] text-[#605e5c]">{l.count}</span>}
                <button type="button" title="Opciones" aria-label={`Opciones de ${l.name}`}
                  onClick={(e) => { e.stopPropagation(); const r = (e.currentTarget as HTMLElement).getBoundingClientRect(); setMenu({ x: r.left, y: r.bottom, label: l }); }}
                  className="opacity-0 group-hover:opacity-100 focus:opacity-100 w-5 h-5 rounded text-[#605e5c] hover:bg-[#d2d0ce] text-[12px] leading-none">⋯</button>
              </div>
            );
          })}
          <button onClick={() => setDialogo({ modo: 'nueva' })}
            className="flex items-center gap-1.5 px-2 py-1 ml-3 text-[12px] text-[#106ebe] hover:bg-[#e1dfdd] rounded transition-colors">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Nueva etiqueta
          </button>
        </>
      )}
      {menu && (
        <ContextMenu x={menu.x} y={menu.y} onClose={() => setMenu(null)} items={[
          { label: 'Renombrar', icon: ICONO_LAPIZ, onClick: () => setDialogo({ modo: 'editar', label: menu.label }) },
          { label: 'Cambiar color', icon: ICONO_COLOR, onClick: () => setDialogo({ modo: 'editar', label: menu.label }) },
          { label: '', onClick: () => {}, divider: true },
          { label: 'Eliminar', icon: ICONO_BORRAR, danger: true, onClick: () => { void eliminar(menu.label); } },
        ]} />
      )}
      <DialogoEtiqueta abierto={!!dialogo} inicial={dialogo?.modo === 'editar' ? dialogo.label : null}
        onCerrar={() => setDialogo(null)} onGuardar={guardarDialogo} />
    </div>
  );
}
