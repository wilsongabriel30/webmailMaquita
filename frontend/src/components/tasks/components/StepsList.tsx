import { useState, useEffect } from 'react';
import { api } from '../../../api/client';

interface Step {
  id: string;
  title: string;
  completed: boolean;
  position: number;
}

interface Props {
  cardId: string;
}

export function StepsList({ cardId }: Props) {
  const [steps, setSteps] = useState<Step[]>([]);
  const [newTitle, setNewTitle] = useState('');
  const [loading, setLoading] = useState(false);

  const load = async () => {
    try {
      const data = await api.get<Step[]>(`/tasks/cards/${cardId}/steps`);
      setSteps(data.sort((a, b) => a.position - b.position));
    } catch { setSteps([]); }
  };

  useEffect(() => { load(); }, [cardId]);

  const addStep = async () => {
    if (!newTitle.trim()) return;
    setLoading(true);
    try {
      await api.post(`/tasks/cards/${cardId}/steps`, { title: newTitle.trim() });
      setNewTitle('');
      load();
    } catch {}
    setLoading(false);
  };

  const toggleStep = async (step: Step) => {
    try {
      await api.put(`/tasks/steps/${step.id}`, { completed: !step.completed });
      setSteps(prev => prev.map(s => s.id === step.id ? { ...s, completed: !s.completed } : s));
    } catch {}
  };

  const removeStep = async (id: string) => {
    try {
      await api.del(`/tasks/steps/${id}`);
      setSteps(prev => prev.filter(s => s.id !== id));
    } catch {}
  };

  const completed = steps.filter(s => s.completed).length;
  const total = steps.length;

  return (
    <div style={{ padding: '12px 20px', borderBottom: '1px solid #edebe9' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#605e5c" strokeWidth="2">
          <path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" />
        </svg>
        <span style={{ fontSize: 13, fontWeight: 600, color: '#323130', flex: 1 }}>
          Pasos {total > 0 && <span style={{ fontWeight: 400, color: '#a19f9d' }}>({completed}/{total})</span>}
        </span>
      </div>

      {total > 0 && (
        <div style={{ height: 3, background: '#edebe9', borderRadius: 2, marginBottom: 8 }}>
          <div style={{ height: '100%', background: '#0078d4', borderRadius: 2, width: `${total > 0 ? (completed / total) * 100 : 0}%`, transition: 'width 0.3s' }} />
        </div>
      )}

      {steps.map(step => (
        <div key={step.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0' }}>
          <input type="checkbox" checked={step.completed} onChange={() => toggleStep(step)}
            style={{ accentColor: '#0078d4', width: 16, height: 16, cursor: 'pointer' }} />
          <span style={{
            flex: 1, fontSize: 13, color: step.completed ? '#a19f9d' : '#323130',
            textDecoration: step.completed ? 'line-through' : 'none',
          }}>{step.title}</span>
          <button onClick={() => removeStep(step.id)}
            style={{ background: 'none', border: 'none', color: '#a19f9d', cursor: 'pointer', fontSize: 14, opacity: 0.5, padding: '0 4px' }}
            onMouseEnter={e => e.currentTarget.style.opacity = '1'}
            onMouseLeave={e => e.currentTarget.style.opacity = '0.5'}>
            ×
          </button>
        </div>
      ))}

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0078d4" strokeWidth="2">
          <path d="M12 5v14M5 12h14" />
        </svg>
        <input value={newTitle} onChange={e => setNewTitle(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && addStep()}
          placeholder="Agregar paso"
          style={{ flex: 1, border: 'none', outline: 'none', fontSize: 13, color: '#323130', padding: '4px 0' }} />
        {newTitle && (
          <button onClick={addStep} disabled={loading}
            style={{ background: 'none', border: 'none', color: '#0078d4', cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>
            Agregar
          </button>
        )}
      </div>
    </div>
  );
}
