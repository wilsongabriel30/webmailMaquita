/**
 * Conversación con el buzón («pregúntale a tu correo») dentro del panel lateral.
 * Cada pregunta va a /rag/ask; la respuesta muestra en qué correos se basó.
 */
import { useEffect, useRef, useState } from 'react';
import { api } from '../../api/client';
import { useAsistenteStore, type FuenteRag } from './asistenteStore';
import { useEstadoIndice } from './useEstadoIndice';
import { FuentesRespuesta } from './FuentesRespuesta';

const SUGERENCIAS = [
  '¿Qué tengo pendiente o requiere mi atención?',
  '¿Hay correos importantes sin responder?',
  'Resume lo más relevante de mi bandeja.',
];

export function ConversacionCorreo() {
  const mensajes = useAsistenteStore((s) => s.mensajes);
  const agregar = useAsistenteStore((s) => s.agregar);
  const reiniciar = useAsistenteStore((s) => s.reiniciar);
  const { estado, aviso, sincronizando, sincronizar } = useEstadoIndice(true);
  const [pregunta, setPregunta] = useState('');
  const [pensando, setPensando] = useState(false);
  const finRef = useRef<HTMLDivElement>(null);

  useEffect(() => { finRef.current?.scrollIntoView({ block: 'end' }); }, [mensajes.length, pensando]);

  if (estado && !estado.enabled) {
    return (
      <p className="text-xs text-[#605e5c] px-4 py-3">
        Las preguntas sobre tu bandeja aún no están habilitadas para tu dominio.
      </p>
    );
  }

  const preguntar = async (texto?: string) => {
    const q = (texto ?? pregunta).trim();
    if (!q || pensando) return;
    setPregunta('');
    agregar({ rol: 'usuario', texto: q });
    setPensando(true);
    try {
      const r = await api.post<{ answer: string; sources: FuenteRag[] }>('/rag/ask', { question: q });
      agregar({ rol: 'asistente', texto: r?.answer || '(sin respuesta)', fuentes: r?.sources || [] });
    } catch {
      agregar({ rol: 'asistente', texto: 'No pude consultar tu bandeja ahora. Inténtalo de nuevo en un momento.', error: true });
    }
    setPensando(false);
  };

  const sinIndice = estado && estado.indexed === 0;
  const sy = estado?.sync;

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3" aria-live="polite">
        {sinIndice && !sincronizando && (
          <div className="rounded bg-[#eff6fc] p-3 text-xs text-[#323130] space-y-2">
            <p>Para responder sobre tu bandeja primero necesito leerla una vez. Puedes seguir usando el correo mientras tanto.</p>
            <button type="button" onClick={sincronizar}
              className="text-xs px-3 py-1.5 rounded text-white" style={{ backgroundColor: '#0078d4' }}>
              Preparar mi bandeja
            </button>
          </div>
        )}
        {sincronizando && (
          <p className="text-xs text-[#605e5c]" role="status">
            Preparando tu bandeja… {sy ? `${sy.indexed} correos listos.` : ''} Esto sigue solo aunque cierres el panel.
          </p>
        )}
        {aviso && !sincronizando && <p className="text-xs text-[#605e5c]" role="status">{aviso}</p>}

        {mensajes.length === 0 && !sinIndice && (
          <div className="space-y-2">
            <p className="text-xs text-[#605e5c]">Pregúntame sobre tus correos. Por ejemplo:</p>
            {SUGERENCIAS.map((s) => (
              <button key={s} type="button" onClick={() => preguntar(s)}
                className="block w-full text-left text-xs px-3 py-2 rounded border border-[#e1dfdd] text-[#323130] hover:bg-[#f3f2f1]">
                {s}
              </button>
            ))}
          </div>
        )}

        {mensajes.map((m) => (
          <div key={m.id} className={m.rol === 'usuario' ? 'flex justify-end' : ''}>
            <div className={m.rol === 'usuario'
              ? 'max-w-[85%] rounded-lg px-3 py-2 text-[13px] bg-[#deecf9] text-[#323130]'
              : 'rounded-lg px-3 py-2 text-[13px] border border-[#edebe9] bg-[#faf9f8] text-[#323130]'}>
              <p className="whitespace-pre-wrap" style={m.error ? { color: '#a4262c' } : undefined}>{m.texto}</p>
              {m.fuentes && m.fuentes.length > 0 && <FuentesRespuesta fuentes={m.fuentes} />}
            </div>
          </div>
        ))}
        {pensando && <p className="text-xs text-[#605e5c]">Revisando tus correos…</p>}
        <div ref={finRef} />
      </div>

      <form className="border-t border-[#edebe9] p-3 space-y-2" onSubmit={(e) => { e.preventDefault(); preguntar(); }}>
        <textarea value={pregunta} onChange={(e) => setPregunta(e.target.value)} rows={2}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); preguntar(); } }}
          placeholder="Escribe tu pregunta y pulsa Enter…" aria-label="Pregunta para el asistente"
          className="w-full px-3 py-2 rounded text-[13px] resize-none bg-white text-[#323130] border border-[#e1dfdd]" />
        <div className="flex items-center justify-between">
          <button type="button" onClick={reiniciar} disabled={mensajes.length === 0}
            className="text-[11px] text-[#605e5c] hover:underline disabled:opacity-40">Nueva conversación</button>
          <button type="submit" disabled={pensando || !pregunta.trim()}
            className="text-xs px-4 py-1.5 rounded text-white disabled:opacity-50" style={{ backgroundColor: '#0078d4' }}>
            Preguntar
          </button>
        </div>
      </form>
    </div>
  );
}
