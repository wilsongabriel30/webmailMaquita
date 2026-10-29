// «Asignar a» en el panel de una tarea (como en To Do): a una o varias personas de la lista. En una lista sin compartir
// solo cabe asignársela a una misma; para asignar a otras hay que compartir la lista.
import { useState } from 'react';
import { api } from '../../../api/client';
import type { Task } from '../types';
import { COLORS } from '../types';
import { useMiembros } from '../hooks/useMiembros';
import { CirculoPersona } from './CirculoPersona';
import { desplegable, filaSeccion, seccion } from './estiloPanel';

export function AsignarTarea({ task, onAsignada }: { task: Task; onAsignada: (t: Task) => void }) {
  const { miembros } = useMiembros(task.list_id);
  const [abierto, setAbierto] = useState(false);
  const [error, setError] = useState('');
  const asignados = task.asignados || [];
  const nombreDe = (email: string) => miembros.find(m => m.email === email)?.nombre || email.split('@')[0];

  const guardar = async (emails: string[]) => {
    setError('');
    try {
      onAsignada(await api.put<Task>(`/tasks/tasks/${task.id}/asignados`, { emails }));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo asignar');
    }
  };
  const alternar = (email: string) =>
    void guardar(asignados.includes(email) ? asignados.filter(e => e !== email) : [...asignados, email]);

  return (
    <div style={seccion}>
      <button type="button" style={filaSeccion} aria-expanded={abierto} onClick={() => setAbierto(!abierto)}>
        <svg aria-hidden="true" width={18} height={18} viewBox="0 0 24 24" fill="none" stroke={asignados.length ? COLORS.primary : COLORS.secondary} strokeWidth={1.8}>
          <path d="M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M19 8v6M22 11h-6" />
        </svg>
        <span style={{ flex: 1, color: asignados.length ? COLORS.primary : COLORS.text }}>
          {asignados.length ? `Asignada a ${asignados.map(nombreDe).join(', ')}` : 'Asignar a'}
        </span>
        <span style={{ display: 'flex' }}>
          {asignados.slice(0, 4).map(e => <CirculoPersona key={e} email={e} nombre={nombreDe(e)} tamano={22} />)}
        </span>
      </button>
      {abierto && (
        <div style={{ ...desplegable, width: 260 }}>
          {miembros.map(m => (
            <label key={m.email} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 8px', fontSize: 13, cursor: 'pointer' }}>
              <input type="checkbox" checked={asignados.includes(m.email)} onChange={() => alternar(m.email)} />
              <CirculoPersona email={m.email} nombre={m.nombre} tamano={22} />
              <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.nombre}</span>
            </label>
          ))}
          {miembros.length <= 1 && (
            <div style={{ padding: '6px 8px', fontSize: 12, color: COLORS.secondary }}>
              Para asignar a otras personas, comparte primero la lista.
            </div>
          )}
        </div>
      )}
      {error && <div role="alert" style={{ marginLeft: 30, marginTop: 4, fontSize: 12, color: '#d13438' }}>{error}</div>}
    </div>
  );
}
