/**
 * Correos recién enviados, arriba de la lista de «Enviados» (06/11/2026; revisado 13/11/2026).
 *
 * Desde que se pulsa «Enviar», el correo se ve en «Enviados» como uno más, mientras el servidor lo
 * entrega por detrás (lib/envioSegundoPlano.ts). No dice «Enviando…» ni muestra ruedas de espera,
 * y no aparece en las demás carpetas: el personal pidió que el envío se sienta inmediato.
 * Cuando el servidor confirma, la fila provisional se retira y la lista ya trae el correo real.
 * Si el envío falla, la fila desaparece y el redactor avisa y vuelve a abrir el correo.
 */
import { useEffect, useState } from 'react';
import { enviosRecientes, EVENTO_ENVIOS_RECIENTES, type EnvioReciente } from '../../lib/enviosRecientes';
import { useMailStore } from '../../store/mailStore';

const NOMBRES_ENVIADOS = /^(sent|sent items|sent messages|enviados|elementos enviados)$/i;

export function EnviosEnCurso() {
  const [lista, setLista] = useState<EnvioReciente[]>(enviosRecientes());
  const carpeta = useMailStore(s => s.currentFolder);
  const esEnviados = useMailStore(s => s.folders.find(f => f.name === s.currentFolder)?.type === 'sent') || NOMBRES_ENVIADOS.test(carpeta || '');
  useEffect(() => {
    const h = () => setLista(enviosRecientes());
    window.addEventListener(EVENTO_ENVIOS_RECIENTES, h);
    return () => window.removeEventListener(EVENTO_ENVIOS_RECIENTES, h);
  }, []);
  if (!lista.length || !esEnviados) return null;
  return (
    <div>
      {lista.map(e => (
        <div key={e.id} data-envio-reciente style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 14px 9px 64px', borderBottom: '1px solid #edebe9', fontSize: 13, color: '#323130' }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.para ? `Para: ${e.para}` : '(sin destinatarios)'}</div>
            <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#605e5c' }}>{e.asunto}</div>
          </div>
          <span style={{ flexShrink: 0, fontSize: 12, color: '#605e5c' }}>ahora</span>
        </div>
      ))}
    </div>
  );
}
