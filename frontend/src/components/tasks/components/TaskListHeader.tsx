import { useState } from 'react';
import type { ActiveView, Orden, TaskList } from '../types';
import { SMART_LISTS, COLORS } from '../types';
import { SelectorVista } from './SelectorVista';
import type { ModoVista } from './modoVista';
import { ORDENES } from './ordenarTareas';
import { colorDeLista, separarEmoji } from './nombreLista';

interface Props {
  activeView: ActiveView;
  /** Lista propia o compartida abierta (su nombre, emoji y color van en el título). */
  lista?: TaskList;
  orden: Orden;
  onOrdenChange: (o: Orden) => void;
  modo: ModoVista;
  onModoChange: (m: ModoVista) => void;
  /** Texto buscado: el título pasa a ser «Resultados de …». */
  busqueda?: string;
}

const SORT_OPTIONS = ORDENES;

export function TaskListHeader({ activeView, lista, orden: sortBy, onOrdenChange: onSortChange, modo, onModoChange, busqueda }: Props) {
  const [showSort, setShowSort] = useState(false);
  const smart = SMART_LISTS.find(s => s.id === activeView);
  const nombre = lista ? separarEmoji(lista.name) : { emoji: '', texto: '' };
  const title = busqueda ? `Resultados de «${busqueda}»` : smart ? smart.name : (nombre.texto || 'Tareas');
  const isSmartList = !!smart;
  const colorTitulo = isSmartList ? COLORS.primary : (colorDeLista(lista?.color) || COLORS.text);

  const today = new Date();
  const dateStrRaw = today.toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' });
  const dateStr = dateStrRaw.charAt(0).toUpperCase() + dateStrRaw.slice(1);

  const currentSort = SORT_OPTIONS.find(o => o.value === sortBy);

  return (
    <div style={{
      padding: '20px 24px 12px', display: 'flex', flexDirection: 'column', gap: 8,
      fontFamily: "'Segoe UI', system-ui, sans-serif",
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button
          aria-label="Alternar panel de listas"
          onClick={() => window.dispatchEvent(new CustomEvent('toggle-tasks-sidebar'))}
          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4, display: 'flex', color: COLORS.secondary }}
        >
          <svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
        <h1 style={{
          fontSize: 20, fontWeight: 600, margin: 0,
          color: colorTitulo,
        }}>
          {!busqueda && nombre.emoji && <span aria-hidden="true" style={{ marginRight: 8 }}>{nombre.emoji}</span>}
          {title}
        </h1>
        <SelectorVista modo={modo} onCambiar={onModoChange} />
        <div style={{ flex: 1 }} />

        {/* Sort button with dropdown */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setShowSort(!showSort)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '6px 12px', fontSize: 13, color: COLORS.secondary,
              background: 'transparent', border: 'none', cursor: 'pointer', borderRadius: 4,
            }}
            onMouseEnter={e => (e.currentTarget.style.background = COLORS.hoverBg)}
            onMouseLeave={e => { if (!showSort) e.currentTarget.style.background = 'transparent'; }}
          >
            <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M3 6h18M3 12h12M3 18h6" />
            </svg>
            <span>Ordenar</span>
            {currentSort && sortBy !== (lista || activeView === 'tasks' ? 'manual' : 'date') && (
              <span style={{ fontSize: 11, color: COLORS.primary, fontWeight: 500 }}>
                ({currentSort.label})
              </span>
            )}
          </button>

          {showSort && (
            <>
              <div style={{ position: 'fixed', inset: 0, zIndex: 99 }} onClick={() => setShowSort(false)} />
              <div style={{
                position: 'absolute', right: 0, top: '100%', marginTop: 4, zIndex: 100,
                background: 'white', border: `1px solid ${COLORS.border}`, borderRadius: 6,
                boxShadow: '0 4px 12px rgba(0,0,0,0.15)', padding: 4, minWidth: 200,
              }}>
                {SORT_OPTIONS.map(opt => (
                  <div key={opt.value} role="menuitemradio" aria-checked={sortBy === opt.value}
                    onClick={() => { onSortChange(opt.value); setShowSort(false); }}
                    style={{
                      padding: '8px 12px', fontSize: 13, cursor: 'pointer', borderRadius: 4,
                      display: 'flex', alignItems: 'center', gap: 8,
                      fontWeight: sortBy === opt.value ? 600 : 400,
                      color: sortBy === opt.value ? COLORS.primary : COLORS.text,
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = COLORS.hoverBg)}
                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                  >
                    {sortBy === opt.value && (
                      <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke={COLORS.primary} strokeWidth={3}>
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    )}
                    <span style={{ marginLeft: sortBy === opt.value ? 0 : 22 }}>{opt.label}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {activeView === 'my-day' && (
        <div style={{ fontSize: 13, color: COLORS.secondary }}>{dateStr}</div>
      )}
    </div>
  );
}
