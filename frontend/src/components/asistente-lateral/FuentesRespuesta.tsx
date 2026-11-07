/**
 * Correos en los que se basó una respuesta del asistente. Cada uno abre el correo con un clic,
 * aunque la persona esté en otra sección (Calendario, Contactos…).
 */
import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { abrirCorreoPorUid } from '../../lib/deepLinkCorreo';
import { useResponsive } from '../../hooks/useResponsive';
import { useAsistenteStore, type FuenteRag } from './asistenteStore';

const RUTAS_CORREO = ['/', '/webmail', '/webmail/'];

export function FuentesRespuesta({ fuentes }: { fuentes: FuenteRag[] }) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { isMobile } = useResponsive();
  const cerrar = useAsistenteStore((s) => s.cerrar);
  const [fallo, setFallo] = useState('');

  const abrir = async (f: FuenteRag) => {
    if (!f.folder || !f.uid) return;
    setFallo('');
    if (!RUTAS_CORREO.includes(pathname)) navigate('/');
    const ok = await abrirCorreoPorUid(f.folder, f.uid);
    if (!ok) { setFallo('Ese correo ya no está en tu bandeja (quizá se movió o se eliminó).'); return; }
    if (isMobile) cerrar(); // en el móvil el panel tapa el correo
  };

  return (
    <div className="mt-2 pt-2 border-t border-[#edebe9]">
      <p className="text-[11px] text-[#605e5c] mb-1">
        Basado en {fuentes.length} {fuentes.length === 1 ? 'correo' : 'correos'}{fuentes.some((f) => f.uid) ? ' (pulsa para abrirlo)' : ''}:
      </p>
      <ul className="space-y-1">
        {fuentes.map((f, i) => (
          <li key={i}>
            {f.uid ? (
              <button type="button" onClick={() => abrir(f)} title={`Abrir: ${f.subject} — ${f.sender}`}
                className="w-full text-left rounded px-2 py-1 bg-white border border-[#edebe9] hover:bg-[#eff6fc]">
                <span className="block text-[12px] text-[#0078d4] truncate">{f.subject || '(sin asunto)'}</span>
                <span className="block text-[11px] text-[#605e5c] truncate">{f.sender}</span>
              </button>
            ) : (
              <span className="block text-[11px] text-[#605e5c] truncate" title={`${f.subject} — ${f.sender}`}>· {f.subject} ({f.sender})</span>
            )}
          </li>
        ))}
      </ul>
      {fallo && <p className="text-[11px] mt-1" style={{ color: '#a4262c' }} role="alert">{fallo}</p>}
    </div>
  );
}
