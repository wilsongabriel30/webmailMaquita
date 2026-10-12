import { useEffect, useState } from 'react';
import SafeEmailViewer from './SafeEmailViewer';

/**
 * Vista previa de un correo adjunto (.eml / message/rfc822), 12/10/2026.
 *
 * El backend lo abre con el mismo lector y saneado que la bandeja
 * (`/api/mail/attachment-message/...`); aquí se pinta como un correo:
 * cabecera, cuerpo (en el iframe aislado de siempre) y lista de adjuntos.
 */

interface CorreoAdjunto {
  from: string;
  to: string;
  cc: string;
  subject: string;
  date: string | null;
  text_body: string;
  html_body: string;
  blocked_image_count: number;
  attachments: { filename: string; content_type: string; size: number }[];
}

interface Props {
  folder: string;
  uid: number;
  partNumber: string;
  onError: () => void;
}

function formatoFecha(fecha: string | null): string {
  if (!fecha) return '';
  const d = new Date(fecha);
  return isNaN(d.getTime()) ? fecha : d.toLocaleString('es-EC', { dateStyle: 'full', timeStyle: 'short' });
}

function formatoTamano(bytes: number): string {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

export default function VistaPreviaCorreo({ folder, uid, partNumber, onError }: Props) {
  const [correo, setCorreo] = useState<CorreoAdjunto | null>(null);

  useEffect(() => {
    let vigente = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reinicio al cambiar de adjunto
    setCorreo(null);
    fetch('/api/mail/attachment-message/' + encodeURIComponent(folder) + '/' + uid + '/' + encodeURIComponent(partNumber), {
      credentials: 'include',
    })
      .then((r) => { if (!r.ok) throw new Error(); return r.json(); })
      .then((c: CorreoAdjunto) => { if (vigente) setCorreo(c); })
      .catch(() => { if (vigente) onError(); });
    return () => { vigente = false; };
  }, [folder, uid, partNumber, onError]);

  if (!correo) {
    return <div className="animate-spin rounded-full h-8 w-8 border-2 border-[#0078d4] border-t-transparent" />;
  }

  const fila = (etiqueta: string, valor: string) =>
    valor ? (
      <div className="flex gap-2 text-[13px]">
        <span className="w-14 flex-shrink-0 text-[#605e5c] dark:text-[#999]">{etiqueta}</span>
        <span className="text-[#323130] dark:text-[#e0e0e0] break-all">{valor}</span>
      </div>
    ) : null;

  return (
    <div className="w-full h-[70vh] overflow-auto self-stretch bg-white dark:bg-[#2d2d2d] rounded border border-[#edebe9] dark:border-[#444]">
      <div className="px-4 py-3 border-b border-[#edebe9] dark:border-[#444] space-y-1">
        <h2 className="text-[16px] font-semibold text-[#323130] dark:text-[#e0e0e0] mb-2">{correo.subject}</h2>
        {fila('De', correo.from)}
        {fila('Para', correo.to)}
        {fila('CC', correo.cc)}
        {fila('Fecha', formatoFecha(correo.date))}
        {correo.attachments.length > 0 && (
          <div className="flex gap-2 text-[13px] pt-1">
            <span className="w-14 flex-shrink-0 text-[#605e5c] dark:text-[#999]">Adjuntos</span>
            <span className="text-[#323130] dark:text-[#e0e0e0]">
              {correo.attachments.map((a) => `${a.filename} (${formatoTamano(a.size)})`).join(' · ')}
            </span>
          </div>
        )}
        {correo.blocked_image_count > 0 && (
          <p className="text-[12px] text-[#605e5c] dark:text-[#999] pt-1">
            Se bloquearon {correo.blocked_image_count} imágenes externas de este correo adjunto.
          </p>
        )}
      </div>
      <div className="p-4">
        {correo.html_body ? (
          <SafeEmailViewer htmlBody={correo.html_body} />
        ) : (
          <pre className="text-[13px] font-sans text-[#323130] dark:text-[#e0e0e0] whitespace-pre-wrap">{correo.text_body}</pre>
        )}
      </div>
    </div>
  );
}
