// Pasos de una tarea (como en To Do): agregar, marcar, cambiar el texto y quitar. Avisa con onCambio para que
// la fila de la tarea muestre «n de m».
import { useEffect, useState } from 'react';
import { api } from '../../../api/client';
import { COLORS } from '../types';

interface Step {
  id: string;
  title: string;
  completed: boolean;
  position: number;
}

interface Props {
  cardId: string;
  onCambio?: () => void;
}

const ordenar = (s: Step[]) => [...s].sort((a, b) => a.position - b.position);

export function StepsList({ cardId, onCambio }: Props) {
  const [steps, setSteps] = useState<Step[]>([]);
  const [newTitle, setNewTitle] = useState('');
  const [loading, setLoading] = useState(false);
  const [editando, setEditando] = useState<string | null>(null);
  const [texto, setTexto] = useState('');

  useEffect(() => {
    let vigente = true;
    api.get<Step[]>(`/tasks/cards/${cardId}/steps`)
      .catch(() => [] as Step[])
      .then(data => { if (vigente) setSteps(ordenar(data)); });
    return () => { vigente = false; };
  }, [cardId]);

  const addStep = async () => {
    if (!newTitle.trim()) return;
    setLoading(true);
    try {
      const paso = await api.post<Step>(`/tasks/cards/${cardId}/steps`, { title: newTitle.trim() });
      setSteps(prev => ordenar([...prev, paso]));
      setNewTitle('');
      onCambio?.();
    } catch { /* se puede volver a intentar */ }
    setLoading(false);
  };

  const cambiar = async (step: Step, datos: Partial<Step>) => {
    setSteps(prev => prev.map(s => (s.id === step.id ? { ...s, ...datos } : s)));
    try {
      await api.put(`/tasks/steps/${step.id}`, datos);
      onCambio?.();
    } catch {
      setSteps(prev => prev.map(s => (s.id === step.id ? step : s)));
    }
  };

  const guardarTexto = (step: Step) => {
    setEditando(null);
    const t = texto.trim();
    if (t && t !== step.title) void cambiar(step, { title: t });
  };

  const removeStep = async (id: string) => {
    try {
      await api.del(`/tasks/steps/${id}`);
      setSteps(prev => prev.filter(s => s.id !== id));
      onCambio?.();
    } catch { /* queda como estaba */ }
  };

  const completed = steps.filter(s => s.completed).length;
  const total = steps.length;

  return (
    <div style={{ padding: '0 16px 10px' }}>
      {total > 0 && (
        <div style={{ fontSize: 12, color: COLORS.secondary, margin: '4px 0 6px' }}>
          Pasos: {completed} de {total}
        </div>
      )}

      {steps.map(step => (
        <div key={step.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0' }}>
          <input type="checkbox" checked={step.completed} aria-label={`Paso ${step.title}`}
            onChange={() => cambiar(step, { completed: !step.completed })}
            style={{ accentColor: COLORS.primary, width: 16, height: 16, cursor: 'pointer' }} />
          {editando === step.id ? (
            <input autoFocus value={texto} aria-label="Texto del paso" onChange={e => setTexto(e.target.value)}
              onBlur={() => guardarTexto(step)}
              onKeyDown={e => { if (e.key === 'Enter') guardarTexto(step); if (e.key === 'Escape') setEditando(null); }}
              style={{ flex: 1, fontSize: 13, border: `1px solid ${COLORS.primary}`, borderRadius: 2, padding: '2px 4px', fontFamily: 'inherit' }} />
          ) : (
            <span onClick={() => { setEditando(step.id); setTexto(step.title); }} title="Clic para cambiar el texto"
              style={{
                flex: 1, fontSize: 13, cursor: 'text', color: step.completed ? COLORS.muted : COLORS.text,
                textDecoration: step.completed ? 'line-through' : 'none',
              }}>{step.title}</span>
          )}
          <button type="button" aria-label={`Quitar el paso ${step.title}`} onClick={() => removeStep(step.id)}
            style={{ background: 'none', border: 'none', color: COLORS.muted, cursor: 'pointer', fontSize: 14, opacity: 0.6, padding: '0 4px' }}
            onMouseEnter={e => { e.currentTarget.style.opacity = '1'; }}
            onMouseLeave={e => { e.currentTarget.style.opacity = '0.6'; }}>
            ×
          </button>
        </div>
      ))}

      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginTop: 4 }}>
        <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={COLORS.primary} strokeWidth="1.6">
          <path d="M12 5v14M5 12h14" />
        </svg>
        <input className="paso-nuevo" value={newTitle} onChange={e => setNewTitle(e.target.value)} aria-label="Nuevo paso"
          onKeyDown={e => { if (e.key === 'Enter') void addStep(); }}
          placeholder={total ? 'Siguiente paso' : 'Agregar paso'}
          style={{ flex: 1, border: 'none', outline: 'none', background: 'transparent', fontSize: 14, color: COLORS.text, padding: '6px 0', fontFamily: 'inherit' }} />
        {newTitle && (
          <button type="button" onClick={addStep} disabled={loading}
            style={{ background: 'none', border: 'none', color: COLORS.primary, cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>
            Agregar
          </button>
        )}
      </div>
    </div>
  );
}
