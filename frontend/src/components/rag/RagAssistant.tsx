import { useEffect, useState } from 'react';
import { api } from '../../api/client';

const SUGERENCIAS = [
  '¿Tengo algo pendiente o que requiera mi atención?',
  '¿Hay correos importantes sin responder?',
  'Resume lo más relevante de mi bandeja.',
];

interface Status { enabled: boolean; indexed: number; }
interface Source { subject: string; sender: string; sim: number; }

export function RagAssistant() {
  const [status, setStatus] = useState<Status | null>(null);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState<'sync' | 'ask' | ''>('');
  const [answer, setAnswer] = useState('');
  const [sources, setSources] = useState<Source[]>([]);

  const loadStatus = () => api.get<Status>('/rag/status').then(setStatus).catch(() => setStatus({ enabled: false, indexed: 0 }));
  useEffect(() => { loadStatus(); }, []);

  const sync = async () => {
    setBusy('sync');
    try { await api.post('/rag/sync', {}); await loadStatus(); } catch { /* fail-open */ }
    setBusy('');
  };
  const ask = async (question?: string) => {
    const text = (question ?? q).trim();
    if (!text) return;
    setQ(text); setBusy('ask'); setAnswer(''); setSources([]);
    try {
      const r = await api.post<{ answer: string; sources: Source[] }>('/rag/ask', { question: text });
      setAnswer(r?.answer || ''); setSources(r?.sources || []);
    } catch { setAnswer('Hubo un error al consultar.'); }
    setBusy('');
  };

  if (status && !status.enabled) {
    return (
      <div className="p-8 max-w-2xl mx-auto text-center" style={{ color: '#605e5c' }}>
        <h1 className="text-lg font-semibold mb-2" style={{ color: '#323130' }}>Pregúntale a tu correo</h1>
        <p className="text-sm">El asistente de correo con IA aún no está habilitado para tu dominio.</p>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-4">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: '#323130' }}>Pregúntale a tu correo</h1>
        <p className="text-sm" style={{ color: '#605e5c' }}>
          Busca y responde sobre tu bandeja con IA local y privada. {status ? `${status.indexed} correos indexados.` : ''}
        </p>
      </div>

      {status && status.indexed === 0 && (
        <div className="rounded-lg p-4 text-sm" style={{ background: '#fff4ce', color: '#7a6400' }}>
          Aún no he indexado tu bandeja. Pulsa <b>Sincronizar mi bandeja</b> para empezar.
        </div>
      )}

      <div className="flex gap-2 flex-wrap">
        {SUGERENCIAS.map((sg, i) => (
          <button key={i} onClick={() => ask(sg)} className="text-xs px-3 py-1.5 rounded-full" style={{ border: '1px solid #e1dfdd', color: '#484644' }}>{sg}</button>
        ))}
      </div>

      <div className="flex gap-2 items-end">
        <textarea value={q} onChange={(e) => setQ(e.target.value)} rows={2} placeholder="Escribe tu pregunta…"
          className="flex-1 px-3 py-2 rounded text-sm resize-none" style={{ border: '1px solid #e1dfdd' }} />
        <button onClick={() => ask()} disabled={busy !== '' || !q.trim()} className="text-white text-sm px-4 py-2 rounded disabled:opacity-50" style={{ backgroundColor: '#0078d4' }}>
          {busy === 'ask' ? 'Pensando…' : 'Preguntar'}
        </button>
      </div>

      <div>
        <button onClick={sync} disabled={busy !== ''} className="text-xs px-3 py-1.5 rounded disabled:opacity-50" style={{ border: '1px solid #e1dfdd', color: '#484644' }}>
          {busy === 'sync' ? 'Sincronizando…' : 'Sincronizar mi bandeja'}
        </button>
      </div>

      {answer && (
        <div className="rounded-lg p-4 space-y-2" style={{ border: '1px solid #e1dfdd', background: '#faf9f8' }}>
          <pre className="text-sm whitespace-pre-wrap" style={{ color: '#323130', fontFamily: 'inherit' }}>{answer}</pre>
          {sources.length > 0 && (
            <div className="text-xs pt-2" style={{ color: '#605e5c', borderTop: '1px solid #edebe9' }}>
              <div className="font-medium mt-1 mb-1">Basado en:</div>
              <ul className="space-y-0.5">
                {sources.map((s, i) => <li key={i}>· {s.subject} <span style={{ color: '#a19f9d' }}>({s.sim})</span></li>)}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
