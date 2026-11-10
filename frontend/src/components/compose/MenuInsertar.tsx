/**
 * Menú «Adjuntar» de la cinta de redacción (09/11/2026).
 *
 * Reclamo: en la pestaña Insertar el botón «Adjuntar archivo» tenía flecha pero no desplegaba nada,
 * y no existía la opción de adjuntar un correo (antiguo o de otra persona) al responder o reenviar.
 * Este menú reúne todas las formas de insertar algo en el mensaje:
 *   - Archivo del equipo            → evento `compose-attach` (ComposePanel abre el selector de archivos)
 *   - Archivo de la Nube (Almacén)  → evento `compose-attach-cloud` (SelectorArchivosNube)
 *   - Correo como adjunto           → evento `compose-attach-mail` (SelectorCorreoAdjunto)
 *   - Imagen en el texto / Enlace   → acciones del editor que le pasa la cinta
 * Los eventos de ventana son el mismo contrato que ya usan la barra principal y ComposePanel, así
 * funciona igual en un correo nuevo, en una respuesta o en un reenvío.
 */
import { useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { LargeBtn, MedBtn } from './BotonesCinta';
import { EVENTO_ADJUNTAR_CORREO } from '../../lib/correosComoAdjunto';

interface Props {
  size: 'med' | 'large';
  onImagen?: () => void;
  onEnlace?: () => void;
}

interface Opcion { etiqueta: string; detalle: string; icono: string; accion: () => void }

const ICONOS = {
  clip: 'M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13',
  equipo: 'M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z',
  nube: 'M7 16a4 4 0 01-.88-7.9A5 5 0 0115.9 6.1 4.5 4.5 0 0117 15h-1m-4-1v6m0-6l-2 2m2-2l2 2',
  correo: 'M3 8l9 6 9-6M4 6h16a1 1 0 011 1v10a1 1 0 01-1 1H4a1 1 0 01-1-1V7a1 1 0 011-1z',
  imagen: 'M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z',
  enlace: 'M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1',
};

function Icono({ d, s }: { d: string; s: number }) {
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="#0078d4" strokeWidth={1.5} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d={d} />
    </svg>
  );
}

export function MenuInsertar({ size, onImagen, onEnlace }: Props) {
  const [abierto, setAbierto] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const ancla = useRef<HTMLDivElement>(null);

  const alternar = () => {
    if (!abierto && ancla.current) {
      const r = ancla.current.getBoundingClientRect();
      setPos({ top: r.bottom + 4, left: r.left });
    }
    setAbierto(a => !a);
  };

  const emitir = (nombre: string) => () => window.dispatchEvent(new CustomEvent(nombre));

  const opciones: Opcion[] = [
    { etiqueta: 'Archivo del equipo', detalle: 'Documentos, imágenes o cualquier archivo de este equipo', icono: ICONOS.equipo, accion: emitir('compose-attach') },
    { etiqueta: 'Archivo de la Nube (Almacén)', detalle: 'Elegir de sus carpetas de la Nube de Maquita', icono: ICONOS.nube, accion: emitir('compose-attach-cloud') },
    { etiqueta: 'Correo como adjunto', detalle: 'Un correo antiguo o de otra persona, completo, como .eml', icono: ICONOS.correo, accion: emitir(EVENTO_ADJUNTAR_CORREO) },
  ];
  if (onImagen) opciones.push({ etiqueta: 'Imagen en el texto', detalle: 'La imagen se ve dentro del mensaje, no como adjunto', icono: ICONOS.imagen, accion: onImagen });
  if (onEnlace) opciones.push({ etiqueta: 'Enlace', detalle: 'Vincular el texto seleccionado a una dirección web', icono: ICONOS.enlace, accion: onEnlace });

  const icono: ReactNode = <Icono d={ICONOS.clip} s={size === 'large' ? 22 : 16} />;

  return (
    <div className="relative" ref={ancla}>
      {size === 'large'
        ? <LargeBtn icon={icono} label={'Adjuntar\narchivo'} onClick={alternar} hasDropdown active={abierto} />
        : <MedBtn icon={icono} label="Adjuntar" onClick={alternar} hasDropdown />}
      {abierto && createPortal(
        <>
          <div className="fixed inset-0 z-[9998]" onClick={() => setAbierto(false)} />
          <div role="menu" aria-label="Opciones para insertar"
            className="fixed w-[320px] bg-white rounded shadow-lg border border-[#edebe9] z-[9999] py-1" style={{ top: pos.top, left: pos.left }}>
            <div className="px-3 py-1 text-[11px] font-semibold text-[#605e5c] uppercase tracking-wide">Insertar en el mensaje</div>
            {opciones.map(o => (
              <button key={o.etiqueta} type="button" role="menuitem" onClick={() => { setAbierto(false); o.accion(); }}
                className="w-full text-left px-3 py-[7px] hover:bg-[#f3f2f1] flex items-start gap-3">
                <span className="mt-[2px] shrink-0"><Icono d={o.icono} s={18} /></span>
                <span className="min-w-0">
                  <span className="block text-[13px] text-[#323130]">{o.etiqueta}</span>
                  <span className="block text-[11px] text-[#605e5c] leading-tight">{o.detalle}</span>
                </span>
              </button>
            ))}
          </div>
        </>,
        document.body
      )}
    </div>
  );
}
