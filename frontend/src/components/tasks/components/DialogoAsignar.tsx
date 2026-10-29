// Recuadro «Asignar tarea a:» (F5): buscar personas de la organización en el directorio, escribir un mensaje opcional
// y enviar. A quien la recibe le llega un aviso y la tarea le aparece en «Asignado a mí».
import { useEffect, useState } from 'react';
import { api } from '../../../api/client';
import { SelectorPersonas } from '../../tareas/SelectorPersonas';
import type { Task } from '../types';
import { COLORS } from '../types';

interface Props {
  task: Task;
  onCerrar: () => void;
  onAsignada: (t: Task) => void;
}

const boton = (principal: boolean) => ({
  fontSize: 13, padding: '7px 16px', borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit',
  border: `1px solid ${principal ? COLORS.primary : COLORS.border}`,
  background: principal ? COLORS.primary : 'white', color: principal ? 'white' : COLORS.text,
});

export function DialogoAsignar({ task, onCerrar, onAsignada }: Props) {
  const [personas, setPersonas] = useState<string[]>(task.asignados || []);
  const [mensaje, setMensaje] = useState('');
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    const tecla = (e: KeyboardEvent) => { if (e.key === 'Escape') onCerrar(); };
    window.addEventListener('keydown', tecla);
    return () => window.removeEventListener('keydown', tecla);
  }, [onCerrar]);

  const enviar = async () => {
    setEnviando(true);
    setError('');
    try {
      onAsignada(await api.put<Task>(`/tasks/tasks/${task.id}/asignados`, { emails: personas, mensaje: mensaje.trim() }));
      onCerrar();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo asignar la tarea');
    }
    setEnviando(false);
  };

  return (
    <div role="presentation" onClick={onCerrar}
      style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div role="dialog" aria-modal="true" aria-label="Asignar tarea a" onClick={e => e.stopPropagation()}
        style={{
          width: 440, maxWidth: '100%', background: 'white', borderRadius: 8, boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
          fontFamily: "'Segoe UI', system-ui, sans-serif", display: 'flex', flexDirection: 'column',
        }}>
        <div style={{ display: 'flex', alignItems: 'center', padding: '16px 20px 4px' }}>
          <h2 style={{ flex: 1, margin: 0, fontSize: 16, fontWeight: 600, color: COLORS.text }}>Asignar tarea a:</h2>
          <button type="button" aria-label="Cerrar" onClick={onCerrar}
            style={{ background: 'none', border: 'none', fontSize: 20, cursor: 'pointer', color: COLORS.secondary }}>&times;</button>
        </div>
        <div style={{ padding: '0 20px 12px', fontSize: 13, color: COLORS.secondary, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          «{task.title}»
        </div>
        <div style={{ padding: '0 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div role="group" aria-label="Personas" style={{ fontSize: 12, color: COLORS.secondary }}>
            Personas (busca por nombre, correo o departamento)
            <div style={{ marginTop: 4 }}>
              <SelectorPersonas valor={personas} onChange={setPersonas} placeholder="Escribe un nombre o correo…" autoFocus />
            </div>
          </div>
          <label style={{ fontSize: 12, color: COLORS.secondary }}>
            Mensaje (opcional)
            <textarea value={mensaje} maxLength={500} onChange={e => setMensaje(e.target.value)} rows={3}
              placeholder="Por ejemplo: ¿me ayudas con esto antes del viernes?"
              style={{
                display: 'block', width: '100%', marginTop: 4, boxSizing: 'border-box', fontSize: 13, padding: '6px 8px',
                border: `1px solid ${COLORS.border}`, borderRadius: 4, fontFamily: 'inherit', resize: 'vertical',
              }} />
          </label>
          <p style={{ margin: 0, fontSize: 12, color: COLORS.secondary }}>
            Le llegará un aviso y verá la tarea en su «Asignado a mí». Para quitar una asignación, quita a la persona y envía.
          </p>
          {error && <div role="alert" style={{ fontSize: 12, color: '#d13438' }}>{error}</div>}
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, padding: '16px 20px' }}>
          <button type="button" onClick={onCerrar} style={boton(false)}>Cancelar</button>
          <button type="button" disabled={enviando} onClick={enviar} style={boton(true)}>
            {enviando ? 'Enviando…' : 'Enviar'}
          </button>
        </div>
      </div>
    </div>
  );
}
