/**
 * Diálogo «Firmar este PDF» del visor de adjuntos (09/11/2026).
 *
 * Pedido: firmar los PDF que llegan al correo sin descargarlos y subirlos a Raíces; solo
 * firmar (no editar), y que sirva desde el celular. Dos pasos: formulario (certificado,
 * contraseña, página, posición) y resultado (descargar / responder / reenviar con el firmado).
 * La firma la hace Raíces con el certificado de la persona (lib/firmaPdf.ts).
 */
import { useState } from 'react';
import { firmarAdjunto, ErrorFirmaPdf, type ResultadoFirma } from '../../../lib/firmaPdf';
import { FormularioFirmaPdf, type OpcionesFirma, type ValoresFirmaIniciales } from './FormularioFirmaPdf';
import { ResultadoFirmaPdf } from './ResultadoFirmaPdf';

interface Props {
  open: boolean;
  onClose: () => void;
  folder: string;
  uid: number;
  partNumber: string;
  filename: string;
  onResponderCon?: (archivo: File) => void;
  onReenviarCon?: (archivo: File) => void;
}

export function DialogoFirmarPdf({ open, onClose, folder, uid, partNumber, filename, onResponderCon, onReenviarCon }: Props) {
  const [firmando, setFirmando] = useState(false);
  const [error, setError] = useState('');
  const [resultado, setResultado] = useState<ResultadoFirma | null>(null);
  // Firmas sucesivas (varias personas, o la misma firma en varias hojas): la versión firmada se
  // conserva en memoria y la siguiente firma se pone sobre ella; Raíces firma de forma incremental.
  const [documento, setDocumento] = useState<Blob | null>(null);
  const [firmas, setFirmas] = useState(0);
  const [ultima, setUltima] = useState<ValoresFirmaIniciales | undefined>(undefined);
  const [ultimaPagina, setUltimaPagina] = useState<number | undefined>(undefined);

  if (!open) return null;

  const cerrar = () => {
    setResultado(null); setError(''); setDocumento(null); setFirmas(0); setUltima(undefined); setUltimaPagina(undefined);
    onClose();
  };

  const firmar = async (o: OpcionesFirma) => {
    setFirmando(true); setError('');
    try {
      const r = await firmarAdjunto({
        folder, uid, partNumber, filename, archivoPdf: documento,
        certificadoId: o.certificadoId, archivoP12: o.archivoP12, password: o.password,
        posicion: o.posicion, area: o.area, razon: o.razon,
        guardar: o.guardar, guardarPassword: o.guardarPassword,
      });
      setDocumento(r.blob); setFirmas(n => n + 1);
      setUltima({ certificadoId: o.certificadoId, archivoP12: o.archivoP12, password: o.password });
      if (o.area) setUltimaPagina(o.area.pagina);
      if (o.accion === 'otra') return;      // se queda en el formulario para dibujar la siguiente firma
      if (o.accion === 'responder' && onResponderCon) {
        // Pedido: tras firmar, responder enseguida el mismo correo con «nombre_firmado.pdf» adjunto
        // y el texto automático ya redactado (editable antes de enviar).
        cerrar();
        onResponderCon(new File([r.blob], r.nombre, { type: 'application/pdf' }));
        return;
      }
      setResultado(r);
    } catch (e) {
      setError(e instanceof ErrorFirmaPdf ? e.message : 'No se pudo firmar el PDF. Intente de nuevo.');
    } finally {
      setFirmando(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[1200] flex items-end sm:items-center justify-center bg-black/50 p-0 sm:p-4"
      // stopPropagation: este diálogo vive dentro del visor de adjuntos, cuyo fondo cierra el visor al
      // hacer clic; sin esto, cualquier clic en el formulario cerraba el visor y el diálogo a la vez.
      onClick={e => { e.stopPropagation(); if (e.target === e.currentTarget && !firmando) cerrar(); }}
      onKeyDown={e => { if (e.key === 'Escape') { e.stopPropagation(); if (!firmando) cerrar(); } }}>
      <div role="dialog" aria-modal="true" aria-labelledby="firma-pdf-titulo"
        className="w-full sm:max-w-[640px] max-h-[95vh] overflow-auto bg-white dark:bg-[#2d2d2d] rounded-t-lg sm:rounded-lg shadow-2xl">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#edebe9] dark:border-[#444]">
          <h2 id="firma-pdf-titulo" className="text-[15px] font-semibold text-[#323130] dark:text-[#e0e0e0] flex items-center gap-2">
            <svg className="w-5 h-5 text-[#0078d4]" fill="none" stroke="currentColor" strokeWidth={1.6} viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M4 21h16" />
            </svg>
            {resultado ? 'PDF firmado' : (firmas ? `Firma N.º ${firmas + 1}` : 'Firmar este PDF')}
          </h2>
          <button type="button" onClick={cerrar} disabled={firmando} aria-label="Cerrar"
            className="p-1.5 rounded hover:bg-[#f3f2f1] dark:hover:bg-[#383838] text-[#605e5c] dark:text-[#aaa]">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
        {resultado ? (
          <ResultadoFirmaPdf blob={resultado.blob} nombre={resultado.nombre} onCerrar={cerrar} firmas={firmas}
            onOtra={() => setResultado(null)}
            certificadoGuardado={resultado.certificadoGuardado} passwordGuardada={resultado.passwordGuardada}
            onResponder={onResponderCon ? (f) => { cerrar(); onResponderCon(f); } : undefined}
            onReenviar={onReenviarCon ? (f) => { cerrar(); onReenviarCon(f); } : undefined} />
        ) : (
          <FormularioFirmaPdf nombreArchivo={filename} folder={folder} uid={uid} partNumber={partNumber}
            firmando={firmando} error={error} puedeResponder={!!onResponderCon} onFirmar={firmar} onCancelar={cerrar}
            documento={documento} firmasPuestas={firmas} paginaInicial={ultimaPagina} inicial={ultima} />
        )}
      </div>
    </div>
  );
}
