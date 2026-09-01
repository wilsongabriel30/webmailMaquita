// Tablero kanban: Pendiente / En curso / Completada (+ En espera y Vencida cuando hay). Arrastrar la tarjeta cambia el estado.
import { useState } from 'react';
import type { Estado, Tarea } from './tipos';
import { ESTADO_NOMBRE } from './tipos';
import { TarjetaTarea } from './TarjetaTarea';

interface Props { tareas: Tarea[]; onAbrir: (t: Tarea) => void; onCambiarEstado: (t: Tarea, estado: Estado) => void }
const COLUMNAS: Estado[] = ['espera', 'pendiente', 'en_curso', 'vencida', 'completada'];
const COLOR: Record<Estado, string> = { espera: '#8a8886', pendiente: '#0078d4', en_curso: '#c19c00', vencida: '#d13438', completada: '#107c10' };

export function TableroKanban({ tareas, onAbrir, onCambiarEstado }: Props) {
  const [arrastrando, setArrastrando] = useState<Tarea | null>(null);
  const [sobre, setSobre] = useState<Estado | null>(null);
  const visibles = COLUMNAS.filter(c => !['espera', 'vencida'].includes(c) || tareas.some(t => t.estado === c));
  return (
    <div style={{ display: 'flex', gap: 12, padding: '8px 24px 16px', overflowX: 'auto', height: '100%', alignItems: 'flex-start' }}>
      {visibles.map(col => {
        const lista = tareas.filter(t => t.estado === col);
        const destinoValido = col !== 'vencida' && arrastrando && arrastrando.estado !== col;
        return (
          <div key={col} onDragOver={e => { if (destinoValido) { e.preventDefault(); setSobre(col); } }} onDragLeave={() => setSobre(null)}
            onDrop={e => { e.preventDefault(); if (arrastrando && destinoValido) onCambiarEstado(arrastrando, col === 'espera' ? 'pendiente' : col); setArrastrando(null); setSobre(null); }}
            style={{ minWidth: 260, width: 260, background: sobre === col ? '#e5f1fb' : '#f3f2f1', borderRadius: 8, padding: 8, borderTop: `4px solid ${COLOR[col]}`, transition: 'background .15s' }}>
            <div style={{ fontWeight: 700, fontSize: 13, color: '#323130', padding: '2px 4px 6px', display: 'flex', justifyContent: 'space-between' }}>
              {ESTADO_NOMBRE[col]} <span style={{ color: '#605e5c', fontWeight: 400 }}>{lista.length}</span>
            </div>
            {lista.map(t => <TarjetaTarea key={t.id} tarea={t} onAbrir={onAbrir} compacta arrastrable onDragStart={setArrastrando} />)}
            {!lista.length && <div style={{ fontSize: 12, color: '#a19f9d', padding: 10, textAlign: 'center' }}>Arrastra aquí</div>}
          </div>
        );
      })}
    </div>
  );
}
