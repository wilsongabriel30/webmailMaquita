/**
 * «Enviando…» arriba de la lista de Enviados (06/11/2026): el correo se ve ahí desde que se
 * pulsa Enviar (pasada la cuenta atrás de «Deshacer»), mientras el servidor lo envía por detrás
 * (lib/envioSegundoPlano.ts). Al terminar desaparece y la lista ya trae el correo enviado.
 */
import { useEffect, useState } from 'react';
import { enviosEnCurso, type EnvioEnCurso } from '../../lib/envioSegundoPlano';

export function EnviosEnCurso() {
  const [lista, setLista] = useState<EnvioEnCurso[]>(enviosEnCurso());
  useEffect(() => {
    const h = () => setLista(enviosEnCurso());
    window.addEventListener('envios-en-curso', h);
    return () => window.removeEventListener('envios-en-curso', h);
  }, []);
  if (!lista.length) return null;
  return (
    <div role="status" aria-live="polite" style={{ borderBottom: '1px solid #edebe9', background: '#f3f9fd' }}>
      {lista.map(e => (
        <div key={e.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 14px', fontSize: 13, color: '#323130' }}>
          <span className="animate-spin" style={{ width: 12, height: 12, borderRadius: '50%', border: '2px solid #0078d4', borderTopColor: 'transparent', flexShrink: 0 }} />
          <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            <b>Enviando…</b> {e.asunto}{e.para ? <span style={{ color: '#605e5c' }}> · Para: {e.para}</span> : null}
          </span>
        </div>
      ))}
    </div>
  );
}
