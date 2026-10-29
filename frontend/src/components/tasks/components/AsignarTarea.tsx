// «Asignar tarea a» en el panel de una tarea (F4; desde la F5 abre el recuadro «Asignar tarea a:»): se puede asignar
// a cualquier persona de la organización y a quien la recibe le aparece en su «Asignado a mí».
import { useState } from 'react';
import type { Task } from '../types';
import { COLORS } from '../types';
import { useMiembros } from '../hooks/useMiembros';
import { CirculoPersona } from './CirculoPersona';
import { DialogoAsignar } from './DialogoAsignar';
import { filaSeccion, seccion } from './estiloPanel';

export function AsignarTarea({ task, onAsignada }: { task: Task; onAsignada: (t: Task) => void }) {
  const { miembros } = useMiembros(task.list_id);
  const [abierto, setAbierto] = useState(false);
  const asignados = task.asignados || [];
  const nombreDe = (email: string) => miembros.find(m => m.email === email)?.nombre || email.split('@')[0];

  return (
    <div style={seccion}>
      <button type="button" style={filaSeccion} aria-haspopup="dialog" onClick={() => setAbierto(true)}>
        <svg aria-hidden="true" width={18} height={18} viewBox="0 0 24 24" fill="none" stroke={asignados.length ? COLORS.primary : COLORS.secondary} strokeWidth={1.6}>
          <path d="M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M19 8v6M22 11h-6" />
        </svg>
        <span style={{ flex: 1, color: asignados.length ? COLORS.primary : COLORS.text }}>
          {asignados.length ? `Asignada a ${asignados.map(nombreDe).join(', ')}` : 'Asignar tarea a…'}
        </span>
        <span style={{ display: 'flex' }}>
          {asignados.slice(0, 4).map(e => <CirculoPersona key={e} email={e} nombre={nombreDe(e)} tamano={22} />)}
        </span>
      </button>
      {abierto && <DialogoAsignar task={task} onCerrar={() => setAbierto(false)} onAsignada={onAsignada} />}
    </div>
  );
}
