/**
 * Aviso «El remitente pidió confirmación de lectura» (09/11/2026), como el de Outlook.
 *
 * Aparece al abrir un correo que la pide y aún no se contestó. Botones «Enviar» / «No enviar»
 * y un enlace para dejarlo fijo (siempre / nunca) en la preferencia del servidor. Con la
 * preferencia «siempre» el acuse sale solo (si va al remitente) y se muestra una línea breve;
 * con «nunca» no se muestra nada. En cualquier caso el correo queda marcado para no repetir.
 */
import { useEffect, useRef, useState } from 'react';
import { guardarPreferenciaAcuse, preferenciaAcuse, responderAcuse, type PedidoAcuse } from '../../lib/acuseLectura';

interface Props {
  folder: string;
  uid: number;
  pedido: PedidoAcuse | null | undefined;
}

type Estado = 'oculto' | 'preguntar' | 'enviando' | 'enviado' | 'declinado' | 'error';

export function AvisoAcuseLectura({ folder, uid, pedido }: Props) {
  const [estado, setEstado] = useState<Estado>('oculto');
  const [error, setError] = useState('');
  const clave = `${folder}/${uid}`;
  const resuelto = useRef<string>('');   // evita enviar dos veces el mismo correo al re-renderizar

  useEffect(() => {
    let vigente = true;
    setEstado('oculto'); setError('');
    if (!pedido) return;
    preferenciaAcuse().then(async pref => {
      if (!vigente) return;
      if (pref === 'nunca') { setEstado('oculto'); return; }
      if (pref === 'siempre' && pedido.mismo_remitente) {
        if (resuelto.current === clave) return;
        resuelto.current = clave;
        setEstado('enviando');
        try {
          await responderAcuse(folder, uid, true);
          if (vigente) setEstado('enviado');
        } catch {
          if (vigente) { setEstado('error'); setError('No se pudo enviar la confirmación de lectura.'); }
        }
        return;
      }
      setEstado('preguntar');
    });
    return () => { vigente = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clave, pedido?.to]);

  if (!pedido || estado === 'oculto') return null;

  const responder = async (enviar: boolean) => {
    setEstado('enviando'); setError('');
    try {
      await responderAcuse(folder, uid, enviar);
      setEstado(enviar ? 'enviado' : 'declinado');
    } catch {
      setEstado('error'); setError('No se pudo enviar la confirmación. Intente de nuevo.');
    }
  };
  const fijar = async (valor: 'siempre' | 'nunca') => {
    try { await guardarPreferenciaAcuse(valor); } catch { /* se mantiene «preguntar» */ }
    await responder(valor === 'siempre');
  };

  const boton = 'h-[30px] px-3 rounded text-[12px] font-medium';

  if (estado === 'enviado' || estado === 'declinado') {
    return (
      <p className="mt-2 text-[12px] text-[#605e5c] dark:text-[#aaa]" role="status">
        {estado === 'enviado'
          ? <>Se envió la confirmación de lectura a <b>{pedido.to}</b>.</>
          : 'No se envió la confirmación de lectura.'}
      </p>
    );
  }

  return (
    <div role="status" className="mt-2 flex flex-wrap items-center gap-2 rounded border border-[#f8d22a] bg-[#fff4ce] dark:bg-[#4a3f0e] dark:border-[#8a7420] px-3 py-2 text-[12px] text-[#323130] dark:text-[#e0e0e0]">
      <svg className="w-4 h-4 text-[#8a6d00] shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12s3.75-7.5 9.75-7.5 9.75 7.5 9.75 7.5-3.75 7.5-9.75 7.5S2.25 12 2.25 12z" />
        <circle cx="12" cy="12" r="3" />
      </svg>
      <span className="flex-1 min-w-[180px]">
        El remitente pidió una <b>confirmación de lectura</b>
        {pedido.mismo_remitente ? '' : <> (se enviaría a <b>{pedido.to}</b>)</>}. ¿Desea enviarla?
      </span>
      {estado === 'enviando' ? (
        <span className="text-[#605e5c]">Enviando…</span>
      ) : (
        <span className="flex items-center gap-1.5">
          <button type="button" onClick={() => responder(true)} className={boton + ' bg-[#0078d4] text-white'}>Enviar</button>
          <button type="button" onClick={() => responder(false)} className={boton + ' border border-[#8a8886] bg-white dark:bg-[#1e1e1e]'}>No enviar</button>
        </span>
      )}
      {estado !== 'enviando' && (
        <span className="w-full text-[11px] text-[#605e5c] dark:text-[#aaa]">
          No volver a preguntar:{' '}
          <button type="button" onClick={() => fijar('siempre')} className="text-[#0078d4] hover:underline">enviar siempre</button>
          {' · '}
          <button type="button" onClick={() => fijar('nunca')} className="text-[#0078d4] hover:underline">no enviar nunca</button>
          {' '}(se cambia en Configuración → General).
        </span>
      )}
      {error && <span className="w-full text-[#a4262c]">{error}</span>}
    </div>
  );
}
