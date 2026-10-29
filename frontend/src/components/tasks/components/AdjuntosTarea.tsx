// Archivos adjuntos de una tarea (como en To Do). El servidor los valida igual que los adjuntos del correo:
// hasta 25 MB, sin extensiones peligrosas y con el análisis antimalware.
import { useEffect, useRef, useState } from 'react';
import { api } from '../../../api/client';
import type { AdjuntoTarea } from '../types';
import { COLORS } from '../types';
import { seccion } from './estiloPanel';

const MAX_MB = 25;

function tamano(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

async function explicarRechazo(res: Response): Promise<string> {
  try {
    const d = (await res.json()).detail;
    if (typeof d === 'string') return d;
    if (d?.reason) return d.reason;
    if (d?.attachment_blocked) return 'El análisis de seguridad bloqueó el archivo.';
  } catch { /* respuesta sin JSON */ }
  return res.status === 413 ? `El archivo supera el límite de ${MAX_MB} MB.` : `No se pudo subir (HTTP ${res.status}).`;
}

export function AdjuntosTarea({ cardId, onCambio }: { cardId: string; onCambio: () => void }) {
  const [adjuntos, setAdjuntos] = useState<AdjuntoTarea[]>([]);
  const [subiendo, setSubiendo] = useState(false);
  const [error, setError] = useState('');
  const entrada = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let vigente = true;
    api.get<AdjuntoTarea[]>(`/tasks/tasks/${cardId}/adjuntos`)
      .catch(() => [] as AdjuntoTarea[])
      .then(a => { if (vigente) { setAdjuntos(a); setError(''); } });
    return () => { vigente = false; };
  }, [cardId]);

  const subir = async (archivos: FileList | null) => {
    if (!archivos?.length) return;
    setSubiendo(true);
    setError('');
    for (const archivo of Array.from(archivos)) {
      if (archivo.size > MAX_MB * 1024 * 1024) { setError(`«${archivo.name}» supera el límite de ${MAX_MB} MB.`); continue; }
      const datos = new FormData();
      datos.append('archivo', archivo);
      try {
        const res = await fetch(`/api/tasks/tasks/${cardId}/adjuntos`, { method: 'POST', body: datos, credentials: 'include' });
        if (!res.ok) { setError(`«${archivo.name}»: ${await explicarRechazo(res)}`); continue; }
        const nuevo: AdjuntoTarea = await res.json();
        setAdjuntos(prev => [...prev, nuevo]);
      } catch {
        setError(`«${archivo.name}»: no se pudo subir. Revisa la conexión.`);
      }
    }
    setSubiendo(false);
    if (entrada.current) entrada.current.value = '';
    onCambio();
  };

  const borrar = async (a: AdjuntoTarea) => {
    if (!confirm(`¿Quitar el archivo «${a.nombre}» de la tarea?`)) return;
    try {
      await api.del(`/tasks/adjuntos/${a.id}`);
      setAdjuntos(prev => prev.filter(x => x.id !== a.id));
      onCambio();
    } catch {
      setError('No se pudo quitar el archivo.');
    }
  };

  return (
    <div style={{ ...seccion, gap: 6 }}>
      {adjuntos.map(a => (
        <div key={a.id} style={{ display: 'flex', alignItems: 'center', gap: 10, width: '100%' }}>
          <span aria-hidden="true" style={{
            width: 32, height: 32, borderRadius: 4, background: COLORS.activeBg, color: COLORS.primary, fontSize: 10, fontWeight: 600,
            display: 'flex', alignItems: 'center', justifyContent: 'center', textTransform: 'uppercase', flexShrink: 0,
          }}>{(a.nombre.split('.').pop() || '').slice(0, 4)}</span>
          <a href={`/api/tasks/adjuntos/${a.id}`} download={a.nombre} title={`Descargar ${a.nombre}`}
            style={{ flex: 1, minWidth: 0, color: COLORS.text, textDecoration: 'none' }}>
            <div style={{ fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.nombre}</div>
            <div style={{ fontSize: 11, color: COLORS.secondary }}>{tamano(a.tamano)}</div>
          </a>
          <button type="button" aria-label={`Quitar ${a.nombre}`} title="Quitar archivo" onClick={() => borrar(a)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: COLORS.secondary, fontSize: 16, padding: '0 4px' }}>
            &times;
          </button>
        </div>
      ))}
      <button type="button" disabled={subiendo} onClick={() => entrada.current?.click()}
        style={{
          display: 'flex', alignItems: 'center', gap: 12, background: 'none', border: 'none', padding: 0, fontSize: 14,
          fontFamily: 'inherit', color: COLORS.text, cursor: subiendo ? 'wait' : 'pointer',
        }}>
        <svg aria-hidden="true" width={18} height={18} viewBox="0 0 24 24" fill="none" stroke={COLORS.secondary} strokeWidth={1.8}>
          <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
        </svg>
        {subiendo ? 'Subiendo…' : 'Agregar archivo'}
      </button>
      <input ref={entrada} type="file" multiple hidden onChange={e => subir(e.target.files)} />
      {error && <div role="alert" style={{ fontSize: 12, color: '#d13438' }}>{error}</div>}
    </div>
  );
}
