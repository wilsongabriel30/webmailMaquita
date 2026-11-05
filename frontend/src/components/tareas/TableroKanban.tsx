// Tablero de Seguimiento: En espera (si hay) / Pendiente / En curso / Completada. Arrastrar una tarjeta con el
// cursor a otra columna cambia su estado. La tarjeta se mueve al soltarla y, si el servidor no acepta el cambio,
// vuelve a su columna (el aviso lo da SeguimientoVista). Las vencidas van en su columna con el semáforo rojo.
import { useState } from 'react';
import type { Tarea } from './tipos';
import { ESTADO_NOMBRE } from './tipos';
import { TarjetaTarea } from './TarjetaTarea';
import { type CambioEstado, type Columna, columnaDe, columnasVisibles, destinoValido, sePuedeArrastrar } from './columnasTablero';

interface Props { tareas: Tarea[]; onAbrir: (t: Tarea) => void; onCambiarEstado: CambioEstado }
const COLOR: Record<Columna, string> = { espera: '#8a8886', pendiente: '#0078d4', en_curso: '#c19c00', completada: '#107c10' };
const TIPO = 'application/x-tarea-seguimiento';

export function TableroKanban({ tareas, onAbrir, onCambiarEstado }: Props) {
  const [arrastrando, setArrastrando] = useState<Tarea | null>(null);
  const [sobre, setSobre] = useState<Columna | null>(null);
  // Movidas a la espera de la respuesta del servidor: se ven ya en su columna nueva.
  const [movidas, setMovidas] = useState<Record<string, Columna>>({});

  const columna = (t: Tarea): Columna => movidas[t.id] ?? columnaDe(t);
  const soltar = async (t: Tarea, col: Columna) => {
    setMovidas(m => ({ ...m, [t.id]: col }));
    try {
      await onCambiarEstado(t, col);
    } finally {
      setMovidas(m => { const n = { ...m }; delete n[t.id]; return n; });
    }
  };

  return (
    <div style={{ display: 'flex', gap: 12, padding: '8px 24px 16px', overflowX: 'auto', height: '100%', alignItems: 'flex-start' }}>
      {columnasVisibles(tareas).map(col => {
        const lista = tareas.filter(t => columna(t) === col);
        const valido = destinoValido(arrastrando && { ...arrastrando, estado: columna(arrastrando) }, col);
        const resaltada = sobre === col && valido;
        return (
          <div key={col} role="list" aria-label={`${ESTADO_NOMBRE[col]}: ${lista.length} tareas`}
            onDragOver={e => { if (valido) { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; if (sobre !== col) setSobre(col); } }}
            onDragLeave={e => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setSobre(null); }}
            onDrop={e => {
              e.preventDefault();
              const id = e.dataTransfer.getData(TIPO) || arrastrando?.id;
              const t = tareas.find(x => x.id === id) || null;
              setArrastrando(null); setSobre(null);
              if (t && destinoValido({ ...t, estado: columna(t) }, col)) void soltar(t, col);
            }}
            style={{
              minWidth: 260, width: 260, background: resaltada ? '#e5f1fb' : '#f3f2f1', borderRadius: 8, padding: 8,
              borderTop: `4px solid ${COLOR[col]}`, outline: resaltada ? '2px dashed #0078d4' : 'none', outlineOffset: -2,
              transition: 'background .15s', minHeight: 120,
            }}>
            <div style={{ fontWeight: 700, fontSize: 13, color: '#323130', padding: '2px 4px 6px', display: 'flex', justifyContent: 'space-between' }}>
              {ESTADO_NOMBRE[col]} <span style={{ color: '#605e5c', fontWeight: 400 }}>{lista.length}</span>
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
                onDragEnd={() => { setArrastrando(null); setSobre(null); }} />
            ))}
            {!lista.length && (
              <div style={{ fontSize: 12, color: '#a19f9d', padding: 10, textAlign: 'center' }}>
                {col === 'espera' ? '' : 'Arrastra aquí'}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
