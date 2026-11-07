/**
 * Acciones de IA sobre el correo abierto: resumirlo y sugerir respuestas.
 * Usa los mismos servicios que la vista del correo (/ai/summarize y /ai/smart-reply).
 */
import { useState } from 'react';
import { api } from '../../api/client';
import { useMailStore } from '../../store/mailStore';
import type { MessageFull } from '../../types';
import { abrirRespuestaConTexto } from './abrirRespuesta';

export function AccionesCorreoActual() {
  const msg = useMailStore((s) => s.selectedMessage);
  const carpeta = useMailStore((s) => s.currentFolder);

  if (!msg) {
    return (
      <p className="text-xs text-[#605e5c] px-4 py-3">
        Abre un correo y aquí podrás resumirlo o pedir ideas para responder.
      </p>
    );
  }
  // La clave reinicia lo generado (resumen, ideas) al cambiar de correo.
  return <AccionesDeUnCorreo key={`${carpeta}:${msg.uid}`} msg={msg} carpeta={carpeta} />;
}

function AccionesDeUnCorreo({ msg, carpeta }: { msg: MessageFull; carpeta: string }) {
  const [cargando, setCargando] = useState<'' | 'resumen' | 'respuestas'>('');
  const [resumen, setResumen] = useState('');
  const [respuestas, setRespuestas] = useState<string[]>([]);
  const [error, setError] = useState('');

  const resumir = async () => {
    setCargando('resumen'); setError(''); setResumen('');
    try {
      const r = await api.post<{ summary: string }>('/ai/summarize', { message_ids: [String(msg.uid)], folder: carpeta });
      setResumen(r?.summary || 'No se pudo generar el resumen.');
    } catch {
      setError('La IA no respondió. Inténtalo de nuevo en un momento.');
    }
    setCargando('');
  };

  const sugerir = async () => {
    setCargando('respuestas'); setError(''); setRespuestas([]);
    try {
      const r = await api.post<{ suggestions: string[] }>('/ai/smart-reply', { message_id: String(msg.uid), folder: carpeta });
      const lista = (r?.suggestions || []).filter(Boolean);
      if (lista.length) setRespuestas(lista);
      else setError('La IA no propuso respuestas para este correo.');
    } catch {
      setError('La IA no respondió. Inténtalo de nuevo en un momento.');
    }
    setCargando('');
  };

  const boton = 'text-xs px-3 py-1.5 rounded border border-[#e1dfdd] text-[#323130] hover:bg-[#f3f2f1] disabled:opacity-50';

  return (
    <div className="px-4 py-3 space-y-2">
      <p className="text-[11px] text-[#605e5c] truncate" title={msg.subject}>
        Correo abierto: <span className="text-[#323130] font-medium">{msg.subject || '(sin asunto)'}</span>
      </p>
      <div className="flex gap-2 flex-wrap">
        <button type="button" className={boton} onClick={resumir} disabled={cargando !== ''}>
          {cargando === 'resumen' ? 'Resumiendo…' : 'Resumir este correo'}
        </button>
        <button type="button" className={boton} onClick={sugerir} disabled={cargando !== ''}>
          {cargando === 'respuestas' ? 'Pensando…' : 'Ideas para responder'}
        </button>
      </div>

      {error && <p className="text-xs" style={{ color: '#a4262c' }} role="alert">{error}</p>}

      {resumen && (
        <div className="rounded border border-[#edebe9] bg-[#faf9f8] p-3">
          <p className="text-[11px] font-semibold text-[#605e5c] mb-1">Resumen</p>
          <p className="text-[13px] text-[#323130] whitespace-pre-wrap">{resumen}</p>
        </div>
      )}

      {respuestas.length > 0 && (
        <div className="space-y-2">
          <p className="text-[11px] font-semibold text-[#605e5c]">Elige una para empezar tu respuesta:</p>
          {respuestas.map((texto, i) => (
            <button key={i} type="button" onClick={() => abrirRespuestaConTexto(msg, texto)}
              className="block w-full text-left text-[13px] text-[#323130] rounded border border-[#edebe9] bg-white hover:bg-[#eff6fc] p-2.5"
              title="Abre la respuesta con este texto; podrás editarlo antes de enviar">
              {texto}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
