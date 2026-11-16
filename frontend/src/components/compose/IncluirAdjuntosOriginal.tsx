/**
 * IncluirAdjuntosOriginal.tsx — al responder (a una persona o a todos), ofrece incluir los
 * adjuntos del correo original (16/11/2026).
 *
 * Una respuesta no lleva los adjuntos del original (el destinatario ya los tiene), pero al
 * «Responder a todos» a veces hay que volver a mandarlos. Zimbra tenía un botón para eso y el
 * personal lo pidió. Aquí no se cargan solos: se ofrecen con un botón, y una vez dentro del
 * redactor se ven, se pueden abrir y se puede quitar alguno, igual que en un reenvío.
 *
 * La franja desaparece cuando ya no queda ningún adjunto del original por incluir.
 */
import { useState } from 'react';
import { cargarAdjuntosDelReenvio, esPeligroso, type ArchivoAdjunto } from '../../lib/adjuntosBorrador';
import { showToast } from '../common/Toast';
import type { AttachmentInfo } from '../../types';

interface Props {
  origen?: { folder: string; uid: number; adjuntos?: AttachmentInfo[] };
  /** Adjuntos que ya están en el redactor: los que coinciden por nombre no se vuelven a ofrecer. */
  presentes: ArchivoAdjunto[];
  onCargados: (archivos: ArchivoAdjunto[]) => void;
}

export function IncluirAdjuntosOriginal({ origen, presentes, onCargados }: Props) {
  const [cargando, setCargando] = useState(false);
  if (!origen) return null;

  const yaEstan = new Set(presentes.map(a => a.name));
  const faltan = (origen.adjuntos || []).filter(a =>
    !a.is_inline && !!a.filename && !a.dentro_de && !esPeligroso(a.filename) && !yaEstan.has(a.filename));
  if (!faltan.length) return null;

  const incluir = async () => {
    setCargando(true);
    try {
      const cargados = await cargarAdjuntosDelReenvio({ folder: origen.folder, uid: origen.uid, adjuntos: faltan });
      if (cargados.length) onCargados(cargados);
      if (cargados.length < faltan.length) {
        showToast(cargados.length
          ? 'No se pudieron traer todos los adjuntos del correo original'
          : 'No se pudieron traer los adjuntos del correo original');
      }
    } finally {
      setCargando(false);
    }
  };

  const n = faltan.length;
  return (
    <div className="px-4 py-2 border-b border-[#edebe9] bg-[#faf9f8] shrink-0 flex items-center gap-3 flex-wrap">
      <p className="text-[12px] text-[#605e5c] min-w-0">
        El correo original tiene {n} archivo{n > 1 ? 's' : ''} adjunto{n > 1 ? 's' : ''} que no va{n > 1 ? 'n' : ''} en esta respuesta.
      </p>
      <button type="button" onClick={incluir} disabled={cargando}
        title="Adjuntar a esta respuesta los archivos que llegaron en el correo original"
        className="flex items-center gap-1.5 px-2.5 py-1 text-[12px] font-medium text-[#0078d4] border border-[#0078d4] rounded hover:bg-[#eff6fc] disabled:opacity-60 disabled:cursor-wait shrink-0">
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
        </svg>
        {cargando ? 'Trayendo los adjuntos…' : 'Incluir adjuntos del original'}
      </button>
    </div>
  );
}
