/**
 * Vista previa de un correo adjunto (.eml) ANTES de enviar (09/11/2026).
 *
 * Reclamo: «se arrastró un correo, se subió como un formato y no se puede ver qué estamos
 * enviando». Si el .eml salió de nuestro buzón, el botón «Ver» abre el correo original en su
 * ventana (lib/abrirEnPestana.ts). Esta vista es para los demás casos (un .eml traído del equipo):
 * se lee en el navegador (lib/parseEml.ts) y se muestran asunto, remitente, fecha y cuerpo.
 * El HTML pasa por sanitizeHtml y se pinta en un iframe aislado (sandbox sin scripts).
 */
import { useEffect, useState } from 'react';
import { leerEml, type CorreoEml } from '../../lib/parseEml';
import { sanitizeHtml } from '../../lib/sanitize';

interface Props {
  archivo: File;
  onClose: () => void;
}

function Fila({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  if (!valor) return null;
  return (
    <div className="flex gap-2 text-[12px] leading-5">
      <span className="w-14 shrink-0 text-[#605e5c] dark:text-[#a19f9d]">{etiqueta}</span>
      <span className="text-[#323130] dark:text-[#e0e0e0] break-words min-w-0">{valor}</span>
    </div>
  );
}

export function VistaPreviaCorreoAdjunto({ archivo, onClose }: Props) {
  const [correo, setCorreo] = useState<CorreoEml | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let vigente = true;
    leerEml(archivo).then(c => { if (vigente) setCorreo(c); }).catch(() => { if (vigente) setError(true); });
    return () => { vigente = false; };
  }, [archivo]);

  useEffect(() => {
    const tecla = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', tecla);
    return () => window.removeEventListener('keydown', tecla);
  }, [onClose]);

  const cuerpoHtml = correo
    ? (correo.html ? sanitizeHtml(correo.html) : `<pre style="white-space:pre-wrap;font-family:Calibri,Segoe UI,sans-serif;font-size:14px;margin:0">${escapar(correo.texto)}</pre>`)
    : '';

  return (
    <div className="fixed inset-0 z-[70] bg-black/50 flex items-center justify-center p-4" onClick={onClose} role="dialog" aria-modal="true" aria-label="Vista previa del correo adjunto">
      <div className="bg-white dark:bg-[#252423] rounded-lg shadow-xl w-full max-w-3xl h-[85vh] flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="px-4 py-3 border-b border-[#edebe9] dark:border-[#3b3a39] flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <p className="text-[11px] uppercase tracking-wide text-[#605e5c] dark:text-[#a19f9d]">Correo adjunto · así lo recibirá el destinatario</p>
            <h2 className="text-[15px] font-semibold text-[#323130] dark:text-[#e0e0e0] truncate">{correo?.subject || archivo.name.replace(/\.eml$/i, '') || '(sin asunto)'}</h2>
            {correo && (
              <div className="mt-1">
                <Fila etiqueta="De" valor={correo.from} />
                <Fila etiqueta="Para" valor={correo.to} />
                <Fila etiqueta="Fecha" valor={correo.date} />
                {correo.adjuntos.length > 0 && <Fila etiqueta="Adjuntos" valor={correo.adjuntos.join(', ')} />}
              </div>
            )}
          </div>
          <button type="button" onClick={onClose} aria-label="Cerrar vista previa"
            className="w-8 h-8 rounded flex items-center justify-center text-[#605e5c] hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39]">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
        <div className="flex-1 min-h-0 bg-white">
          {error && <p className="p-6 text-[13px] text-[#a4262c]">No se pudo leer este correo. Se enviará igual como archivo adjunto.</p>}
          {!error && !correo && <p className="p-6 text-[13px] text-[#605e5c]">Leyendo el correo…</p>}
          {correo && (
            <iframe title="Cuerpo del correo adjunto" sandbox="" className="w-full h-full border-0"
              srcDoc={`<!DOCTYPE html><html><head><meta charset="utf-8"><base target="_blank"><style>body{font-family:Calibri,'Segoe UI',sans-serif;font-size:14px;color:#323130;margin:16px;word-break:break-word}img{max-width:100%}</style></head><body>${cuerpoHtml}</body></html>`} />
          )}
        </div>
      </div>
    </div>
  );
}

function escapar(t: string): string {
  return t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
