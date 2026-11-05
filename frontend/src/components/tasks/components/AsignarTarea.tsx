// «Asignar tarea a» en el panel de una tarea. Desde la fase 2 de la unificación (05/11/2026) abre el cuadro único
// «Asignar tarea» (el de Seguimiento) con los datos de esta tarea; al guardar, la misma tarea pasa a tener seguimiento
// y a quien la recibe le aparece en su «Asignado a mí».
import { useState } from 'react';
import type { Task } from '../types';
import { COLORS } from '../types';
import { useMiembros } from '../hooks/useMiembros';
import { AsignarTareaDialogo, type DesdeTarea } from '../../tareas/AsignarTareaDialogo';
import { CirculoPersona } from './CirculoPersona';
import { desdeTareaDeLista } from './desdeTareaDeLista';
import { filaSeccion, seccion } from './estiloPanel';

export function AsignarTarea({ task, onAsignada }: { task: Task; onAsignada: () => void }) {
  const { miembros } = useMiembros(task.list_id);
  // Se toma una foto de la tarea al abrir: si la lista se refresca mientras tanto, el formulario no se borra.
  const [desde, setDesde] = useState<DesdeTarea | null>(null);
  const asignados = task.asignados || [];
  const nombreDe = (email: string) => miembros.find(m => m.email === email)?.nombre || email.split('@')[0];

  return (
    <div style={seccion}>
      <button type="button" style={filaSeccion} aria-haspopup="dialog" onClick={() => setDesde(desdeTareaDeLista(task))}>
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
      <AsignarTareaDialogo abierto={!!desde} desde={desde} onCerrar={() => setDesde(null)} onCreada={onAsignada} />
    </div>
  );
}
