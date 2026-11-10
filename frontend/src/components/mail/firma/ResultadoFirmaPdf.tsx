/**
 * Resultado de la firma (09/11/2026): vista previa del PDF firmado y qué hacer con él:
 * descargarlo, responder el correo adjuntándolo o reenviarlo. El original no se toca.
 */
import { useEffect, useMemo } from 'react';
import { descargarBlob } from '../../../lib/firmaPdf';

interface Props {
  blob: Blob;
  nombre: string;
  onResponder?: (archivo: File) => void;
  onReenviar?: (archivo: File) => void;
  onCerrar: () => void;
  certificadoGuardado?: boolean;
  passwordGuardada?: boolean;
  /** Firmas que lleva el documento. */
  firmas?: number;
  /** Volver al formulario para poner otra firma sobre esta versión. */
  onOtra?: () => void;
}

export function ResultadoFirmaPdf({ blob, nombre, onResponder, onReenviar, onCerrar, certificadoGuardado, passwordGuardada, firmas = 1, onOtra }: Props) {
  const url = useMemo(() => URL.createObjectURL(blob), [blob]);
  useEffect(() => () => URL.revokeObjectURL(url), [url]);
  const archivo = () => new File([blob], nombre, { type: 'application/pdf' });

  const boton = 'h-[40px] px-4 rounded text-[13px] font-medium flex items-center justify-center gap-2';

  return (
    <div className="flex flex-col gap-3 p-4 text-[13px]">
      <p className="text-[#107c10] font-medium flex items-center gap-2">
        <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
        PDF firmado: {nombre}{firmas > 1 ? ` (${firmas} firmas)` : ''}
      </p>
      {certificadoGuardado && (
        <p className="text-[12px] text-[#605e5c] dark:text-[#aaa]">
          Su certificado quedó guardado en Raíces{passwordGuardada ? ' junto con su contraseña' : ''}: la próxima vez solo tendrá que elegirlo.
        </p>
      )}
      {/* Vista previa (en celular el navegador puede no dibujar PDF embebido: el botón Descargar siempre está). */}
      <iframe title="Vista previa del PDF firmado" src={url}
        className="w-full h-[40vh] sm:h-[50vh] border border-[#edebe9] dark:border-[#444] rounded bg-white" />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {onOtra && (
          <button type="button" onClick={onOtra} className={boton + ' border border-[#0078d4] text-[#0078d4] sm:col-span-2'}>
            Añadir otra firma (otra hoja u otra persona)
          </button>
        )}
        <button type="button" onClick={() => descargarBlob(blob, nombre)} className={boton + ' bg-[#0078d4] text-white'}>
          Descargar el PDF firmado
        </button>
        {onResponder && (
          <button type="button" onClick={() => onResponder(archivo())} className={boton + ' border border-[#0078d4] text-[#0078d4]'}>
            Responder con el PDF firmado
          </button>
        )}
        {onReenviar && (
          <button type="button" onClick={() => onReenviar(archivo())} className={boton + ' border border-[#0078d4] text-[#0078d4]'}>
            Reenviar el PDF firmado
          </button>
        )}
        <button type="button" onClick={onCerrar} className={boton + ' border border-[#8a8886] text-[#323130] dark:text-[#e0e0e0]'}>
          Cerrar
        </button>
      </div>
    </div>
  );
}
