// Tablero de Seguimiento: Vencidas / En espera (si hay) / Pendiente / En curso / Completada. Arrastrar una tarjeta
// con el cursor a otra columna cambia su estado. La tarjeta se mueve al soltarla y, si el servidor no acepta el
// cambio, vuelve a su columna (el aviso lo da SeguimientoVista). Una vencida sigue en «Vencidas» hasta completarla
// (ver columnasTablero.ts); su tarjeta muestra el estado nuevo.
import { useState } from 'react';
import type { Tarea } from './tipos';
import { ESTADO_NOMBRE } from './tipos';
import { TarjetaTarea } from './TarjetaTarea';
import { type CambioEstado, type Columna, columnaDe, columnasVisibles, conEstado, destinoValido, sePuedeArrastrar } from './columnasTablero';

interface Props {
  tareas: Tarea[]; onAbrir: (t: Tarea) => void; onCambiarEstado: CambioEstado;
  /** Quitar del tablero (archivar) completadas: no se borran, pasan a «Archivadas». */
  onQuitar?: (ids: string[]) => void;
}
const COLOR: Record<Columna, string> = { vencida: '#d13438', espera: '#8a8886', pendiente: '#0078d4', en_curso: '#c19c00', completada: '#107c10' };
const TIPO = 'application/x-tarea-seguimiento';
const titulo = (col: Columna) => (col === 'vencida' ? 'Vencidas' : ESTADO_NOMBRE[col]);

export function TableroKanban({ tareas, onAbrir, onCambiarEstado, onQuitar }: Props) {
  const [arrastrando, setArrastrando] = useState<Tarea | null>(null);
  const [sobre, setSobre] = useState<Columna | null>(null);
  // Movidas a la espera de la respuesta del servidor: se ven ya con su estado nuevo.
  const [movidas, setMovidas] = useState<Record<string, Parameters<typeof conEstado>[1]>>({});

  const efectiva = (t: Tarea): Tarea => (t.id in movidas ? conEstado(t, movidas[t.id]) : t);
  const soltar = async (t: Tarea, col: Parameters<typeof conEstado>[1]) => {
    setMovidas(m => ({ ...m, [t.id]: col }));
    try {
      await onCambiarEstado(t, col);
    } finally {
      setMovidas(m => { const n = { ...m }; delete n[t.id]; return n; });
    }
  };

  return (
    <div style={{ display: 'flex', gap: 12, padding: '8px 24px 16px', overflowX: 'auto', alignItems: 'flex-start' }}>
      {columnasVisibles(tareas).map(col => {
        const lista = tareas.map(efectiva).filter(t => columnaDe(t) === col);
        const valido = destinoValido(arrastrando && efectiva(arrastrando), col);
        const resaltada = sobre === col && valido;
        return (
          <div key={col} role="list" aria-label={`${titulo(col)}: ${lista.length} tareas`}
            onDragOver={e => { if (valido) { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; if (sobre !== col) setSobre(col); } }}
            onDragLeave={e => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setSobre(null); }}
            onDrop={e => {
              e.preventDefault();
              const id = e.dataTransfer.getData(TIPO) || arrastrando?.id;
              const t = tareas.find(x => x.id === id) || null;
              setArrastrando(null); setSobre(null);
              if (t && destinoValido(efectiva(t), col)) void soltar(t, col);
            }}
            style={{
              minWidth: 260, width: 260, background: resaltada ? '#e5f1fb' : '#f3f2f1', borderRadius: 8, padding: 8,
              borderTop: `4px solid ${COLOR[col]}`, outline: resaltada ? '2px dashed #0078d4' : 'none', outlineOffset: -2,
              transition: 'background .15s', minHeight: 120,
            }}>
            <div style={{ fontWeight: 700, fontSize: 13, color: '#323130', padding: '2px 4px 6px', display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <span style={{ flex: 1 }}>{titulo(col)}</span>
              {col === 'completada' && onQuitar && lista.length > 0 && (
                <button type="button" onClick={() => onQuitar(lista.map(t => t.id))} title="Quitarlas del tablero (no se borran: quedan en «Archivadas»)"
                  style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', fontSize: 12, color: '#0078d4', fontWeight: 400, fontFamily: 'inherit' }}>
                  Quitar todas
                </button>
              )}
              <span style={{ color: '#605e5c', fontWeight: 400 }}>{lista.length}</span>
            </div>
            {lista.map(t => (
              <TarjetaTarea key={t.id} tarea={t} onAbrir={onAbrir} compacta
                arrastrable={sePuedeArrastrar(t)} atenuada={arrastrando?.id === t.id || t.id in movidas}
                onDragStart={(tarea, e) => {
                  // Firefox no empieza a arrastrar si no se guarda un dato.
                  e.dataTransfer.setData(TIPO, tarea.id);
                  e.dataTransfer.setData('text/plain', tarea.titulo);
                  e.dataTransfer.effectAllowed = 'move';
                  setArrastrando(tarea);
                }}
                onDragEnd={() => { setArrastrando(null); setSobre(null); }}
                accion={col === 'completada' && onQuitar ? { texto: 'Quitar del tablero', titulo: 'No se borra: queda en «Archivadas»', onClick: x => onQuitar([x.id]) } : undefined} />
            ))}
            {!lista.length && (
              <div style={{ fontSize: 12, color: '#a19f9d', padding: 10, textAlign: 'center' }}>
                {col === 'espera' ? '' : col === 'vencida' ? 'Nada vencido' : 'Arrastra aquí'}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
