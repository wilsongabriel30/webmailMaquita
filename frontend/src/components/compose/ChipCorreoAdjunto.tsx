/**
 * Chip de un correo adjunto (.eml) en la lista de adjuntos del redactor (09/11/2026).
 *
 * A diferencia de un archivo normal, se muestra con icono de sobre, el asunto legible (no el nombre
 * crudo del archivo), remitente y fecha, y un botón «Ver» que abre el correo original en su propia
 * ventana (si salió de nuestro buzón) o una vista previa leyendo el .eml (si vino del equipo).
 */
import { useState } from 'react';
import type { ArchivoAdjunto } from '../../lib/adjuntosBorrador';
import { asuntoDeAdjuntoCorreo } from '../../lib/origenCorreoAdjunto';
import { abrirMensajeEnVentana } from '../../lib/abrirEnPestana';
import { nombreRemitente } from '../../lib/textoAvisoCorreo';
import { fechaCortaLista } from '../../lib/fechaLegible';
import { VistaPreviaCorreoAdjunto } from './VistaPreviaCorreoAdjunto';

interface Props {
  adjunto: ArchivoAdjunto;
  onRemove: () => void;
}

function detalle(adj: ArchivoAdjunto): string {
  const partes: string[] = [];
  const de = nombreRemitente(adj.correo?.from);
  if (de) partes.push(de);
  if (adj.correo?.date) {
    const d = new Date(adj.correo.date);
    if (!isNaN(d.getTime())) partes.push(fechaCortaLista(d));
  }
  return partes.join(' · ') || 'Correo adjunto';
}

export function ChipCorreoAdjunto({ adjunto, onRemove }: Props) {
  const [verEml, setVerEml] = useState(false);
  const asunto = asuntoDeAdjuntoCorreo(adjunto);
  const origen = adjunto.correo;
  const puedeVer = !!origen || !!adjunto.file;

  const ver = () => {
    if (origen) abrirMensajeEnVentana(origen.folder, origen.uid);
    else if (adjunto.file) setVerEml(true);
  };

  return (
    <div className="flex items-center gap-2 px-2.5 py-2 bg-[#f0f6fc] border border-[#c7e0f4] rounded-md shadow-sm group hover:border-[#0078d4] transition-colors w-[300px] max-w-full">
      <div className="w-7 h-7 bg-[#deecf9] rounded flex items-center justify-center shrink-0" aria-hidden="true">
        <svg className="w-4 h-4" fill="none" stroke="#0078d4" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.6} d="M3 8l9 6 9-6M4 6h16a1 1 0 011 1v10a1 1 0 01-1 1H4a1 1 0 01-1-1V7a1 1 0 011-1z" />
        </svg>
      </div>
      <button type="button" onClick={ver} disabled={!puedeVer}
        title={puedeVer ? `Ver el correo «${asunto}» antes de enviar` : asunto}
        className="min-w-0 flex-1 text-left enabled:cursor-pointer disabled:cursor-default group/ver">
        <p className="text-[12px] text-[#323130] truncate font-medium group-enabled/ver:group-hover/ver:underline">{asunto}</p>
        <p className="text-[12px] text-[#605e5c] truncate">
          {detalle(adjunto)}
          {puedeVer && <span className="text-[#0078d4]"> · Ver</span>}
        </p>
      </button>
      <button type="button" onClick={onRemove} aria-label={`Quitar el correo adjunto ${asunto}`} title={`Quitar el correo adjunto ${asunto}`}
        className="w-6 h-6 rounded-full flex items-center justify-center text-[#605e5c] hover:text-[#a4262c] hover:bg-[#fde7e9] transition-all shrink-0">
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
      {verEml && adjunto.file && <VistaPreviaCorreoAdjunto archivo={adjunto.file} onClose={() => setVerEml(false)} />}
    </div>
  );
}
