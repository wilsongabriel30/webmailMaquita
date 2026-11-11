/**
 * Reacciones a un correo, como en Outlook (11/11/2026): carita junto a Responder y menú con 👍 ❤️ 🎉 😂 😮 😢.
 *
 * La reacción no envía ningún correo: se guarda en el servidor junto al mensaje y la ven quienes tienen
 * ese mismo correo en este servidor. Una por persona: elegir otra la cambia y elegir la misma la quita.
 * Al pasar el cursor sobre una reacción se ve quién la puso.
 */
import { useEffect, useRef, useState } from 'react';
import { api } from '../../api/client';
import { showToast } from '../common/Toast';

const CATALOGO = ['👍', '❤️', '🎉', '😂', '😮', '😢'];
const NOMBRE: Record<string, string> = {
  '👍': 'Me gusta', '❤️': 'Me encanta', '🎉': 'Celebrar', '😂': 'Me divierte', '😮': 'Me sorprende', '😢': 'Me entristece',
};

interface Grupo { emoji: string; total: number; personas: string[]; mia: boolean }
interface Respuesta { message_id?: string; reacciones?: Grupo[] }

export function ReaccionesCorreo({ folder, uid }: { folder: string; uid: number }) {
  const [grupos, setGrupos] = useState<Grupo[]>([]);
  const [idMensaje, setIdMensaje] = useState('');
  const [abierto, setAbierto] = useState(false);
  const caja = useRef<HTMLSpanElement>(null);
  const idActual = useRef('');
  const ruta = `/mail/reacciones/${encodeURIComponent(folder)}/${uid}`;

  // El componente se monta de nuevo por cada correo (key en AccionesRapidasCorreo).
  useEffect(() => {
    let vivo = true;
    const cargar = () => {
      api.get<Respuesta>(ruta)
        .then((r) => { if (vivo) { setGrupos(r.reacciones || []); setIdMensaje(r.message_id || ''); } })
        .catch(() => { /* sin reacciones a la vista */ });
    };
    cargar();
    // Otra persona reaccionó a este mismo correo: se actualiza sin recargar la página.
    const alLlegar = (e: Event) => {
      const d = (e as CustomEvent).detail as { message_id?: string } | undefined;
      if (d?.message_id && d.message_id === idActual.current) cargar();
    };
    window.addEventListener('reaccion-correo', alLlegar);
    return () => { vivo = false; window.removeEventListener('reaccion-correo', alLlegar); };
  }, [ruta]);
  useEffect(() => { idActual.current = idMensaje; }, [idMensaje]);

  useEffect(() => {
    if (!abierto) return;
    const fuera = (e: MouseEvent) => { if (caja.current && !caja.current.contains(e.target as Node)) setAbierto(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setAbierto(false); };
    document.addEventListener('mousedown', fuera);
    document.addEventListener('keydown', esc);
    return () => { document.removeEventListener('mousedown', fuera); document.removeEventListener('keydown', esc); };
  }, [abierto]);

  const reaccionar = async (emoji: string) => {
    setAbierto(false);
    try {
      const r = await api.post<Respuesta>(ruta, { emoji });
      setGrupos(r.reacciones || []);
    } catch { showToast('No se pudo guardar la reacción'); }
  };

  if (folder === 'Drafts') return null;

  return (
    <span ref={caja} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, position: 'relative', marginRight: 4 }}>
      {grupos.map((g) => (
        <button key={g.emoji} type="button" onClick={() => reaccionar(g.emoji)}
          title={`${NOMBRE[g.emoji] || 'Reacción'}: ${g.personas.join(', ')}`}
          aria-label={`${NOMBRE[g.emoji] || 'Reacción'}, ${g.total}. ${g.personas.join(', ')}`}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 3, height: 26, padding: '0 8px', borderRadius: 13, cursor: 'pointer',
            fontSize: 13, border: `1px solid ${g.mia ? '#0078d4' : '#d2d0ce'}`, background: g.mia ? '#deecf9' : '#fff', color: '#323130',
          }}>
          <span style={{ fontSize: 15, lineHeight: 1 }}>{g.emoji}</span>{g.total}
        </button>
      ))}
      <button type="button" className="bg-transparent hover:bg-[#f3f2f1] text-[#323130]" title="Reaccionar" aria-label="Reaccionar a este correo"
        aria-haspopup="true" aria-expanded={abierto} onClick={() => setAbierto((v) => !v)}
        style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 30, height: 30, border: 'none', borderRadius: 4, cursor: 'pointer' }}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="9" /><path d="M8.5 14.5a4.5 4.5 0 007 0" /><path d="M9 9.5h.01M15 9.5h.01" />
        </svg>
      </button>
      {abierto && (
        <div role="menu" aria-label="Reacciones" className="bg-white border border-[#e1dfdd]" style={{
          position: 'absolute', top: '100%', right: 0, marginTop: 4, zIndex: 60, display: 'flex', gap: 2, padding: '4px 8px',
          borderRadius: 22, boxShadow: '0 4px 14px rgba(0,0,0,.18)',
        }}>
          {CATALOGO.map((e) => (
            <button key={e} type="button" role="menuitem" title={NOMBRE[e]} aria-label={NOMBRE[e]} onClick={() => reaccionar(e)}
              className="hover:bg-[#f3f2f1]"
              style={{ width: 36, height: 36, fontSize: 22, lineHeight: 1, border: 'none', background: 'transparent', borderRadius: 18, cursor: 'pointer' }}>
              {e}
            </button>
          ))}
        </div>
      )}
    </span>
  );
}
